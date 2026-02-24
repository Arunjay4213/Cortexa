"""Grounding & Contamination Detection API.

Three endpoints matching the three detection modes:

1. POST /grounding/scan     — batch assessment of all agent memories
2. POST /grounding/gate     — write-path check for a single candidate memory
3. POST /grounding/quarantine — simulate removal of suspect memories

All DB reads happen here; computation is delegated to the pure engines
in cortex.attribution.grounding and cortex.attribution.contamination.
"""

from __future__ import annotations

import time

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.database import get_session
from cortex.db.tables import (
    memories,
    transactions,
    contradictions,
    memory_profiles,
)
from cortex.attribution.grounding import (
    MemoryForGrounding,
    TransactionForGrounding,
    compute_grounding_scores,
)
from cortex.attribution.contamination import (
    scan_contamination,
    gate_memory,
    simulate_quarantine,
)
from cortex.models import (
    GroundingScanRequest,
    GroundingScoreResponse,
    ContaminationScanResponse,
    GateCheckRequest,
    GateCheckResponse,
    QuarantineRequest,
    QuarantineSimulationResponse,
)

router = APIRouter(tags=["grounding"])


# ── Helpers ──────────────────────────────────────────────────────────

async def _load_memories_for_grounding(
    db: AsyncSession, agent_id: str,
) -> list[MemoryForGrounding]:
    """Fetch active memories with profile data, convert to engine dataclass."""
    stmt = (
        select(
            memories.c.id,
            memories.c.content,
            memories.c.embedding,
            memories.c.tokens,
            memories.c.retrieval_count,
            memories.c.created_at,
            memories.c.metadata_,
            memory_profiles.c.total_attribution,
            memory_profiles.c.mean_attribution,
        )
        .outerjoin(memory_profiles, memories.c.id == memory_profiles.c.memory_id)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.archived_at.is_(None),
                memories.c.embedding.isnot(None),
            )
        )
    )
    rows = (await db.execute(stmt)).fetchall()

    result = []
    for row in rows:
        meta = row.metadata_ or {}
        result.append(MemoryForGrounding(
            id=row.id,
            content=row.content,
            embedding=np.array(row.embedding, dtype=np.float64),
            tokens=row.tokens,
            retrieval_count=row.retrieval_count or 0,
            total_attribution=row.total_attribution or 0.0,
            mean_attribution=row.mean_attribution or 0.0,
            created_at=row.created_at,
            source_type=meta.get("source_type", "unknown"),
            source_transaction_id=meta.get("source_transaction_id"),
        ))
    return result


async def _load_transactions_for_grounding(
    db: AsyncSession, agent_id: str, limit: int = 50,
) -> list[TransactionForGrounding]:
    """Fetch recent completed transactions with embeddings."""
    stmt = (
        select(transactions)
        .where(
            and_(
                transactions.c.agent_id == agent_id,
                transactions.c.status == "completed",
                transactions.c.query_embedding.isnot(None),
                transactions.c.response_embedding.isnot(None),
            )
        )
        .order_by(transactions.c.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).fetchall()

    result = []
    for row in rows:
        result.append(TransactionForGrounding(
            id=row.id,
            query_text=row.query_text,
            query_embedding=np.array(row.query_embedding, dtype=np.float64),
            response_embedding=np.array(row.response_embedding, dtype=np.float64),
            retrieved_memory_ids=list(row.retrieved_memory_ids or []),
        ))
    return result


async def _load_contradiction_pairs(
    db: AsyncSession, memory_ids: list[str],
) -> set[tuple[str, str]]:
    """Fetch unresolved contradiction pairs involving any of the given memories."""
    if not memory_ids:
        return set()

    stmt = (
        select(contradictions.c.memory_id_1, contradictions.c.memory_id_2)
        .where(
            and_(
                contradictions.c.resolved == False,  # noqa: E712
                contradictions.c.memory_id_1.in_(memory_ids)
                | contradictions.c.memory_id_2.in_(memory_ids),
            )
        )
    )
    rows = (await db.execute(stmt)).fetchall()
    return {
        (min(row.memory_id_1, row.memory_id_2), max(row.memory_id_1, row.memory_id_2))
        for row in rows
    }


# ── POST /grounding/scan ────────────────────────────────────────────

@router.post("/grounding/scan", response_model=ContaminationScanResponse)
async def scan_agent_memories(
    req: GroundingScanRequest,
    db: AsyncSession = Depends(get_session),
):
    """Batch scan all active memories for contamination risk.

    Returns per-memory grounding scores with risk levels and
    recommended actions, sorted by risk (most contaminated first).
    """
    mems = await _load_memories_for_grounding(db, req.agent_id)
    if not mems:
        raise HTTPException(status_code=404, detail="No active memories found for agent")

    txns = await _load_transactions_for_grounding(db, req.agent_id, req.transaction_window)
    mem_ids = [m.id for m in mems]
    contradiction_pairs = await _load_contradiction_pairs(db, mem_ids)

    # Run pure computation
    scan_result = scan_contamination(
        memories=mems,
        transactions=txns,
        contradiction_pairs=contradiction_pairs if contradiction_pairs else None,
    )

    # Convert to Pydantic response
    flags = [
        GroundingScoreResponse(
            memory_id=f.memory_id,
            grounding_score=round(f.grounding_score, 4),
            provenance_score=round(f.impact_if_removed.get("provenance", 0.0), 4),
            corroboration_score=round(f.impact_if_removed.get("corroboration", 0.0), 4),
            empirical_score=round(f.impact_if_removed.get("empirical", 0.0), 4),
            counterfactual_score=round(f.impact_if_removed.get("counterfactual", 0.0), 4),
            risk_level=f.risk_level,
            reasons=f.reasons,
            recommended_action=f.recommended_action,
        )
        for f in scan_result.flags
    ]

    return ContaminationScanResponse(
        total_memories=scan_result.total_memories,
        trusted=scan_result.trusted,
        uncertain=scan_result.uncertain,
        suspect=scan_result.suspect,
        contaminated=scan_result.contaminated,
        system_contamination_rate=scan_result.system_contamination_rate,
        compute_time_ms=scan_result.compute_time_ms,
        flags=flags,
    )


# ── POST /grounding/gate ────────────────────────────────────────────

@router.post("/grounding/gate", response_model=GateCheckResponse)
async def gate_check_memory(
    req: GateCheckRequest,
    db: AsyncSession = Depends(get_session),
):
    """Write-path gate: check a candidate memory before storage.

    Detects redundancy, contradictions, and hallucination risk.
    Returns a should_store recommendation with detailed reasoning.
    """
    # Build candidate embedding — require it to be provided or generate it
    if req.embedding is None:
        # If no embedding provided, we can't run grounding analysis
        raise HTTPException(
            status_code=400,
            detail="Embedding is required for gate check. "
            "Pre-compute the embedding before calling this endpoint.",
        )

    candidate_embedding = np.array(req.embedding, dtype=np.float64)

    # Build candidate MemoryForGrounding
    import uuid
    candidate_id = str(uuid.uuid4())
    candidate = MemoryForGrounding(
        id=candidate_id,
        content=req.content,
        embedding=candidate_embedding,
        tokens=len(req.content) // 4,
        source_type=req.source_type,
    )

    # Load existing memories and transactions
    existing_mems = await _load_memories_for_grounding(db, req.agent_id)
    txns = await _load_transactions_for_grounding(db, req.agent_id, limit=50)

    # Run pure computation
    gate_result = gate_memory(
        candidate=candidate,
        existing_memories=existing_mems,
        recent_transactions=txns,
    )

    return GateCheckResponse(
        should_store=gate_result.should_store,
        grounding_score=round(gate_result.grounding_score, 4),
        risk_level=gate_result.risk_level,
        reasons=gate_result.reasons,
        contradicts_existing=gate_result.contradicts_existing,
        redundant_with=gate_result.redundant_with,
    )


# ── POST /grounding/quarantine ──────────────────────────────────────

@router.post("/grounding/quarantine", response_model=QuarantineSimulationResponse)
async def quarantine_memories(
    req: QuarantineRequest,
    db: AsyncSession = Depends(get_session),
):
    """Simulate quarantining suspect memories and measure system impact.

    Does NOT actually remove the memories — runs counterfactual analysis
    to predict what would happen if they were removed. Use the counterfactual
    commit endpoint to actually apply the removal.
    """
    if not req.memory_ids:
        raise HTTPException(status_code=400, detail="No memory IDs provided")

    # Verify all memory IDs exist and belong to the agent
    mems = await _load_memories_for_grounding(db, req.agent_id)
    mem_id_set = {m.id for m in mems}
    missing = [mid for mid in req.memory_ids if mid not in mem_id_set]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Memory IDs not found for agent: {missing[:5]}",
        )

    txns = await _load_transactions_for_grounding(db, req.agent_id, req.transaction_window)

    # Run pure computation
    result = simulate_quarantine(
        suspect_ids=req.memory_ids,
        all_memories=mems,
        transactions=txns,
    )

    return QuarantineSimulationResponse(
        quarantined_count=result["quarantined_count"],
        chi_before=result.get("chi_before"),
        chi_after=result.get("chi_after"),
        chi_improvement=result.get("chi_improvement", 0.0),
        health_improved=result.get("health_improved", False),
        coverage_gap_change=result.get("coverage_gap_change", 0),
        transactions_affected=result.get("transactions_affected", 0),
        recommendation=result.get("recommendation", ""),
        compute_time_ms=result.get("compute_time_ms", 0.0),
    )

"""Counterfactual Memory Staging API — "git diff" for memory.

Ephemeral in-memory session store. Sessions live until committed, discarded,
or server restart. No persistence needed — staging is a preview operation.
"""

from __future__ import annotations

import uuid
import time
from datetime import UTC, datetime

import numpy as np
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, and_

from cortex.database import get_session
from cortex.db.tables import (
    memories,
    transactions,
    contradictions,
    lifecycle_events,
    agent_cost_configs,
)
from cortex.attribution.counterfactual import (
    MemoryRecord,
    TransactionRecord,
    ChangeSpec,
    run_counterfactual,
)
from cortex.models import (
    TokenCostConfig,
    CounterfactualStageRequest,
    CounterfactualResult,
    CounterfactualImpact,
    AttributionDelta,
    AttributionSummary,
    ContradictionDelta,
    CoverageDelta,
    CHIDelta,
    FinancialDelta,
    StagingSessionStatus,
)

router = APIRouter(tags=["counterfactual"])

# ── Ephemeral session store with TTL ─────────────────────────────────

_sessions: dict[str, dict] = {}
_SESSION_TTL_SECONDS = 3600  # 1 hour


def _cleanup_expired_sessions() -> int:
    """Remove sessions older than TTL. Returns count of removed sessions."""
    now = time.time()
    expired = [
        sid for sid, data in _sessions.items()
        if now - data.get("_created_epoch", 0) > _SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _sessions[sid]
    return len(expired)


# ── Helpers ──────────────────────────────────────────────────────────

async def _get_cost_config(agent_id: str, db) -> TokenCostConfig:
    """Look up per-agent cost config or return default."""
    row = (
        await db.execute(
            select(
                agent_cost_configs.c.input_token_cost,
                agent_cost_configs.c.output_token_cost,
            ).where(agent_cost_configs.c.agent_id == agent_id)
        )
    ).first()
    if row:
        return TokenCostConfig(input_token_cost=row[0], output_token_cost=row[1])
    return TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)


# ── POST /counterfactual/stage ───────────────────────────────────────

@router.post("/counterfactual/stage", response_model=CounterfactualResult)
async def stage_counterfactual(req: CounterfactualStageRequest):
    """Create a staging session: fetch data, run counterfactual, store result."""
    _cleanup_expired_sessions()  # GC before creating new session
    session_id = str(uuid.uuid4())
    t0 = time.perf_counter()

    async with get_session() as db:
        # 1. Fetch active memories for agent
        mem_stmt = (
            select(memories)
            .where(
                and_(
                    memories.c.agent_id == req.agent_id,
                    memories.c.deleted_at.is_(None),
                    memories.c.archived_at.is_(None),
                    memories.c.embedding.isnot(None),
                )
            )
        )
        mem_rows = (await db.execute(mem_stmt)).fetchall()

        if not mem_rows:
            raise HTTPException(status_code=404, detail="No active memories found for agent")

        current_memories = []
        for row in mem_rows:
            current_memories.append(MemoryRecord(
                id=row.id,
                content=row.content,
                embedding=np.array(row.embedding, dtype=np.float64),
                tokens=row.tokens,
                tier=row.tier,
                created_at=row.created_at,
                last_accessed=row.last_accessed,
                agent_id=row.agent_id,
                retrieval_count=row.retrieval_count,
            ))

        # 2. Fetch recent completed transactions
        txn_stmt = (
            select(transactions)
            .where(
                and_(
                    transactions.c.agent_id == req.agent_id,
                    transactions.c.status == "completed",
                    transactions.c.query_embedding.isnot(None),
                )
            )
            .order_by(transactions.c.created_at.desc())
            .limit(req.transaction_window)
        )
        txn_rows = (await db.execute(txn_stmt)).fetchall()

        transaction_records = []
        for row in txn_rows:
            if row.response_embedding is None:
                continue
            transaction_records.append(TransactionRecord(
                id=row.id,
                query_text=row.query_text,
                query_embedding=np.array(row.query_embedding, dtype=np.float64),
                response_embedding=np.array(row.response_embedding, dtype=np.float64),
                retrieved_memory_ids=list(row.retrieved_memory_ids or []),
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
            ))

        # 3. Fetch existing unresolved contradictions
        mem_ids = [m.id for m in current_memories]
        if mem_ids:
            contra_stmt = (
                select(contradictions)
                .where(
                    and_(
                        contradictions.c.resolved == False,
                        contradictions.c.memory_id_1.in_(mem_ids)
                        | contradictions.c.memory_id_2.in_(mem_ids),
                    )
                )
            )
            contra_rows = (await db.execute(contra_stmt)).fetchall()
            existing_contradictions = [
                (row.memory_id_1, row.memory_id_2, row.confidence)
                for row in contra_rows
            ]
        else:
            existing_contradictions = []

        # 4. Get cost config
        cost_config = await _get_cost_config(req.agent_id, db)

    # 5. Convert request changes to ChangeSpec
    changes = []
    for c in req.changes:
        changes.append(ChangeSpec(
            action=c.action.value,
            memory_id=c.memory_id,
            content=c.content,
            embedding=np.array(c.embedding, dtype=np.float64) if c.embedding else None,
            tokens=c.tokens,
        ))

    # 6. Run counterfactual
    try:
        raw_result = run_counterfactual(
            current_memories=current_memories,
            changes=changes,
            transactions=transaction_records,
            existing_contradictions=existing_contradictions,
            cost_config=cost_config,
            include_analysis=req.include_analysis,
            sim_threshold=req.sim_threshold,
            coverage_threshold=req.coverage_threshold,
        )
        status = StagingSessionStatus.completed
        error = None
    except Exception as e:
        raw_result = None
        status = StagingSessionStatus.failed
        error = str(e)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    # 7. Build response
    impact = None
    if raw_result:
        impact = CounterfactualImpact(
            attribution_deltas=[
                AttributionDelta(**d) for d in (raw_result.get("attribution_deltas") or [])
            ],
            summary=AttributionSummary(**raw_result["summary"]) if raw_result.get("summary") else None,
            contradictions=ContradictionDelta(**raw_result["contradictions"]) if raw_result.get("contradictions") else None,
            coverage=CoverageDelta(**raw_result["coverage"]) if raw_result.get("coverage") else None,
            chi=CHIDelta(**raw_result["chi"]) if raw_result.get("chi") else None,
            financial=FinancialDelta(**raw_result["financial"]) if raw_result.get("financial") else None,
        )

    result = CounterfactualResult(
        session_id=session_id,
        agent_id=req.agent_id,
        status=status,
        changes_proposed=len(req.changes),
        transactions_analyzed=len(transaction_records),
        compute_time_ms=round(elapsed_ms, 2),
        impact=impact,
        error=error,
    )

    # Store session for later commit/discard
    _sessions[session_id] = {
        "result": result,
        "changes": req.changes,
        "agent_id": req.agent_id,
        "created_at": datetime.now(UTC),
        "_created_epoch": time.time(),  # for TTL cleanup
    }

    return result


# ── GET /counterfactual/{session_id} ─────────────────────────────────

@router.get("/counterfactual/{session_id}", response_model=CounterfactualResult)
async def get_session_result(session_id: str):
    """Retrieve a stored staging session result."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session["result"]


# ── POST /counterfactual/{session_id}/commit ─────────────────────────

@router.post("/counterfactual/{session_id}/commit")
async def commit_session(session_id: str):
    """Apply staged changes to the database."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["result"].status != StagingSessionStatus.completed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot commit session in {session['result'].status} state",
        )

    agent_id = session["agent_id"]
    changes = session["changes"]

    async with get_session() as db:
        for change in changes:
            now = datetime.now(UTC)
            if change.action.value == "add":
                new_id = change.memory_id or str(uuid.uuid4())
                tokens = change.tokens or (len(change.content) // 4 if change.content else 0)
                await db.execute(
                    memories.insert().values(
                        id=new_id,
                        content=change.content or "",
                        embedding=change.embedding,
                        tokens=tokens,
                        agent_id=agent_id,
                        tier="warm",
                        criticality=0.5,
                        retrieval_count=0,
                        created_at=now,
                    )
                )
                await db.execute(
                    lifecycle_events.insert().values(
                        id=str(uuid.uuid4()),
                        agent_id=agent_id,
                        action="counterfactual_add",
                        memory_id=new_id,
                        details={"session_id": session_id, "content_preview": (change.content or "")[:100]},
                        created_at=now,
                    )
                )

            elif change.action.value == "remove":
                if change.memory_id:
                    await db.execute(
                        memories.update()
                        .where(memories.c.id == change.memory_id)
                        .values(deleted_at=now)
                    )
                    await db.execute(
                        lifecycle_events.insert().values(
                            id=str(uuid.uuid4()),
                            agent_id=agent_id,
                            action="counterfactual_remove",
                            memory_id=change.memory_id,
                            details={"session_id": session_id},
                            created_at=now,
                        )
                    )

            elif change.action.value == "edit":
                if change.memory_id:
                    update_vals: dict = {}
                    if change.content is not None:
                        update_vals["content"] = change.content
                    if change.embedding is not None:
                        update_vals["embedding"] = change.embedding
                    if change.tokens is not None:
                        update_vals["tokens"] = change.tokens
                    if update_vals:
                        await db.execute(
                            memories.update()
                            .where(memories.c.id == change.memory_id)
                            .values(**update_vals)
                        )
                    await db.execute(
                        lifecycle_events.insert().values(
                            id=str(uuid.uuid4()),
                            agent_id=agent_id,
                            action="counterfactual_edit",
                            memory_id=change.memory_id,
                            details={"session_id": session_id, "fields_updated": list(update_vals.keys())},
                            created_at=now,
                        )
                    )

        await db.commit()

    # Mark session as committed
    session["result"].status = StagingSessionStatus.committed
    return {"status": "committed", "session_id": session_id}


# ── DELETE /counterfactual/{session_id} ──────────────────────────────

@router.delete("/counterfactual/{session_id}")
async def discard_session(session_id: str):
    """Discard a staging session without applying changes."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session["result"].status = StagingSessionStatus.discarded
    del _sessions[session_id]
    return {"status": "discarded", "session_id": session_id}

"""Attribution score query endpoints + ContextCite exact attribution + CAMA."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.api.websocket import manager
from cortex.config import settings
from cortex.database import get_session
from cortex.db.tables import (
    attribution_scores,
    calibration_pairs,
    memories,
    memory_profiles,
    transactions,
)
from cortex.models import AttributionMethod, AttributionScore, MemoryProfile

router = APIRouter(tags=["attribution"])


@router.get("/attribution/{txn_id}")
async def get_attribution_by_transaction(
    txn_id: str,
    db: AsyncSession = Depends(get_session),
):
    rows = (
        await db.execute(
            select(attribution_scores).where(attribution_scores.c.transaction_id == txn_id)
        )
    ).all()
    if not rows:
        raise HTTPException(404, "No attribution scores found for this transaction")

    return [
        AttributionScore(
            id=r.id,
            memory_id=r.memory_id,
            transaction_id=r.transaction_id,
            score=r.score,
            raw_score=r.raw_score,
            method=r.method,
            confidence=r.confidence,
            compute_time_ms=r.compute_time_ms,
        )
        for r in rows
    ]


@router.get("/attribution/memory/{memory_id}")
async def get_attribution_by_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_session),
):
    score_rows = (
        await db.execute(
            select(attribution_scores)
            .where(attribution_scores.c.memory_id == memory_id)
            .order_by(attribution_scores.c.score.desc())
        )
    ).all()

    profile_row = (
        await db.execute(
            select(memory_profiles).where(memory_profiles.c.memory_id == memory_id)
        )
    ).first()

    profile = None
    if profile_row:
        profile = MemoryProfile(
            memory_id=profile_row.memory_id,
            mean_attribution=profile_row.mean_attribution,
            m2=profile_row.m2,
            retrieval_count=profile_row.retrieval_count,
            total_attribution=profile_row.total_attribution,
            trend=profile_row.trend,
            updated_at=profile_row.updated_at,
        )

    scores = [
        AttributionScore(
            id=r.id,
            memory_id=r.memory_id,
            transaction_id=r.transaction_id,
            score=r.score,
            raw_score=r.raw_score,
            method=r.method,
            confidence=r.confidence,
            compute_time_ms=r.compute_time_ms,
        )
        for r in score_rows
    ]

    return {"scores": scores, "profile": profile}


@router.post("/attribution/{txn_id}/exact")
async def trigger_exact_attribution(
    txn_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Trigger ContextCite exact attribution for a transaction.

    Runs N ablated forward passes to compute exact attribution scores.
    Stores calibration pairs for the two-speed bridge.
    Returns cost_usd so users see what they're spending.
    """
    # Load transaction
    txn_row = (
        await db.execute(select(transactions).where(transactions.c.id == txn_id))
    ).first()
    if not txn_row:
        raise HTTPException(404, "Transaction not found")
    if not txn_row.response_text:
        raise HTTPException(400, "Transaction has no response text (still pending)")

    # Load retrieved memories
    mem_ids = txn_row.retrieved_memory_ids or []
    if not mem_ids:
        raise HTTPException(400, "Transaction has no retrieved memories")

    mem_rows = (
        await db.execute(
            select(memories)
            .where(memories.c.id.in_(mem_ids))
            .order_by(memories.c.id)
        )
    ).all()

    if not mem_rows:
        raise HTTPException(404, "No memories found for this transaction")

    # Get existing EAS scores for calibration pairs
    eas_scores_rows = (
        await db.execute(
            select(attribution_scores).where(
                attribution_scores.c.transaction_id == txn_id,
                attribution_scores.c.method == AttributionMethod.eas.value,
            )
        )
    ).all()
    eas_by_memory = {r.memory_id: r.score for r in eas_scores_rows}

    # Run ContextCite
    from cortex.attribution.contextcite import ContextCiteEngine

    engine = ContextCiteEngine(
        num_samples=settings.contextcite_num_samples,
        lasso_lambda=settings.contextcite_lasso_lambda,
        provider_name=settings.llm_provider,
        api_key=settings.llm_api_key,
    )

    result = await engine.compute_attribution(
        query_text=txn_row.query_text,
        memories_text=[r.content for r in mem_rows],
        memory_ids=[r.id for r in mem_rows],
        response_text=txn_row.response_text,
    )

    # Store ContextCite attribution scores
    score_objs = []
    now = datetime.now(UTC)
    for i, mem_row in enumerate(mem_rows):
        score_val = result.scores[i] if i < len(result.scores) else 0.0
        raw_val = result.raw_scores[i] if i < len(result.raw_scores) else 0.0
        score_id = str(uuid.uuid4())

        await db.execute(
            attribution_scores.insert().values(
                id=score_id,
                memory_id=mem_row.id,
                transaction_id=txn_id,
                score=score_val,
                raw_score=raw_val,
                method=AttributionMethod.contextcite.value,
                confidence=result.lds,
                compute_time_ms=result.compute_ms,
            )
        )

        score_objs.append(AttributionScore(
            id=score_id,
            memory_id=mem_row.id,
            transaction_id=txn_id,
            score=score_val,
            raw_score=raw_val,
            method=AttributionMethod.contextcite,
            confidence=result.lds,
            compute_time_ms=result.compute_ms,
        ))

        # Save calibration pair if EAS score exists
        eas_score = eas_by_memory.get(mem_row.id)
        if eas_score is not None:
            await db.execute(
                calibration_pairs.insert().values(
                    id=str(uuid.uuid4()),
                    memory_id=mem_row.id,
                    transaction_id=txn_id,
                    eas_score=eas_score,
                    exact_score=score_val,
                    method="contextcite",
                    created_at=now,
                )
            )

    await db.commit()
    await manager.broadcast("dashboard", {"type": "attribution_scored", "agent_id": txn_row.agent_id, "transaction_id": txn_id})

    return {
        "transaction_id": txn_id,
        "scores": score_objs,
        "lds": result.lds,
        "compute_ms": result.compute_ms,
        "cost_usd": result.cost_usd,
        "num_samples": result.num_samples,
        "method": "contextcite",
    }


@router.post("/attribution/{txn_id}/cama")
async def trigger_cama_attribution(
    txn_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Trigger CAMA (Claim-Aware Memory Attribution) for a transaction.

    Decomposes the response into claims, runs NLI entailment against
    retrieved memories, computes per-claim Shapley values, and aggregates
    into memory-level attribution scores with hallucination detection.

    Returns claim-level analysis, hallucination index, and dead memories.
    """
    import numpy as np

    from cortex.attribution.cama import CAMAEngine
    from cortex.attribution.cama_config import CAMAConfig

    # Load transaction
    txn_row = (
        await db.execute(select(transactions).where(transactions.c.id == txn_id))
    ).first()
    if not txn_row:
        raise HTTPException(404, "Transaction not found")
    if not txn_row.response_text:
        raise HTTPException(400, "Transaction has no response text (still pending)")

    # Load retrieved memories
    mem_ids = txn_row.retrieved_memory_ids or []
    if not mem_ids:
        raise HTTPException(400, "Transaction has no retrieved memories")

    mem_rows = (
        await db.execute(
            select(memories)
            .where(memories.c.id.in_(mem_ids))
            .order_by(memories.c.id)
        )
    ).all()

    if not mem_rows:
        raise HTTPException(404, "No memories found for this transaction")

    # Build memory data
    memory_ids = [r.id for r in mem_rows]
    memory_contents = {r.id: r.content for r in mem_rows}
    memory_embeddings = np.array([r.embedding for r in mem_rows if r.embedding])

    # Configure CAMA from settings
    config = CAMAConfig(
        similarity_threshold=settings.cama_similarity_threshold,
        entailment_threshold=settings.cama_entailment_threshold,
        hallucination_threshold=settings.cama_hallucination_threshold,
        max_candidates_per_claim=settings.cama_max_candidates_per_claim,
        nli_model=settings.cama_nli_model,
        max_claims=settings.cama_max_claims,
        shapley_value_fn=settings.cama_shapley_value_fn,
    )
    engine = CAMAEngine(config=config)

    # Run CAMA pipeline
    try:
        result = await engine.compute_attribution(
            response_text=txn_row.response_text,
            memory_ids=memory_ids,
            memory_contents=memory_contents,
            memory_embeddings=memory_embeddings,
            llm_provider=settings.llm_provider,
            llm_api_key=settings.llm_api_key,
            llm_model=settings.cama_llm_model,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"CAMA pipeline failed: {exc}",
        )

    # Compute total latency
    total_ms = (
        result.latency_ms.decompose_ms
        + result.latency_ms.gate_ms
        + result.latency_ms.entail_ms
        + result.latency_ms.shapley_ms
        + result.latency_ms.aggregate_ms
    )

    # Store CAMA attribution scores
    score_objs = []
    now = datetime.now(UTC)
    for mem_id in memory_ids:
        score_val = result.scores.get(mem_id, 0.0)
        score_id = str(uuid.uuid4())

        await db.execute(
            attribution_scores.insert().values(
                id=score_id,
                memory_id=mem_id,
                transaction_id=txn_id,
                score=score_val,
                raw_score=score_val,  # CAMA scores are already normalized
                method=AttributionMethod.cama.value,
                confidence=1.0 - result.hallucination_index,
                compute_time_ms=total_ms,
            )
        )

        score_objs.append(AttributionScore(
            id=score_id,
            memory_id=mem_id,
            transaction_id=txn_id,
            score=score_val,
            raw_score=score_val,
            method=AttributionMethod.cama,
            confidence=1.0 - result.hallucination_index,
            compute_time_ms=total_ms,
        ))

    await db.commit()
    await manager.broadcast("dashboard", {
        "type": "attribution_scored",
        "agent_id": txn_row.agent_id,
        "transaction_id": txn_id,
        "method": "cama",
    })

    # Serialize claims for JSON response
    claims_data = []
    for c in result.claims:
        claims_data.append({
            "claim": c.claim,
            "claim_type": c.claim_type,
            "support_type": c.support_type,
            "sources": [
                {
                    "memory_id": s.memory_id,
                    "shapley_value": s.shapley_value,
                    "entailment": s.entailment,
                }
                for s in c.sources
            ],
            "best_entailment": c.best_entailment,
            "is_hallucination": c.is_hallucination,
            "hallucination_reason": c.hallucination_reason,
        })

    return {
        "transaction_id": txn_id,
        "scores": {mid: result.scores.get(mid, 0.0) for mid in memory_ids},
        "claims": claims_data,
        "unsupported_claims": [
            {"claim": u.claim, "best_entailment": u.best_entailment}
            for u in result.unsupported_claims
        ],
        "hallucination_index": result.hallucination_index,
        "dead_memories": result.dead_memories,
        "method": "cama",
        "num_claims": result.num_claims,
        "num_nli_calls": result.num_nli_calls,
        "latency_ms": {
            "decompose_ms": result.latency_ms.decompose_ms,
            "gate_ms": result.latency_ms.gate_ms,
            "entail_ms": result.latency_ms.entail_ms,
            "shapley_ms": result.latency_ms.shapley_ms,
            "aggregate_ms": result.latency_ms.aggregate_ms,
        },
        "attribution_scores": score_objs,
    }

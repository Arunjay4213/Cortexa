"""Attribution score query endpoints + ContextCite exact attribution."""

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

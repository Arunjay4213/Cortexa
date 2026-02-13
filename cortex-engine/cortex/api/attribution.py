"""Attribution score query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.database import get_session
from cortex.db.tables import attribution_scores, memory_profiles
from cortex.models import AttributionScore, MemoryProfile

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

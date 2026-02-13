"""Health snapshots and contradiction endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.database import get_session
from cortex.db.tables import contradictions, health_snapshots
from cortex.models import Contradiction, HealthSnapshot

router = APIRouter(tags=["health"])


@router.get("/health/{agent_id}")
async def get_health(
    agent_id: str,
    db: AsyncSession = Depends(get_session),
):
    rows = (
        await db.execute(
            select(health_snapshots)
            .where(health_snapshots.c.agent_id == agent_id)
            .order_by(health_snapshots.c.timestamp.desc())
            .limit(20)
        )
    ).all()

    return [
        HealthSnapshot(
            id=r.id,
            agent_id=r.agent_id,
            contradiction_rate=r.contradiction_rate,
            retrieval_efficiency=r.retrieval_efficiency,
            semantic_drift=r.semantic_drift,
            memory_quality=r.memory_quality,
            timestamp=r.timestamp,
        )
        for r in rows
    ]


@router.get("/health/contradictions")
async def list_contradictions(
    resolved: bool | None = None,
    db: AsyncSession = Depends(get_session),
):
    q = select(contradictions)
    if resolved is not None:
        q = q.where(contradictions.c.resolved == resolved)
    q = q.order_by(contradictions.c.detected_at.desc()).limit(100)

    rows = (await db.execute(q)).all()
    return [
        Contradiction(
            id=r.id,
            memory_id_1=r.memory_id_1,
            memory_id_2=r.memory_id_2,
            type=r.type,
            confidence=r.confidence,
            detected_at=r.detected_at,
            resolved=r.resolved,
        )
        for r in rows
    ]

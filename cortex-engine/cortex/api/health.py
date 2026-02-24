"""Health snapshots, contradiction endpoints, and NLI detection."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.database import get_session
from cortex.db.tables import contradictions, health_snapshots
from cortex.models import Contradiction, HealthSnapshot, CHIComputeResponse

router = APIRouter(tags=["health"])


# NOTE: /health/contradictions MUST be defined before /health/{agent_id}
# so FastAPI doesn't match "contradictions" as an agent_id parameter.

@router.get("/health/contradictions")
async def list_contradictions(
    resolved: bool | None = None,
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    q = select(contradictions)
    if resolved is not None:
        q = q.where(contradictions.c.resolved == resolved)
    if agent_id:
        from cortex.db.tables import memories
        # Get memory IDs for this agent
        mem_ids_q = select(memories.c.id).where(memories.c.agent_id == agent_id)
        mem_ids = [r[0] for r in (await db.execute(mem_ids_q)).all()]
        if mem_ids:
            q = q.where(
                contradictions.c.memory_id_1.in_(mem_ids)
                | contradictions.c.memory_id_2.in_(mem_ids)
            )
        else:
            return []
    q = q.order_by(contradictions.c.detected_at.desc()).limit(100)

    rows = (await db.execute(q)).all()
    return [
        {
            "id": r.id,
            "memory_id_1": r.memory_id_1,
            "memory_id_2": r.memory_id_2,
            "type": r.type,
            "confidence": r.confidence,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            "resolved": r.resolved,
            "resolved_at": r.resolved_at.isoformat() if hasattr(r, "resolved_at") and r.resolved_at else None,
            "resolved_by": r.resolved_by if hasattr(r, "resolved_by") else None,
        }
        for r in rows
    ]


@router.post("/health/contradictions/detect")
async def detect_contradictions_endpoint(
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """Trigger NLI-based contradiction detection batch."""
    from cortex.attribution.contradiction import run_detection_batch

    count, detected = await run_detection_batch(db, agent_id=agent_id)
    return {"detected": count, "contradictions": detected}


@router.patch("/health/contradictions/{contradiction_id}/resolve")
async def resolve_contradiction(
    contradiction_id: str,
    resolved_by: str = "system",
    db: AsyncSession = Depends(get_session),
):
    """Mark a contradiction as resolved."""
    row = (
        await db.execute(
            select(contradictions).where(contradictions.c.id == contradiction_id)
        )
    ).first()
    if not row:
        raise HTTPException(404, "Contradiction not found")

    await db.execute(
        update(contradictions)
        .where(contradictions.c.id == contradiction_id)
        .values(
            resolved=True,
            resolved_at=datetime.now(UTC),
            resolved_by=resolved_by,
        )
    )
    await db.commit()

    return {"id": contradiction_id, "resolved": True, "resolved_by": resolved_by}


@router.post("/health/compute/{agent_id}")
async def compute_chi_endpoint(
    agent_id: str,
    db: AsyncSession = Depends(get_session),
) -> CHIComputeResponse:
    """Compute CHI for an agent and store snapshot.

    This endpoint:
    1. Loads all non-deleted memories for the agent
    2. Computes the 5 CHI components from database state
    3. Stores the result in health_snapshots
    4. Broadcasts health_updated event via WebSocket
    5. Returns the computed CHI score + breakdown
    """
    from cortex.metrics.health import compute_agent_chi
    from cortex.api.websocket import manager
    import uuid

    # Compute CHI from current database state
    chi_result = await compute_agent_chi(db, agent_id)

    # Store snapshot
    snapshot_id = str(uuid.uuid4())
    from sqlalchemy import insert
    now = datetime.now(UTC)
    await db.execute(
        insert(health_snapshots).values(
            id=snapshot_id,
            agent_id=agent_id,
            # Store CHI components
            chi_score=chi_result.score,
            chi_grade=chi_result.grade,
            accuracy_component=chi_result.accuracy_component,
            freshness_component=chi_result.freshness_component,
            coverage_component=chi_result.coverage_component,
            consistency_component=chi_result.consistency_component,
            efficiency_component=chi_result.efficiency_component,
            # Legacy columns (set to 0 for now)
            contradiction_rate=0.0,
            retrieval_efficiency=0.0,
            semantic_drift=0.0,
            memory_quality=0.0,
            timestamp=now,
        )
    )
    await db.commit()

    # Broadcast WebSocket event
    await manager.broadcast("dashboard", {
        "type": "health_updated",
        "agent_id": agent_id,
        "chi_score": chi_result.score,
        "chi_grade": chi_result.grade,
    })

    return CHIComputeResponse(
        agent_id=agent_id,
        chi_score=chi_result.score,
        chi_grade=chi_result.grade,
        components={
            "accuracy": chi_result.accuracy_component,
            "freshness": chi_result.freshness_component,
            "coverage": chi_result.coverage_component,
            "consistency": chi_result.consistency_component,
            "efficiency": chi_result.efficiency_component,
        },
        timestamp=now,
        snapshot_id=snapshot_id,
    )


@router.get("/health/chi/{agent_id}")
async def get_latest_chi(
    agent_id: str,
    db: AsyncSession = Depends(get_session),
) -> CHIComputeResponse | None:
    """Get the latest CHI snapshot for an agent."""
    row = (
        await db.execute(
            select(health_snapshots)
            .where(
                health_snapshots.c.agent_id == agent_id,
                health_snapshots.c.chi_score.isnot(None),  # Only CHI snapshots
            )
            .order_by(health_snapshots.c.timestamp.desc())
            .limit(1)
        )
    ).first()

    if not row:
        return None

    return CHIComputeResponse(
        agent_id=row.agent_id,
        chi_score=row.chi_score,
        chi_grade=row.chi_grade,
        components={
            "accuracy": row.accuracy_component,
            "freshness": row.freshness_component,
            "coverage": row.coverage_component,
            "consistency": row.consistency_component,
            "efficiency": row.efficiency_component,
        },
        timestamp=row.timestamp,
        snapshot_id=row.id,
    )


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
            chi_score=r.chi_score,
            chi_grade=r.chi_grade,
            accuracy_component=r.accuracy_component,
            freshness_component=r.freshness_component,
            coverage_component=r.coverage_component,
            consistency_component=r.consistency_component,
            efficiency_component=r.efficiency_component,
            timestamp=r.timestamp,
        )
        for r in rows
    ]

"""CRUD + profile endpoints for memories."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.attribution import embed_single
from cortex.database import get_session
from cortex.db.tables import memories, memory_profiles
from cortex.models import (
    MemoryCreate,
    MemoryProfile,
    MemoryUnit,
    MemoryUpdate,
    PaginatedResponse,
)

router = APIRouter(tags=["memories"])


def _row_to_memory(row) -> MemoryUnit:
    return MemoryUnit(
        id=row.id,
        content=row.content,
        embedding=row.embedding or [],
        tokens=row.tokens,
        agent_id=row.agent_id,
        tier=row.tier,
        criticality=row.criticality,
        metadata=row.metadata_ or {},
        retrieval_count=row.retrieval_count,
        created_at=row.created_at,
        last_accessed=row.last_accessed,
        deleted_at=row.deleted_at,
    )


@router.post("/memories", response_model=MemoryUnit, status_code=201)
async def create_memory(
    body: MemoryCreate,
    db: AsyncSession = Depends(get_session),
):
    mem_id = str(uuid.uuid4())
    embedding = embed_single(body.content)
    tokens = len(body.content.split())  # rough token estimate

    await db.execute(
        memories.insert().values(
            id=mem_id,
            content=body.content,
            embedding=embedding,
            tokens=tokens,
            agent_id=body.agent_id,
            tier=body.tier.value,
            criticality=body.criticality,
            metadata_=body.metadata,
            retrieval_count=0,
            created_at=datetime.utcnow(),
        )
    )
    await db.commit()

    row = (await db.execute(select(memories).where(memories.c.id == mem_id))).first()
    return _row_to_memory(row)


@router.get("/memories", response_model=PaginatedResponse)
async def list_memories(
    agent_id: str | None = None,
    tier: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    q = select(memories).where(memories.c.deleted_at.is_(None))
    count_q = select(func.count()).select_from(memories).where(memories.c.deleted_at.is_(None))

    if agent_id:
        q = q.where(memories.c.agent_id == agent_id)
        count_q = count_q.where(memories.c.agent_id == agent_id)
    if tier:
        q = q.where(memories.c.tier == tier)
        count_q = count_q.where(memories.c.tier == tier)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(q.order_by(memories.c.created_at.desc()).offset(offset).limit(limit))).all()

    return PaginatedResponse(
        items=[_row_to_memory(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/memories/{memory_id}")
async def get_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_session),
):
    row = (
        await db.execute(
            select(memories).where(memories.c.id == memory_id, memories.c.deleted_at.is_(None))
        )
    ).first()
    if not row:
        raise HTTPException(404, "Memory not found")

    mem = _row_to_memory(row)

    # Attach profile if exists
    profile_row = (
        await db.execute(select(memory_profiles).where(memory_profiles.c.memory_id == memory_id))
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

    return {"memory": mem, "profile": profile}


@router.patch("/memories/{memory_id}", response_model=MemoryUnit)
async def update_memory(
    memory_id: str,
    body: MemoryUpdate,
    db: AsyncSession = Depends(get_session),
):
    row = (
        await db.execute(
            select(memories).where(memories.c.id == memory_id, memories.c.deleted_at.is_(None))
        )
    ).first()
    if not row:
        raise HTTPException(404, "Memory not found")

    values: dict = {}
    if body.tier is not None:
        values["tier"] = body.tier.value
    if body.criticality is not None:
        values["criticality"] = body.criticality
    if body.metadata is not None:
        values["metadata_"] = body.metadata

    if values:
        await db.execute(update(memories).where(memories.c.id == memory_id).values(**values))
        await db.commit()

    row = (await db.execute(select(memories).where(memories.c.id == memory_id))).first()
    return _row_to_memory(row)


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_session),
):
    row = (
        await db.execute(
            select(memories).where(memories.c.id == memory_id, memories.c.deleted_at.is_(None))
        )
    ).first()
    if not row:
        raise HTTPException(404, "Memory not found")

    # Soft delete
    await db.execute(
        update(memories).where(memories.c.id == memory_id).values(deleted_at=datetime.utcnow())
    )
    await db.commit()

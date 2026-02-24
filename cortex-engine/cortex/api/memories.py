"""CRUD + profile + search endpoints for memories."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.attribution import embed, embed_single
from cortex.api.websocket import manager
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
    try:
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
                created_at=datetime.now(UTC),
            )
        )
        await db.commit()
        await manager.broadcast("dashboard", {"type": "memory_update", "agent_id": body.agent_id, "memory_id": mem_id})

        row = (await db.execute(select(memories).where(memories.c.id == mem_id))).first()
        return _row_to_memory(row)
    except Exception as e:
        import sys, traceback
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"ERROR in create_memory:", file=sys.stderr)
        print(f"Exception: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


# NOTE: /memories/search MUST be defined before /memories/{memory_id}
# so FastAPI doesn't match "search" as a memory_id parameter.

@router.get("/memories/search")
async def search_memories(
    q: str = Query(..., description="Search query text"),
    agent_id: str | None = None,
    top_k: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """Semantic search: embed query, cosine similarity against all memory embeddings, top-k."""
    query_embedding = np.array(embed_single(q))

    # Fetch all non-deleted memories with embeddings
    mem_q = select(memories).where(
        memories.c.deleted_at.is_(None),
        memories.c.embedding.isnot(None),
    )
    if agent_id:
        mem_q = mem_q.where(memories.c.agent_id == agent_id)

    rows = (await db.execute(mem_q)).all()
    if not rows:
        return []

    # Compute cosine similarities
    scored: list[tuple[float, object]] = []
    for row in rows:
        if not row.embedding:
            continue
        mem_emb = np.array(row.embedding)
        norm_q = np.linalg.norm(query_embedding)
        norm_m = np.linalg.norm(mem_emb)
        if norm_q == 0 or norm_m == 0:
            sim = 0.0
        else:
            sim = float(np.dot(query_embedding, mem_emb) / (norm_q * norm_m))
        scored.append((sim, row))

    # Sort by similarity descending, take top-k
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    return [
        {
            "memory": _row_to_memory(row),
            "similarity": round(sim, 4),
        }
        for sim, row in top
    ]


@router.get("/memories", response_model=PaginatedResponse)
async def list_memories(
    agent_id: str | None = None,
    tier: str | None = None,
    sort_by: str = Query("created_at", description="Field to sort by"),
    order: str = Query("desc", description="Sort order: asc or desc"),
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

    # Sort
    valid_sort_fields = {
        "created_at": memories.c.created_at,
        "retrieval_count": memories.c.retrieval_count,
        "criticality": memories.c.criticality,
        "tokens": memories.c.tokens,
        "last_accessed": memories.c.last_accessed,
    }
    sort_col = valid_sort_fields.get(sort_by, memories.c.created_at)
    if order == "asc":
        q = q.order_by(sort_col.asc())
    else:
        q = q.order_by(sort_col.desc())

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(q.offset(offset).limit(limit))).all()

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
        await manager.broadcast("dashboard", {"type": "memory_update", "agent_id": row.agent_id, "memory_id": memory_id})

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
        update(memories).where(memories.c.id == memory_id).values(deleted_at=datetime.now(UTC))
    )
    await db.commit()
    await manager.broadcast("dashboard", {"type": "memory_update", "agent_id": row.agent_id, "memory_id": memory_id})

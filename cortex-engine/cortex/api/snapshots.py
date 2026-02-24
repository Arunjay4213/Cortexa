"""Phase 4: Memory snapshots, branches, and diff API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.database import get_session
from cortex.db.tables import (
    memories,
    memory_branches,
    memory_profiles,
    memory_snapshot_entries,
    memory_snapshots,
)
from cortex.models import (
    BranchCreate,
    BranchResponse,
    DiffEntry,
    SnapshotCreate,
    SnapshotDiff,
    SnapshotEntryResponse,
    SnapshotResponse,
)

router = APIRouter(tags=["snapshots"])


@router.post("/snapshots/{agent_id}", response_model=SnapshotResponse, status_code=201)
async def create_snapshot(
    agent_id: str,
    body: SnapshotCreate,
    db: AsyncSession = Depends(get_session),
):
    """Create a snapshot of current memories for an agent."""
    snapshot_id = str(uuid.uuid4())

    # Fetch current non-deleted memories for this agent
    mem_rows = (
        await db.execute(
            select(memories).where(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
            )
        )
    ).all()

    # Get attribution data for each memory
    profile_map: dict[str, float] = {}
    if mem_rows:
        mem_ids = [r.id for r in mem_rows]
        profile_rows = (
            await db.execute(
                select(memory_profiles).where(memory_profiles.c.memory_id.in_(mem_ids))
            )
        ).all()
        for pr in profile_rows:
            profile_map[pr.memory_id] = pr.total_attribution

    # Create snapshot
    now = datetime.now(UTC)
    await db.execute(
        memory_snapshots.insert().values(
            id=snapshot_id,
            name=body.name,
            agent_id=agent_id,
            description=body.description,
            memory_count=len(mem_rows),
            created_at=now,
            created_by=body.created_by,
        )
    )

    # Copy memory state into snapshot entries
    for mem in mem_rows:
        await db.execute(
            memory_snapshot_entries.insert().values(
                snapshot_id=snapshot_id,
                memory_id=mem.id,
                content=mem.content,
                embedding=mem.embedding,
                tier=mem.tier,
                token_count=mem.tokens,
                total_attribution=profile_map.get(mem.id, 0.0),
            )
        )

    await db.commit()

    return SnapshotResponse(
        id=snapshot_id,
        name=body.name,
        agent_id=agent_id,
        description=body.description,
        memory_count=len(mem_rows),
        created_at=now,
        created_by=body.created_by,
    )


@router.get("/snapshots/{agent_id}", response_model=list[SnapshotResponse])
async def list_snapshots(
    agent_id: str,
    db: AsyncSession = Depends(get_session),
):
    """List all snapshots for an agent."""
    rows = (
        await db.execute(
            select(memory_snapshots)
            .where(memory_snapshots.c.agent_id == agent_id)
            .order_by(memory_snapshots.c.created_at.desc())
        )
    ).all()

    return [
        SnapshotResponse(
            id=r.id,
            name=r.name,
            agent_id=r.agent_id,
            description=r.description,
            memory_count=r.memory_count,
            created_at=r.created_at,
            created_by=r.created_by,
        )
        for r in rows
    ]


@router.get("/snapshots/{agent_id}/{snapshot_id}")
async def get_snapshot(
    agent_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Get a snapshot with its entries."""
    snap = (
        await db.execute(
            select(memory_snapshots).where(
                memory_snapshots.c.id == snapshot_id,
                memory_snapshots.c.agent_id == agent_id,
            )
        )
    ).first()
    if not snap:
        raise HTTPException(404, "Snapshot not found")

    entries = (
        await db.execute(
            select(memory_snapshot_entries).where(
                memory_snapshot_entries.c.snapshot_id == snapshot_id
            )
        )
    ).all()

    return {
        "snapshot": SnapshotResponse(
            id=snap.id,
            name=snap.name,
            agent_id=snap.agent_id,
            description=snap.description,
            memory_count=snap.memory_count,
            created_at=snap.created_at,
            created_by=snap.created_by,
        ),
        "entries": [
            SnapshotEntryResponse(
                memory_id=e.memory_id,
                content=e.content,
                tier=e.tier,
                token_count=e.token_count,
                total_attribution=e.total_attribution,
            )
            for e in entries
        ],
    }


@router.get("/snapshots/{agent_id}/{id1}/diff/{id2}", response_model=SnapshotDiff)
async def diff_snapshots(
    agent_id: str,
    id1: str,
    id2: str,
    db: AsyncSession = Depends(get_session),
):
    """Compute diff between two snapshots."""
    entries_a = (
        await db.execute(
            select(memory_snapshot_entries).where(
                memory_snapshot_entries.c.snapshot_id == id1
            )
        )
    ).all()
    entries_b = (
        await db.execute(
            select(memory_snapshot_entries).where(
                memory_snapshot_entries.c.snapshot_id == id2
            )
        )
    ).all()

    map_a = {e.memory_id: e for e in entries_a}
    map_b = {e.memory_id: e for e in entries_b}

    added: list[DiffEntry] = []
    removed: list[DiffEntry] = []
    modified: list[DiffEntry] = []

    # Memories in B but not in A → added
    for mid, eb in map_b.items():
        if mid not in map_a:
            added.append(DiffEntry(
                memory_id=mid,
                status="added",
                content_b=eb.content,
                tier_b=eb.tier,
            ))

    # Memories in A but not in B → removed
    for mid, ea in map_a.items():
        if mid not in map_b:
            removed.append(DiffEntry(
                memory_id=mid,
                status="removed",
                content_a=ea.content,
                tier_a=ea.tier,
            ))

    # Memories in both → check for modifications
    for mid in map_a:
        if mid in map_b:
            ea, eb = map_a[mid], map_b[mid]
            if ea.content != eb.content or ea.tier != eb.tier:
                modified.append(DiffEntry(
                    memory_id=mid,
                    status="modified",
                    content_a=ea.content,
                    content_b=eb.content,
                    tier_a=ea.tier,
                    tier_b=eb.tier,
                ))

    return SnapshotDiff(
        snapshot_a_id=id1,
        snapshot_b_id=id2,
        added=added,
        removed=removed,
        modified=modified,
    )


@router.post("/snapshots/{agent_id}/{snapshot_id}/restore")
async def restore_snapshot(
    agent_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Restore memories from a snapshot — replaces current agent memories.

    Atomic operation: either the full restore succeeds or nothing changes.
    Creates an auto-snapshot of current state before restoring so the
    operation can be undone.
    """
    from sqlalchemy import update

    snap = (
        await db.execute(
            select(memory_snapshots).where(
                memory_snapshots.c.id == snapshot_id,
                memory_snapshots.c.agent_id == agent_id,
            )
        )
    ).first()
    if not snap:
        raise HTTPException(404, "Snapshot not found")

    entries = (
        await db.execute(
            select(memory_snapshot_entries).where(
                memory_snapshot_entries.c.snapshot_id == snapshot_id
            )
        )
    ).all()

    if not entries:
        raise HTTPException(400, "Snapshot has no entries to restore")

    # ── Auto-snapshot current state before restoring ──────────────
    # This lets the user undo the restore if needed.
    now = datetime.now(UTC)
    current_mems = (
        await db.execute(
            select(memories).where(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
            )
        )
    ).all()

    pre_restore_id = str(uuid.uuid4())

    # Get attribution data for pre-restore snapshot
    pre_profile_map: dict[str, float] = {}
    if current_mems:
        pre_mem_ids = [r.id for r in current_mems]
        pre_profile_rows = (
            await db.execute(
                select(memory_profiles).where(
                    memory_profiles.c.memory_id.in_(pre_mem_ids)
                )
            )
        ).all()
        for pr in pre_profile_rows:
            pre_profile_map[pr.memory_id] = pr.total_attribution

    await db.execute(
        memory_snapshots.insert().values(
            id=pre_restore_id,
            name=f"pre-restore-{snapshot_id[:8]}",
            agent_id=agent_id,
            description=f"Auto-snapshot before restoring {snap.name}",
            memory_count=len(current_mems),
            created_at=now,
            created_by="system:restore",
        )
    )
    for mem in current_mems:
        await db.execute(
            memory_snapshot_entries.insert().values(
                snapshot_id=pre_restore_id,
                memory_id=mem.id,
                content=mem.content,
                embedding=mem.embedding,
                tier=mem.tier,
                token_count=mem.tokens,
                total_attribution=pre_profile_map.get(mem.id, 0.0),
            )
        )

    # ── Atomic restore: soft-delete current + re-create from snapshot ──
    # All operations below are in the same DB transaction.
    # If any step fails, SQLAlchemy rolls back the entire transaction
    # including the soft-deletes — nothing changes.
    try:
        # Step 1: Soft-delete all current memories
        await db.execute(
            update(memories)
            .where(memories.c.agent_id == agent_id, memories.c.deleted_at.is_(None))
            .values(deleted_at=now)
        )

        # Step 2: Restore each memory from the snapshot
        restored_count = 0
        for entry in entries:
            existing = (
                await db.execute(
                    select(memories.c.id).where(memories.c.id == entry.memory_id)
                )
            ).first()

            if existing:
                await db.execute(
                    update(memories)
                    .where(memories.c.id == entry.memory_id)
                    .values(
                        content=entry.content,
                        tier=entry.tier,
                        tokens=entry.token_count,
                        deleted_at=None,
                    )
                )
            else:
                await db.execute(
                    memories.insert().values(
                        id=entry.memory_id,
                        content=entry.content,
                        embedding=entry.embedding,
                        tokens=entry.token_count,
                        agent_id=agent_id,
                        tier=entry.tier,
                        criticality=0.5,
                        metadata_={},
                        retrieval_count=0,
                        created_at=now,
                    )
                )
            restored_count += 1

        # Step 3: Commit everything atomically — auto-snapshot + soft-delete + restore
        await db.commit()

    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Restore failed atomically — no changes applied. Error: {exc}",
        )

    return {
        "restored_from": snapshot_id,
        "agent_id": agent_id,
        "memory_count": restored_count,
        "pre_restore_snapshot_id": pre_restore_id,
    }


@router.post("/branches/{agent_id}", response_model=BranchResponse, status_code=201)
async def create_branch(
    agent_id: str,
    body: BranchCreate,
    db: AsyncSession = Depends(get_session),
):
    """Create a branch from a snapshot."""
    snap = (
        await db.execute(
            select(memory_snapshots).where(
                memory_snapshots.c.id == body.snapshot_id,
                memory_snapshots.c.agent_id == agent_id,
            )
        )
    ).first()
    if not snap:
        raise HTTPException(404, "Snapshot not found")

    branch_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    await db.execute(
        memory_branches.insert().values(
            id=branch_id,
            name=body.name,
            parent_snapshot_id=body.snapshot_id,
            agent_id=agent_id,
            description=body.description,
            created_at=now,
        )
    )
    await db.commit()

    return BranchResponse(
        id=branch_id,
        name=body.name,
        parent_snapshot_id=body.snapshot_id,
        agent_id=agent_id,
        description=body.description,
        created_at=now,
    )


@router.get("/branches/{agent_id}", response_model=list[BranchResponse])
async def list_branches(
    agent_id: str,
    db: AsyncSession = Depends(get_session),
):
    """List all branches for an agent."""
    rows = (
        await db.execute(
            select(memory_branches)
            .where(memory_branches.c.agent_id == agent_id)
            .order_by(memory_branches.c.created_at.desc())
        )
    ).all()

    return [
        BranchResponse(
            id=r.id,
            name=r.name,
            parent_snapshot_id=r.parent_snapshot_id,
            agent_id=r.agent_id,
            description=r.description,
            created_at=r.created_at,
        )
        for r in rows
    ]

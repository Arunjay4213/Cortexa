"""Memory intelligence endpoints: write, dedup, health."""

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth import require_auth
from app.events import event_bus
from app.limiter import limiter

router = APIRouter()


# ── In-process memory store (per engine instance) ─────────────────────────
# Stores hashes of written memories per agent for duplicate detection.
# In production this would be a Redis set or DB table.
_memory_store: dict[str, list[dict]] = {}  # agent_id -> list of {hash, text, ts}


def _similarity_hash(text: str) -> str:
    """Normalize and hash memory text for near-duplicate detection."""
    norm = re.sub(r"\s+", " ", text.lower().strip())
    # Remove common stop words for semantic similarity
    norm = re.sub(r"\b(the|a|an|is|are|was|were|it|this|that)\b", "", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.md5(norm.encode()).hexdigest()


def _token_overlap(a: str, b: str) -> float:
    """Jaccard token overlap between two texts."""
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _detect_duplicate(
    text: str, agent_memories: list[dict], threshold: float = 0.7
) -> tuple[bool, str | None]:
    """
    Check if text is a near-duplicate of any existing memory.
    Returns (is_duplicate, matching_memory_text).
    """
    h = _similarity_hash(text)
    for mem in agent_memories:
        # Exact hash match
        if mem["hash"] == h:
            return True, mem["text"]
        # Token overlap check
        if _token_overlap(text, mem["text"]) >= threshold:
            return True, mem["text"]
    return False, None


# ── Models ─────────────────────────────────────────────────────────────────


class MemoryWriteRequest(BaseModel):
    memory: str
    agent_id: str = "default"
    metadata: dict | None = None


class MemoryWriteResponse(BaseModel):
    status: Literal["written", "duplicate", "merged"]
    memory_id: str
    duplicate_of: str | None = None
    duplicate_pct: float | None = None
    agent_id: str


class MemoryHealthResponse(BaseModel):
    agent_id: str
    total_memories: int
    duplicate_count: int
    duplicate_pct: float
    unique_memories: int
    token_burn_savings_pct: float  # Estimated % of tokens wasted on duplicates


class MemoryTraceRequest(BaseModel):
    query: str
    agent_id: str = "default"
    top_k: int = 5


class MemoryTraceResponse(BaseModel):
    query: str
    agent_id: str
    matches: list[dict]  # [{memory, score, ts, memory_id}]
    total_searched: int


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/v1/memory/write", response_model=MemoryWriteResponse)
@limiter.limit("300/minute")
async def memory_write(
    request: Request,
    body: MemoryWriteRequest,
    api_key_id: str | None = Depends(require_auth),
):
    """
    Write a memory with automatic duplicate detection.

    Returns status: 'written' | 'duplicate' | 'merged'
    Publishes a memory_write / memory_duplicate SSE event.
    """
    agent_id = body.agent_id
    if agent_id not in _memory_store:
        _memory_store[agent_id] = []

    agent_memories = _memory_store[agent_id]
    is_dup, dup_of = _detect_duplicate(body.memory, agent_memories)

    ts_str = datetime.now(timezone.utc).isoformat()
    mem_hash = _similarity_hash(body.memory)
    memory_id = f"{agent_id}:{mem_hash[:8]}"

    if is_dup:
        # Duplicate — do not write
        total = len(agent_memories)
        dup_count = sum(
            1 for m in agent_memories if m.get("is_duplicate", False)
        ) + 1
        dup_pct = dup_count / (total + 1) * 100 if total > 0 else 0.0

        asyncio.create_task(event_bus.publish({
            "type": "memory_duplicate",
            "ts": ts_str,
            "agent_id": agent_id,
            "api_key_id": api_key_id,
            "memory_preview": body.memory[:200],
            "duplicate_of": (dup_of or "")[:200],
            "memory_id": memory_id,
            "total_memories": total,
            "duplicate_pct": round(dup_pct, 1),
            "hi": 0.0,
            "latency_ms": 0,
        }))

        return MemoryWriteResponse(
            status="duplicate",
            memory_id=memory_id,
            duplicate_of=dup_of,
            duplicate_pct=round(dup_pct, 1),
            agent_id=agent_id,
        )

    # Write the memory
    agent_memories.append({
        "hash": mem_hash,
        "text": body.memory,
        "ts": ts_str,
        "memory_id": memory_id,
        "metadata": body.metadata or {},
        "is_duplicate": False,
    })

    total = len(agent_memories)
    asyncio.create_task(event_bus.publish({
        "type": "memory_write",
        "ts": ts_str,
        "agent_id": agent_id,
        "api_key_id": api_key_id,
        "memory_preview": body.memory[:200],
        "memory_id": memory_id,
        "total_memories": total,
        "hi": 0.0,
        "latency_ms": 0,
    }))

    return MemoryWriteResponse(
        status="written",
        memory_id=memory_id,
        duplicate_of=None,
        duplicate_pct=None,
        agent_id=agent_id,
    )


@router.get("/v1/memory/health/{agent_id}", response_model=MemoryHealthResponse)
@limiter.limit("60/minute")
async def memory_health(
    request: Request,
    agent_id: str,
    api_key_id: str | None = Depends(require_auth),
):
    """
    Return memory health stats for an agent.
    Key metric: duplicate_pct — what % of memory store is redundant.
    """
    memories = _memory_store.get(agent_id, [])
    total = len(memories)

    if total == 0:
        return MemoryHealthResponse(
            agent_id=agent_id,
            total_memories=0,
            duplicate_count=0,
            duplicate_pct=0.0,
            unique_memories=0,
            token_burn_savings_pct=0.0,
        )

    # Count duplicates by re-running detection in sequence
    dup_count = 0
    seen: list[dict] = []
    for mem in memories:
        is_dup, _ = _detect_duplicate(mem["text"], seen)
        if is_dup:
            dup_count += 1
        else:
            seen.append(mem)

    dup_pct = dup_count / total * 100 if total > 0 else 0.0
    unique = total - dup_count

    return MemoryHealthResponse(
        agent_id=agent_id,
        total_memories=total,
        duplicate_count=dup_count,
        duplicate_pct=round(dup_pct, 1),
        unique_memories=unique,
        token_burn_savings_pct=round(dup_pct, 1),  # Each dup wastes tokens on every call
    )


@router.post("/v1/memory/trace", response_model=MemoryTraceResponse)
@limiter.limit("60/minute")
async def memory_trace(
    request: Request,
    body: MemoryTraceRequest,
    api_key_id: str | None = Depends(require_auth),
):
    """
    Trace which memories are most relevant to a query.
    Uses token overlap scoring (fast, no embedding required).
    """
    memories = _memory_store.get(body.agent_id, [])

    scored = []
    for mem in memories:
        score = _token_overlap(body.query, mem["text"])
        if score > 0:
            scored.append({
                "memory": mem["text"],
                "score": round(score, 3),
                "ts": mem["ts"],
                "memory_id": mem["memory_id"],
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: body.top_k]

    return MemoryTraceResponse(
        query=body.query,
        agent_id=body.agent_id,
        matches=top,
        total_searched=len(memories),
    )


@router.delete("/v1/memory/{agent_id}")
@limiter.limit("30/minute")
async def clear_memory(
    request: Request,
    agent_id: str,
    api_key_id: str | None = Depends(require_auth),
):
    """Clear all memories for an agent."""
    count = len(_memory_store.get(agent_id, []))
    _memory_store.pop(agent_id, None)
    return {"cleared": count, "agent_id": agent_id}

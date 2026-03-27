"""Health check engine for memory auditing.

Computes ghost token %, contradiction count, staleness,
MAS distribution, and overall health score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from cx.adapters.base import MemoryAdapter, MemoryRecord


@dataclass
class GhostToken:
    memory_id: str
    content: str
    mas_score: float
    reason: str  # "low_mas", "duplicate", "no_access"


@dataclass
class Contradiction:
    memory_a_id: str
    memory_a_content: str
    memory_a_source: str | None
    memory_b_id: str
    memory_b_content: str
    memory_b_source: str | None
    explanation: str


@dataclass
class AuditReport:
    """Full audit results."""
    total_memories: int
    collections: list[str]
    health_score: float  # 0-100

    # Ghost tokens
    ghost_tokens: list[GhostToken] = field(default_factory=list)
    ghost_pct: float = 0.0
    estimated_token_waste_per_day: int = 0
    estimated_cost_waste_per_day: float = 0.0

    # Contradictions
    contradictions: list[Contradiction] = field(default_factory=list)

    # Staleness
    stale_count: int = 0
    stale_days_threshold: int = 30
    no_provenance_count: int = 0
    source_outdated_count: int = 0

    # MAS distribution
    mas_high_count: int = 0   # >= 0.7
    mas_mid_count: int = 0    # 0.3 - 0.7
    mas_low_count: int = 0    # < 0.3
    mas_avg: float = 0.0

    adapter_description: str = ""


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _estimate_tokens(content: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(content) // 4)


def run_audit(
    adapter: MemoryAdapter,
    ghost_threshold: float = 0.05,
    stale_days: int = 30,
    on_progress: Any = None,
) -> AuditReport:
    """Run a full memory health audit.

    Args:
        adapter: The memory backend to audit.
        ghost_threshold: MAS score below which a memory is flagged as ghost.
        stale_days: Days since last access to flag as stale.
        on_progress: Optional callback(current, total) for progress updates.
    """
    memories = adapter.list_memories()
    total = len(memories)
    collections = adapter.list_collections()

    ghosts: list[GhostToken] = []
    stale_count = 0
    no_provenance = 0
    source_outdated = 0
    mas_values: list[float] = []
    now = datetime.now()

    # Duplicate detection via embeddings
    embeddings = adapter.get_embeddings([m.id for m in memories])
    seen_pairs: set[tuple[str, str]] = set()

    for i, mem in enumerate(memories):
        if on_progress:
            on_progress(i + 1, total)

        mas = mem.mas_score if mem.mas_score is not None else 0.0
        mas_values.append(mas)

        # Ghost token detection
        if mas <= ghost_threshold:
            ghosts.append(GhostToken(
                memory_id=mem.id,
                content=mem.content[:80],
                mas_score=mas,
                reason="low_mas",
            ))
        elif mem.access_count == 0 and mem.last_accessed == mem.created_at:
            ghosts.append(GhostToken(
                memory_id=mem.id,
                content=mem.content[:80],
                mas_score=mas,
                reason="no_access",
            ))

        # Check for near-duplicates (embedding similarity > 0.95)
        if mem.id in embeddings:
            emb_a = embeddings[mem.id]
            for j, other in enumerate(memories):
                if j <= i or other.id not in embeddings:
                    continue
                pair = (min(mem.id, other.id), max(mem.id, other.id))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                sim = _cosine_similarity(emb_a, embeddings[other.id])
                if sim > 0.95 and mem.id not in [g.memory_id for g in ghosts]:
                    ghosts.append(GhostToken(
                        memory_id=mem.id,
                        content=f"{mem.content[:60]} (duplicate of {other.id})",
                        mas_score=mas,
                        reason="duplicate",
                    ))

        # Staleness
        if mem.last_accessed:
            days_since = (now - mem.last_accessed).days
            if days_since > stale_days:
                stale_count += 1

        # Provenance
        if not mem.source:
            no_provenance += 1
        elif mem.source_updated_at and mem.created_at:
            if mem.source_updated_at > mem.created_at:
                source_outdated += 1

    # Contradiction detection
    contradictions: list[Contradiction] = []
    if hasattr(adapter, "get_contradictions"):
        for c in adapter.get_contradictions():
            contradictions.append(Contradiction(
                memory_a_id=c["memory_a"]["id"],
                memory_a_content=c["memory_a"]["content"],
                memory_a_source=c["memory_a"].get("source"),
                memory_b_id=c["memory_b"]["id"],
                memory_b_content=c["memory_b"]["content"],
                memory_b_source=c["memory_b"].get("source"),
                explanation=c["explanation"],
            ))

    # MAS distribution
    mas_high = sum(1 for v in mas_values if v >= 0.7)
    mas_mid = sum(1 for v in mas_values if 0.3 <= v < 0.7)
    mas_low = sum(1 for v in mas_values if v < 0.3)
    mas_avg = sum(mas_values) / len(mas_values) if mas_values else 0.0

    # Cost estimation
    ghost_token_count = sum(_estimate_tokens(g.content) for g in ghosts)
    # Assume ~100 queries/day, each retrieves ~10 memories
    # Ghost tokens get retrieved proportionally to their % in the store
    ghost_pct = len(ghosts) / total if total > 0 else 0.0
    estimated_wasted_tokens = int(ghost_token_count * 100 * ghost_pct)
    # ~$0.003 per 1K input tokens (Claude Sonnet pricing rough estimate)
    estimated_cost = estimated_wasted_tokens * 0.003 / 1000

    # Health score (0-100)
    # Weights: ghost % (30%), contradictions (25%), staleness (20%), MAS (25%)
    ghost_score = max(0, 100 - (ghost_pct * 200))  # 0% ghosts = 100, 50% = 0
    contradiction_score = max(0, 100 - (len(contradictions) * 25))  # 0 = 100, 4+ = 0
    stale_pct = stale_count / total if total > 0 else 0.0
    stale_score = max(0, 100 - (stale_pct * 200))
    mas_score_component = mas_avg * 100  # Higher avg MAS = healthier

    health_score = (
        ghost_score * 0.30
        + contradiction_score * 0.25
        + stale_score * 0.20
        + mas_score_component * 0.25
    )
    health_score = max(0, min(100, health_score))

    return AuditReport(
        total_memories=total,
        collections=collections,
        health_score=round(health_score, 1),
        ghost_tokens=sorted(ghosts, key=lambda g: g.mas_score),
        ghost_pct=round(ghost_pct * 100, 1),
        estimated_token_waste_per_day=estimated_wasted_tokens,
        estimated_cost_waste_per_day=round(estimated_cost, 2),
        contradictions=contradictions,
        stale_count=stale_count,
        stale_days_threshold=stale_days,
        no_provenance_count=no_provenance,
        source_outdated_count=source_outdated,
        mas_high_count=mas_high,
        mas_mid_count=mas_mid,
        mas_low_count=mas_low,
        mas_avg=round(mas_avg, 3),
        adapter_description=adapter.connect(),
    )

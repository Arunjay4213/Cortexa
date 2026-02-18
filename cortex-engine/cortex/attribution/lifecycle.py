"""Phase 3 Lifecycle Engine — automated memory optimization.

Provides recommendations for:
- Archive: memories with negative P&L (cost > attribution value)
- Consolidate: exact duplicates (content_hash) and near-duplicates
- Tier changes: promote trending-up, demote trending-down
- Budget optimization: greedy submodular token budget allocation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, func, and_, update, insert
from sqlalchemy.ext.asyncio import AsyncConnection

from cortex.db.tables import memories, memory_profiles, attribution_scores, lifecycle_events
from cortex.metrics.calculator import memory_pnl
from cortex.models import (
    ArchiveRecommendation,
    BudgetOptimization,
    ConsolidationRecommendation,
    LifecycleRecommendations,
    TierRecommendation,
    TokenCostConfig,
)

# Default cost config when no per-agent config is available
_DEFAULT_CONFIG = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)


async def _get_cost_config(agent_id: str, db: AsyncConnection) -> TokenCostConfig:
    """Look up per-agent cost config or return default."""
    from cortex.db.tables import agent_cost_configs
    row = (
        await db.execute(
            select(agent_cost_configs.c.input_token_cost, agent_cost_configs.c.output_token_cost)
            .where(agent_cost_configs.c.agent_id == agent_id)
        )
    ).first()
    if row:
        return TokenCostConfig(input_token_cost=row[0], output_token_cost=row[1])
    return _DEFAULT_CONFIG


async def recommend_archive(agent_id: str, db: AsyncConnection) -> list[ArchiveRecommendation]:
    """Find memories with negative P&L — cost exceeds attribution value."""
    config = await _get_cost_config(agent_id, db)

    # Join memories with their profiles to get attribution data
    stmt = (
        select(
            memories.c.id,
            memories.c.agent_id,
            memories.c.tokens,
            memories.c.retrieval_count,
            func.coalesce(memory_profiles.c.total_attribution, 0.0).label("total_attribution"),
        )
        .outerjoin(memory_profiles, memories.c.id == memory_profiles.c.memory_id)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.archived_at.is_(None),
            )
        )
    )
    rows = (await db.execute(stmt)).fetchall()

    recommendations = []
    for row in rows:
        pnl = memory_pnl(
            memory_id=row.id,
            total_attribution=row.total_attribution,
            retrieval_count=row.retrieval_count,
            tokens=row.tokens,
            config=config,
        )
        if pnl.pnl < 0:
            recommendations.append(
                ArchiveRecommendation(
                    memory_id=row.id,
                    agent_id=row.agent_id,
                    revenue=pnl.revenue,
                    cost=pnl.cost,
                    pnl=pnl.pnl,
                    reason="negative_pnl",
                )
            )

    # Sort by worst P&L first
    recommendations.sort(key=lambda r: r.pnl)
    return recommendations


async def recommend_consolidate(agent_id: str, db: AsyncConnection) -> list[ConsolidationRecommendation]:
    """Find exact duplicates via content_hash GROUP BY."""
    stmt = (
        select(
            memories.c.content_hash,
            func.array_agg(memories.c.id).label("memory_ids"),
            func.count().label("cnt"),
        )
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.archived_at.is_(None),
                memories.c.content_hash.isnot(None),
            )
        )
        .group_by(memories.c.content_hash)
        .having(func.count() > 1)
    )
    rows = (await db.execute(stmt)).fetchall()

    recommendations = []
    for row in rows:
        ids = list(row.memory_ids)
        # Keep the first one as canonical (oldest), rest are duplicates
        canonical = ids[0]
        duplicates = ids[1:]
        recommendations.append(
            ConsolidationRecommendation(
                canonical_memory_id=canonical,
                duplicate_memory_ids=duplicates,
                method="content_hash",
            )
        )
    return recommendations


async def recommend_semantic_consolidate(
    agent_id: str,
    db: AsyncConnection,
    similarity_threshold: float = 0.85,
) -> list[ConsolidationRecommendation]:
    """Find near-duplicate memories via cosine similarity on embeddings.

    Unlike recommend_consolidate (exact content_hash), this detects
    semantically similar memories that may have different wording but
    convey the same information. Groups are formed greedily.
    """
    stmt = (
        select(memories.c.id, memories.c.embedding)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.archived_at.is_(None),
                memories.c.embedding.isnot(None),
            )
        )
        .order_by(memories.c.created_at)  # oldest first = canonical
    )
    rows = (await db.execute(stmt)).fetchall()

    if len(rows) < 2:
        return []

    import numpy as np

    valid = [(r.id, np.array(r.embedding)) for r in rows if r.embedding]
    if len(valid) < 2:
        return []

    ids = [v[0] for v in valid]
    embeddings = np.array([v[1] for v in valid])

    # Normalize
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    normed = embeddings / norms

    # Cosine similarity matrix
    sim_matrix = normed @ normed.T

    # Greedy grouping: assign each memory to the first group it matches
    assigned: set[int] = set()
    recommendations = []

    for i in range(len(ids)):
        if i in assigned:
            continue

        group = [i]
        assigned.add(i)

        for j in range(i + 1, len(ids)):
            if j in assigned:
                continue
            if sim_matrix[i, j] >= similarity_threshold:
                group.append(j)
                assigned.add(j)

        if len(group) > 1:
            canonical = ids[group[0]]
            duplicates = [ids[g] for g in group[1:]]
            recommendations.append(
                ConsolidationRecommendation(
                    canonical_memory_id=canonical,
                    duplicate_memory_ids=duplicates,
                    method="cosine_similarity",
                )
            )

    return recommendations


async def recommend_tier_changes(agent_id: str, db: AsyncConnection) -> list[TierRecommendation]:
    """Promote trending-up memories, demote trending-down."""
    stmt = (
        select(
            memories.c.id,
            memories.c.tier,
            memory_profiles.c.trend,
        )
        .join(memory_profiles, memories.c.id == memory_profiles.c.memory_id)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.archived_at.is_(None),
            )
        )
    )
    rows = (await db.execute(stmt)).fetchall()

    tier_order = ["cold", "warm", "hot"]
    recommendations = []
    for row in rows:
        current_idx = tier_order.index(row.tier) if row.tier in tier_order else 1
        if row.trend == "up" and current_idx < 2:
            new_tier = tier_order[current_idx + 1]
            recommendations.append(
                TierRecommendation(
                    memory_id=row.id,
                    current_tier=row.tier,
                    recommended_tier=new_tier,
                    trend=row.trend,
                    reason=f"Trending up — promote from {row.tier} to {new_tier}",
                )
            )
        elif row.trend == "down" and current_idx > 0:
            new_tier = tier_order[current_idx - 1]
            recommendations.append(
                TierRecommendation(
                    memory_id=row.id,
                    current_tier=row.tier,
                    recommended_tier=new_tier,
                    trend=row.trend,
                    reason=f"Trending down — demote from {row.tier} to {new_tier}",
                )
            )
    return recommendations


async def compute_budget_optimization(
    agent_id: str, db: AsyncConnection, budget_tokens: int
) -> BudgetOptimization:
    """Greedy submodular: sort by total_attribution / tokens, fill budget."""
    stmt = (
        select(
            memories.c.id,
            memories.c.tokens,
            func.coalesce(memory_profiles.c.total_attribution, 0.0).label("total_attribution"),
        )
        .outerjoin(memory_profiles, memories.c.id == memory_profiles.c.memory_id)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.archived_at.is_(None),
                memories.c.tokens > 0,
            )
        )
    )
    rows = (await db.execute(stmt)).fetchall()

    # Compute efficiency ratio and sort descending
    scored = []
    for row in rows:
        efficiency = row.total_attribution / row.tokens if row.tokens > 0 else 0.0
        scored.append((row.id, row.tokens, row.total_attribution, efficiency))
    scored.sort(key=lambda x: x[3], reverse=True)

    selected = []
    total_tokens = 0
    total_attr = 0.0
    for mem_id, tokens, attr, _ in scored:
        if total_tokens + tokens <= budget_tokens:
            selected.append(mem_id)
            total_tokens += tokens
            total_attr += attr

    return BudgetOptimization(
        budget_tokens=budget_tokens,
        selected_memory_ids=selected,
        total_tokens=total_tokens,
        total_attribution=total_attr,
        excluded_count=len(rows) - len(selected),
    )


async def get_lifecycle_recommendations(
    agent_id: str, db: AsyncConnection
) -> LifecycleRecommendations:
    """Aggregate all recommendations with estimated savings."""
    archive = await recommend_archive(agent_id, db)
    consolidate_exact = await recommend_consolidate(agent_id, db)
    consolidate_semantic = await recommend_semantic_consolidate(agent_id, db)
    consolidate = consolidate_exact + consolidate_semantic
    tier_changes = await recommend_tier_changes(agent_id, db)

    # Estimate monthly savings: sum of negative P&L from archive candidates
    # plus cost savings from consolidating duplicates
    archive_savings = sum(abs(r.cost) for r in archive)
    # Rough estimate: each duplicate costs ~same as original per month
    dup_count = sum(len(c.duplicate_memory_ids) for c in consolidate)
    consolidate_savings = dup_count * 0.001  # rough estimate

    return LifecycleRecommendations(
        agent_id=agent_id,
        archive=archive,
        consolidate=consolidate,
        tier_changes=tier_changes,
        estimated_monthly_savings=archive_savings + consolidate_savings,
    )


async def execute_archive(
    agent_id: str, memory_ids: list[str], db: AsyncConnection, executed_by: str = "system"
) -> int:
    """Archive memories and log lifecycle events."""
    now = datetime.now(UTC)
    count = 0
    for mid in memory_ids:
        await db.execute(
            update(memories)
            .where(and_(memories.c.id == mid, memories.c.agent_id == agent_id))
            .values(archived_at=now, archive_reason="negative_pnl")
        )
        await db.execute(
            insert(lifecycle_events).values(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                action="archive",
                memory_id=mid,
                details={"reason": "negative_pnl"},
                executed_by=executed_by,
                created_at=now,
            )
        )
        count += 1
    return count


async def execute_tier_changes(
    agent_id: str, changes: dict[str, str], db: AsyncConnection, executed_by: str = "system"
) -> int:
    """Apply tier changes and log lifecycle events."""
    now = datetime.now(UTC)
    count = 0
    for mid, new_tier in changes.items():
        # Get current tier
        row = (await db.execute(
            select(memories.c.tier).where(memories.c.id == mid)
        )).first()
        old_tier = row.tier if row else "unknown"

        await db.execute(
            update(memories)
            .where(and_(memories.c.id == mid, memories.c.agent_id == agent_id))
            .values(tier=new_tier)
        )
        await db.execute(
            insert(lifecycle_events).values(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                action="tier_change",
                memory_id=mid,
                details={"old_tier": old_tier, "new_tier": new_tier},
                executed_by=executed_by,
                created_at=now,
            )
        )
        count += 1
    return count


async def execute_consolidation(
    agent_id: str, groups: list[list[str]], db: AsyncConnection, executed_by: str = "system"
) -> int:
    """Soft-delete duplicate memories, keeping the canonical (first in each group)."""
    now = datetime.now(UTC)
    count = 0
    for group in groups:
        if len(group) < 2:
            continue
        canonical = group[0]
        duplicates = group[1:]
        for mid in duplicates:
            await db.execute(
                update(memories)
                .where(and_(memories.c.id == mid, memories.c.agent_id == agent_id))
                .values(deleted_at=now)
            )
            await db.execute(
                insert(lifecycle_events).values(
                    id=str(uuid.uuid4()),
                    agent_id=agent_id,
                    action="consolidate",
                    memory_id=mid,
                    details={"canonical_id": canonical, "method": "content_hash"},
                    executed_by=executed_by,
                    created_at=now,
                )
            )
            count += 1
    return count

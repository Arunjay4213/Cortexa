"""Composite Health Index & Staleness — §4.4, §4.5.

CHI(A, t) = w₁·Accuracy(A) + w₂·Freshness(A) + w₃·Coverage(A) + w₄·Consistency(A) + w₅·Efficiency(A)

where Σwᵢ = 1 and each component ∈ [0, 1].

Staleness(mᵢ, t) = 1 − exp(−λ · (t − t_last))
  λ is the decay constant; default half-life = 7 days → λ = ln(2)/7 ≈ 0.099
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from dataclasses import dataclass

import numpy as np


# ── Staleness ─────────────────────────────────────────────────────────

def staleness_score(
    last_accessed: datetime | None,
    now: datetime | None = None,
    half_life_days: float = 7.0,
) -> float:
    """Staleness(mᵢ, t) = 1 − exp(−λ · Δt).

    Returns value in [0, 1]. 0 = just accessed, 1 = completely stale.
    half_life_days controls decay rate. At t = half_life, staleness = 0.5.
    """
    if last_accessed is None:
        return 1.0  # never accessed = fully stale

    if now is None:
        now = datetime.now(UTC)

    # Handle timezone-naive datetimes
    if last_accessed.tzinfo is None:
        delta_seconds = (now.replace(tzinfo=None) - last_accessed).total_seconds()
    else:
        delta_seconds = (now - last_accessed).total_seconds()

    if delta_seconds <= 0:
        return 0.0

    delta_days = delta_seconds / 86400.0
    lambda_ = math.log(2) / half_life_days
    return 1.0 - math.exp(-lambda_ * delta_days)


def batch_staleness(
    last_accessed_times: list[datetime | None],
    now: datetime | None = None,
    half_life_days: float = 7.0,
) -> list[float]:
    """Compute staleness for a batch of memories."""
    if now is None:
        now = datetime.now(UTC)
    return [staleness_score(t, now, half_life_days) for t in last_accessed_times]


# ── Composite Health Index ────────────────────────────────────────────

@dataclass
class CHIWeights:
    """Weights for the 5 CHI components. Must sum to 1."""
    accuracy: float = 0.25
    freshness: float = 0.20
    coverage: float = 0.20
    consistency: float = 0.20
    efficiency: float = 0.15

    def __post_init__(self):
        total = self.accuracy + self.freshness + self.coverage + self.consistency + self.efficiency
        if abs(total - 1.0) > 1e-6:
            # Normalize
            self.accuracy /= total
            self.freshness /= total
            self.coverage /= total
            self.consistency /= total
            self.efficiency /= total


@dataclass
class CHIResult:
    """Result of CHI computation."""
    score: float                        # composite score ∈ [0, 1]
    accuracy_component: float           # attribution quality (mean EAS of retrieved memories)
    freshness_component: float          # 1 - mean staleness
    coverage_component: float | None    # query coverage rate (None if insufficient data)
    consistency_component: float        # 1 - contradiction rate
    efficiency_component: float         # 1 - waste rate
    weights: CHIWeights
    grade: str                          # A/B/C/D/F


def compute_chi(
    accuracy: float,
    freshness: float,
    coverage: float | None,
    consistency: float,
    efficiency: float,
    weights: CHIWeights | None = None,
) -> CHIResult:
    """Compute Composite Health Index.

    All inputs should be in [0, 1] where 1 is best.

    Args:
        accuracy: retrieval accuracy (e.g., mean attribution score)
        freshness: 1 - mean staleness score
        coverage: fraction of queries covered by memories (None if insufficient data)
        consistency: 1 - contradiction rate
        efficiency: 1 - token waste rate / 100

    If coverage is None (insufficient transaction data), uses 4-component mode
    with reweighted coefficients that still sum to 1.0.
    """
    if weights is None:
        weights = CHIWeights()

    # 4-component mode: redistribute coverage weight if None
    if coverage is None:
        # Redistribute coverage's 0.20 weight proportionally among other 4 components
        # Original: accuracy=0.25, freshness=0.20, consistency=0.20, efficiency=0.15
        # Total without coverage: 0.80
        # Scale factor: 1.0 / 0.80 = 1.25
        w_accuracy = weights.accuracy * 1.25
        w_freshness = weights.freshness * 1.25
        w_consistency = weights.consistency * 1.25
        w_efficiency = weights.efficiency * 1.25
        coverage_val = 0.0  # for display purposes
    else:
        # 5-component mode: use standard weights
        w_accuracy = weights.accuracy
        w_freshness = weights.freshness
        w_consistency = weights.consistency
        w_efficiency = weights.efficiency
        coverage_val = max(0.0, min(1.0, coverage))

    # Clamp inputs to [0, 1]
    accuracy = max(0.0, min(1.0, accuracy))
    freshness = max(0.0, min(1.0, freshness))
    consistency = max(0.0, min(1.0, consistency))
    efficiency = max(0.0, min(1.0, efficiency))

    if coverage is None:
        score = (
            w_accuracy * accuracy
            + w_freshness * freshness
            + w_consistency * consistency
            + w_efficiency * efficiency
        )
    else:
        score = (
            w_accuracy * accuracy
            + w_freshness * freshness
            + weights.coverage * coverage_val
            + w_consistency * consistency
            + w_efficiency * efficiency
        )

    # Grade
    if score >= 0.9:
        grade = "A"
    elif score >= 0.8:
        grade = "B"
    elif score >= 0.7:
        grade = "C"
    elif score >= 0.6:
        grade = "D"
    else:
        grade = "F"

    return CHIResult(
        score=round(score, 4),
        accuracy_component=round(accuracy, 4),
        freshness_component=round(freshness, 4),
        coverage_component=round(coverage_val, 4) if coverage is not None else None,
        consistency_component=round(consistency, 4),
        efficiency_component=round(efficiency, 4),
        weights=weights,
        grade=grade,
    )


async def compute_agent_chi(
    db,  # AsyncConnection
    agent_id: str,
    weights: CHIWeights | None = None,
) -> CHIResult:
    """Compute CHI for an agent by gathering all component metrics from DB.

    This is the high-level entry point that pulls together all health signals.
    """
    from sqlalchemy import select, func, and_
    from cortex.db.tables import (
        memories, memory_profiles, contradictions, transactions,
    )
    from cortex.metrics.calculator import token_waste_rate as calc_waste

    # 1. Attribution quality: mean attribution score across RETRIEVED memories.
    # Only counts memories that have been used (retrieval_count > 0) —
    # unused memories shouldn't drag down the score.
    attr_stmt = (
        select(func.avg(memory_profiles.c.mean_attribution))
        .select_from(
            memory_profiles.join(
                memories,
                memory_profiles.c.memory_id == memories.c.id,
            )
        )
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memory_profiles.c.retrieval_count > 0,
            )
        )
    )
    accuracy_raw = (await db.execute(attr_stmt)).scalar() or 0.0
    accuracy = min(1.0, float(accuracy_raw))

    # 2. Freshness: 1 - mean staleness
    mem_stmt = (
        select(memories.c.last_accessed)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
            )
        )
    )
    mem_rows = (await db.execute(mem_stmt)).fetchall()
    if mem_rows:
        staleness_values = batch_staleness([r.last_accessed for r in mem_rows])
        freshness = 1.0 - (sum(staleness_values) / len(staleness_values))
    else:
        freshness = 0.0

    # 3. Coverage: compute from query-memory similarity
    # Requires at least 10 transactions for meaningful coverage analysis
    from cortex.attribution.coverage import compute_coverage

    # Count recent transactions
    txn_count_stmt = (
        select(func.count())
        .select_from(transactions)
        .where(
            and_(
                transactions.c.agent_id == agent_id,
                transactions.c.query_embedding.isnot(None),
            )
        )
    )
    txn_count = (await db.execute(txn_count_stmt)).scalar() or 0

    if txn_count >= 10:
        # Sufficient data: compute real coverage
        cov_result = await compute_coverage(db, agent_id, query_limit=100)
        coverage = cov_result["coverage_rate"]
    else:
        # Insufficient data: use 4-component mode
        coverage = None

    # 4. Consistency: 1 - contradiction rate
    total_mems = (
        await db.execute(
            select(func.count())
            .select_from(memories)
            .where(
                and_(
                    memories.c.agent_id == agent_id,
                    memories.c.deleted_at.is_(None),
                )
            )
        )
    ).scalar() or 0

    contradiction_count = (
        await db.execute(
            select(func.count())
            .select_from(contradictions)
            .where(contradictions.c.resolved == False)
        )
    ).scalar() or 0

    if total_mems > 0:
        contradiction_rate = min(1.0, contradiction_count / total_mems)
        consistency = 1.0 - contradiction_rate
    else:
        consistency = 1.0

    # 5. Efficiency: 1 - waste_rate/100
    # Get recent attribution scores and token counts
    from cortex.db.tables import attribution_scores
    attr_rows = (
        await db.execute(
            select(attribution_scores.c.score, attribution_scores.c.memory_id)
            .where(attribution_scores.c.memory_id.in_(
                select(memories.c.id).where(
                    and_(
                        memories.c.agent_id == agent_id,
                        memories.c.deleted_at.is_(None),
                    )
                )
            ))
        )
    ).fetchall()

    if attr_rows:
        scores = [r.score for r in attr_rows]
        # Get token counts for corresponding memories
        mem_tokens = (
            await db.execute(
                select(memories.c.id, memories.c.tokens)
                .where(
                    and_(
                        memories.c.agent_id == agent_id,
                        memories.c.deleted_at.is_(None),
                    )
                )
            )
        ).fetchall()
        token_map = {r.id: r.tokens for r in mem_tokens}
        token_counts = [token_map.get(r.memory_id, 0) for r in attr_rows]
        waste = calc_waste(scores, token_counts)
        efficiency = 1.0 - (waste / 100.0)
    else:
        efficiency = 0.5

    return compute_chi(accuracy, freshness, coverage, consistency, efficiency, weights)

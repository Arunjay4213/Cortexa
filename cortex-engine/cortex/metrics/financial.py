"""Financial Metrics — §7.1 Sharpe Ratio, §7.2 Portfolio ROI.

Memory Sharpe Ratio: risk-adjusted return for individual memories.
  SR(mᵢ) = (E[Rᵢ] − Rf) / σ(Rᵢ)
  where Rᵢ = per-retrieval attribution, Rf = risk-free rate (minimum useful attribution)

Portfolio ROI: aggregate return across a memory portfolio (agent's full memory set).
  ROI(A) = Σᵢ wᵢ · ROIᵢ  where wᵢ = tokensᵢ / Σⱼ tokensⱼ
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class MemorySharpeRatio:
    """Sharpe ratio for a single memory."""
    memory_id: str
    sharpe_ratio: float
    mean_return: float         # E[Rᵢ]
    std_return: float          # σ(Rᵢ)
    risk_free_rate: float      # Rf
    num_observations: int
    interpretation: str        # "excellent" | "good" | "average" | "poor"


@dataclass
class PortfolioROI:
    """Aggregate ROI for an agent's memory portfolio."""
    agent_id: str
    total_roi: float
    weighted_roi: float        # token-weighted ROI
    total_revenue: float
    total_cost: float
    memory_count: int
    top_performers: list[dict]    # best ROI memories
    bottom_performers: list[dict] # worst ROI memories
    diversification_score: float  # 1 - Gini of attribution distribution


def compute_sharpe_ratio(
    memory_id: str,
    attribution_scores: list[float],
    risk_free_rate: float = 0.01,
) -> MemorySharpeRatio:
    """Compute Memory Sharpe Ratio.

    SR(mᵢ) = (E[Rᵢ] − Rf) / σ(Rᵢ)

    Args:
        memory_id: the memory identifier
        attribution_scores: per-retrieval attribution scores (returns)
        risk_free_rate: minimum useful attribution threshold
    """
    if not attribution_scores or len(attribution_scores) < 2:
        return MemorySharpeRatio(
            memory_id=memory_id,
            sharpe_ratio=0.0,
            mean_return=0.0,
            std_return=0.0,
            risk_free_rate=risk_free_rate,
            num_observations=len(attribution_scores),
            interpretation="insufficient_data",
        )

    returns = np.array(attribution_scores)
    mean_return = float(returns.mean())
    std_return = float(returns.std(ddof=1))  # sample std

    if std_return < 1e-10:
        # Zero volatility — if mean > rf, infinite sharpe (cap at 10)
        sr = 10.0 if mean_return > risk_free_rate else 0.0
    else:
        sr = (mean_return - risk_free_rate) / std_return

    # Interpretation
    if sr >= 3.0:
        interpretation = "excellent"
    elif sr >= 1.5:
        interpretation = "good"
    elif sr >= 0.5:
        interpretation = "average"
    else:
        interpretation = "poor"

    return MemorySharpeRatio(
        memory_id=memory_id,
        sharpe_ratio=round(sr, 4),
        mean_return=round(mean_return, 6),
        std_return=round(std_return, 6),
        risk_free_rate=risk_free_rate,
        num_observations=len(attribution_scores),
        interpretation=interpretation,
    )


def compute_portfolio_roi(
    agent_id: str,
    memory_data: list[dict],
) -> PortfolioROI:
    """Compute aggregate Portfolio ROI for an agent.

    ROI(A) = Σᵢ wᵢ · ROIᵢ  where wᵢ = tokensᵢ / Σⱼ tokensⱼ

    Args:
        agent_id: the agent identifier
        memory_data: list of dicts with keys:
            - memory_id: str
            - revenue: float (total attribution value)
            - cost: float (total token cost)
            - tokens: int (memory token count)
            - roi: float (individual ROI)
    """
    if not memory_data:
        return PortfolioROI(
            agent_id=agent_id,
            total_roi=0.0,
            weighted_roi=0.0,
            total_revenue=0.0,
            total_cost=0.0,
            memory_count=0,
            top_performers=[],
            bottom_performers=[],
            diversification_score=0.0,
        )

    total_tokens = sum(m.get("tokens", 0) for m in memory_data)
    total_revenue = sum(m.get("revenue", 0.0) for m in memory_data)
    total_cost = sum(m.get("cost", 0.0) for m in memory_data)

    # Total ROI
    total_roi = (total_revenue - total_cost) / total_cost if total_cost > 0 else 0.0

    # Token-weighted ROI
    if total_tokens > 0:
        weighted_roi = sum(
            (m.get("tokens", 0) / total_tokens) * m.get("roi", 0.0)
            for m in memory_data
        )
    else:
        weighted_roi = 0.0

    # Sort by ROI for top/bottom performers
    sorted_data = sorted(memory_data, key=lambda m: m.get("roi", 0.0), reverse=True)

    top_performers = [
        {"memory_id": m["memory_id"], "roi": round(m.get("roi", 0.0), 4)}
        for m in sorted_data[:5]
    ]
    bottom_performers = [
        {"memory_id": m["memory_id"], "roi": round(m.get("roi", 0.0), 4)}
        for m in sorted_data[-5:]
    ]

    # Diversification score (1 - Gini of revenue distribution)
    revenues = np.array([m.get("revenue", 0.0) for m in memory_data])
    if revenues.sum() > 0:
        from cortex.metrics.calculator import gini_coefficient
        gini = gini_coefficient(revenues)
        diversification = 1.0 - gini
    else:
        diversification = 0.0

    return PortfolioROI(
        agent_id=agent_id,
        total_roi=round(total_roi, 4),
        weighted_roi=round(weighted_roi, 4),
        total_revenue=round(total_revenue, 6),
        total_cost=round(total_cost, 6),
        memory_count=len(memory_data),
        top_performers=top_performers,
        bottom_performers=bottom_performers,
        diversification_score=round(diversification, 4),
    )


async def compute_agent_portfolio(
    db,  # AsyncConnection
    agent_id: str,
) -> PortfolioROI:
    """Compute portfolio ROI from database for an agent."""
    from sqlalchemy import select, func, and_
    from cortex.db.tables import memories, memory_profiles
    from cortex.metrics.calculator import memory_pnl
    from cortex.models import TokenCostConfig

    # Get per-agent cost config
    from cortex.attribution.lifecycle import _get_cost_config
    config = await _get_cost_config(agent_id, db)

    stmt = (
        select(
            memories.c.id,
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

    memory_data = []
    for row in rows:
        pnl = memory_pnl(
            memory_id=row.id,
            total_attribution=row.total_attribution,
            retrieval_count=row.retrieval_count,
            tokens=row.tokens,
            config=config,
        )
        memory_data.append({
            "memory_id": row.id,
            "revenue": pnl.revenue,
            "cost": pnl.cost,
            "tokens": row.tokens,
            "roi": pnl.roi,
        })

    return compute_portfolio_roi(agent_id, memory_data)

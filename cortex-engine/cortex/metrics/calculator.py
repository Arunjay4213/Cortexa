"""
CortexOS Metrics Calculator — ported from calculator.ts.

Bloomberg Terminal-style metrics:
  - Token Economics ($)
  - Accuracy Impact (%)
  - Risk Exposure (!)
"""

from __future__ import annotations

import math

import numpy as np

from cortex.models import TokenCostConfig, TransactionCost, MemoryPnL


# ── Token Economics ────────────────────────────────────────────────────

def transaction_cost(
    input_tokens: int,
    output_tokens: int,
    config: TokenCostConfig,
    transaction_id: str = "",
) -> TransactionCost:
    """Cost(ξ) = π_in · |C| + π_out · |r|"""
    ic = input_tokens * config.input_token_cost
    oc = output_tokens * config.output_token_cost
    return TransactionCost(
        transaction_id=transaction_id,
        input_cost=ic,
        output_cost=oc,
        total_cost=ic + oc,
    )


def memory_pnl(
    memory_id: str,
    total_attribution: float,
    retrieval_count: int,
    tokens: int,
    config: TokenCostConfig,
) -> MemoryPnL:
    """Revenue − Cost per memory.

    Revenue ≈ total attribution (proxy for value delivered).
    Cost ≈ tokens × input price × retrieval count.
    """
    revenue = total_attribution
    cost = tokens * config.input_token_cost * retrieval_count
    pnl = revenue - cost
    roi = (revenue / cost) if cost > 0 else 0.0
    return MemoryPnL(memory_id=memory_id, revenue=revenue, cost=cost, pnl=pnl, roi=roi)


# ── Gini Coefficient ──────────────────────────────────────────────────

def gini_coefficient(scores: list[float] | np.ndarray) -> float:
    """Attribution concentration — 0 = perfectly equal, 1 = one memory dominates."""
    arr = np.asarray(scores, dtype=np.float64)
    if arr.size == 0:
        return 0.0
    n = arr.size
    mean = arr.mean()
    if mean == 0:
        return 0.0
    sorted_arr = np.sort(arr)
    # G = Σᵢ Σⱼ |xᵢ − xⱼ| / (2n²μ)
    diffs = np.abs(sorted_arr[:, None] - sorted_arr[None, :]).sum()
    return float(diffs / (2 * n * n * mean))


# ── Signal-to-Noise Ratio ─────────────────────────────────────────────

def snr_db(scores: list[float] | np.ndarray) -> float:
    """Memory SNR in decibels.

    signal = Σ(sᵢ² for sᵢ > 0)
    noise  = Σ(sᵢ² for sᵢ ≤ 0) + ε
    SNR_dB = 10·log₁₀(signal / noise)
    """
    arr = np.asarray(scores, dtype=np.float64)
    if arr.size == 0:
        return 0.0
    signal = (arr[arr > 0] ** 2).sum()
    noise = (arr[arr <= 0] ** 2).sum() + 1e-10
    return float(10 * math.log10(signal / noise))


# ── Token Waste Rate ──────────────────────────────────────────────────

def token_waste_rate(
    scores: list[float],
    token_counts: list[int],
    threshold: float = 0.01,
) -> float:
    """% of tokens with near-zero attribution (|aᵢ| < threshold)."""
    if not scores or not token_counts:
        return 0.0
    total_tokens = 0
    wasted_tokens = 0
    for s, t in zip(scores, token_counts):
        total_tokens += t
        if abs(s) < threshold:
            wasted_tokens += t
    return (wasted_tokens / total_tokens * 100) if total_tokens > 0 else 0.0


# ── Contradiction Risk ────────────────────────────────────────────────

def contradiction_risk(probabilities: list[float]) -> float:
    """CRS = 1 − Π(1 − pᵢⱼ)"""
    if not probabilities:
        return 0.0
    product = 1.0
    for p in probabilities:
        product *= 1.0 - p
    return 1.0 - product

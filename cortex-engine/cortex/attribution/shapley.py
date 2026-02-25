"""
Exact Shapley computation for CAMA.

Because CAMA's support sets per claim are small (typically 1-5 memories after
the similarity gate + NLI filter), we compute exact Shapley values by
enumerating all 2^|S| subsets. No approximation needed.

Three value functions routed by claim type:
  - factual     → v_max:      v(S) = max(scores in S)
  - synthesis   → v_noisy_or: v(S) = 1 - Π(1 - sᵢ) for sᵢ in S
  - aggregation → v_additive: v(S) = min(1, Σ sᵢ)
"""

from __future__ import annotations

import math
from itertools import combinations


# ── Value functions ──────────────────────────────────────────────────────────

def v_max(scores: list[float]) -> float:
    """Factual claims: best single memory wins."""
    return max(scores) if scores else 0.0


def v_noisy_or(scores: list[float]) -> float:
    """Synthesis claims: each memory independently contributes.

    P(supported) = 1 - Π(1 - sᵢ)
    """
    if not scores:
        return 0.0
    p = 1.0
    for s in scores:
        p *= (1.0 - s)
    return 1.0 - p


def v_additive(scores: list[float]) -> float:
    """Aggregation claims: linear sum capped at 1."""
    return min(1.0, sum(scores)) if scores else 0.0


# ── Claim type → value function routing ──────────────────────────────────────

_CLAIM_TYPE_TO_VFN = {
    "factual": v_max,
    "synthesis": v_noisy_or,
    "aggregation": v_additive,
    "opinion": v_max,  # treat opinions same as factual
}


def _get_value_fn(claim_type: str):
    """Return the value function for a claim type."""
    return _CLAIM_TYPE_TO_VFN.get(claim_type, v_max)


# ── Exact Shapley ────────────────────────────────────────────────────────────

def exact_shapley(
    support_set: list[tuple[str, float]],
    value_fn,
) -> dict[str, float]:
    """Exact Shapley values over a small support set (|S| <= ~15).

    φᵢ = Σ_{S ⊆ N\\{i}} [|S|!(n-|S|-1)! / n!] × [v(S ∪ {i}) - v(S)]

    Args:
        support_set: list of (memory_id, entailment_score)
        value_fn: coalition scores → float (v_max, v_noisy_or, or v_additive)

    Returns:
        memory_id → Shapley value (normalized to sum to 1.0)
    """
    n = len(support_set)
    if n == 0:
        return {}
    if n == 1:
        return {support_set[0][0]: 1.0}

    ids = [m_id for m_id, _ in support_set]
    scores = [s for _, s in support_set]
    shapley = [0.0] * n

    for i in range(n):
        others = [j for j in range(n) if j != i]
        for size in range(len(others) + 1):
            for combo in combinations(others, size):
                S = list(combo)
                S_with_i = S + [i]
                v_with = value_fn([scores[j] for j in S_with_i])
                v_without = value_fn([scores[j] for j in S]) if S else 0.0
                weight = math.factorial(len(S)) * math.factorial(n - len(S) - 1) / math.factorial(n)
                shapley[i] += weight * (v_with - v_without)

    # Normalize
    total = sum(shapley)
    if total > 1e-8:
        shapley = [sv / total for sv in shapley]

    return dict(zip(ids, shapley))


def compute_shapley(
    entailment_scores: dict[str, float],
    value_fn: str = "weighted",
    threshold: float = 0.5,
    claim_type: str = "factual",
) -> dict[str, float]:
    """Dispatch to exact Shapley with the appropriate value function.

    Args:
        entailment_scores: memory_id → entailment probability
        value_fn: legacy param — ignored if claim_type is set
        threshold: not used (kept for API compat)
        claim_type: "factual", "synthesis", or "aggregation" — determines value function

    Returns:
        memory_id → Shapley value (normalized)
    """
    if not entailment_scores:
        return {}

    # Build support set
    support_set = [(mid, score) for mid, score in entailment_scores.items()]

    # Route value function based on claim type
    vfn = _get_value_fn(claim_type)

    return exact_shapley(support_set, vfn)

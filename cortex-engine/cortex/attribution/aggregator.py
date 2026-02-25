"""
CAMA aggregator — claim-level Shapley values → memory-level attribution scores.

Takes per-claim Shapley values and aggregates them into final memory scores:
  1. Sum each memory's Shapley values across all claims
  2. Normalize so scores sum to 1.0
  3. Classify claims as essential/redundant/unsupported
  4. Flag hallucinated claims
  5. Identify dead memories
"""

from __future__ import annotations

from cortex.attribution.types import (
    CAMAResult,
    ClaimAnalysis,
    ClaimSource,
    LatencyBreakdown,
    UnsupportedClaim,
)


def classify_support(
    sources: list[ClaimSource],
    entailment_threshold: float = 0.5,
) -> str:
    """Classify a claim's support type based on its sources.

    - "essential": exactly one supporting memory (removing it loses the claim)
    - "redundant": multiple supporting memories (can lose one and still be supported)
    - "unsupported": no memory entails the claim above threshold
    """
    supporting = [s for s in sources if s.entailment >= entailment_threshold]
    if len(supporting) == 0:
        return "unsupported"
    elif len(supporting) == 1:
        return "essential"
    else:
        return "redundant"


def aggregate(
    claims: list[str],
    claim_types: list[str],
    entailment_scores: list[dict[str, float]],
    shapley_values: list[dict[str, float]],
    all_memory_ids: list[str],
    dead_memories: list[str],
    entailment_threshold: float = 0.5,
    hallucination_threshold: float = 0.5,
    latency: LatencyBreakdown | None = None,
    num_nli_calls: int = 0,
    hallucination_reasons: dict[int, str] | None = None,
) -> CAMAResult:
    """Aggregate claim-level analysis into a complete CAMA result.

    Args:
        claims: list of claim strings
        claim_types: list of claim_type per claim ("factual"/"synthesis"/"opinion")
        entailment_scores: per-claim {memory_id: entailment_prob}
        shapley_values: per-claim {memory_id: shapley_value}
        all_memory_ids: complete list of memory IDs that were retrieved
        dead_memories: memory IDs that never passed the similarity gate
        entailment_threshold: threshold to count as "supporting"
        hallucination_threshold: claims below this are hallucinated
        latency: timing breakdown
        num_nli_calls: total NLI inference count

    Returns:
        Complete CAMAResult
    """
    num_claims = len(claims)
    claim_analyses: list[ClaimAnalysis] = []
    unsupported: list[UnsupportedClaim] = []

    # Per-memory raw attribution (sum of Shapley values across claims)
    memory_raw_scores: dict[str, float] = {mid: 0.0 for mid in all_memory_ids}

    hallucination_count = 0
    verifiable_count = 0  # only factual/synthesis/aggregation count for index

    for i in range(num_claims):
        claim_text = claims[i]
        claim_type = claim_types[i] if i < len(claim_types) else "factual"
        ent_scores = entailment_scores[i] if i < len(entailment_scores) else {}
        shap_values = shapley_values[i] if i < len(shapley_values) else {}

        # Build sources list
        sources: list[ClaimSource] = []
        for mem_id, shap_val in shap_values.items():
            ent_val = ent_scores.get(mem_id, 0.0)
            if ent_val >= entailment_threshold:
                sources.append(ClaimSource(
                    memory_id=mem_id,
                    shapley_value=shap_val,
                    entailment=ent_val,
                ))

        # Best entailment across all candidates (not just those above threshold)
        best_ent = max(ent_scores.values()) if ent_scores else 0.0

        # Classify support type
        support_type = classify_support(sources, entailment_threshold)

        # Opinion claims are subjective — cannot be hallucinated in the
        # factual sense, so skip them for hallucination scoring.
        is_opinion = claim_type == "opinion"

        # Is hallucinated? (only applies to verifiable claims)
        _reasons = hallucination_reasons or {}
        is_hallucination = False
        reason = ""

        if is_opinion:
            # Opinions are not verifiable — mark but don't count
            reason = "opinion_skip"
        elif i in _reasons:
            is_hallucination = True
            reason = _reasons[i]
        elif best_ent < hallucination_threshold:
            is_hallucination = True
            if not ent_scores:
                reason = "nli_empty"
            else:
                reason = "nli_low"

        # Only count verifiable claims toward the index
        if not is_opinion:
            verifiable_count += 1

        if is_hallucination:
            hallucination_count += 1
            unsupported.append(UnsupportedClaim(
                claim=claim_text,
                best_entailment=best_ent,
            ))

        claim_analyses.append(ClaimAnalysis(
            claim=claim_text,
            claim_type=claim_type,
            support_type=support_type,
            sources=sources,
            best_entailment=best_ent,
            is_hallucination=is_hallucination,
            hallucination_reason=reason,
        ))

        # Accumulate Shapley values into memory scores
        # Only count supported sources (above entailment threshold)
        for source in sources:
            memory_raw_scores[source.memory_id] += source.shapley_value

    # Normalize scores to sum to 1.0
    total = sum(memory_raw_scores.values())
    if total > 1e-8:
        scores = {mid: val / total for mid, val in memory_raw_scores.items()}
    else:
        # No memory contributed — uniform zero
        scores = {mid: 0.0 for mid in all_memory_ids}

    # Hallucination index — only count verifiable (non-opinion) claims
    hallucination_index = hallucination_count / verifiable_count if verifiable_count > 0 else 0.0

    return CAMAResult(
        scores=scores,
        claims=claim_analyses,
        unsupported_claims=unsupported,
        hallucination_index=round(hallucination_index, 3),
        dead_memories=dead_memories,
        method="cama",
        num_claims=num_claims,
        num_nli_calls=num_nli_calls,
        latency_ms=latency or LatencyBreakdown(),
    )

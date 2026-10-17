"""Shapley-based MAS computation — Tier 4 of the CAMA pipeline.

Uses entailment-based approximation instead of full permutation sampling:
  MAS(m, c) = softmax(entailment(m, c) / τ) across all memories
  Final MAS = weighted average across claims.
"""

import math

from cortexa.engine.models import Attribution, Claim, EntailmentScore, Memory


def _softmax_with_temperature(
    values: list[float], temperature: float = 0.5
) -> list[float]:
    """Compute softmax with temperature scaling."""
    if not values:
        return []
    scaled = [v / temperature for v in values]
    max_val = max(scaled)
    exp_vals = [math.exp(v - max_val) for v in scaled]
    total = sum(exp_vals)
    if total == 0:
        return [1.0 / len(values)] * len(values)
    return [v / total for v in exp_vals]


class AttributionComputer:
    """Computes MAS (Memory Attribution Scores) using normalized entailment."""

    def __init__(self, temperature: float = 0.5, ghost_threshold: float = 0.05) -> None:
        self.temperature = temperature
        self.ghost_threshold = ghost_threshold

    def compute(
        self,
        claims: list[Claim],
        memories: list[Memory],
        entailments: list[EntailmentScore],
    ) -> list[Attribution]:
        """Compute MAS for all (memory, claim) pairs.

        Algorithm:
        1. For each claim, gather entailment scores from all memories
        2. Apply softmax with temperature to get normalized MAS per claim
        3. Classify contribution type based on scores
        """
        # Index entailment scores by (memory_id, claim_id)
        ent_map: dict[tuple[str, str], EntailmentScore] = {}
        for es in entailments:
            ent_map[(es.memory_id, es.claim_id)] = es

        attributions: list[Attribution] = []

        for claim in claims:
            # Gather entailment scores for this claim across all memories
            mem_entailments: list[tuple[Memory, float, EntailmentScore]] = []
            for memory in memories:
                key = (memory.id, claim.id)
                if key in ent_map:
                    es = ent_map[key]
                    mem_entailments.append((memory, es.entailment, es))
                else:
                    # No entailment computed — treat as neutral
                    mem_entailments.append((memory, 0.0, None))

            # Compute softmax-normalized MAS for this claim
            raw_scores = [e for _, e, _ in mem_entailments]
            mas_scores = _softmax_with_temperature(raw_scores, self.temperature)

            for (memory, _, es), mas in zip(mem_entailments, mas_scores):
                # Determine contribution type
                if es is not None and es.label == "contradiction":
                    ctype = "contradicting"
                elif mas < self.ghost_threshold:
                    ctype = "ghost"
                elif es is not None and es.entailment > 0.5:
                    ctype = "supporting"
                else:
                    ctype = "neutral"

                attributions.append(
                    Attribution(
                        claim_id=claim.id,
                        memory_id=memory.id,
                        mas_score=round(mas, 4),
                        entailment_score=round(es.entailment if es else 0.0, 4),
                        numerical_match=None,  # filled in by scorer
                        contribution_type=ctype,
                    )
                )

        return attributions

    def aggregate_mas(
        self, attributions: list[Attribution], memory_id: str
    ) -> float:
        """Compute aggregate MAS for a memory across all claims."""
        scores = [a.mas_score for a in attributions if a.memory_id == memory_id]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

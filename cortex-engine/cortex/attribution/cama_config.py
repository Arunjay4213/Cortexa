"""
CAMA configuration — all thresholds and tunables for the CAMA pipeline.

Named cama_config to avoid collision with the top-level cortex.config module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CAMAConfig:
    """All CAMA thresholds in one place."""

    # Similarity gate: minimum cosine similarity for a memory to be a candidate
    # for NLI against a claim. Below this, the memory is skipped (saves NLI calls).
    similarity_threshold: float = 0.3

    # NLI entailment: minimum entailment probability to count as "supports"
    entailment_threshold: float = 0.5

    # Hallucination: a claim is hallucinated if its best entailment is below this
    hallucination_threshold: float = 0.5

    # Maximum number of memories to pass through the gate per claim
    # (limits NLI calls to at most max_candidates_per_claim per claim)
    max_candidates_per_claim: int = 5

    # DeBERTa model name for NLI
    nli_model: str = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"

    # Claim decomposition: maximum claims to extract from a response
    max_claims: int = 20

    # Shapley value function to use: "binary" | "weighted" | "marginal"
    shapley_value_fn: str = "weighted"


# Module-level default instance
DEFAULT_CONFIG = CAMAConfig()

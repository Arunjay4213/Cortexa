"""
CAMA type definitions — Claim-Aware Memory Attribution.

All dataclasses used across the CAMA pipeline:
  decompose → gate → entail → shapley → aggregate
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClaimSource:
    """A single memory's contribution to a claim."""
    memory_id: str
    shapley_value: float
    entailment: float  # NLI entailment probability


@dataclass
class ClaimAnalysis:
    """Full analysis of a single claim extracted from the response."""
    claim: str
    claim_type: str  # "factual" | "synthesis" | "opinion"
    support_type: str  # "essential" | "redundant" | "unsupported"
    sources: list[ClaimSource] = field(default_factory=list)
    best_entailment: float = 0.0
    is_hallucination: bool = False
    hallucination_reason: str = ""  # "" | "numerical_ungrounded" | "nli_empty" | "nli_low"


@dataclass
class LatencyBreakdown:
    """Per-stage latency in milliseconds."""
    decompose_ms: float = 0.0
    gate_ms: float = 0.0
    entail_ms: float = 0.0
    shapley_ms: float = 0.0
    aggregate_ms: float = 0.0


@dataclass
class UnsupportedClaim:
    """A claim with no sufficient memory support."""
    claim: str
    best_entailment: float


@dataclass
class CAMAResult:
    """Complete CAMA attribution result."""
    scores: dict[str, float]  # memory_id → normalized attribution score
    claims: list[ClaimAnalysis]
    unsupported_claims: list[UnsupportedClaim]
    hallucination_index: float  # fraction of claims that are hallucinated
    dead_memories: list[str]  # memory_ids that never passed similarity gate
    method: str = "cama"
    num_claims: int = 0
    num_nli_calls: int = 0
    latency_ms: LatencyBreakdown = field(default_factory=LatencyBreakdown)

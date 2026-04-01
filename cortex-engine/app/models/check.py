from enum import Enum

from pydantic import BaseModel


class ClaimVerdict(str, Enum):
    GROUNDED = "GROUNDED"
    NUM_MISMATCH = "NUM_MISMATCH"
    UNSUPPORTED = "UNSUPPORTED"
    OPINION = "OPINION"


class Claim(BaseModel):
    text: str
    grounded: bool
    verdict: ClaimVerdict
    reason: str = ""
    source_quote: str | None = None
    confidence: float = 1.0

    # Populated only when config.attribution = True
    attribution: list[dict] | None = None
    primary_source_index: int | None = None


class CheckConfig(BaseModel):
    attribution: bool = False  # enable leave-one-out Shapley
    attribution_threshold: float = 0.05  # min abs(influence) to report
    max_attribution_sources: int = 10  # cap sources for attribution


class CheckRequest(BaseModel):
    response: str  # The agent's response to verify
    sources: list[str]  # The ground truth documents/memories
    agent_id: str | None = None  # Which agent produced this response
    config: CheckConfig | None = None  # Optional overrides


class CheckResponse(BaseModel):
    hallucination_index: float  # 0.0 (perfect) to 1.0 (all hallucinated)
    total_claims: int
    grounded_count: int
    hallucinated_count: int
    opinion_count: int
    claims: list[Claim]
    latency_ms: float
    attribution_calls: int | None = None  # total NLI calls for attribution
    attribution_latency_ms: float | None = None  # time spent on attribution

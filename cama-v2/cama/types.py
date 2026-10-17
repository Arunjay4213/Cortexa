"""Pydantic data models for CAMA v2 pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Memory(BaseModel):
    """A single memory unit provided as context to the LLM."""

    id: str
    content: str
    source: str | None = None
    source_updated_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)


class TokenScore(BaseModel):
    """Per-token hallucination probability."""

    token: str
    index: int
    hallucination_prob: float


class HallucinatedSpan(BaseModel):
    """A contiguous span of hallucinated tokens in the response."""

    text: str
    start_char: int
    end_char: int
    score: float  # avg hallucination prob across span tokens
    token_scores: list[TokenScore]


class MemoryAttribution(BaseModel):
    """Attribution of a single memory to a hallucinated span."""

    memory_id: str
    mas: float  # Memory Attribution Score [0, 1], normalized
    delta: float  # Raw LOO delta (signed)
    direction: str  # "supporting", "causing", "ghost"
    neutral_score: float = 0.0  # NLI neutral probability (used for ghost confirmation)
    raw_contradiction: float = 0.0  # Raw NLI contradiction score (unnormalized)
    raw_entailment: float = 0.0  # Raw NLI entailment score (unnormalized)


class SpanAttribution(BaseModel):
    """Full attribution for one hallucinated span."""

    span: HallucinatedSpan
    attributions: list[MemoryAttribution]  # sorted by |delta| descending
    diagnosis: str  # "stale_memory", "wrong_memory", "contradiction", "fabricated", "supported"
    culprit_memory_id: str | None


class Contradiction(BaseModel):
    """A pair of memories that contradict each other."""

    memory_id_1: str
    memory_id_2: str
    explanation: str
    span_text: str | None = None


class TraceResult(BaseModel):
    """Full output of the CAMA v2 pipeline."""

    query: str
    response: str
    memories_used: list[str]
    hallucinated_spans: list[HallucinatedSpan]
    span_attributions: list[SpanAttribution]
    ghost_memories: list[str]
    contradictions: list[Contradiction]
    stale_memories: list[str]
    health_score: float
    hallucination_rate: float  # fraction of response tokens flagged
    latency_ms: float
    detection_method: str  # "LettuceDetector" or "EmbeddingDetector"
    attribution_method: str  # "LOODetectorAttributor" or "LOOEmbeddingAttributor"
    memory_health: list[dict] | None = None  # Per-memory health report (optional)

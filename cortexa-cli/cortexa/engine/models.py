"""Pydantic data models for the CAMA pipeline."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Memory(BaseModel):
    """A single memory from the agent's memory store."""

    id: str = Field(default_factory=_new_id)
    content: str
    source: str | None = None
    source_updated_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime | None = None
    access_count: int = 0
    embedding: list[float] | None = None
    metadata: dict = Field(default_factory=dict)


class Claim(BaseModel):
    """An atomic, verifiable claim extracted from an LLM response."""

    id: str = Field(default_factory=_new_id)
    text: str
    source_response: str
    claim_type: Literal["factual", "numerical", "temporal", "relational", "opinion"] = "factual"


class NumericalMatch(BaseModel):
    """Result of comparing a number in a claim against a number in a memory."""

    claim_id: str
    memory_id: str
    claim_value: float
    memory_value: float
    match_type: Literal["exact", "approximate", "contradiction", "unverified"]
    tolerance: float = 0.05


class NumericalResult(BaseModel):
    """Output of the numerical gate for a set of claims and memories."""

    matches: list[NumericalMatch] = Field(default_factory=list)
    contradictions: list[NumericalMatch] = Field(default_factory=list)
    unverified: list[str] = Field(default_factory=list)  # claim IDs with numbers but no match


class EntailmentScore(BaseModel):
    """NLI entailment result for a single (memory, claim) pair."""

    memory_id: str
    claim_id: str
    entailment: float  # P(entailment) [0, 1]
    contradiction: float  # P(contradiction) [0, 1]
    neutral: float  # P(neutral) [0, 1]
    label: Literal["entailment", "contradiction", "neutral"]
    confidence: float  # max(entailment, contradiction, neutral)


class Attribution(BaseModel):
    """Memory attribution for a specific claim."""

    claim_id: str
    memory_id: str
    mas_score: float = Field(ge=0.0, le=1.0)  # Memory Attribution Score
    entailment_score: float = Field(ge=0.0, le=1.0)
    numerical_match: bool | None = None
    contribution_type: Literal["supporting", "contradicting", "neutral", "ghost"]


class Contradiction(BaseModel):
    """A detected contradiction between two memories."""

    memory_id_1: str
    memory_id_2: str
    claim_id: str | None = None
    explanation: str
    severity: float = Field(ge=0.0, le=1.0)


class GhostToken(BaseModel):
    """A memory identified as a ghost token (wastes context, no attribution)."""

    memory_id: str
    max_mas: float  # highest MAS across all claims
    waste_tokens: int  # estimated token count of this memory
    reason: str


class StaleMemory(BaseModel):
    """A memory flagged as potentially stale."""

    memory_id: str
    created_at: datetime
    source_updated_at: datetime | None
    days_since_update: int
    similarity_to_source: float | None = None  # cosine similarity if computable
    reason: str


class TraceResult(BaseModel):
    """Full result of tracing a query-response pair through the CAMA pipeline."""

    trace_id: str = Field(default_factory=_new_id)
    query: str
    response: str
    claims: list[Claim]
    attributions: list[Attribution]
    ghost_tokens: list[GhostToken] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    stale_memories: list[StaleMemory] = Field(default_factory=list)
    health_score: float = Field(ge=0.0, le=100.0)
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def ghost_memory_ids(self) -> list[str]:
        return [g.memory_id for g in self.ghost_tokens]


class AuditResult(BaseModel):
    """Full health audit of a memory store."""

    total_memories: int
    ghost_count: int
    ghost_percentage: float
    contradiction_count: int
    contradictions: list[Contradiction] = Field(default_factory=list)
    stale_count: int
    stale_memories: list[StaleMemory] = Field(default_factory=list)
    health_score: float = Field(ge=0.0, le=100.0)
    estimated_waste_tokens: int = 0
    estimated_waste_cost_monthly: float = 0.0  # at $0.01/1K tokens
    recommendations: list[str] = Field(default_factory=list)


class GateResult(BaseModel):
    """Pre-generation memory risk scoring result."""

    query: str
    memories_scored: int
    high_risk: list[str] = Field(default_factory=list)  # memory IDs with risk flags
    contradictions: list[Contradiction] = Field(default_factory=list)
    stale: list[StaleMemory] = Field(default_factory=list)
    safe_to_generate: bool = True
    risk_summary: str = ""

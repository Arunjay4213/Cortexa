"""
Pydantic models mapping the CortexOS paper definitions.

Memory Unit  M = (m, φ, τ)
Transaction  ξ = (q, S, C, r, t)
Attribution  aᵢ
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class MemoryTier(str, Enum):
    hot = "hot"
    warm = "warm"
    cold = "cold"


class AttributionMethod(str, Enum):
    eas = "eas"
    exact = "exact"
    contextcite = "contextcite"
    amortized = "amortized"


# ── Memory ─────────────────────────────────────────────────────────────

class MemoryCreate(BaseModel):
    content: str
    agent_id: str = "default"
    tier: MemoryTier = MemoryTier.warm
    criticality: float = 0.5
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    tier: MemoryTier | None = None
    criticality: float | None = None
    metadata: dict[str, Any] | None = None


class MemoryUnit(BaseModel):
    """M = (m, φ, τ) — a single memory unit."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    embedding: list[float] = Field(default_factory=list)
    tokens: int = 0
    agent_id: str = "default"
    tier: MemoryTier = MemoryTier.warm
    criticality: float = 0.5
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime | None = None
    deleted_at: datetime | None = None


# ── Transaction ────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    """Input to POST /transactions — the critical path (complete transaction)."""
    query_text: str
    response_text: str
    retrieved_memory_ids: list[str]
    agent_id: str = "default"
    query_embedding: list[float] | None = None
    response_embedding: list[float] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str = "unknown"


class TransactionInitiate(BaseModel):
    """Phase 1 of two-phase protocol: create pending transaction at search time."""
    query_text: str
    retrieved_memory_ids: list[str]
    agent_id: str = "default"
    query_embedding: list[float] | None = None
    model: str = "unknown"


class TransactionComplete(BaseModel):
    """Phase 2 of two-phase protocol: complete with response for deferred attribution."""
    response_text: str
    response_embedding: list[float] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class TransactionStatus(str, Enum):
    pending = "pending"
    completed = "completed"


class Transaction(BaseModel):
    """ξ = (q, S, C, r, t) — a single agent transaction."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_text: str
    query_embedding: list[float] = Field(default_factory=list)
    response_text: str | None = None
    response_embedding: list[float] = Field(default_factory=list)
    retrieved_memory_ids: list[str] = Field(default_factory=list)
    agent_id: str = "default"
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "unknown"
    status: TransactionStatus = TransactionStatus.completed
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ── Attribution ────────────────────────────────────────────────────────

class AttributionScore(BaseModel):
    """aᵢ — attribution of memory i in transaction ξ."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_id: str
    transaction_id: str
    score: float          # normalized ∈ [0,1], sums to 1
    raw_score: float      # before normalization
    method: AttributionMethod = AttributionMethod.eas
    confidence: float = 1.0
    compute_time_ms: float = 0.0


# ── Memory Profile (Welford online) ───────────────────────────────────

class MemoryProfile(BaseModel):
    """Πᵢ(t) — running statistics for memory i."""
    memory_id: str
    mean_attribution: float = 0.0
    m2: float = 0.0  # Welford's M2 accumulator; variance = m2 / max(n-1, 1)
    retrieval_count: int = 0
    total_attribution: float = 0.0
    trend: str = "stable"  # "up" | "down" | "stable"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def attribution_variance(self) -> float:
        return self.m2 / max(self.retrieval_count - 1, 1)


# ── Token Economics ────────────────────────────────────────────────────

class TokenCostConfig(BaseModel):
    """Per-agent/provider token pricing. No hardcoded defaults —
    callers must supply costs or look up from agent_cost_configs table."""
    input_token_cost: float
    output_token_cost: float


class TransactionCost(BaseModel):
    """Cost(ξ) = π_in·|C| + π_out·|r|"""
    transaction_id: str
    input_cost: float
    output_cost: float
    total_cost: float


class MemoryPnL(BaseModel):
    """Revenue − Cost per memory."""
    memory_id: str
    revenue: float        # attribution-weighted value
    cost: float           # token cost of storage + retrieval
    pnl: float
    roi: float            # (revenue / cost) if cost > 0


# ── Health ─────────────────────────────────────────────────────────────

class Contradiction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_id_1: str
    memory_id_2: str
    type: str = "logical"  # logical | temporal_update | concurrent_conflict | ambiguous
    confidence: float = 0.0
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved: bool = False


class HealthSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    contradiction_rate: float = 0.0
    retrieval_efficiency: float = 0.0
    semantic_drift: float = 0.0
    memory_quality: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ── Dashboard / View Models ───────────────────────────────────────────

class AgentSummary(BaseModel):
    agent_id: str
    total_memories: int = 0
    total_transactions: int = 0
    avg_attribution: float = 0.0
    tier_distribution: dict[str, int] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
    gini_coefficient: float = 0.0
    snr_db: float = 0.0
    waste_rate: float = 0.0
    contradiction_count: int = 0
    last_active: datetime | None = None


class DashboardOverview(BaseModel):
    agents: list[AgentSummary] = Field(default_factory=list)
    total_memories: int = 0
    total_transactions: int = 0
    total_attributions: int = 0
    overall_gini: float = 0.0
    overall_snr_db: float = 0.0
    overall_waste_rate: float = 0.0


# ── Calibration (§3.4 two-speed loop) ──────────────────────────────────

class CalibrationPair(BaseModel):
    """Paired (EAS, exact) observation for calibrating the fast path."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_id: str
    transaction_id: str
    eas_score: float
    exact_score: float
    method: str = "contextcite"  # exact | contextcite
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ── Agent Cost Configuration ──────────────────────────────────────────

class AgentCostConfig(BaseModel):
    """Per-agent token pricing — different LLM providers have different pricing."""
    agent_id: str
    input_token_cost: float
    output_token_cost: float
    provider: str | None = None   # "openai", "anthropic", "google", etc.
    model_id: str | None = None   # "gpt-4", "claude-3-opus", etc.
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ── Paginated response ────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    offset: int
    limit: int


# ── Transaction with scores (returned from POST) ──────────────────────

class TransactionWithScores(BaseModel):
    transaction: Transaction
    scores: list[AttributionScore]
    cost: TransactionCost

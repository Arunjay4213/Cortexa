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
        if self.retrieval_count < 2:
            return 0.0
        return self.m2 / (self.retrieval_count - 1)


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
    # Legacy metrics (deprecated)
    contradiction_rate: float = 0.0
    retrieval_efficiency: float = 0.0
    semantic_drift: float = 0.0
    memory_quality: float = 0.0
    # New CHI metrics
    chi_score: float | None = None
    chi_grade: str | None = None
    accuracy_component: float | None = None
    freshness_component: float | None = None
    coverage_component: float | None = None
    consistency_component: float | None = None
    efficiency_component: float | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CHIComputeResponse(BaseModel):
    """Response from POST /health/compute/{agent_id}."""
    agent_id: str
    chi_score: float
    chi_grade: str
    components: dict[str, float | None]  # accuracy, freshness, coverage (may be None), consistency, efficiency
    timestamp: datetime
    snapshot_id: str


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


# ── Phase 2: Dashboard API models ────────────────────────────────────

class TimeSeriesBucket(BaseModel):
    timestamp: datetime
    value: float
    count: int = 0


class TimeSeriesResponse(BaseModel):
    metric: str
    agent_id: str | None = None
    buckets: list[TimeSeriesBucket] = Field(default_factory=list)
    days: int = 7


class TopMemoryResponse(BaseModel):
    memory_id: str
    content: str
    agent_id: str
    total_attribution: float
    mean_attribution: float
    retrieval_count: int
    tier: str


class CostSummaryResponse(BaseModel):
    agent_id: str | None = None
    total_cost: float = 0.0
    input_cost: float = 0.0
    output_cost: float = 0.0
    transaction_count: int = 0
    avg_cost_per_transaction: float = 0.0


class AgentDetail(BaseModel):
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
    cost_config: AgentCostConfig | None = None
    recent_transactions: list[Transaction] = Field(default_factory=list)


# ── Phase 3: Lifecycle Automation ─────────────────────────────────────

class ArchiveRecommendation(BaseModel):
    memory_id: str
    agent_id: str
    revenue: float
    cost: float
    pnl: float
    reason: str = "negative_pnl"


class ConsolidationRecommendation(BaseModel):
    canonical_memory_id: str
    duplicate_memory_ids: list[str]
    method: str = "content_hash"  # content_hash | cosine_similarity


class TierRecommendation(BaseModel):
    memory_id: str
    current_tier: str
    recommended_tier: str
    trend: str  # up | down | stable
    reason: str


class BudgetOptimization(BaseModel):
    budget_tokens: int
    selected_memory_ids: list[str]
    total_tokens: int
    total_attribution: float
    excluded_count: int


class LifecycleRecommendations(BaseModel):
    agent_id: str
    archive: list[ArchiveRecommendation] = Field(default_factory=list)
    consolidate: list[ConsolidationRecommendation] = Field(default_factory=list)
    tier_changes: list[TierRecommendation] = Field(default_factory=list)
    estimated_monthly_savings: float = 0.0


class ExecuteRecommendationsRequest(BaseModel):
    archive_memory_ids: list[str] = Field(default_factory=list)
    tier_changes: dict[str, str] = Field(default_factory=dict)  # memory_id -> new_tier
    consolidate_groups: list[list[str]] = Field(default_factory=list)  # [[canonical, dup1, dup2], ...]


# ── Phase 4: Memory Versioning ────────────────────────────────────────

class SnapshotCreate(BaseModel):
    name: str
    description: str | None = None
    created_by: str | None = None


class SnapshotEntryResponse(BaseModel):
    memory_id: str
    content: str
    tier: str
    token_count: int
    total_attribution: float


class SnapshotResponse(BaseModel):
    id: str
    name: str
    agent_id: str
    description: str | None = None
    memory_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None


class DiffEntry(BaseModel):
    memory_id: str
    status: str  # "added" | "removed" | "modified"
    content_a: str | None = None
    content_b: str | None = None
    tier_a: str | None = None
    tier_b: str | None = None


class SnapshotDiff(BaseModel):
    snapshot_a_id: str
    snapshot_b_id: str
    added: list[DiffEntry] = Field(default_factory=list)
    removed: list[DiffEntry] = Field(default_factory=list)
    modified: list[DiffEntry] = Field(default_factory=list)


class BranchCreate(BaseModel):
    name: str
    snapshot_id: str
    description: str | None = None


class BranchResponse(BaseModel):
    id: str
    name: str
    parent_snapshot_id: str
    agent_id: str
    description: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ── Phase 5: Counterfactual Memory Staging ───────────────────────────

class CounterfactualChangeAction(str, Enum):
    add = "add"
    remove = "remove"
    edit = "edit"


class CounterfactualChange(BaseModel):
    action: CounterfactualChangeAction
    memory_id: str | None = None       # required for remove/edit
    content: str | None = None          # required for add/edit
    embedding: list[float] | None = None  # required for add/edit
    tokens: int | None = None           # optional, estimated from content if missing


class CounterfactualStageRequest(BaseModel):
    agent_id: str
    changes: list[CounterfactualChange]
    transaction_window: int = 50
    include_analysis: set[str] | None = None  # {"attribution","contradictions","coverage","chi","financial"}
    sim_threshold: float = 0.7
    coverage_threshold: float = 0.4


class AttributionDelta(BaseModel):
    transaction_id: str
    query_text: str
    before: dict[str, float]     # memory_id -> score
    after: dict[str, float]      # memory_id -> score
    top_memory_changed: bool
    max_score_delta: float


class AttributionSummary(BaseModel):
    transactions_affected: int
    avg_score_delta: float
    max_score_delta: float
    new_memories_in_top3: int


class ContradictionDelta(BaseModel):
    new_contradictions: list[dict]
    resolved_contradictions: list[dict]
    net_change: int


class CoverageDelta(BaseModel):
    gaps_before: int
    gaps_after: int
    gap_change: int


class CHIDelta(BaseModel):
    before: float
    after: float
    delta: float


class FinancialDelta(BaseModel):
    portfolio_roi_before: float
    portfolio_roi_after: float
    estimated_monthly_savings: float


class CounterfactualImpact(BaseModel):
    attribution_deltas: list[AttributionDelta] = Field(default_factory=list)
    summary: AttributionSummary | None = None
    contradictions: ContradictionDelta | None = None
    coverage: CoverageDelta | None = None
    chi: CHIDelta | None = None
    financial: FinancialDelta | None = None


class StagingSessionStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    committed = "committed"
    discarded = "discarded"


class CounterfactualResult(BaseModel):
    session_id: str
    agent_id: str
    status: StagingSessionStatus
    changes_proposed: int
    transactions_analyzed: int
    compute_time_ms: float
    impact: CounterfactualImpact | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ── Phase 6: Grounding & Contamination Detection ────────────────────

class GroundingScanRequest(BaseModel):
    agent_id: str
    transaction_window: int = 50


class GroundingScoreResponse(BaseModel):
    memory_id: str
    grounding_score: float
    provenance_score: float
    corroboration_score: float
    empirical_score: float
    counterfactual_score: float
    risk_level: str
    reasons: list[str] = Field(default_factory=list)
    recommended_action: str = "keep"


class ContaminationScanResponse(BaseModel):
    total_memories: int
    trusted: int
    uncertain: int
    suspect: int
    contaminated: int
    system_contamination_rate: float
    compute_time_ms: float
    flags: list[GroundingScoreResponse] = Field(default_factory=list)


class GateCheckRequest(BaseModel):
    content: str
    agent_id: str
    embedding: list[float] | None = None
    source_type: str = "unknown"


class GateCheckResponse(BaseModel):
    should_store: bool
    grounding_score: float
    risk_level: str
    reasons: list[str] = Field(default_factory=list)
    contradicts_existing: list[str] = Field(default_factory=list)
    redundant_with: list[str] = Field(default_factory=list)


class QuarantineRequest(BaseModel):
    agent_id: str
    memory_ids: list[str]
    transaction_window: int = 50


class QuarantineSimulationResponse(BaseModel):
    quarantined_count: int
    chi_before: float | None = None
    chi_after: float | None = None
    chi_improvement: float = 0.0
    health_improved: bool = False
    coverage_gap_change: int = 0
    transactions_affected: int = 0
    recommendation: str = ""
    compute_time_ms: float = 0.0

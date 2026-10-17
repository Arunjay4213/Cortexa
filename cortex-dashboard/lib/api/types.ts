/**
 * TypeScript interfaces matching backend Pydantic models.
 */

export type MemoryTier = "hot" | "warm" | "cold";
export type AttributionMethod = "eas" | "exact" | "contextcite" | "amortized";
export type TransactionStatus = "pending" | "completed";

export interface MemoryUnit {
  id: string;
  content: string;
  embedding: number[];
  tokens: number;
  agent_id: string;
  tier: MemoryTier;
  criticality: number;
  metadata: Record<string, unknown>;
  retrieval_count: number;
  created_at: string;
  last_accessed: string | null;
  deleted_at: string | null;
}

export interface MemoryCreate {
  content: string;
  agent_id?: string;
  tier?: MemoryTier;
  criticality?: number;
  metadata?: Record<string, unknown>;
}

export interface MemoryUpdate {
  tier?: MemoryTier;
  criticality?: number;
  metadata?: Record<string, unknown>;
}

export interface Transaction {
  id: string;
  query_text: string;
  query_embedding: number[];
  response_text: string | null;
  response_embedding: number[];
  retrieved_memory_ids: string[];
  agent_id: string;
  input_tokens: number;
  output_tokens: number;
  model: string;
  status: TransactionStatus;
  created_at: string;
}

export interface AttributionScore {
  id: string;
  memory_id: string;
  transaction_id: string;
  score: number;
  raw_score: number;
  method: AttributionMethod;
  confidence: number;
  compute_time_ms: number;
}

export interface MemoryProfile {
  memory_id: string;
  mean_attribution: number;
  m2: number;
  retrieval_count: number;
  total_attribution: number;
  trend: string;
  updated_at: string;
}

export interface TransactionCost {
  transaction_id: string;
  input_cost: number;
  output_cost: number;
  total_cost: number;
}

export interface TransactionWithScores {
  transaction: Transaction;
  scores: AttributionScore[];
  cost: TransactionCost;
}

export interface Contradiction {
  id: string;
  memory_id_1: string;
  memory_id_2: string;
  type: string;
  confidence: number;
  detected_at: string;
  resolved: boolean;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface HealthSnapshot {
  id: string;
  agent_id: string;
  contradiction_rate: number;
  retrieval_efficiency: number;
  semantic_drift: number;
  memory_quality: number;
  timestamp: string;
}

export interface AgentSummary {
  agent_id: string;
  total_memories: number;
  total_transactions: number;
  avg_attribution: number;
  tier_distribution: Record<string, number>;
  token_usage: Record<string, number>;
  gini_coefficient: number;
  snr_db: number;
  waste_rate: number;
  contradiction_count: number;
  last_active: string | null;
}

export interface AgentCostConfig {
  agent_id: string;
  input_token_cost: number;
  output_token_cost: number;
  provider: string | null;
  model_id: string | null;
  updated_at: string;
}

export interface AgentDetail extends AgentSummary {
  cost_config: AgentCostConfig | null;
  recent_transactions: Transaction[];
}

export interface DashboardOverview {
  agents: AgentSummary[];
  total_memories: number;
  total_transactions: number;
  total_attributions: number;
  overall_gini: number;
  overall_snr_db: number;
  overall_waste_rate: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface TimeSeriesBucket {
  timestamp: string;
  value: number;
  count: number;
}

export interface TimeSeriesResponse {
  metric: string;
  agent_id: string | null;
  buckets: TimeSeriesBucket[];
  days: number;
}

export interface TopMemoryResponse {
  memory_id: string;
  content: string;
  agent_id: string;
  total_attribution: number;
  mean_attribution: number;
  retrieval_count: number;
  tier: string;
}

export interface CostSummaryResponse {
  agent_id: string | null;
  total_cost: number;
  input_cost: number;
  output_cost: number;
  transaction_count: number;
  avg_cost_per_transaction: number;
}

export interface MemorySearchResult {
  memory: MemoryUnit;
  similarity: number;
}

export interface ExactAttributionResult {
  transaction_id: string;
  scores: AttributionScore[];
  lds: number;
  compute_ms: number;
  cost_usd: number;
  num_samples: number;
  method: string;
}

export interface ContradictionDetectionResult {
  detected: number;
  contradictions: Contradiction[];
}

export interface WebSocketMessage {
  sequence_id: number;
  type: "transaction" | "score" | "alert" | "contradiction" | "memory_update" | "transaction_created" | "attribution_scored" | "lifecycle_executed" | "agent_updated";
  data: Record<string, unknown>;
}

// ── Phase 3: Lifecycle Automation ────────────────────────────────────

export interface ArchiveRecommendation {
  memory_id: string;
  agent_id: string;
  revenue: number;
  cost: number;
  pnl: number;
  reason: string;
}

export interface ConsolidationRecommendation {
  canonical_memory_id: string;
  duplicate_memory_ids: string[];
  method: string;
}

export interface TierRecommendation {
  memory_id: string;
  current_tier: string;
  recommended_tier: string;
  trend: string;
  reason: string;
}

export interface BudgetOptimization {
  budget_tokens: number;
  selected_memory_ids: string[];
  total_tokens: number;
  total_attribution: number;
  excluded_count: number;
}

export interface LifecycleRecommendations {
  agent_id: string;
  archive: ArchiveRecommendation[];
  consolidate: ConsolidationRecommendation[];
  tier_changes: TierRecommendation[];
  estimated_monthly_savings: number;
}

export interface ExecuteRecommendationsRequest {
  archive_memory_ids: string[];
  tier_changes: Record<string, string>;
  consolidate_groups: string[][];
}

export interface ExecuteRecommendationsResponse {
  agent_id: string;
  archived: number;
  tier_changed: number;
  consolidated: number;
  total_actions: number;
}

// ── Phase 4: Memory Versioning ────────────────────────────────────────

export interface SnapshotResponse {
  id: string;
  name: string;
  agent_id: string;
  description: string | null;
  memory_count: number;
  created_at: string;
  created_by: string | null;
}

export interface SnapshotEntryResponse {
  memory_id: string;
  content: string;
  tier: string;
  token_count: number;
  total_attribution: number;
}

export interface DiffEntry {
  memory_id: string;
  status: "added" | "removed" | "modified";
  content_a: string | null;
  content_b: string | null;
  tier_a: string | null;
  tier_b: string | null;
}

export interface SnapshotDiff {
  snapshot_a_id: string;
  snapshot_b_id: string;
  added: DiffEntry[];
  removed: DiffEntry[];
  modified: DiffEntry[];
}

export interface BranchResponse {
  id: string;
  name: string;
  parent_snapshot_id: string;
  agent_id: string;
  description: string | null;
  created_at: string;
}

// ── Phase 5: Counterfactual Memory Staging ───────────────────────────

export type CounterfactualChangeAction = "add" | "remove" | "edit";

export interface CounterfactualChange {
  action: CounterfactualChangeAction;
  memory_id?: string | null;
  content?: string | null;
  embedding?: number[] | null;
  tokens?: number | null;
}

export interface CounterfactualStageRequest {
  agent_id: string;
  changes: CounterfactualChange[];
  transaction_window?: number;
  include_analysis?: string[] | null;
  sim_threshold?: number;
  coverage_threshold?: number;
}

export interface AttributionDelta {
  transaction_id: string;
  query_text: string;
  before: Record<string, number>;
  after: Record<string, number>;
  top_memory_changed: boolean;
  max_score_delta: number;
}

export interface AttributionSummary {
  transactions_affected: number;
  avg_score_delta: number;
  max_score_delta: number;
  new_memories_in_top3: number;
}

export interface ContradictionDelta {
  new_contradictions: Record<string, unknown>[];
  resolved_contradictions: Record<string, unknown>[];
  net_change: number;
}

export interface CoverageDelta {
  gaps_before: number;
  gaps_after: number;
  gap_change: number;
}

export interface CHIDelta {
  before: number;
  after: number;
  delta: number;
}

export interface FinancialDelta {
  portfolio_roi_before: number;
  portfolio_roi_after: number;
  estimated_monthly_savings: number;
}

export interface CounterfactualImpact {
  attribution_deltas: AttributionDelta[];
  summary: AttributionSummary | null;
  contradictions: ContradictionDelta | null;
  coverage: CoverageDelta | null;
  chi: CHIDelta | null;
  financial: FinancialDelta | null;
}

export type StagingSessionStatus =
  | "running"
  | "completed"
  | "failed"
  | "committed"
  | "discarded";

export interface CounterfactualResult {
  session_id: string;
  agent_id: string;
  status: StagingSessionStatus;
  changes_proposed: number;
  transactions_analyzed: number;
  compute_time_ms: number;
  impact: CounterfactualImpact | null;
  error: string | null;
  created_at?: string;
}

// ── Phase 6: Grounding & Contamination Detection ────────────────────

export interface GroundingScanRequest {
  agent_id: string;
  transaction_window?: number;
}

export interface GroundingScoreResponse {
  memory_id: string;
  grounding_score: number;
  provenance_score: number;
  corroboration_score: number;
  empirical_score: number;
  counterfactual_score: number;
  risk_level: string;
  reasons: string[];
  recommended_action: string;
}

export interface ContaminationScanResponse {
  total_memories: number;
  trusted: number;
  uncertain: number;
  suspect: number;
  contaminated: number;
  system_contamination_rate: number;
  compute_time_ms: number;
  flags: GroundingScoreResponse[];
}

export interface GateCheckRequest {
  content: string;
  agent_id: string;
  embedding?: number[] | null;
  source_type?: string;
}

export interface GateCheckResponse {
  should_store: boolean;
  grounding_score: number;
  risk_level: string;
  reasons: string[];
  contradicts_existing: string[];
  redundant_with: string[];
}

export interface QuarantineRequest {
  agent_id: string;
  memory_ids: string[];
  transaction_window?: number;
}

export interface QuarantineSimulationResponse {
  quarantined_count: number;
  chi_before: number | null;
  chi_after: number | null;
  chi_improvement: number;
  health_improved: boolean;
  coverage_gap_change: number;
  transactions_affected: number;
  recommendation: string;
  compute_time_ms: number;
}

/**
 * Dashboard-specific types for the CortexOS observability UI.
 *
 * These are presentation-layer interfaces shaped for the Grafana-style
 * dashboard. They differ from lib/api/types.ts (which mirrors backend Pydantic
 * models) — the dashboard types carry pre-computed health, financial, and
 * attribution data ready for direct rendering.
 */

// ── Time Series ────────────────────────────────────────────────────────

export interface TimeSeriesPoint {
  timestamp: string;
  value: number;
}

// ── Memory ──────────────────────────────────────────────────────────────

export type MemoryType = 'raw' | 'consolidated' | 'critical';
export type MemoryStatus = 'active' | 'archived' | 'deleted' | 'pending_deletion';

export interface Memory {
  id: string;
  content: string;
  type: MemoryType;
  status: MemoryStatus;
  createdAt: string;
  lastRetrieved: string;
  retrievalCount: number;
  tokenCount: number;

  // Health (CHI components)
  healthScore: number;           // 0-1 composite health index component
  stalenessScore: number;        // 0-1, higher = more stale
  contradictionsWith: string[];  // IDs of contradicting memories
  driftScore: number;            // 0-1 semantic drift from cluster centroid

  // Financial (token economics)
  revenuePerDay: number;
  costPerDay: number;
  roi: number;
  sharpeRatio: number;
}

// ── Query Trace ─────────────────────────────────────────────────────────

export type ScoreType = 'eas' | 'contextcite' | 'calibrated';
export type HealthStatus = 'ok' | 'stale' | 'contradictory' | 'drifted';
export type HallucinationRisk = 'none' | 'low' | 'medium' | 'high';

export interface RetrievedMemory {
  memoryId: string;
  content: string;
  attributionScore: number;
  scoreType: ScoreType;
  healthStatus: HealthStatus;
}

export interface StatementAttribution {
  statement: string;
  memoryScores: { memoryId: string; score: number }[];
}

export interface QueryTrace {
  id: string;
  query: string;
  response: string;
  agentId: string;
  timestamp: string;
  totalCost: number;
  latencyMs: number;
  memoriesRetrieved: RetrievedMemory[];
  hallucinationRisk: HallucinationRisk;
  statementAttribution?: StatementAttribution[];
}

// ── Health Alerts ───────────────────────────────────────────────────────

export type AlertSeverity = 'critical' | 'warning' | 'info';
export type AlertType = 'contradiction' | 'stale' | 'drift' | 'coverage_gap';

export interface HealthAlert {
  id: string;
  severity: AlertSeverity;
  type: AlertType;
  memoryIds: string[];
  description: string;
  detectedAt: string;
  resolved: boolean;
}

// ── Deletion / GDPR ────────────────────────────────────────────────────

export type DeletionStatus = 'pending' | 'processing' | 'completed' | 'verified';

export interface DeletionRequest {
  id: string;
  userId: string;
  status: DeletionStatus;
  requestedAt: string;
  completedAt?: string;
  footprintSize: number;
  nodesDeleted: number;
  edgesAffected: number;
  certificateHash?: string;
}

// ── Provenance Graph ────────────────────────────────────────────────────

export type ProvenanceNodeType =
  | 'interaction'
  | 'memory'
  | 'summary'
  | 'embedding'
  | 'response';

export type ProvenanceEdgeType = 'creation' | 'attribution' | 'derivation';

export interface ProvenanceNode {
  id: string;
  type: ProvenanceNodeType;
  label: string;
  userId?: string;
  createdAt: string;
}

export interface ProvenanceEdge {
  id: string;
  source: string;
  target: string;
  type: ProvenanceEdgeType;
  weight?: number;
}

// ── Dashboard KPIs ──────────────────────────────────────────────────────

export type GDPRStatus = 'compliant' | 'pending_deletions' | 'overdue';

export interface DashboardKPIs {
  compositeHealthIndex: number;
  chiHistory: TimeSeriesPoint[];              // 30 days
  memoryROI: number;
  activeMemories: number;
  totalMemories: number;
  attributionConfidence: number;
  hallucinationRate: number;
  hallucinationHistory: TimeSeriesPoint[];    // 30 days
  tokenWasteRate: number;
  tokenWasteHistory: TimeSeriesPoint[];       // 30 days
  gdprStatus: GDPRStatus;
  pendingDeletions: number;
  queriesToday: number;
  queriesPerSecond: number;
  queryVolumeHistory: TimeSeriesPoint[];      // 24 hours, per-hour
  costToday: number;
  costHistory: TimeSeriesPoint[];             // 30 days
  memoriesByHealth: {
    healthy: number;
    stale: number;
    contradictory: number;
    drifted: number;
    archived: number;
  };
}

// ── Lifecycle / Budget Optimizer ────────────────────────────────────────

export interface BudgetStats {
  budgetTokens: number;
  usedTokens: number;
  monthlySpend: number;
  projectedSavings: number;
}

export type ImpactDirection = 'positive' | 'negative' | 'neutral';
export type ArchiveReason = 'auto-archive' | 'manual' | 'consolidation';

export interface OptimizationRecommendation {
  id: string;
  priority: number;
  title: string;
  description: string;
  impactLabel: string;
  impactDirection: ImpactDirection;
  savingsPerMonth: number;
  memoryIds: string[];
}

export interface ArchivedMemoryEntry {
  memoryId: string;
  content: string;
  originalStatus: MemoryStatus;
  archivedAt: string;
  reason: ArchiveReason;
  tokenCount: number;
}

"use client";

import { useState, useMemo, useCallback } from "react";
import {
  BookOpen,
  Search,
  Copy,
  Check,
  ChevronRight,
  Zap,
  Database,
  GitBranch,
  Shield,
  Activity,
  Layers,
  AlertTriangle,
  Terminal,
  Globe,
  ArrowRight,
  ExternalLink,
  Code2,
  Server,
  Key,
  Clock,
  Hash,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface EndpointParam {
  name: string;
  type: string;
  required: boolean;
  description: string;
  default?: string;
}

interface EndpointDef {
  method: HttpMethod;
  path: string;
  summary: string;
  description: string;
  params?: EndpointParam[];
  body?: string;
  response: string;
  category: string;
}

type SectionId =
  | "getting-started"
  | "authentication"
  | "sdk-core"
  | "sdk-types"
  | "integrations"
  | "tui-monitor"
  | "memories"
  | "transactions"
  | "attribution"
  | "health"
  | "lifecycle"
  | "snapshots"
  | "counterfactual"
  | "grounding"
  | "dashboard"
  | "websocket"
  | "errors"
  | "rate-limits";

interface NavSection {
  id: SectionId;
  label: string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  divider?: string;
}

// ── Navigation sections ──────────────────────────────────────────────────

const NAV_SECTIONS: NavSection[] = [
  { id: "getting-started", label: "Getting Started", icon: Zap, divider: "SDK" },
  { id: "authentication", label: "Authentication", icon: Key },
  { id: "sdk-core", label: "SDK Core", icon: Terminal },
  { id: "sdk-types", label: "Result Types", icon: Code2 },
  { id: "integrations", label: "Integrations", icon: Layers },
  { id: "tui-monitor", label: "TUI Monitor", icon: Activity },
  { id: "memories", label: "Memories", icon: Database, divider: "Engine API" },
  { id: "transactions", label: "Transactions", icon: Hash },
  { id: "attribution", label: "Attribution", icon: Activity },
  { id: "health", label: "Health & Contradictions", icon: AlertTriangle },
  { id: "lifecycle", label: "Lifecycle Automation", icon: Layers },
  { id: "snapshots", label: "Snapshots & Branches", icon: GitBranch },
  { id: "counterfactual", label: "Counterfactual Staging", icon: Code2 },
  { id: "grounding", label: "Grounding & Contamination", icon: Shield },
  { id: "dashboard", label: "Dashboard Analytics", icon: Globe },
  { id: "websocket", label: "WebSocket Events", icon: Server },
  { id: "errors", label: "Error Handling", icon: AlertTriangle, divider: "Reference" },
  { id: "rate-limits", label: "Rate Limits", icon: Clock },
];

// ── API endpoint definitions ─────────────────────────────────────────────

const ENDPOINTS: EndpointDef[] = [
  // ── Memories ────────────────────────
  {
    method: "GET",
    path: "/api/v1/memories",
    summary: "List memories",
    description:
      "Returns a paginated list of memory units. Supports filtering by agent, tier, and custom sorting.",
    params: [
      { name: "agent_id", type: "string", required: false, description: "Filter by agent ID" },
      { name: "tier", type: "string", required: false, description: 'Filter by tier: "hot", "warm", or "cold"' },
      { name: "sort_by", type: "string", required: false, description: "Sort field (e.g. created_at, retrieval_count)", default: "created_at" },
      { name: "order", type: "string", required: false, description: '"asc" or "desc"', default: "desc" },
      { name: "offset", type: "integer", required: false, description: "Pagination offset", default: "0" },
      { name: "limit", type: "integer", required: false, description: "Page size (max 100)", default: "50" },
    ],
    response: `{
  "items": [
    {
      "id": "mem-a1b2c3",
      "content": "The user prefers dark mode UI themes.",
      "embedding": [0.123, -0.456, ...],
      "tokens": 8,
      "agent_id": "agent-001",
      "tier": "hot",
      "criticality": 0.85,
      "metadata": { "source": "user_preference" },
      "retrieval_count": 42,
      "created_at": "2026-02-15T10:30:00Z",
      "last_accessed": "2026-02-28T14:22:00Z",
      "deleted_at": null
    }
  ],
  "total": 1247,
  "offset": 0,
  "limit": 50
}`,
    category: "memories",
  },
  {
    method: "GET",
    path: "/api/v1/memories/{memory_id}",
    summary: "Get memory detail",
    description:
      "Returns a single memory unit along with its attribution profile, including mean attribution, trend, and retrieval stats.",
    params: [
      { name: "memory_id", type: "string", required: true, description: "Memory UUID" },
    ],
    response: `{
  "memory": {
    "id": "mem-a1b2c3",
    "content": "The user prefers dark mode UI themes.",
    "tokens": 8,
    "agent_id": "agent-001",
    "tier": "hot",
    "criticality": 0.85,
    "retrieval_count": 42,
    "created_at": "2026-02-15T10:30:00Z",
    "last_accessed": "2026-02-28T14:22:00Z"
  },
  "profile": {
    "memory_id": "mem-a1b2c3",
    "mean_attribution": 0.72,
    "m2": 0.034,
    "retrieval_count": 42,
    "total_attribution": 30.24,
    "trend": "rising",
    "updated_at": "2026-02-28T14:22:00Z"
  }
}`,
    category: "memories",
  },
  {
    method: "POST",
    path: "/api/v1/memories",
    summary: "Create memory",
    description:
      "Creates a new memory unit. The system automatically generates an embedding, calculates token count, and runs gate-check validation.",
    body: `{
  "content": "User's preferred timezone is PST.",
  "agent_id": "agent-001",
  "tier": "warm",
  "criticality": 0.6,
  "metadata": { "source": "onboarding" }
}`,
    response: `{
  "id": "mem-d4e5f6",
  "content": "User's preferred timezone is PST.",
  "embedding": [0.234, -0.567, ...],
  "tokens": 7,
  "agent_id": "agent-001",
  "tier": "warm",
  "criticality": 0.6,
  "metadata": { "source": "onboarding" },
  "retrieval_count": 0,
  "created_at": "2026-02-28T15:00:00Z",
  "last_accessed": null,
  "deleted_at": null
}`,
    category: "memories",
  },
  {
    method: "PATCH",
    path: "/api/v1/memories/{memory_id}",
    summary: "Update memory",
    description:
      "Partially updates a memory unit. Only the provided fields are changed. Use this to promote/demote tier, adjust criticality, or update metadata.",
    params: [
      { name: "memory_id", type: "string", required: true, description: "Memory UUID" },
    ],
    body: `{
  "tier": "hot",
  "criticality": 0.95,
  "metadata": { "source": "onboarding", "verified": true }
}`,
    response: `{
  "id": "mem-d4e5f6",
  "content": "User's preferred timezone is PST.",
  "tier": "hot",
  "criticality": 0.95,
  "metadata": { "source": "onboarding", "verified": true },
  ...
}`,
    category: "memories",
  },
  {
    method: "DELETE",
    path: "/api/v1/memories/{memory_id}",
    summary: "Delete memory",
    description:
      "Soft-deletes a memory unit. Sets deleted_at timestamp. The memory is excluded from future retrievals but remains in the provenance graph for audit compliance.",
    params: [
      { name: "memory_id", type: "string", required: true, description: "Memory UUID" },
    ],
    response: `204 No Content`,
    category: "memories",
  },
  {
    method: "GET",
    path: "/api/v1/memories/search",
    summary: "Search memories",
    description:
      "Performs semantic similarity search across memory embeddings. Returns the top-k most relevant memories ranked by cosine similarity.",
    params: [
      { name: "q", type: "string", required: true, description: "Natural language search query" },
      { name: "agent_id", type: "string", required: false, description: "Limit search to a specific agent" },
      { name: "top_k", type: "integer", required: false, description: "Number of results to return", default: "10" },
    ],
    response: `[
  {
    "memory": {
      "id": "mem-a1b2c3",
      "content": "The user prefers dark mode UI themes.",
      "tier": "hot",
      ...
    },
    "similarity": 0.89
  }
]`,
    category: "memories",
  },

  // ── Transactions ────────────────────
  {
    method: "GET",
    path: "/api/v1/transactions",
    summary: "List transactions",
    description:
      "Returns a paginated list of LLM transactions. Each transaction represents a single query-response cycle including which memories were retrieved.",
    params: [
      { name: "agent_id", type: "string", required: false, description: "Filter by agent ID" },
      { name: "status", type: "string", required: false, description: '"pending" or "completed"' },
      { name: "offset", type: "integer", required: false, description: "Pagination offset", default: "0" },
      { name: "limit", type: "integer", required: false, description: "Page size (max 100)", default: "50" },
    ],
    response: `{
  "items": [
    {
      "id": "txn-x1y2z3",
      "query_text": "What theme does the user prefer?",
      "response_text": "The user prefers dark mode.",
      "retrieved_memory_ids": ["mem-a1b2c3", "mem-d4e5f6"],
      "agent_id": "agent-001",
      "input_tokens": 45,
      "output_tokens": 12,
      "model": "gpt-4o",
      "status": "completed",
      "created_at": "2026-02-28T14:22:00Z"
    }
  ],
  "total": 583,
  "offset": 0,
  "limit": 50
}`,
    category: "transactions",
  },
  {
    method: "GET",
    path: "/api/v1/transactions/{transaction_id}",
    summary: "Get transaction detail",
    description:
      "Returns a single transaction along with all associated attribution scores. Use this to inspect which memories influenced a specific response and by how much.",
    params: [
      { name: "transaction_id", type: "string", required: true, description: "Transaction UUID" },
    ],
    response: `{
  "transaction": {
    "id": "txn-x1y2z3",
    "query_text": "What theme does the user prefer?",
    "response_text": "The user prefers dark mode.",
    "retrieved_memory_ids": ["mem-a1b2c3", "mem-d4e5f6"],
    "agent_id": "agent-001",
    "input_tokens": 45,
    "output_tokens": 12,
    "model": "gpt-4o",
    "status": "completed"
  },
  "scores": [
    {
      "id": "attr-001",
      "memory_id": "mem-a1b2c3",
      "transaction_id": "txn-x1y2z3",
      "score": 0.82,
      "raw_score": 0.78,
      "method": "eas",
      "confidence": 0.95,
      "compute_time_ms": 34
    }
  ]
}`,
    category: "transactions",
  },
  {
    method: "POST",
    path: "/api/v1/transactions",
    summary: "Create transaction",
    description:
      "Records a new LLM transaction. CortexOS automatically computes embeddings, runs attribution scoring (EAS method by default), and calculates cost metrics.",
    body: `{
  "query_text": "What is the user's preferred language?",
  "response_text": "The user prefers English.",
  "retrieved_memory_ids": ["mem-a1b2c3"],
  "agent_id": "agent-001",
  "model": "gpt-4o"
}`,
    response: `{
  "transaction": {
    "id": "txn-n3w1d",
    "query_text": "What is the user's preferred language?",
    "response_text": "The user prefers English.",
    "retrieved_memory_ids": ["mem-a1b2c3"],
    "agent_id": "agent-001",
    "input_tokens": 38,
    "output_tokens": 8,
    "model": "gpt-4o",
    "status": "completed",
    "created_at": "2026-02-28T15:05:00Z"
  },
  "scores": [
    {
      "memory_id": "mem-a1b2c3",
      "score": 0.67,
      "method": "eas",
      "confidence": 0.91
    }
  ],
  "cost": {
    "transaction_id": "txn-n3w1d",
    "input_cost": 0.00019,
    "output_cost": 0.00006,
    "total_cost": 0.00025
  }
}`,
    category: "transactions",
  },

  // ── Attribution ────────────────────
  {
    method: "GET",
    path: "/api/v1/attribution/{transaction_id}",
    summary: "Get attribution scores",
    description:
      "Returns all attribution scores for a given transaction. Each score represents how much influence a specific memory had on the response, computed via Efficient Amortized Shapley (EAS).",
    params: [
      { name: "transaction_id", type: "string", required: true, description: "Transaction UUID" },
    ],
    response: `[
  {
    "id": "attr-001",
    "memory_id": "mem-a1b2c3",
    "transaction_id": "txn-x1y2z3",
    "score": 0.82,
    "raw_score": 0.78,
    "method": "eas",
    "confidence": 0.95,
    "compute_time_ms": 34
  },
  {
    "id": "attr-002",
    "memory_id": "mem-d4e5f6",
    "transaction_id": "txn-x1y2z3",
    "score": 0.15,
    "raw_score": 0.12,
    "method": "eas",
    "confidence": 0.88,
    "compute_time_ms": 34
  }
]`,
    category: "attribution",
  },
  {
    method: "GET",
    path: "/api/v1/attribution/memory/{memory_id}",
    summary: "Get memory attribution profile",
    description:
      "Returns the aggregate attribution profile for a memory across all transactions. Includes mean attribution, total contribution, trend direction, and Welford online variance.",
    params: [
      { name: "memory_id", type: "string", required: true, description: "Memory UUID" },
    ],
    response: `{
  "scores": [
    {
      "memory_id": "mem-a1b2c3",
      "transaction_id": "txn-x1y2z3",
      "score": 0.82,
      "method": "eas",
      "confidence": 0.95
    }
  ],
  "profile": {
    "memory_id": "mem-a1b2c3",
    "mean_attribution": 0.72,
    "m2": 0.034,
    "retrieval_count": 42,
    "total_attribution": 30.24,
    "trend": "rising",
    "updated_at": "2026-02-28T14:22:00Z"
  }
}`,
    category: "attribution",
  },
  {
    method: "POST",
    path: "/api/v1/attribution/{transaction_id}/exact",
    summary: "Compute exact Shapley attribution",
    description:
      "Triggers an exact Shapley value computation for a transaction. This is expensive (exponential in memory count) but provides ground-truth attribution. Use for auditing or when EAS confidence is low.",
    params: [
      { name: "transaction_id", type: "string", required: true, description: "Transaction UUID" },
    ],
    response: `{
  "transaction_id": "txn-x1y2z3",
  "scores": [
    {
      "memory_id": "mem-a1b2c3",
      "score": 0.84,
      "raw_score": 0.84,
      "method": "exact",
      "confidence": 1.0,
      "compute_time_ms": 1250
    }
  ],
  "lds": 0.023,
  "compute_ms": 1250,
  "cost_usd": 0.0042,
  "num_samples": 64,
  "method": "exact_shapley"
}`,
    category: "attribution",
  },

  // ── Health ────────────────────
  {
    method: "GET",
    path: "/api/v1/health/{agent_id}",
    summary: "Get health snapshots",
    description:
      "Returns historical health snapshots for an agent. Each snapshot captures contradiction rate, retrieval efficiency, semantic drift, and overall memory quality score.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    response: `[
  {
    "id": "hs-001",
    "agent_id": "agent-001",
    "contradiction_rate": 0.03,
    "retrieval_efficiency": 0.87,
    "semantic_drift": 0.12,
    "memory_quality": 0.91,
    "timestamp": "2026-02-28T14:00:00Z"
  }
]`,
    category: "health",
  },
  {
    method: "GET",
    path: "/api/v1/health/contradictions",
    summary: "List contradictions",
    description:
      "Returns detected contradictions between memory pairs. A contradiction means two memories contain semantically conflicting information.",
    params: [
      { name: "agent_id", type: "string", required: false, description: "Filter by agent ID" },
      { name: "resolved", type: "boolean", required: false, description: "Filter by resolution status" },
    ],
    response: `[
  {
    "id": "ctr-001",
    "memory_id_1": "mem-a1b2c3",
    "memory_id_2": "mem-g7h8i9",
    "type": "semantic_negation",
    "confidence": 0.92,
    "detected_at": "2026-02-27T10:00:00Z",
    "resolved": false,
    "resolved_at": null,
    "resolved_by": null
  }
]`,
    category: "health",
  },
  {
    method: "POST",
    path: "/api/v1/health/contradictions/detect",
    summary: "Detect contradictions",
    description:
      "Triggers a full contradiction detection scan across all memories for a given agent. Compares semantic embeddings and uses NLI models to identify conflicting pairs.",
    params: [
      { name: "agent_id", type: "string", required: false, description: "Scope to a specific agent (scans all if omitted)" },
    ],
    response: `{
  "detected": 3,
  "contradictions": [
    {
      "id": "ctr-new-001",
      "memory_id_1": "mem-a1b2c3",
      "memory_id_2": "mem-j0k1l2",
      "type": "temporal_conflict",
      "confidence": 0.87,
      "detected_at": "2026-02-28T15:10:00Z"
    }
  ]
}`,
    category: "health",
  },
  {
    method: "PATCH",
    path: "/api/v1/health/contradictions/{contradiction_id}/resolve",
    summary: "Resolve contradiction",
    description:
      "Marks a contradiction as resolved. Optionally records who resolved it for audit purposes.",
    params: [
      { name: "contradiction_id", type: "string", required: true, description: "Contradiction UUID" },
      { name: "resolved_by", type: "string", required: false, description: "Identifier of who resolved it" },
    ],
    response: `{
  "id": "ctr-001",
  "resolved": true,
  "resolved_by": "admin@company.com"
}`,
    category: "health",
  },

  // ── Lifecycle ────────────────────
  {
    method: "GET",
    path: "/api/v1/lifecycle/{agent_id}/recommendations",
    summary: "Get lifecycle recommendations",
    description:
      "Analyzes memory portfolio and returns optimization recommendations: memories to archive (negative ROI), duplicates to consolidate, and tier changes based on usage patterns.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    response: `{
  "agent_id": "agent-001",
  "archive": [
    {
      "memory_id": "mem-old-001",
      "agent_id": "agent-001",
      "revenue": 0.002,
      "cost": 0.015,
      "pnl": -0.013,
      "reason": "Negative ROI over 30-day window"
    }
  ],
  "consolidate": [
    {
      "canonical_memory_id": "mem-a1b2c3",
      "duplicate_memory_ids": ["mem-dup-001", "mem-dup-002"],
      "method": "semantic_similarity"
    }
  ],
  "tier_changes": [
    {
      "memory_id": "mem-d4e5f6",
      "current_tier": "warm",
      "recommended_tier": "hot",
      "trend": "rising",
      "reason": "Attribution rising, 15x retrievals in 7d"
    }
  ],
  "estimated_monthly_savings": 12.45
}`,
    category: "lifecycle",
  },
  {
    method: "POST",
    path: "/api/v1/lifecycle/{agent_id}/execute",
    summary: "Execute recommendations",
    description:
      "Applies lifecycle recommendations in bulk. Supports archiving memories, changing tiers, and consolidating duplicates in a single atomic operation.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    body: `{
  "archive_memory_ids": ["mem-old-001"],
  "tier_changes": { "mem-d4e5f6": "hot" },
  "consolidate_groups": [["mem-dup-001", "mem-dup-002"]]
}`,
    response: `{
  "agent_id": "agent-001",
  "archived": 1,
  "tier_changed": 1,
  "consolidated": 2,
  "total_actions": 4
}`,
    category: "lifecycle",
  },
  {
    method: "GET",
    path: "/api/v1/lifecycle/{agent_id}/budget",
    summary: "Budget optimization",
    description:
      "Given a token budget, selects the optimal subset of memories that maximizes total attribution within the budget constraint. Uses a knapsack-style algorithm.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
      { name: "budget_tokens", type: "integer", required: false, description: "Maximum token budget", default: "100000" },
    ],
    response: `{
  "budget_tokens": 100000,
  "selected_memory_ids": ["mem-a1b2c3", "mem-d4e5f6", ...],
  "total_tokens": 94500,
  "total_attribution": 847.2,
  "excluded_count": 23
}`,
    category: "lifecycle",
  },

  // ── Snapshots & Branches ────────────────────
  {
    method: "POST",
    path: "/api/v1/snapshots/{agent_id}",
    summary: "Create snapshot",
    description:
      "Takes a point-in-time snapshot of all memories for an agent. Snapshots are immutable and can be used for diffing, rollback, or branching.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    body: `{
  "name": "pre-deployment-v2",
  "description": "Snapshot before deploying memory update v2",
  "created_by": "admin@company.com"
}`,
    response: `{
  "id": "snap-001",
  "name": "pre-deployment-v2",
  "agent_id": "agent-001",
  "description": "Snapshot before deploying memory update v2",
  "memory_count": 1247,
  "created_at": "2026-02-28T15:00:00Z",
  "created_by": "admin@company.com"
}`,
    category: "snapshots",
  },
  {
    method: "GET",
    path: "/api/v1/snapshots/{agent_id}",
    summary: "List snapshots",
    description: "Returns all snapshots for a given agent, ordered by creation time.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    response: `[
  {
    "id": "snap-001",
    "name": "pre-deployment-v2",
    "agent_id": "agent-001",
    "memory_count": 1247,
    "created_at": "2026-02-28T15:00:00Z"
  }
]`,
    category: "snapshots",
  },
  {
    method: "GET",
    path: "/api/v1/snapshots/{agent_id}/{snapshot_id}",
    summary: "Get snapshot entries",
    description: "Returns the full contents of a snapshot — every memory that was captured at the time the snapshot was taken.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
      { name: "snapshot_id", type: "string", required: true, description: "Snapshot UUID" },
    ],
    response: `{
  "snapshot": { "id": "snap-001", "name": "pre-deployment-v2", ... },
  "entries": [
    {
      "memory_id": "mem-a1b2c3",
      "content": "The user prefers dark mode UI themes.",
      "tier": "hot",
      "token_count": 8,
      "total_attribution": 30.24
    }
  ]
}`,
    category: "snapshots",
  },
  {
    method: "GET",
    path: "/api/v1/snapshots/{agent_id}/{id_a}/diff/{id_b}",
    summary: "Diff two snapshots",
    description:
      "Compares two snapshots and returns all added, removed, and modified memories between them. Useful for understanding what changed between deployments.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
      { name: "id_a", type: "string", required: true, description: "First snapshot UUID" },
      { name: "id_b", type: "string", required: true, description: "Second snapshot UUID" },
    ],
    response: `{
  "snapshot_a_id": "snap-001",
  "snapshot_b_id": "snap-002",
  "added": [
    { "memory_id": "mem-new-001", "status": "added", "content_b": "New fact..." }
  ],
  "removed": [
    { "memory_id": "mem-old-001", "status": "removed", "content_a": "Outdated fact..." }
  ],
  "modified": [
    {
      "memory_id": "mem-a1b2c3",
      "status": "modified",
      "content_a": "User prefers dark mode.",
      "content_b": "User prefers dark mode with high contrast.",
      "tier_a": "warm",
      "tier_b": "hot"
    }
  ]
}`,
    category: "snapshots",
  },
  {
    method: "POST",
    path: "/api/v1/snapshots/{agent_id}/{snapshot_id}/restore",
    summary: "Restore snapshot",
    description:
      "Rolls back an agent's memories to the state captured in a snapshot. This replaces all current memories with the snapshot contents.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
      { name: "snapshot_id", type: "string", required: true, description: "Snapshot UUID to restore" },
    ],
    response: `{
  "restored_from": "snap-001",
  "agent_id": "agent-001",
  "memory_count": 1247
}`,
    category: "snapshots",
  },
  {
    method: "POST",
    path: "/api/v1/branches/{agent_id}",
    summary: "Create branch",
    description:
      "Creates a named branch from a snapshot. Branches allow parallel experimentation with different memory configurations without affecting the main memory store.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    body: `{
  "name": "experiment/new-retrieval",
  "snapshot_id": "snap-001",
  "description": "Testing new retrieval strategy"
}`,
    response: `{
  "id": "branch-001",
  "name": "experiment/new-retrieval",
  "parent_snapshot_id": "snap-001",
  "agent_id": "agent-001",
  "description": "Testing new retrieval strategy",
  "created_at": "2026-02-28T15:30:00Z"
}`,
    category: "snapshots",
  },
  {
    method: "GET",
    path: "/api/v1/branches/{agent_id}",
    summary: "List branches",
    description: "Returns all branches for a given agent.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    response: `[
  {
    "id": "branch-001",
    "name": "experiment/new-retrieval",
    "parent_snapshot_id": "snap-001",
    "agent_id": "agent-001",
    "created_at": "2026-02-28T15:30:00Z"
  }
]`,
    category: "snapshots",
  },

  // ── Counterfactual ────────────────────
  {
    method: "POST",
    path: "/api/v1/counterfactual/stage",
    summary: "Stage counterfactual changes",
    description:
      'Simulates "what-if" memory changes without committing them. Proposes adds, removes, or edits, then analyzes how they would impact attribution scores, contradictions, coverage, CHI (Contextual Health Index), and financial metrics.',
    body: `{
  "agent_id": "agent-001",
  "changes": [
    { "action": "add", "content": "User recently moved to NYC." },
    { "action": "remove", "memory_id": "mem-old-001" },
    { "action": "edit", "memory_id": "mem-a1b2c3", "content": "User prefers dark mode with OLED black." }
  ],
  "transaction_window": 50,
  "include_analysis": ["contradictions", "coverage", "chi", "financial"],
  "sim_threshold": 0.7,
  "coverage_threshold": 0.5
}`,
    response: `{
  "session_id": "cf-sess-001",
  "agent_id": "agent-001",
  "status": "completed",
  "changes_proposed": 3,
  "transactions_analyzed": 50,
  "compute_time_ms": 2340,
  "impact": {
    "attribution_deltas": [
      {
        "transaction_id": "txn-x1y2z3",
        "query_text": "What theme does the user prefer?",
        "before": { "mem-a1b2c3": 0.82 },
        "after": { "mem-a1b2c3": 0.88 },
        "top_memory_changed": false,
        "max_score_delta": 0.06
      }
    ],
    "summary": {
      "transactions_affected": 12,
      "avg_score_delta": 0.04,
      "max_score_delta": 0.15,
      "new_memories_in_top3": 2
    },
    "contradictions": {
      "new_contradictions": [],
      "resolved_contradictions": [{ ... }],
      "net_change": -1
    },
    "coverage": {
      "gaps_before": 5,
      "gaps_after": 3,
      "gap_change": -2
    },
    "chi": {
      "before": 0.72,
      "after": 0.81,
      "delta": 0.09
    },
    "financial": {
      "portfolio_roi_before": 3.2,
      "portfolio_roi_after": 4.1,
      "estimated_monthly_savings": 8.50
    }
  }
}`,
    category: "counterfactual",
  },
  {
    method: "GET",
    path: "/api/v1/counterfactual/{session_id}",
    summary: "Get staging session",
    description: "Returns the current state and results of a counterfactual staging session.",
    params: [
      { name: "session_id", type: "string", required: true, description: "Session UUID" },
    ],
    response: `{
  "session_id": "cf-sess-001",
  "agent_id": "agent-001",
  "status": "completed",
  "changes_proposed": 3,
  "transactions_analyzed": 50,
  "compute_time_ms": 2340,
  "impact": { ... }
}`,
    category: "counterfactual",
  },
  {
    method: "POST",
    path: "/api/v1/counterfactual/{session_id}/commit",
    summary: "Commit staging session",
    description:
      "Commits all proposed changes from a counterfactual session into the live memory store. This is irreversible — take a snapshot first if you want rollback capability.",
    params: [
      { name: "session_id", type: "string", required: true, description: "Session UUID" },
    ],
    response: `{
  "status": "committed",
  "session_id": "cf-sess-001"
}`,
    category: "counterfactual",
  },
  {
    method: "DELETE",
    path: "/api/v1/counterfactual/{session_id}",
    summary: "Discard staging session",
    description: "Discards a counterfactual session without applying any changes.",
    params: [
      { name: "session_id", type: "string", required: true, description: "Session UUID" },
    ],
    response: `{
  "status": "discarded",
  "session_id": "cf-sess-001"
}`,
    category: "counterfactual",
  },

  // ── Grounding ────────────────────
  {
    method: "POST",
    path: "/api/v1/grounding/scan",
    summary: "Contamination scan",
    description:
      "Runs a full contamination detection scan across an agent's memories. Evaluates provenance, corroboration, empirical validation, and counterfactual importance for each memory.",
    body: `{
  "agent_id": "agent-001",
  "transaction_window": 100
}`,
    response: `{
  "total_memories": 1247,
  "trusted": 1180,
  "uncertain": 42,
  "suspect": 20,
  "contaminated": 5,
  "system_contamination_rate": 0.004,
  "compute_time_ms": 4500,
  "flags": [
    {
      "memory_id": "mem-suspect-001",
      "grounding_score": 0.23,
      "provenance_score": 0.1,
      "corroboration_score": 0.3,
      "empirical_score": 0.2,
      "counterfactual_score": 0.3,
      "risk_level": "suspect",
      "reasons": ["No provenance chain", "Low corroboration"],
      "recommended_action": "quarantine"
    }
  ]
}`,
    category: "grounding",
  },
  {
    method: "POST",
    path: "/api/v1/grounding/gate",
    summary: "Gate-check memory",
    description:
      "Evaluates whether a new memory should be stored. Checks grounding score, contradiction risk, and redundancy before the memory enters the store. Use this as a write-time guard.",
    body: `{
  "content": "The CEO announced Q4 revenue of $2.3B.",
  "agent_id": "agent-001",
  "source_type": "user_input"
}`,
    response: `{
  "should_store": true,
  "grounding_score": 0.78,
  "risk_level": "trusted",
  "reasons": ["Strong provenance from user input"],
  "contradicts_existing": [],
  "redundant_with": ["mem-rev-q3"]
}`,
    category: "grounding",
  },
  {
    method: "POST",
    path: "/api/v1/grounding/quarantine",
    summary: "Quarantine simulation",
    description:
      "Simulates the impact of quarantining (removing) specific memories. Shows how CHI, coverage, and affected transactions would change before you actually quarantine them.",
    body: `{
  "agent_id": "agent-001",
  "memory_ids": ["mem-suspect-001", "mem-suspect-002"],
  "transaction_window": 50
}`,
    response: `{
  "quarantined_count": 2,
  "chi_before": 0.72,
  "chi_after": 0.78,
  "chi_improvement": 0.06,
  "health_improved": true,
  "coverage_gap_change": 0,
  "transactions_affected": 7,
  "recommendation": "Safe to quarantine. CHI improves by 8.3%.",
  "compute_time_ms": 890
}`,
    category: "grounding",
  },

  // ── Dashboard Analytics ────────────────────
  {
    method: "GET",
    path: "/api/v1/dashboard/overview",
    summary: "Dashboard overview",
    description:
      "Returns system-wide metrics: total memories, transactions, attributions, agent summaries, Gini coefficient (attribution fairness), SNR, and waste rate.",
    response: `{
  "agents": [
    {
      "agent_id": "agent-001",
      "total_memories": 1247,
      "total_transactions": 583,
      "avg_attribution": 0.45,
      "tier_distribution": { "hot": 320, "warm": 612, "cold": 315 },
      "token_usage": { "input": 245000, "output": 89000 },
      "gini_coefficient": 0.34,
      "snr_db": 12.5,
      "waste_rate": 0.18,
      "contradiction_count": 3,
      "last_active": "2026-02-28T14:22:00Z"
    }
  ],
  "total_memories": 3420,
  "total_transactions": 1592,
  "total_attributions": 8734,
  "overall_gini": 0.38,
  "overall_snr_db": 11.2,
  "overall_waste_rate": 0.22
}`,
    category: "dashboard",
  },
  {
    method: "GET",
    path: "/api/v1/dashboard/timeseries",
    summary: "Time series metrics",
    description:
      "Returns time-bucketed metric data for charting. Supported metrics: attribution_avg, cost_total, transaction_count, memory_count, contradiction_rate.",
    params: [
      { name: "metric", type: "string", required: true, description: "Metric name (e.g. attribution_avg, cost_total)" },
      { name: "agent_id", type: "string", required: false, description: "Filter to a specific agent" },
      { name: "days", type: "integer", required: false, description: "Lookback period in days", default: "7" },
    ],
    response: `{
  "metric": "attribution_avg",
  "agent_id": "agent-001",
  "buckets": [
    { "timestamp": "2026-02-27T00:00:00Z", "value": 0.43, "count": 85 },
    { "timestamp": "2026-02-28T00:00:00Z", "value": 0.47, "count": 92 }
  ],
  "days": 7
}`,
    category: "dashboard",
  },
  {
    method: "GET",
    path: "/api/v1/dashboard/top-memories",
    summary: "Top performing memories",
    description: "Returns the highest-attribution memories sorted by total contribution.",
    params: [
      { name: "agent_id", type: "string", required: false, description: "Filter to a specific agent" },
      { name: "limit", type: "integer", required: false, description: "Number of results", default: "10" },
    ],
    response: `[
  {
    "memory_id": "mem-a1b2c3",
    "content": "The user prefers dark mode UI themes.",
    "agent_id": "agent-001",
    "total_attribution": 30.24,
    "mean_attribution": 0.72,
    "retrieval_count": 42,
    "tier": "hot"
  }
]`,
    category: "dashboard",
  },
  {
    method: "GET",
    path: "/api/v1/dashboard/cost-summary",
    summary: "Cost summary",
    description: "Returns aggregated cost metrics: total spend, input vs output breakdown, average cost per transaction.",
    params: [
      { name: "agent_id", type: "string", required: false, description: "Filter to a specific agent" },
    ],
    response: `{
  "agent_id": "agent-001",
  "total_cost": 45.67,
  "input_cost": 32.10,
  "output_cost": 13.57,
  "transaction_count": 583,
  "avg_cost_per_transaction": 0.078
}`,
    category: "dashboard",
  },

  // ── Agents ────────────────────
  {
    method: "GET",
    path: "/api/v1/agents",
    summary: "List agents",
    description: "Returns summary statistics for all registered agents.",
    response: `[
  {
    "agent_id": "agent-001",
    "total_memories": 1247,
    "total_transactions": 583,
    "avg_attribution": 0.45,
    "tier_distribution": { "hot": 320, "warm": 612, "cold": 315 },
    "gini_coefficient": 0.34,
    "snr_db": 12.5,
    "waste_rate": 0.18,
    "contradiction_count": 3,
    "last_active": "2026-02-28T14:22:00Z"
  }
]`,
    category: "dashboard",
  },
  {
    method: "GET",
    path: "/api/v1/agents/{agent_id}",
    summary: "Get agent detail",
    description: "Returns detailed information about a specific agent, including cost configuration and recent transactions.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    response: `{
  "agent_id": "agent-001",
  "total_memories": 1247,
  "total_transactions": 583,
  "avg_attribution": 0.45,
  "cost_config": {
    "agent_id": "agent-001",
    "input_token_cost": 0.00001,
    "output_token_cost": 0.00003,
    "provider": "openai",
    "model_id": "gpt-4o"
  },
  "recent_transactions": [...]
}`,
    category: "dashboard",
  },
  {
    method: "PUT",
    path: "/api/v1/agents/{agent_id}/cost-config",
    summary: "Set cost configuration",
    description:
      "Creates or updates cost configuration for an agent. Token costs are used to calculate financial metrics (ROI, PnL) for memory attribution.",
    params: [
      { name: "agent_id", type: "string", required: true, description: "Agent ID" },
    ],
    body: `{
  "agent_id": "agent-001",
  "input_token_cost": 0.00001,
  "output_token_cost": 0.00003,
  "provider": "openai",
  "model_id": "gpt-4o"
}`,
    response: `{
  "agent_id": "agent-001",
  "input_token_cost": 0.00001,
  "output_token_cost": 0.00003,
  "provider": "openai",
  "model_id": "gpt-4o",
  "updated_at": "2026-02-28T15:00:00Z"
}`,
    category: "dashboard",
  },
];

// ── Helpers ──────────────────────────────────────────────────────────────

const METHOD_COLORS: Record<HttpMethod, { color: string; bg: string; border: string }> = {
  GET: { color: "#73bf69", bg: "rgba(115,191,105,0.10)", border: "rgba(115,191,105,0.25)" },
  POST: { color: "#5794f2", bg: "rgba(87,148,242,0.10)", border: "rgba(87,148,242,0.25)" },
  PUT: { color: "#ff9830", bg: "rgba(255,152,48,0.10)", border: "rgba(255,152,48,0.25)" },
  PATCH: { color: "#b877d9", bg: "rgba(184,119,217,0.10)", border: "rgba(184,119,217,0.25)" },
  DELETE: { color: "#f2495c", bg: "rgba(242,73,92,0.10)", border: "rgba(242,73,92,0.25)" },
};

// ── Page component ───────────────────────────────────────────────────────

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState<SectionId>("getting-started");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedEndpoints, setExpandedEndpoints] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const filteredEndpoints = useMemo(() => {
    if (!searchQuery.trim()) return ENDPOINTS;
    const q = searchQuery.toLowerCase();
    return ENDPOINTS.filter(
      (e) =>
        e.path.toLowerCase().includes(q) ||
        e.summary.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        e.method.toLowerCase().includes(q)
    );
  }, [searchQuery]);

  const sectionEndpoints = useMemo(() => {
    return filteredEndpoints.filter((e) => e.category === activeSection);
  }, [filteredEndpoints, activeSection]);

  const toggleEndpoint = useCallback((id: string) => {
    setExpandedEndpoints((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const copyToClipboard = useCallback((text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }, []);

  const hasSectionEndpoints = (sectionId: SectionId) => {
    const categories: Record<SectionId, string | null> = {
      "getting-started": null,
      "authentication": null,
      "sdk-core": null,
      "sdk-types": null,
      "integrations": null,
      "tui-monitor": null,
      "memories": "memories",
      "transactions": "transactions",
      "attribution": "attribution",
      "health": "health",
      "lifecycle": "lifecycle",
      "snapshots": "snapshots",
      "counterfactual": "counterfactual",
      "grounding": "grounding",
      "dashboard": "dashboard",
      "websocket": null,
      "errors": null,
      "rate-limits": null,
    };
    return categories[sectionId] !== null;
  };

  return (
    <div className="flex flex-col" style={{ gap: "var(--panel-gap)" }}>
      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1>API Documentation</h1>
            <span
              className="px-2.5 py-1 text-[12px] font-mono font-bold uppercase tracking-wider rounded-sm"
              style={{
                background: "rgba(115,191,105,0.10)",
                color: "#73bf69",
                border: "1px solid rgba(115,191,105,0.25)",
              }}
            >
              v1
            </span>
          </div>
          <p
            className="mt-2 text-[15px]"
            style={{ color: "var(--grafana-text-secondary)" }}
          >
            Complete reference for the CortexOS Memory Observability API
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className="px-3 py-1.5 text-[13px] font-mono rounded-sm"
            style={{
              background: "#0b0c0e",
              border: "1px solid var(--panel-border)",
              color: "var(--grafana-text-secondary)",
            }}
          >
            Base URL: http://localhost:8000
          </span>
        </div>
      </div>

      {/* ── Main layout: sidebar + content ──────────────────────────── */}
      <div
        className="grid grid-cols-1 lg:grid-cols-12"
        style={{ gap: "var(--panel-gap)" }}
      >
        {/* Left sidebar navigation */}
        <div className="lg:col-span-3">
          <div
            className="flex flex-col overflow-hidden"
            style={{
              position: "sticky",
              top: 16,
              maxHeight: "calc(100vh - 32px)",
              background: "var(--panel-bg)",
              border: "1px solid var(--panel-border)",
              borderRadius: "var(--panel-radius)",
            }}
          >
            {/* Search */}
            <div
              className="px-4 py-3"
              style={{ borderBottom: "1px solid var(--panel-border)" }}
            >
              <div className="relative">
                <Search
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: "var(--grafana-text-muted)" }}
                />
                <input
                  type="text"
                  placeholder="Search endpoints..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-[14px] font-mono focus:outline-none transition-colors"
                  style={{
                    background: "#0b0c0e",
                    border: "1px solid var(--panel-border)",
                    borderRadius: "2px",
                    color: "var(--grafana-text-secondary)",
                  }}
                />
              </div>
            </div>

            {/* Nav items */}
            <nav className="flex flex-col py-1.5 overflow-y-auto flex-1">
              {NAV_SECTIONS.map((section, idx) => {
                const active = activeSection === section.id;
                const Icon = section.icon;
                return (
                  <div key={section.id}>
                  {section.divider && (
                    <div
                      className="px-4 pt-4 pb-1.5 text-[10px] uppercase tracking-[0.15em] font-bold"
                      style={{ color: "var(--grafana-text-muted)" }}
                    >
                      {section.divider}
                    </div>
                  )}
                  <button
                    onClick={() => setActiveSection(section.id)}
                    className="flex items-center gap-3 px-4 py-2.5 text-left text-[14px] transition-colors relative"
                    style={{
                      background: active ? "rgba(115,191,105,0.06)" : "transparent",
                      color: active ? "var(--grafana-green)" : "var(--grafana-text-secondary)",
                    }}
                    onMouseEnter={(e) => {
                      if (!active) {
                        e.currentTarget.style.background = "var(--panel-bg-hover)";
                        e.currentTarget.style.color = "var(--grafana-text-primary)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!active) {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.color = "var(--grafana-text-secondary)";
                      }
                    }}
                  >
                    {active && (
                      <span
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-sm"
                        style={{ background: "var(--grafana-green)" }}
                      />
                    )}
                    <Icon size={16} strokeWidth={1.5} />
                    <span className="truncate">{section.label}</span>
                  </button>
                  </div>
                );
              })}
            </nav>
          </div>
        </div>

        {/* Right content area */}
        <div className="lg:col-span-9 flex flex-col" style={{ gap: "var(--panel-gap)" }}>
          {/* Getting Started */}
          {activeSection === "getting-started" && (
            <>
              <Panel title="Overview">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    CortexOS is an observability layer for AI agent memory. It sits between your memory system and the LLM, tells you which memories influenced each response, what they cost, and whether they helped or hurt. The API follows RESTful conventions with JSON request/response bodies.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3" style={{ gap: "var(--panel-gap)" }}>
                    <FeatureCard
                      icon={Database}
                      title="Memory Management"
                      description="CRUD operations with tiered storage (hot/warm/cold), semantic search, and automatic embedding generation."
                    />
                    <FeatureCard
                      icon={Activity}
                      title="Attribution Scoring"
                      description="Shapley-based attribution tells you exactly which memory influenced each response and by how much."
                    />
                    <FeatureCard
                      icon={Shield}
                      title="Health & Compliance"
                      description="Contradiction detection, contamination scanning, provenance tracking, and GDPR-compliant erasure."
                    />
                  </div>
                </div>
              </Panel>

              <Panel title="Quick Start">
                <div className="flex flex-col gap-5">
                  <Step
                    number={1}
                    title="Install the SDK"
                    copyId="qs-1"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                    code={`pip install cortexos`}
                  />
                  <Step
                    number={2}
                    title="Configure your API key"
                    copyId="qs-2"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                    code={`import cortexos\n\ncortexos.configure(api_key="cx-your-key")`}
                  />
                  <Step
                    number={3}
                    title="Verify an LLM response"
                    copyId="qs-3"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                    code={`result = cortexos.check(\n    response="The return window is 30 days.",\n    sources=["Return policy: 30-day window for all items."]\n)\n\nprint(result.hallucination_index)  # 0.0 = fully grounded\nprint(result.passed)               # True (HI < 0.3)\nprint(result.claims[0].verdict)    # "GROUNDED"`}
                  />
                  <Step
                    number={4}
                    title="Gate a memory before storing"
                    copyId="qs-4"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                    code={`gate = cortexos.gate(\n    memory="Revenue grew 500% last quarter.",\n    sources=["Revenue grew 10% in Q4."]\n)\n\nprint(gate.grounded)        # False\nprint(gate.flagged_claims)  # [{"text": "...", "verdict": "NUM_MISMATCH"}]`}
                  />
                  <Step
                    number={5}
                    title="Launch the TUI monitor"
                    copyId="qs-5"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                    code={`pip install "cortexos[tui]"\ncortexos -k cx-your-api-key`}
                  />
                </div>
              </Panel>

              <Panel title="Core Concepts">
                <div className="flex flex-col gap-4">
                  <ConceptRow
                    term="Memory Unit"
                    definition="A single piece of knowledge stored by an agent. Each memory has content, an embedding vector, a tier (hot/warm/cold), criticality score, and metadata. Memories are the atomic building blocks of an agent's knowledge."
                  />
                  <ConceptRow
                    term="Transaction"
                    definition="A single LLM query-response cycle. Each transaction records the input query, output response, which memories were retrieved, token counts, and the model used. Transactions are the basis for attribution scoring."
                  />
                  <ConceptRow
                    term="Attribution Score"
                    definition="A Shapley-based value (0-1) indicating how much a specific memory influenced a given response. Computed via Efficient Amortized Shapley (EAS) for speed, with exact Shapley available for ground truth."
                  />
                  <ConceptRow
                    term="Memory Tier"
                    definition='Storage classification — "hot" (frequently accessed, high cost), "warm" (moderate access), or "cold" (archived, low cost). CortexOS recommends tier changes based on usage patterns.'
                  />
                  <ConceptRow
                    term="CHI (Contextual Health Index)"
                    definition="A composite score (0-1) that measures overall memory system health. Factors in contradiction rate, retrieval efficiency, semantic drift, and memory quality."
                  />
                  <ConceptRow
                    term="Gini Coefficient"
                    definition="Measures attribution fairness (0-1). A low Gini means attribution is spread evenly across memories. A high Gini means a few memories dominate all responses."
                  />
                  <ConceptRow
                    term="SNR (Signal-to-Noise Ratio)"
                    definition="Expressed in dB. Higher SNR means memories that are retrieved actually contribute to responses. Low SNR means many retrieved memories add noise without value."
                  />
                  <ConceptRow
                    term="Waste Rate"
                    definition="Percentage of memories with negative ROI — costing more in tokens than they contribute in attribution value. The lifecycle engine recommends archiving these."
                  />
                  <ConceptRow
                    term="Grounding Score"
                    definition="A composite score evaluating how well a memory is grounded in reality. Combines provenance, corroboration, empirical validation, and counterfactual importance."
                  />
                </div>
              </Panel>
            </>
          )}

          {/* Authentication */}
          {activeSection === "authentication" && (
            <>
              <Panel title="API Key Authentication">
                <div className="flex flex-col gap-5">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    All SDK and API requests require a CortexOS API key. Keys are prefixed with <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>cx-</code>. Get your key at <span style={{ color: "#8ab8ff" }}>cortexa.ink</span>.
                  </p>
                  <div className="flex flex-col gap-3">
                    <span className="text-[14px] font-medium" style={{ color: "var(--grafana-text-primary)" }}>
                      Option 1: Pass directly to client
                    </span>
                    <CodeBlock
                      code={`from cortexos import Cortex\n\ncx = Cortex(\n    api_key="cx-...",\n    base_url="https://api.cortexa.ink",\n    timeout=30.0,\n    max_retries=3,\n)`}
                      id="auth-direct"
                      copiedId={copiedId}
                      onCopy={copyToClipboard}
                    />
                  </div>
                  <div className="flex flex-col gap-3">
                    <span className="text-[14px] font-medium" style={{ color: "var(--grafana-text-primary)" }}>
                      Option 2: Module-level configure
                    </span>
                    <CodeBlock
                      code={`import cortexos\n\ncortexos.configure(\n    api_key="cx-...",\n    base_url="https://api.cortexa.ink",\n)\n\n# All subsequent calls use these defaults\nresult = cortexos.check(response="...", sources=["..."])`}
                      id="auth-module"
                      copiedId={copiedId}
                      onCopy={copyToClipboard}
                    />
                  </div>
                  <div className="flex flex-col gap-3">
                    <span className="text-[14px] font-medium" style={{ color: "var(--grafana-text-primary)" }}>
                      Option 3: Environment variables
                    </span>
                    <CodeBlock
                      code={`export CORTEX_API_KEY=cx-...\nexport CORTEX_URL=https://api.cortexa.ink  # optional, has default`}
                      id="auth-env"
                      copiedId={copiedId}
                      onCopy={copyToClipboard}
                    />
                  </div>
                </div>
              </Panel>
              <Panel title="Environment Variables">
                <div className="overflow-x-auto">
                  <table className="w-full text-[14px]">
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Variable</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Description</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Default</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>CORTEX_API_KEY</td>
                        <td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>API key for authentication</td>
                        <td className="px-4 py-3 font-mono" style={{ color: "#f2495c" }}>required</td>
                      </tr>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>CORTEX_URL</td>
                        <td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Base URL for the CortexOS engine</td>
                        <td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>https://api.cortexa.ink</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Panel>
            </>
          )}

          {/* WebSocket */}
          {activeSection === "websocket" && (
            <>
              <Panel title="WebSocket Real-Time Events">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    CortexOS provides a WebSocket endpoint for streaming real-time events. The dashboard uses this for live updates without polling.
                  </p>

                  <div className="flex flex-col gap-2">
                    <span className="text-[14px] font-medium" style={{ color: "var(--grafana-text-primary)" }}>
                      Connection
                    </span>
                    <CodeBlock
                      code={`ws://localhost:8000/api/v1/ws`}
                      id="ws-url"
                      copiedId={copiedId}
                      onCopy={copyToClipboard}
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <span className="text-[14px] font-medium" style={{ color: "var(--grafana-text-primary)" }}>
                      Example client
                    </span>
                    <CodeBlock
                      code={`const ws = new WebSocket("ws://localhost:8000/api/v1/ws");\n\nws.onmessage = (event) => {\n  const msg = JSON.parse(event.data);\n  console.log(msg.type, msg.data);\n  // msg.sequence_id — monotonic counter\n  // msg.type — event type (see below)\n  // msg.data — event payload\n};\n\nws.onclose = () => {\n  // Reconnect with exponential backoff\n};`}
                      id="ws-example"
                      copiedId={copiedId}
                      onCopy={copyToClipboard}
                    />
                  </div>
                </div>
              </Panel>

              <Panel title="Event Types">
                <div className="flex flex-col gap-0">
                  <EventTypeRow
                    type="transaction_created"
                    description="Fired when a new transaction is recorded. Payload includes the full transaction object."
                  />
                  <EventTypeRow
                    type="attribution_scored"
                    description="Fired when attribution scores are computed for a transaction. Includes all scores and the transaction ID."
                  />
                  <EventTypeRow
                    type="memory_update"
                    description="Fired when a memory is created, updated, or deleted. Includes the memory ID and change type."
                  />
                  <EventTypeRow
                    type="contradiction"
                    description="Fired when a new contradiction is detected between two memories. Includes both memory IDs and confidence."
                  />
                  <EventTypeRow
                    type="alert"
                    description="Fired when a health metric crosses a threshold. Includes the metric name, current value, and severity."
                  />
                  <EventTypeRow
                    type="lifecycle_executed"
                    description="Fired when lifecycle recommendations are applied. Includes counts of archived, promoted, and consolidated memories."
                  />
                  <EventTypeRow
                    type="agent_updated"
                    description="Fired when an agent's summary statistics are recalculated. Includes the updated agent summary."
                  />
                </div>
              </Panel>

              <Panel title="Message Format">
                <CodeBlock
                  code={`{\n  "sequence_id": 1042,\n  "type": "transaction_created",\n  "data": {\n    "id": "txn-x1y2z3",\n    "agent_id": "agent-001",\n    "query_text": "What theme does the user prefer?",\n    "input_tokens": 45,\n    "output_tokens": 12,\n    "model": "gpt-4o",\n    "status": "completed"\n  }\n}`}
                  id="ws-message-format"
                  copiedId={copiedId}
                  onCopy={copyToClipboard}
                />
              </Panel>
            </>
          )}

          {/* Errors */}
          {activeSection === "errors" && (
            <>
              <Panel title="SDK Exception Hierarchy">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    All SDK exceptions inherit from CortexError. Integrations use CortexOSError for memory-specific errors.
                  </p>
                  <CodeBlock
                    code={`from cortexos import Cortex, CortexError, AuthError, RateLimitError, ServerError\n\ncx = Cortex(api_key="cx-...")\n\ntry:\n    result = cx.check(response="...", sources=["..."])\nexcept AuthError:\n    print("Invalid or missing API key (401/403)")\nexcept RateLimitError as e:\n    print(f"Rate limited — retry after {e.retry_after}s")\nexcept ServerError:\n    print("Server error (5xx)")\nexcept CortexError:\n    print("Other SDK error")`}
                    id="sdk-error-example"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                  <CodeBlock
                    code={`CortexError                       # Base for all SDK errors\n├── AuthError                     # 401/403 — invalid/missing API key\n├── RateLimitError                # 429 — too many requests\n│   └── .retry_after: float       #   seconds to wait\n├── MemoryNotFoundError           # 404 — memory ID not found\n├── ValidationError               # 422 — invalid request payload\n└── ServerError                   # 5xx — unexpected server error\n\nCortexOSError                     # Base for integration errors\n├── MemoryBlockedError            # Memory write blocked by shield/gate\n│   ├── .is_injection: bool       #   was it an injection attempt?\n│   └── .reason: str              #   why it was blocked\n└── VerificationUnavailableError  # API unreachable (fail-open)`}
                    id="sdk-error-hierarchy"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>

              <Panel title="Retry Behavior">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    The HTTP layer automatically retries transient errors with exponential backoff: 0.5s × 2^attempt, up to max_retries (default 3).
                  </p>
                  <div className="grid grid-cols-2" style={{ gap: "var(--panel-gap)" }}>
                    <div className="p-4 rounded-sm" style={{ background: "rgba(115,191,105,0.06)", border: "1px solid rgba(115,191,105,0.20)" }}>
                      <span className="text-[13px] font-medium block mb-2" style={{ color: "#73bf69" }}>Retried</span>
                      <p className="text-[14px] font-mono" style={{ color: "var(--grafana-text-secondary)" }}>429 (rate limit), 502 (bad gateway), 503 (unavailable), 504 (timeout)</p>
                    </div>
                    <div className="p-4 rounded-sm" style={{ background: "rgba(242,73,92,0.06)", border: "1px solid rgba(242,73,92,0.20)" }}>
                      <span className="text-[13px] font-medium block mb-2" style={{ color: "#f2495c" }}>Not Retried</span>
                      <p className="text-[14px] font-mono" style={{ color: "var(--grafana-text-secondary)" }}>401 (auth), 404 (not found), 422 (validation)</p>
                    </div>
                  </div>
                </div>
              </Panel>

              <Panel title="Engine API Error Format">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Engine API endpoints return standard HTTP status codes with a consistent JSON error body.
                  </p>
                  <CodeBlock
                    code={`{\n  "detail": "Memory not found",\n  "status": 404\n}`}
                    id="error-format"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>

              <Panel title="Status Codes">
                <div className="flex flex-col gap-0">
                  <StatusCodeRow code="200" label="OK" description="Request succeeded. Response body contains the result." color="#73bf69" />
                  <StatusCodeRow code="201" label="Created" description="Resource created successfully. Response body contains the new resource." color="#73bf69" />
                  <StatusCodeRow code="204" label="No Content" description="Request succeeded with no response body (e.g., DELETE)." color="#73bf69" />
                  <StatusCodeRow code="400" label="Bad Request" description="Invalid request body, missing required fields, or malformed parameters." color="#ff9830" />
                  <StatusCodeRow code="404" label="Not Found" description="The requested resource does not exist." color="#ff9830" />
                  <StatusCodeRow code="409" label="Conflict" description="Resource conflict (e.g., duplicate memory, session already committed)." color="#ff9830" />
                  <StatusCodeRow code="422" label="Unprocessable Entity" description="Request body is valid JSON but fails validation (e.g., invalid tier value)." color="#ff9830" />
                  <StatusCodeRow code="429" label="Too Many Requests" description="Rate limit exceeded. Check Rate Limits section for details." color="#f2495c" />
                  <StatusCodeRow code="500" label="Internal Error" description="Unexpected server error. Check API logs for details." color="#f2495c" />
                </div>
              </Panel>
            </>
          )}

          {/* Rate Limits */}
          {activeSection === "rate-limits" && (
            <Panel title="Rate Limits">
              <div className="flex flex-col gap-4">
                <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                  Self-hosted CortexOS does not enforce rate limits by default. When deployed behind an API gateway, we recommend the following limits:
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Endpoint Category</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Recommended Limit</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      <RateLimitRow category="Read operations (GET)" limit="1000 req/min" notes="List, get, and search endpoints" />
                      <RateLimitRow category="Write operations (POST/PATCH)" limit="200 req/min" notes="Create, update memory and transactions" />
                      <RateLimitRow category="Exact attribution" limit="10 req/min" notes="Computationally expensive" />
                      <RateLimitRow category="Contamination scan" limit="5 req/min" notes="Full agent memory scan" />
                      <RateLimitRow category="Counterfactual staging" limit="20 req/min" notes="Simulation is moderately expensive" />
                      <RateLimitRow category="WebSocket connections" limit="50 concurrent" notes="Per-client limit" />
                    </tbody>
                  </table>
                </div>
                <div
                  className="p-4 rounded-sm text-[14px]"
                  style={{
                    background: "rgba(87,148,242,0.06)",
                    border: "1px solid rgba(87,148,242,0.20)",
                    color: "var(--grafana-text-secondary)",
                    lineHeight: 1.7,
                  }}
                >
                  Rate limit responses return <code className="font-mono px-1 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>429 Too Many Requests</code> with a <code className="font-mono px-1 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>Retry-After</code> header indicating seconds until the next allowed request.
                </div>
              </div>
            </Panel>
          )}

          {/* SDK Core */}
          {activeSection === "sdk-core" && (
            <>
              <Panel title="Installation">
                <div className="flex flex-col gap-5">
                  <CodeBlock
                    code={`# Core SDK (check + gate)\npip install cortexos\n\n# With TUI monitor\npip install "cortexos[tui]"\n\n# With dev/test tools\npip install "cortexos[dev]"\n\n# Everything\npip install "cortexos[tui,dev]"`}
                    id="sdk-install"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                          <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Extra</th>
                          <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Packages</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>core</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-secondary)" }}>httpx &gt;=0.27, pydantic &gt;=2.7</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>tui</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-secondary)" }}>textual &gt;=0.80, httpx-sse &gt;=0.4, click &gt;=8</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>dev</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-secondary)" }}>pytest &gt;=8, pytest-asyncio &gt;=0.23, respx &gt;=0.21</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Panel>

              <Panel title="cortexos.check()">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    One-liner hallucination check. Verifies an LLM response against source documents and returns a hallucination index (0.0 = fully grounded, 1.0 = fully hallucinated).
                  </p>
                  <CodeBlock
                    code={`import cortexos\n\ncortexos.configure(api_key="cx-your-key")\n\nresult = cortexos.check(\n    response="The product ships in 2-3 business days.",\n    sources=["Shipping: 2-3 business day delivery for all orders."]\n)\n\nprint(result.hallucination_index)   # 0.0\nprint(result.passed)                # True\nprint(result.total_claims)          # 1\nprint(result.claims[0].verdict)     # "GROUNDED"`}
                    id="sdk-check"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>

              <Panel title="cortexos.gate()">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    One-liner memory gating — should this memory be stored? Returns whether the memory is grounded in the provided sources, with details on any flagged claims.
                  </p>
                  <CodeBlock
                    code={`gate = cortexos.gate(\n    memory="Revenue grew 500% last quarter.",\n    sources=["Revenue grew 10% in Q4."]\n)\n\nprint(gate.grounded)        # False\nprint(gate.flagged_claims)  # [{"text": "...", "verdict": "NUM_MISMATCH"}]`}
                    id="sdk-gate"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>

              <Panel title="Cortex (Sync Client)">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Full-featured synchronous client with connection pooling and retries. Supports context manager for automatic cleanup.
                  </p>
                  <CodeBlock
                    code={`from cortexos import Cortex\n\ncx = Cortex(\n    api_key="cx-...",                       # required (or CORTEX_API_KEY env)\n    base_url="https://api.cortexa.ink",     # optional\n    agent_id="default",                      # identifies this agent\n    timeout=30.0,                            # request timeout in seconds\n    max_retries=3,                           # retry count for transient errors\n)\n\n# Context manager support\nwith Cortex(api_key="cx-...") as cx:\n    result = cx.check(\n        response="Our SLA guarantees 99.9% uptime.",\n        sources=[\n            "SLA terms: We guarantee 99.9% uptime for enterprise plans.",\n            "Standard plans have 99.5% uptime SLA."\n        ],\n        agent_id="support-bot",  # optional override\n    )\n\n    print(result.hallucination_index)   # 0.0–1.0\n    print(result.total_claims)          # number of atomic claims\n    print(result.grounded_count)        # claims verified\n    print(result.hallucinated_count)    # claims contradicted\n    print(result.latency_ms)            # pipeline latency\n    print(result.passed)                # True if HI < 0.3\n    print(result.passed_at(0.5))        # True if HI < custom threshold\n\n    for claim in result.claims:\n        print(f"  {claim.verdict}: {claim.text}")\n        print(f"    confidence: {claim.confidence}")\n        print(f"    quote: {claim.source_quote}")\n\n    # Memory gating\n    gate = cx.gate(\n        memory="User prefers overnight shipping.",\n        sources=["User selected standard shipping on last 3 orders."]\n    )\n    if not gate.grounded:\n        print("Blocked — hallucinated memory")\n\n    # Health check\n    status = cx.health()  # {"status": "ok", ...}`}
                    id="sdk-sync-client"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>

              <Panel title="AsyncCortex (Async Client)">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Identical API to Cortex, but all methods are async. Ideal for high-throughput or asyncio-based applications.
                  </p>
                  <CodeBlock
                    code={`import asyncio\nfrom cortexos import AsyncCortex\n\nasync def main():\n    async with AsyncCortex(api_key="cx-...") as cx:\n        result = await cx.check(\n            response="The CEO founded the company in 2015.",\n            sources=["Founded in 2015 by Jane Smith."]\n        )\n        print(result.hallucination_index)\n\n        gate = await cx.gate(\n            memory="Customer is a platinum member.",\n            sources=["Customer tier: Gold."]\n        )\n        print(gate.grounded)  # False\n\n        health = await cx.health()\n\nasyncio.run(main())`}
                    id="sdk-async-client"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>

              <Panel title="VerificationClient (Low-Level)">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Thin async HTTP client used internally by integrations. Includes <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>shield()</code> for injection detection.
                  </p>
                  <CodeBlock
                    code={`from cortexos import VerificationClient\n\nvc = VerificationClient(api_key="cx-...", base_url="https://api.cortexa.ink")\n\n# Async usage\nresult = await vc.check(response="...", sources=["..."])\ngate   = await vc.gate(candidate_memory="...", sources=["..."])\nshield = await vc.shield(candidate_memory="...", source_type="user_input")\n\n# Sync wrappers (for non-async contexts)\nresult = vc.check_sync(response="...", sources=["..."])\ngate   = vc.gate_sync(candidate_memory="...", sources=["..."])\nshield = vc.shield_sync(candidate_memory="...", source_type="user_input")`}
                    id="sdk-verification-client"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>
            </>
          )}

          {/* SDK Result Types */}
          {activeSection === "sdk-types" && (
            <>
              <Panel title="CheckResult">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Returned by <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>check()</code>. Contains the hallucination index, per-claim breakdown, and pass/fail status.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead><tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Field</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Type</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Description</th>
                      </tr></thead>
                      <tbody>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>hallucination_index</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>float</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>0.0 (fully grounded) — 1.0 (fully hallucinated)</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>total_claims</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>int</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Number of atomic claims extracted</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>grounded_count</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>int</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Claims verified by sources</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>hallucinated_count</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>int</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Claims contradicted by sources</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>opinion_count</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>int</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Subjective/uncheckable claims</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>claims</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>list[ClaimResult]</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Per-claim breakdown</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>latency_ms</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>float</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Pipeline latency in milliseconds</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>passed</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>bool</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>True if HI &lt; 0.3</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>passed_at(threshold)</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>method</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>True if HI &lt; given threshold</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Panel>

              <Panel title="ClaimResult">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>Individual claim verdict within a CheckResult.</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead><tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Field</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Type</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Description</th>
                      </tr></thead>
                      <tbody>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>text</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>The atomic claim text</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>grounded</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>bool</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Whether the claim is supported</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>verdict</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>GROUNDED, NUM_MISMATCH, UNSUPPORTED, or OPINION</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>reason</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Explanation of the verdict</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>source_quote</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str | None</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Supporting quote from sources</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>confidence</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>float</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Model confidence (0.0–1.0)</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Panel>

              <Panel title="Verdict Types">
                <div className="flex flex-col gap-0">
                  <EventTypeRow type="GROUNDED" description="Claim is supported by the source documents." />
                  <EventTypeRow type="NUM_MISMATCH" description="Numerical value doesn't match the sources." />
                  <EventTypeRow type="UNSUPPORTED" description="Claim has no support in the sources." />
                  <EventTypeRow type="OPINION" description="Subjective claim — cannot be fact-checked." />
                </div>
              </Panel>

              <Panel title="GateResult">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>Returned by <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>gate()</code>. Indicates whether a memory should be stored.</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead><tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Field</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Type</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Description</th>
                      </tr></thead>
                      <tbody>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>grounded</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>bool</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>True if memory passed the gate</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>hallucination_index</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>float</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>HI score</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>flagged_claims</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>list[dict]</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Claims that failed verification</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>suggested_corrections</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>list[dict] | None</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Suggested fixes (if available)</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Panel>

              <Panel title="ShieldResult">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>Returned by <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>shield()</code> via VerificationClient. Detects injection attacks and anomalies.</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead><tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Field</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Type</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Description</th>
                      </tr></thead>
                      <tbody>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>safe</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>bool</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>True if no threats detected</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>threat_type</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str | None</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>INSTRUCTION_INJECTION, ANOMALY, etc.</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>severity</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str | None</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>CRITICAL, WARN, or INFO</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>blocked_content</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str | None</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>The flagged content</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>source_type</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Origin type of the content</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Panel>
            </>
          )}

          {/* Integrations */}
          {activeSection === "integrations" && (
            <>
              <Panel title="Mem0 Integration">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Drop-in wrapper for Mem0. Intercepts writes with CortexOS shield + gate verification while passing reads through unchanged. Install with <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>pip install cortexos mem0ai</code>.
                  </p>
                  <CodeBlock
                    code={`from cortexos.integrations.mem0 import Mem0Client\n\nmem = Mem0Client(\n    mem0_api_key="m0-...",\n    cortex_api_key="cx-...",\n    sources=["Company policy: 30-day return window."],\n    shield_enabled=True,       # detect injection attacks\n    gate_enabled=True,         # verify grounding before write\n    gate_threshold=0.3,        # block if HI >= 0.3\n    on_block=lambda mem, result: print(f"Blocked: {mem}"),\n    on_threat=lambda mem, result: print(f"Threat: {result.threat_type}"),\n)\n\n# Verified writes — shield + gate run before write reaches Mem0\nmem.add("User prefers express shipping.", user_id="u123")\n\n# Unverified reads — pass through directly to Mem0\nresults = mem.search("shipping preference", user_id="u123")\nmemories = mem.get_all(user_id="u123")\nmem.update(memory_id="...", text="updated text")\nmem.delete(memory_id="...")\nhistory = mem.history(memory_id="...")`}
                    id="int-mem0"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                  <div className="p-4 rounded-sm" style={{ background: "rgba(87,148,242,0.06)", border: "1px solid rgba(87,148,242,0.20)" }}>
                    <p className="text-[14px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.7 }}>
                      <strong style={{ color: "var(--grafana-text-primary)" }}>What happens on add():</strong> 1) Shield checks for injection/anomaly. 2) Gate verifies grounding against sources. 3) If both pass, write reaches Mem0. 4) If CortexOS API is unreachable — <strong style={{ color: "#73bf69" }}>fail-open</strong> (write proceeds with warning).
                    </p>
                  </div>
                </div>
              </Panel>

              <Panel title="SuperMemory Integration">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Drop-in wrapper for SuperMemory. Install with <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>pip install cortexos supermemory</code>.
                  </p>
                  <CodeBlock
                    code={`from cortexos.integrations.supermemory import SuperMemoryClient\n\nsm = SuperMemoryClient(\n    supermemory_api_key="sm-...",\n    cortex_api_key="cx-...",\n    sources=["Product catalog: ..."],\n    shield_enabled=True,\n    gate_enabled=True,\n    gate_threshold=0.3,\n)\n\n# Verified writes\nsm.add(content="Product X costs $99.", container_tag="products")\nsm.add_batch(documents=[\n    {"content": "Fact 1", "container_tag": "facts"},\n    {"content": "Fact 2", "container_tag": "facts"},\n])\n\n# Unverified reads\nresults = sm.search(q="pricing")\ndoc = sm.get(document_id="...")\nsm.update(document_id="...", content="updated")\nsm.delete(document_id="...")`}
                    id="int-supermem"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>

              <Panel title="Building Custom Integrations">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Extend <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>VerifiedMemoryClient</code> to wrap any memory provider with CortexOS verification.
                  </p>
                  <CodeBlock
                    code={`from cortexos.integrations.base import VerifiedMemoryClient\n\nclass MyMemoryClient(VerifiedMemoryClient):\n    def __init__(self, my_provider, **cortex_kwargs):\n        super().__init__(**cortex_kwargs)\n        self._provider = my_provider\n\n    def write(self, text, user_id=None):\n        # This runs shield + gate before writing\n        self._verify_write_sync(text, user_id=user_id)\n        return self._provider.write(text)\n\n    async def write_async(self, text, user_id=None):\n        await self._verify_write(text, user_id=user_id)\n        return await self._provider.write_async(text)\n\n    # Reads pass through — no verification needed\n    def read(self, query):\n        return self._provider.read(query)`}
                    id="int-custom"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead><tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Parameter</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Type</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Description</th>
                      </tr></thead>
                      <tbody>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>cortex_api_key</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>str | None</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>API key (or env var)</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>sources</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>list | Callable | None</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Static docs or fn(user_id) → docs</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>shield_enabled</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>bool</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Run injection detection (default: True)</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>gate_enabled</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>bool</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Run grounding verification (default: True)</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>gate_threshold</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>float</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Block if HI ≥ threshold (default: 0.3)</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>on_block / on_threat</td><td className="px-4 py-3 font-mono" style={{ color: "var(--grafana-text-muted)" }}>Callable | None</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Callbacks for blocked writes / detected threats</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Panel>
            </>
          )}

          {/* TUI Monitor */}
          {activeSection === "tui-monitor" && (
            <>
              <Panel title="TUI Monitor">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    A real-time terminal dashboard for monitoring all verification activity across your agents. Install with <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>pip install &quot;cortexos[tui]&quot;</code>.
                  </p>
                  <CodeBlock
                    code={`# Launch monitor\ncortexos -k cx-your-api-key\n\n# Custom engine URL\ncortexos -k cx-your-api-key -u https://your-engine.example.com`}
                    id="tui-launch"
                    copiedId={copiedId}
                    onCopy={copyToClipboard}
                  />
                </div>
              </Panel>

              <Panel title="Keyboard Shortcuts">
                <div className="overflow-x-auto">
                  <table className="w-full text-[14px]">
                    <thead><tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                      <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Key</th>
                      <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Action</th>
                    </tr></thead>
                    <tbody>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>1–5</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Switch tabs: Feed, Claims, Memory, Agents, Inspect</td></tr>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>p</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Pause / resume event stream</td></tr>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>c</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Clear session data</td></tr>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>f</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Cycle filter: All → Check → Gate → Shield</td></tr>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>s</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Cycle sort (Claims tab): Time → Verdict → Confidence</td></tr>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>e</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Export event to JSON (Inspect tab)</td></tr>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>: or Ctrl+\</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Open command palette</td></tr>
                      <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>q</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Quit</td></tr>
                    </tbody>
                  </table>
                </div>
              </Panel>

              <Panel title="Tabs">
                <div className="flex flex-col gap-0">
                  <ConceptRow term="Tab 1 — Feed" definition="Live stream of all verification events. Left side shows scrolling event log with type, HI score, claim counts, and verdict summary. Right sidebar shows session stats (total checks, grounded%, halluc%, avg HI, latency) plus HI trend sparkline. Events are color-coded: green (HI < 0.2), yellow-green (0.2–0.4), orange (0.4–0.6), red-orange (0.6–0.8), hot pink (≥ 0.8)." />
                  <ConceptRow term="Tab 2 — Claims" definition="Searchable table of every individual claim across all checks. Columns: #, Time, Verdict, Confidence, Claim Text. Verdict icons: ● GROUNDED (green), ✗ NUM_MISMATCH (red), ○ UNSUPPORTED (orange), ◇ OPINION (gray). Press Enter to jump to Inspect tab for selected event." />
                  <ConceptRow term="Tab 3 — Memory" definition="Memory operation log tracking all gate and shield activity. Shows writes attempted/blocked/blocked %, injections caught, anomalies detected, and agent trust distribution. Gate pass = green, gate block = red with HI score, shield injection = red background alert." />
                  <ConceptRow term="Tab 4 — Agents" definition="Per-agent leaderboard ranked by hallucination risk (worst first). Columns: Agent, Checks, Avg HI, Halluc%, Trend, Last Seen. Mini sparklines showing HI trend per agent (last 5 values) with risk banner for high-hallucination agents." />
                  <ConceptRow term="Tab 5 — Inspect" definition="Deep-dive into a single verification event. Shows event type, timestamp, latency, HI score, hallucination count, full claim breakdown with verdict icons, confidence bars, reason text, source quotes, and attribution scores. Press 'e' to export to JSON." />
                </div>
              </Panel>

              <Panel title="Command Palette">
                <div className="flex flex-col gap-4">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.8 }}>
                    Open with <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>:</code> or <code className="font-mono px-1.5 py-0.5 rounded-sm" style={{ background: "#0b0c0e", color: "#8ab8ff" }}>Ctrl+\</code>. Type a command and press Enter.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[14px]">
                      <thead><tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Command</th>
                        <th className="text-left px-4 py-2.5 text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Description</th>
                      </tr></thead>
                      <tbody>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>clear</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Clear all session data</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>export</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Export session to /tmp/cortex_session.json</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>filter check|gate|all</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Filter events by type</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>threshold</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Display current gate threshold</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>connect</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Show connection URL</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>feed|claims|memory|agents|inspect</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Switch to named tab</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>pause</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Toggle pause</td></tr>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)" }}><td className="px-4 py-3 font-mono" style={{ color: "#8ab8ff" }}>quit</td><td className="px-4 py-3" style={{ color: "var(--grafana-text-secondary)" }}>Exit monitor</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </Panel>
            </>
          )}

          {/* Dynamic endpoint sections */}
          {hasSectionEndpoints(activeSection) && (
            <>
              {sectionEndpoints.length === 0 && searchQuery ? (
                <Panel title="No Results">
                  <p className="text-[15px]" style={{ color: "var(--grafana-text-muted)" }}>
                    No endpoints match &ldquo;{searchQuery}&rdquo; in this section.
                  </p>
                </Panel>
              ) : (
                sectionEndpoints.map((endpoint) => {
                  const id = `${endpoint.method}-${endpoint.path}`;
                  const expanded = expandedEndpoints.has(id);
                  return (
                    <EndpointCard
                      key={id}
                      endpoint={endpoint}
                      expanded={expanded}
                      copiedId={copiedId}
                      onToggle={() => toggleEndpoint(id)}
                      onCopy={copyToClipboard}
                    />
                  );
                })
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{
        background: "var(--panel-bg)",
        border: "1px solid var(--panel-border)",
        borderRadius: "var(--panel-radius)",
      }}
    >
      <div
        className="flex items-center px-5 shrink-0"
        style={{ height: 44, borderBottom: "1px solid var(--panel-border)" }}
      >
        <span className="text-[15px] font-medium" style={{ color: "var(--grafana-text-primary)" }}>
          {title}
        </span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  title: string;
  description: string;
}) {
  return (
    <div
      className="flex flex-col gap-2 p-4 rounded-sm"
      style={{
        background: "#0b0c0e",
        border: "1px solid var(--panel-border)",
      }}
    >
      <div className="flex items-center gap-2.5">
        <Icon size={18} strokeWidth={1.5} />
        <span className="text-[15px] font-medium" style={{ color: "var(--grafana-text-primary)" }}>
          {title}
        </span>
      </div>
      <p className="text-[14px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.7 }}>
        {description}
      </p>
    </div>
  );
}

function Step({
  number,
  title,
  code,
  copyId,
  copiedId,
  onCopy,
}: {
  number: number;
  title: string;
  code: string;
  copyId: string;
  copiedId: string | null;
  onCopy: (text: string, id: string) => void;
}) {
  return (
    <div className="flex gap-4">
      <div
        className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full text-[13px] font-bold"
        style={{
          background: "rgba(87,148,242,0.15)",
          color: "#5794f2",
          border: "1px solid rgba(87,148,242,0.30)",
        }}
      >
        {number}
      </div>
      <div className="flex-1 flex flex-col gap-2.5">
        <span className="text-[15px] font-medium" style={{ color: "var(--grafana-text-primary)" }}>
          {title}
        </span>
        <CodeBlock code={code} id={copyId} copiedId={copiedId} onCopy={onCopy} />
      </div>
    </div>
  );
}

function ConceptRow({ term, definition }: { term: string; definition: string }) {
  return (
    <div
      className="flex flex-col gap-1.5 py-4 px-0"
      style={{ borderBottom: "1px solid var(--panel-border)" }}
    >
      <span className="text-[15px] font-medium font-mono" style={{ color: "#8ab8ff" }}>
        {term}
      </span>
      <p className="text-[14px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.7 }}>
        {definition}
      </p>
    </div>
  );
}

function CodeBlock({
  code,
  id,
  copiedId,
  onCopy,
}: {
  code: string;
  id: string;
  copiedId: string | null;
  onCopy: (text: string, id: string) => void;
}) {
  const isCopied = copiedId === id;
  return (
    <div className="relative group">
      <pre
        className="p-4 rounded-sm text-[13px] font-mono leading-relaxed overflow-x-auto"
        style={{
          background: "#0b0c0e",
          border: "1px solid var(--panel-border)",
          color: "var(--grafana-text-secondary)",
        }}
      >
        {code}
      </pre>
      <button
        onClick={() => onCopy(code, id)}
        className="absolute top-2 right-2 p-1.5 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity"
        style={{
          background: "var(--panel-bg)",
          border: "1px solid var(--panel-border)",
          color: isCopied ? "var(--grafana-green)" : "var(--grafana-text-muted)",
        }}
        aria-label="Copy to clipboard"
      >
        {isCopied ? <Check size={12} /> : <Copy size={12} />}
      </button>
    </div>
  );
}

function EventTypeRow({ type, description }: { type: string; description: string }) {
  return (
    <div
      className="flex items-start gap-4 px-0 py-4"
      style={{ borderBottom: "1px solid var(--panel-border)" }}
    >
      <code
        className="shrink-0 px-2.5 py-1 text-[13px] font-mono rounded-sm"
        style={{
          background: "rgba(87,148,242,0.10)",
          color: "#5794f2",
          border: "1px solid rgba(87,148,242,0.25)",
        }}
      >
        {type}
      </code>
      <p className="text-[14px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.6 }}>
        {description}
      </p>
    </div>
  );
}

function StatusCodeRow({
  code,
  label,
  description,
  color,
}: {
  code: string;
  label: string;
  description: string;
  color: string;
}) {
  return (
    <div
      className="flex items-start gap-4 px-0 py-4"
      style={{ borderBottom: "1px solid var(--panel-border)" }}
    >
      <span
        className="shrink-0 w-12 text-center text-[14px] font-mono font-bold rounded-sm py-0.5"
        style={{ color }}
      >
        {code}
      </span>
      <span
        className="shrink-0 w-40 text-[14px] font-medium"
        style={{ color: "var(--grafana-text-primary)" }}
      >
        {label}
      </span>
      <p className="text-[14px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.6 }}>
        {description}
      </p>
    </div>
  );
}

function RateLimitRow({
  category,
  limit,
  notes,
}: {
  category: string;
  limit: string;
  notes: string;
}) {
  return (
    <tr
      className="transition-colors"
      style={{ borderBottom: "1px solid var(--panel-border)" }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--panel-bg-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <td className="px-4 py-3 font-mono text-[14px]" style={{ color: "var(--grafana-text-primary)" }}>
        {category}
      </td>
      <td className="px-4 py-3 text-[14px] font-mono" style={{ color: "#73bf69" }}>
        {limit}
      </td>
      <td className="px-4 py-3 text-[14px]" style={{ color: "var(--grafana-text-muted)" }}>
        {notes}
      </td>
    </tr>
  );
}

function EndpointCard({
  endpoint,
  expanded,
  copiedId,
  onToggle,
  onCopy,
}: {
  endpoint: EndpointDef;
  expanded: boolean;
  copiedId: string | null;
  onToggle: () => void;
  onCopy: (text: string, id: string) => void;
}) {
  const mc = METHOD_COLORS[endpoint.method];
  const id = `${endpoint.method}-${endpoint.path}`;

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{
        background: "var(--panel-bg)",
        border: `1px solid ${expanded ? mc.border : "var(--panel-border)"}`,
        borderRadius: "var(--panel-radius)",
      }}
    >
      {/* Header (clickable) */}
      <button
        onClick={onToggle}
        className="flex items-center gap-3 px-5 w-full text-left transition-colors"
        style={{
          height: 52,
          borderBottom: expanded ? `1px solid var(--panel-border)` : "none",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--panel-bg-hover)")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
      >
        {/* Method badge */}
        <span
          className="shrink-0 px-2.5 py-1 text-[13px] font-mono font-bold uppercase rounded-sm"
          style={{ background: mc.bg, color: mc.color, border: `1px solid ${mc.border}` }}
        >
          {endpoint.method}
        </span>

        {/* Path */}
        <span className="text-[15px] font-mono" style={{ color: "var(--grafana-text-primary)" }}>
          {endpoint.path}
        </span>

        {/* Summary */}
        <span className="text-[14px] ml-auto mr-2 hidden md:block" style={{ color: "var(--grafana-text-muted)" }}>
          {endpoint.summary}
        </span>

        {/* Chevron */}
        <ChevronRight
          size={16}
          className="shrink-0 transition-transform"
          style={{
            color: "var(--grafana-text-muted)",
            transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
          }}
        />
      </button>

      {/* Expanded body */}
      {expanded && (
        <div className="p-5 flex flex-col gap-5">
          {/* Description */}
          <p className="text-[14px]" style={{ color: "var(--grafana-text-secondary)", lineHeight: 1.7 }}>
            {endpoint.description}
          </p>

          {/* Parameters */}
          {endpoint.params && endpoint.params.length > 0 && (
            <div className="flex flex-col gap-3">
              <span className="text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>
                Parameters
              </span>
              <div className="overflow-x-auto">
                <table className="w-full text-[14px]">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                      <th className="text-left px-4 py-2.5 text-[11px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Name</th>
                      <th className="text-left px-4 py-2.5 text-[11px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Type</th>
                      <th className="text-left px-4 py-2.5 text-[11px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Required</th>
                      <th className="text-left px-4 py-2.5 text-[11px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {endpoint.params.map((p) => (
                      <tr key={p.name} style={{ borderBottom: "1px solid var(--panel-border)" }}>
                        <td className="px-4 py-2.5 font-mono" style={{ color: "#8ab8ff" }}>
                          {p.name}
                        </td>
                        <td className="px-4 py-2.5 font-mono" style={{ color: "var(--grafana-text-muted)" }}>
                          {p.type}
                        </td>
                        <td className="px-4 py-2.5">
                          {p.required ? (
                            <span style={{ color: "#f2495c" }}>required</span>
                          ) : (
                            <span style={{ color: "var(--grafana-text-muted)" }}>
                              optional{p.default ? ` (${p.default})` : ""}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5" style={{ color: "var(--grafana-text-secondary)" }}>
                          {p.description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Request body */}
          {endpoint.body && (
            <div className="flex flex-col gap-3">
              <span className="text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>
                Request Body
              </span>
              <CodeBlock code={endpoint.body} id={`${id}-body`} copiedId={copiedId} onCopy={onCopy} />
            </div>
          )}

          {/* Response */}
          <div className="flex flex-col gap-3">
            <span className="text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>
              Response
            </span>
            <CodeBlock code={endpoint.response} id={`${id}-response`} copiedId={copiedId} onCopy={onCopy} />
          </div>

          {/* cURL example */}
          <div className="flex flex-col gap-3">
            <span className="text-[12px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>
              Example
            </span>
            <CodeBlock
              code={generateCurlExample(endpoint)}
              id={`${id}-curl`}
              copiedId={copiedId}
              onCopy={onCopy}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function generateCurlExample(endpoint: EndpointDef): string {
  const base = "http://localhost:8000";
  let path = endpoint.path;

  // Replace path params with sample values
  path = path.replace("{memory_id}", "mem-a1b2c3");
  path = path.replace("{transaction_id}", "txn-x1y2z3");
  path = path.replace("{agent_id}", "agent-001");
  path = path.replace("{contradiction_id}", "ctr-001");
  path = path.replace("{session_id}", "cf-sess-001");
  path = path.replace("{snapshot_id}", "snap-001");
  path = path.replace("{id_a}", "snap-001");
  path = path.replace("{id_b}", "snap-002");

  // Add query params for GET requests
  if (endpoint.method === "GET" && endpoint.params?.some((p) => !p.required && !path.includes(p.name))) {
    const qps = endpoint.params
      .filter((p) => !p.required && !path.includes(p.name))
      .slice(0, 2)
      .map((p) => `${p.name}=${p.default || "value"}`)
      .join("&");
    if (qps) path += `?${qps}`;
  }

  if (endpoint.method === "GET") {
    return `curl ${base}${path}`;
  }

  if (endpoint.method === "DELETE") {
    return `curl -X DELETE ${base}${path}`;
  }

  if (endpoint.body) {
    return `curl -X ${endpoint.method} ${base}${path} \\\n  -H "Content-Type: application/json" \\\n  -d '${endpoint.body.replace(/\n/g, "\n  ")}'`;
  }

  return `curl -X ${endpoint.method} ${base}${path} \\\n  -H "Content-Type: application/json"`;
}

"use client";

import { useState, useMemo, useCallback } from "react";
import {
  Search,
  Trash2,
  Eye,
  Loader2,
  FileText,
  Copy,
  ChevronDown,
  X,
  CheckCircle2,
  Shield,
  Plus,
  Minus,
} from "lucide-react";
import {
  ProvenanceGraph,
  ProvenanceGraphLegend,
} from "@/components/dashboard/ProvenanceGraph";
import { StatPanel } from "@/components/dashboard/StatPanel";
import { GrafanaPanel } from "@/components/dashboard/GrafanaPanel";
import {
  mockProvenanceNodes,
  mockProvenanceEdges,
  mockDeletionRequests,
} from "@/lib/mock-data";
import { formatTimestamp } from "@/lib/utils";
import type {
  ProvenanceNode,
  ProvenanceNodeType,
  ProvenanceEdgeType,
  DeletionRequest,
  DeletionStatus,
} from "@/lib/types";

// ── Constants ────────────────────────────────────────────────────────────

const ALL_NODE_TYPES: ProvenanceNodeType[] = [
  "interaction",
  "memory",
  "summary",
  "embedding",
  "response",
];

// ── Derived stats ────────────────────────────────────────────────────────

const memNodeIds = new Set(
  mockProvenanceNodes.filter((n) => n.type === "memory").map((n) => n.id)
);
const connectedMemNodes = new Set<string>();
for (const e of mockProvenanceEdges) {
  if (memNodeIds.has(e.source)) connectedMemNodes.add(e.source);
  if (memNodeIds.has(e.target)) connectedMemNodes.add(e.target);
}
const provenanceCoverage =
  memNodeIds.size > 0
    ? Math.round((connectedMemNodes.size / memNodeIds.size) * 100)
    : 0;

const uniqueUsers = new Set<string>();
for (const n of mockProvenanceNodes) {
  if (n.userId) uniqueUsers.add(n.userId);
}

const pendingDeletionCount = mockDeletionRequests.filter(
  (d) => d.status === "pending" || d.status === "processing"
).length;

// ── Audit log (mock) ─────────────────────────────────────────────────────

interface AuditEntry {
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR";
  message: string;
}

const mockAuditLog: AuditEntry[] = [
  {
    timestamp: "2026-02-20 14:23:11",
    level: "INFO",
    message:
      "Deletion DR-001 completed. 12 nodes removed. Certificate: sha256:a1b2c3d4...123456",
  },
  {
    timestamp: "2026-02-20 10:45:33",
    level: "INFO",
    message:
      "Provenance graph integrity check passed. 153 nodes, 302 edges verified.",
  },
  {
    timestamp: "2026-02-19 09:15:44",
    level: "INFO",
    message:
      "Deletion DR-003 started. User: user-1023. Footprint: 567 nodes.",
  },
  {
    timestamp: "2026-02-19 09:12:01",
    level: "WARN",
    message:
      "Provenance gap detected: Memory #302 has no creation edge. Orphan node flagged.",
  },
  {
    timestamp: "2026-02-18 16:40:22",
    level: "INFO",
    message:
      "Compliance check passed. Coverage: 94%. All deletion requests within SLA.",
  },
  {
    timestamp: "2026-02-18 11:30:00",
    level: "INFO",
    message:
      "Deletion DR-004 submitted. User: user-7782. Estimated footprint: 89 nodes.",
  },
  {
    timestamp: "2026-02-17 22:15:10",
    level: "WARN",
    message:
      "Cascade analysis for DR-003 found 47 downstream nodes. Review required before execution.",
  },
  {
    timestamp: "2026-02-17 08:00:00",
    level: "INFO",
    message:
      "Scheduled compliance audit started. Scanning provenance graph for orphan nodes.",
  },
  {
    timestamp: "2026-02-16 14:22:18",
    level: "INFO",
    message:
      "Deletion DR-002 verified. Certificate hash: sha256:b2c3d4e5...123456. Audit complete.",
  },
  {
    timestamp: "2026-02-15 16:40:22",
    level: "INFO",
    message:
      "Compliance check passed. Coverage: 94%. GDPR status: compliant.",
  },
  {
    timestamp: "2026-02-14 09:10:55",
    level: "ERROR",
    message:
      "Provenance edge pe-147 references deleted node pn-89. Edge removed during cleanup.",
  },
  {
    timestamp: "2026-02-13 12:00:00",
    level: "INFO",
    message:
      "Retention policy executed. 3 memories past 180-day threshold archived.",
  },
];

// ── Page ─────────────────────────────────────────────────────────────────

export default function CompliancePage() {
  // Graph state
  const [selectedNode, setSelectedNode] = useState<ProvenanceNode | null>(
    null
  );
  const [highlightUserId, setHighlightUserId] = useState<string | null>(
    null
  );
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);
  const [visibleTypes, setVisibleTypes] = useState<Set<ProvenanceNodeType>>(
    new Set(ALL_NODE_TYPES)
  );
  const [userSearchInput, setUserSearchInput] = useState("");

  // Deletion console
  const [newDeletionUserId, setNewDeletionUserId] = useState("");

  // Certificate modal
  const [certModalRequest, setCertModalRequest] =
    useState<DeletionRequest | null>(null);

  // Toggle node type
  const toggleNodeType = useCallback((type: ProvenanceNodeType) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  // Highlight user
  const handleHighlightUser = useCallback(() => {
    const trimmed = userSearchInput.trim();
    if (!trimmed) {
      setHighlightUserId(null);
      return;
    }
    setHighlightUserId(trimmed);
    setDeletingUserId(null);
  }, [userSearchInput]);

  // Simulate deletion
  const handleSimulateDeletion = useCallback(() => {
    if (!highlightUserId) return;
    setDeletingUserId(highlightUserId);
    setTimeout(() => setDeletingUserId(null), 4000);
  }, [highlightUserId]);

  // Selected node stats
  const selectedNodeStats = useMemo(() => {
    if (!selectedNode) return null;
    const inbound = mockProvenanceEdges.filter(
      (e) => e.target === selectedNode.id
    );
    const outbound = mockProvenanceEdges.filter(
      (e) => e.source === selectedNode.id
    );
    return { inbound, outbound };
  }, [selectedNode]);

  return (
    <div className="flex flex-col" style={{ gap: "var(--panel-gap)" }}>
      {/* ── ROW 1: Stat panels ─────────────────────────────────── */}
      <div className="grid-4">
        <StatPanel
          label="Provenance Coverage"
          value={`${provenanceCoverage}%`}
          color="green"
        />
        <StatPanel
          label="Tracked Users"
          value={`${uniqueUsers.size} footprints`}
          color="blue"
        />
        <StatPanel
          label="Provenance Edges"
          value={mockProvenanceEdges.length.toLocaleString()}
          color="cyan"
        />
        <StatPanel
          label="Pending Deletions"
          value={`${pendingDeletionCount} requests`}
          color={pendingDeletionCount > 0 ? "yellow" : "green"}
        />
      </div>

      {/* ── ROW 2: Graph (70%) + Deletion Console (30%) ────────── */}
      <div
        className="grid grid-cols-1 lg:grid-cols-10"
        style={{ gap: "var(--panel-gap)" }}
      >
        {/* Left: Provenance Graph */}
        <div className="lg:col-span-7">
          <GrafanaPanel title="Memory Provenance Graph" noPadding>
            {/* Controls bar */}
            <div
              className="flex flex-wrap items-center gap-3 px-4 py-2.5"
              style={{ borderBottom: "1px solid var(--panel-border)" }}
            >
              {/* User search */}
              <div className="relative">
                <Search
                  size={13}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: "var(--grafana-text-muted)" }}
                />
                <input
                  type="text"
                  placeholder="Filter by user ID..."
                  value={userSearchInput}
                  onChange={(e) => setUserSearchInput(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && handleHighlightUser()
                  }
                  className="pl-8 pr-3 py-1.5 text-[12px] font-mono w-[160px] focus:outline-none transition-colors"
                  style={{
                    background: "#0b0c0e",
                    border: "1px solid var(--panel-border)",
                    borderRadius: "2px",
                    color: "var(--grafana-text-secondary)",
                  }}
                />
              </div>

              <button
                onClick={handleHighlightUser}
                className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium rounded-sm transition-colors"
                style={{
                  background: "transparent",
                  border: "1px solid var(--panel-border)",
                  color: "var(--grafana-text-primary)",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background =
                    "var(--panel-bg-hover)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
              >
                <Eye size={12} />
                Highlight
              </button>

              {highlightUserId && (
                <button
                  onClick={handleSimulateDeletion}
                  disabled={!!deletingUserId}
                  className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium rounded-sm transition-colors disabled:opacity-40"
                  style={{
                    background: "rgba(242,73,92,0.10)",
                    border: "1px solid rgba(242,73,92,0.30)",
                    color: "#f2495c",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background =
                      "rgba(242,73,92,0.18)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background =
                      "rgba(242,73,92,0.10)")
                  }
                >
                  <Trash2 size={12} />
                  Simulate Deletion
                </button>
              )}

              <div className="flex-1" />

              {/* Node type filters */}
              <div className="flex items-center gap-1">
                {ALL_NODE_TYPES.map((type) => {
                  const active = visibleTypes.has(type);
                  return (
                    <button
                      key={type}
                      onClick={() => toggleNodeType(type)}
                      className="px-2 py-1 text-[10px] font-mono rounded-sm transition-colors"
                      style={{
                        background: active
                          ? "var(--panel-bg-hover)"
                          : "transparent",
                        border: `1px solid ${active ? "var(--panel-border)" : "transparent"}`,
                        color: active
                          ? "var(--grafana-text-secondary)"
                          : "var(--grafana-text-disabled)",
                        textDecoration: active ? "none" : "line-through",
                      }}
                    >
                      {type}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Legend */}
            <div
              className="px-4 py-2"
              style={{
                borderBottom: "1px solid var(--panel-border)",
              }}
            >
              <ProvenanceGraphLegend />
            </div>

            {/* Graph area */}
            <div className="relative" style={{ height: 440 }}>
              <ProvenanceGraph
                selectedNodeId={selectedNode?.id ?? null}
                onSelectNode={setSelectedNode}
                highlightUserId={highlightUserId}
                deletingUserId={deletingUserId}
                visibleTypes={visibleTypes}
              />

              {/* Deletion overlay */}
              {deletingUserId && (
                <div
                  className="absolute top-3 left-3 px-3 py-2 rounded-sm flex items-center gap-2 text-[11px]"
                  style={{
                    background: "rgba(242,73,92,0.15)",
                    border: "1px solid rgba(242,73,92,0.30)",
                    color: "#f2495c",
                  }}
                >
                  <Loader2 size={13} className="animate-spin" />
                  Simulating cascade deletion for {deletingUserId}...
                </div>
              )}

              {/* Highlight info */}
              {highlightUserId && !deletingUserId && (
                <div
                  className="absolute top-3 left-3 px-3 py-2 rounded-sm flex items-center gap-2 text-[11px]"
                  style={{
                    background: "var(--panel-bg)",
                    border: "1px solid var(--panel-border)",
                    color: "var(--grafana-text-secondary)",
                  }}
                >
                  Highlighting footprint:{" "}
                  <span
                    className="font-mono"
                    style={{ color: "#5794f2" }}
                  >
                    {highlightUserId}
                  </span>
                  <button
                    onClick={() => {
                      setHighlightUserId(null);
                      setUserSearchInput("");
                    }}
                    className="ml-1"
                    style={{ color: "var(--grafana-text-muted)" }}
                  >
                    <X size={12} />
                  </button>
                </div>
              )}

              {/* Zoom buttons */}
              <div
                className="absolute bottom-3 right-3 flex flex-col gap-1"
              >
                <button
                  className="w-7 h-7 flex items-center justify-center rounded-sm transition-colors"
                  style={{
                    background: "var(--panel-bg)",
                    border: "1px solid var(--panel-border)",
                    color: "var(--grafana-text-muted)",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color =
                      "var(--grafana-text-primary)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color =
                      "var(--grafana-text-muted)")
                  }
                >
                  <Plus size={14} />
                </button>
                <button
                  className="w-7 h-7 flex items-center justify-center rounded-sm transition-colors"
                  style={{
                    background: "var(--panel-bg)",
                    border: "1px solid var(--panel-border)",
                    color: "var(--grafana-text-muted)",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color =
                      "var(--grafana-text-primary)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color =
                      "var(--grafana-text-muted)")
                  }
                >
                  <Minus size={14} />
                </button>
              </div>
            </div>

            {/* Selected node details (inline below graph) */}
            {selectedNode && (
              <div
                className="px-4 py-3 flex flex-wrap items-start gap-4"
                style={{
                  borderTop: "1px solid var(--panel-border)",
                }}
              >
                <div className="flex items-center gap-2">
                  <NodeTypeBadge type={selectedNode.type} />
                  <span
                    className="text-[13px] font-mono font-medium"
                    style={{ color: "var(--grafana-text-primary)" }}
                  >
                    {selectedNode.id}
                  </span>
                </div>
                <div
                  className="text-[12px] font-mono p-2 rounded-sm flex-1 min-w-[200px]"
                  style={{
                    background: "#0b0c0e",
                    border: "1px solid var(--panel-border)",
                    color: "var(--grafana-text-secondary)",
                  }}
                >
                  {selectedNode.label}
                </div>
                <div className="flex items-center gap-4 text-[10px]">
                  {selectedNode.userId && (
                    <span>
                      <span
                        style={{ color: "var(--grafana-text-muted)" }}
                      >
                        User:{" "}
                      </span>
                      <button
                        onClick={() => {
                          setUserSearchInput(selectedNode.userId!);
                          setHighlightUserId(selectedNode.userId!);
                        }}
                        className="font-mono"
                        style={{ color: "#5794f2" }}
                      >
                        {selectedNode.userId}
                      </button>
                    </span>
                  )}
                  <span
                    className="font-mono"
                    style={{ color: "var(--grafana-text-muted)" }}
                  >
                    {formatTimestamp(selectedNode.createdAt)}
                  </span>
                  {selectedNodeStats && (
                    <span
                      className="font-mono"
                      style={{ color: "var(--grafana-text-muted)" }}
                    >
                      {selectedNodeStats.inbound.length}↓{" "}
                      {selectedNodeStats.outbound.length}↑
                    </span>
                  )}
                </div>
              </div>
            )}
          </GrafanaPanel>
        </div>

        {/* Right: Deletion Console */}
        <div className="lg:col-span-3">
          <GrafanaPanel title="GDPR Deletion Requests" noPadding>
            {/* Deletion request table */}
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr
                    style={{
                      borderBottom: "1px solid var(--panel-border)",
                    }}
                  >
                    <th
                      className="text-left px-3 py-2 text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--grafana-text-muted)" }}
                    >
                      Request
                    </th>
                    <th
                      className="text-left px-2 py-2 text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--grafana-text-muted)" }}
                    >
                      Status
                    </th>
                    <th
                      className="text-right px-3 py-2 text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--grafana-text-muted)" }}
                    >
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {mockDeletionRequests.map((dr) => (
                    <DeletionRow
                      key={dr.id}
                      request={dr}
                      onHighlight={(userId) => {
                        setUserSearchInput(userId);
                        setHighlightUserId(userId);
                      }}
                      onViewCert={() => setCertModalRequest(dr)}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* New Deletion Request form */}
            <div
              className="px-3 py-3"
              style={{
                borderTop: "1px solid var(--panel-border)",
              }}
            >
              <div
                className="text-[10px] uppercase tracking-wider font-medium mb-2"
                style={{ color: "var(--grafana-text-muted)" }}
              >
                New Deletion Request
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="user-XXXX"
                  value={newDeletionUserId}
                  onChange={(e) => setNewDeletionUserId(e.target.value)}
                  className="flex-1 px-3 py-1.5 text-[12px] font-mono focus:outline-none transition-colors"
                  style={{
                    background: "#0b0c0e",
                    border: "1px solid var(--panel-border)",
                    borderRadius: "2px",
                    color: "var(--grafana-text-secondary)",
                  }}
                />
                <button
                  disabled={!newDeletionUserId.trim()}
                  className="px-3 py-1.5 text-[11px] font-medium rounded-sm transition-colors whitespace-nowrap disabled:opacity-30"
                  style={{
                    background: "rgba(242,73,92,0.10)",
                    border: "1px solid rgba(242,73,92,0.30)",
                    color: "#f2495c",
                  }}
                >
                  Submit
                </button>
              </div>
              <p
                className="text-[10px] mt-1.5"
                style={{ color: "var(--grafana-text-muted)" }}
              >
                Initiates SISA-compliant erasure with provenance cascade.
              </p>
            </div>
          </GrafanaPanel>
        </div>
      </div>

      {/* ── ROW 3: Audit Trail ─────────────────────────────────── */}
      <GrafanaPanel
        title="Audit Trail"
        headerRight={
          <span
            className="text-[10px] font-mono"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            {mockAuditLog.length} entries · newest first
          </span>
        }
        noPadding
      >
        <div className="overflow-y-auto max-h-[280px]">
          {mockAuditLog.map((entry, i) => (
            <div
              key={i}
              className="flex items-start gap-3 px-4 py-2 font-mono text-[12px] transition-colors"
              style={{
                borderBottom: "1px solid var(--panel-border)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background =
                  "var(--panel-bg-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "transparent")
              }
            >
              {/* Timestamp */}
              <span
                className="shrink-0 tabular-nums"
                style={{ color: "#6e7681" }}
              >
                {entry.timestamp}
              </span>

              {/* Level badge */}
              <LogLevelBadge level={entry.level} />

              {/* Message */}
              <span style={{ color: "#d8d9da" }}>{entry.message}</span>
            </div>
          ))}
        </div>
      </GrafanaPanel>

      {/* Certificate Modal */}
      {certModalRequest && certModalRequest.certificateHash && (
        <CertificateModal
          request={certModalRequest}
          onClose={() => setCertModalRequest(null)}
        />
      )}
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────

function NodeTypeBadge({ type }: { type: ProvenanceNodeType }) {
  const map: Record<
    ProvenanceNodeType,
    { bg: string; color: string; border: string }
  > = {
    interaction: {
      bg: "rgba(87,148,242,0.10)",
      color: "#5794f2",
      border: "rgba(87,148,242,0.25)",
    },
    memory: {
      bg: "rgba(115,191,105,0.10)",
      color: "#73bf69",
      border: "rgba(115,191,105,0.25)",
    },
    summary: {
      bg: "rgba(184,119,217,0.10)",
      color: "#b877d9",
      border: "rgba(184,119,217,0.25)",
    },
    embedding: {
      bg: "var(--panel-bg-hover)",
      color: "var(--grafana-text-muted)",
      border: "var(--panel-border)",
    },
    response: {
      bg: "var(--panel-bg-hover)",
      color: "var(--grafana-text-secondary)",
      border: "var(--panel-border)",
    },
  };
  const s = map[type];
  return (
    <span
      className="px-1.5 py-0.5 text-[10px] font-mono rounded-sm"
      style={{
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.border}`,
      }}
    >
      {type}
    </span>
  );
}

function LogLevelBadge({ level }: { level: AuditEntry["level"] }) {
  const map: Record<string, { color: string; bg: string }> = {
    INFO: { color: "#73bf69", bg: "rgba(115,191,105,0.10)" },
    WARN: { color: "#ff9830", bg: "rgba(255,152,48,0.10)" },
    ERROR: { color: "#f2495c", bg: "rgba(242,73,92,0.10)" },
  };
  const s = map[level];
  return (
    <span
      className="shrink-0 inline-flex items-center justify-center w-[42px] text-[10px] font-bold rounded-sm py-0.5"
      style={{ background: s.bg, color: s.color }}
    >
      {level}
    </span>
  );
}

function StatusBadge({ status }: { status: DeletionStatus }) {
  const map: Record<
    DeletionStatus,
    { color: string; bg: string; border: string; label: string }
  > = {
    pending: {
      color: "#ff9830",
      bg: "rgba(255,152,48,0.10)",
      border: "rgba(255,152,48,0.20)",
      label: "Pending",
    },
    processing: {
      color: "#5794f2",
      bg: "rgba(87,148,242,0.10)",
      border: "rgba(87,148,242,0.20)",
      label: "Processing",
    },
    completed: {
      color: "#73bf69",
      bg: "rgba(115,191,105,0.10)",
      border: "rgba(115,191,105,0.20)",
      label: "Completed",
    },
    verified: {
      color: "#73bf69",
      bg: "rgba(115,191,105,0.10)",
      border: "rgba(115,191,105,0.20)",
      label: "Verified",
    },
  };
  const s = map[status];
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide rounded-sm"
      style={{
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.border}`,
      }}
    >
      {status === "verified" && <CheckCircle2 size={10} />}
      {status === "processing" && (
        <Loader2 size={10} className="animate-spin" />
      )}
      {s.label}
    </span>
  );
}

function DeletionRow({
  request,
  onHighlight,
  onViewCert,
}: {
  request: DeletionRequest;
  onHighlight: (userId: string) => void;
  onViewCert: () => void;
}) {
  return (
    <tr
      style={{ borderBottom: "1px solid var(--panel-border)" }}
      className="transition-colors"
      onMouseEnter={(e) =>
        (e.currentTarget.style.background = "var(--panel-bg-hover)")
      }
      onMouseLeave={(e) =>
        (e.currentTarget.style.background = "transparent")
      }
    >
      <td className="px-3 py-2.5">
        <div className="flex flex-col gap-1">
          <span
            className="text-[12px] font-mono font-medium"
            style={{ color: "var(--grafana-text-primary)" }}
          >
            {request.id.toUpperCase()}
          </span>
          <button
            onClick={() => onHighlight(request.userId)}
            className="text-[11px] font-mono text-left transition-colors"
            style={{ color: "#5794f2" }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.color = "#8ab8ff")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.color = "#5794f2")
            }
          >
            {request.userId}
          </button>
          <div className="flex items-center gap-2 text-[10px]">
            <span style={{ color: "var(--grafana-text-muted)" }}>
              {formatTimestamp(request.requestedAt)}
            </span>
            <span style={{ color: "var(--grafana-text-muted)" }}>
              {request.footprintSize} nodes
            </span>
          </div>
        </div>
      </td>
      <td className="px-2 py-2.5">
        <StatusBadge status={request.status} />
      </td>
      <td className="px-3 py-2.5 text-right">
        {request.certificateHash && (
          <button
            onClick={onViewCert}
            className="text-[11px] font-medium transition-colors"
            style={{ color: "#6e9fff" }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.color = "#8ab8ff")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.color = "#6e9fff")
            }
          >
            View Cert
          </button>
        )}
      </td>
    </tr>
  );
}

function CertificateModal({
  request,
  onClose,
}: {
  request: DeletionRequest;
  onClose: () => void;
}) {
  return (
    <>
      <div
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.6)" }}
        onClick={onClose}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="w-full max-w-md overflow-hidden"
          style={{
            background: "var(--panel-bg)",
            border: "1px solid var(--panel-border)",
            borderRadius: "var(--panel-radius)",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 shrink-0"
            style={{
              height: 36,
              borderBottom: "1px solid var(--panel-border)",
            }}
          >
            <div className="flex items-center gap-2">
              <Shield size={14} style={{ color: "var(--grafana-green)" }} />
              <span
                className="text-[13px] font-medium"
                style={{ color: "var(--grafana-text-primary)" }}
              >
                Deletion Certificate
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-sm transition-colors"
              style={{ color: "var(--grafana-text-muted)" }}
            >
              <X size={14} />
            </button>
          </div>

          {/* Body */}
          <div className="px-4 py-4 flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <span style={{ color: "var(--grafana-text-muted)" }}>
                  Request ID
                </span>
                <div
                  className="font-mono mt-0.5"
                  style={{ color: "var(--grafana-text-primary)" }}
                >
                  {request.id.toUpperCase()}
                </div>
              </div>
              <div>
                <span style={{ color: "var(--grafana-text-muted)" }}>
                  User
                </span>
                <div
                  className="font-mono mt-0.5"
                  style={{ color: "#5794f2" }}
                >
                  {request.userId}
                </div>
              </div>
              <div>
                <span style={{ color: "var(--grafana-text-muted)" }}>
                  Completed
                </span>
                <div
                  className="font-mono mt-0.5"
                  style={{ color: "var(--grafana-text-primary)" }}
                >
                  {request.completedAt
                    ? formatTimestamp(request.completedAt)
                    : "—"}
                </div>
              </div>
              <div>
                <span style={{ color: "var(--grafana-text-muted)" }}>
                  Nodes Deleted
                </span>
                <div
                  className="font-mono mt-0.5"
                  style={{ color: "var(--grafana-text-primary)" }}
                >
                  {request.nodesDeleted}
                </div>
              </div>
            </div>

            {/* Hash */}
            <div>
              <span
                className="text-[10px] uppercase tracking-wider font-medium"
                style={{ color: "var(--grafana-text-muted)" }}
              >
                Certificate Hash
              </span>
              <div
                className="mt-1 flex items-center gap-2 p-2.5 rounded-sm font-mono text-[11px] break-all"
                style={{
                  background: "#0b0c0e",
                  border: "1px solid var(--panel-border)",
                  color: "var(--grafana-green)",
                }}
              >
                <span className="flex-1">
                  {request.certificateHash}
                </span>
                <button
                  onClick={() =>
                    navigator.clipboard.writeText(
                      request.certificateHash!
                    )
                  }
                  className="shrink-0 p-1 rounded-sm transition-colors"
                  style={{ color: "var(--grafana-text-muted)" }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color =
                      "var(--grafana-text-primary)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color =
                      "var(--grafana-text-muted)")
                  }
                >
                  <Copy size={12} />
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 text-[11px]">
              <CheckCircle2
                size={14}
                style={{ color: "var(--grafana-green)" }}
              />
              <span style={{ color: "var(--grafana-green)" }}>
                SISA-compliant erasure verified
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

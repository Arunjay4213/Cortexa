"use client";

import { useState, useMemo, useCallback } from "react";
import {
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Trash2,
  Shield,
  Clock,
  CheckCircle2,
  Loader2,
  AlertTriangle,
  FileText,
  Copy,
  ChevronDown,
  ChevronUp,
  Eye,
} from "lucide-react";
import { ProvenanceGraph, ProvenanceGraphLegend } from "@/components/dashboard/ProvenanceGraph";
import {
  mockProvenanceNodes,
  mockProvenanceEdges,
  mockDeletionRequests,
} from "@/lib/mock-data";
import { formatTimestamp, truncateText } from "@/lib/utils";
import type {
  ProvenanceNode,
  ProvenanceNodeType,
  ProvenanceEdgeType,
  DeletionRequest,
  DeletionStatus,
} from "@/lib/types";

// ── Constants ─────────────────────────────────────────────────────────────

const ALL_NODE_TYPES: ProvenanceNodeType[] = [
  "interaction",
  "memory",
  "summary",
  "embedding",
  "response",
];

const STATUS_CONFIG: Record<DeletionStatus, { icon: typeof CheckCircle2; color: string; bg: string; label: string }> = {
  verified: { icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/10", label: "Verified" },
  completed: { icon: Shield, color: "text-blue-400", bg: "bg-blue-500/10", label: "Completed" },
  processing: { icon: Loader2, color: "text-amber-400", bg: "bg-amber-500/10", label: "Processing" },
  pending: { icon: Clock, color: "text-zinc-400", bg: "bg-zinc-500/10", label: "Pending" },
};

// ── Page Component ────────────────────────────────────────────────────────

export default function CompliancePage() {
  // Graph state
  const [selectedNode, setSelectedNode] = useState<ProvenanceNode | null>(null);
  const [highlightUserId, setHighlightUserId] = useState<string | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);
  const [visibleTypes, setVisibleTypes] = useState<Set<ProvenanceNodeType>>(
    new Set(ALL_NODE_TYPES)
  );
  const [userSearchInput, setUserSearchInput] = useState("");

  // Deletion console state
  const [showDeletionConsole, setShowDeletionConsole] = useState(true);
  const [newDeletionUserId, setNewDeletionUserId] = useState("");

  // Unique user IDs from provenance nodes
  const userIds = useMemo(() => {
    const ids = new Set<string>();
    for (const n of mockProvenanceNodes) {
      if (n.userId) ids.add(n.userId);
    }
    return Array.from(ids).sort();
  }, []);

  // Toggle node type visibility
  const toggleNodeType = useCallback((type: ProvenanceNodeType) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }, []);

  // Handle user search / highlight
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
    // Auto-reset after animation
    setTimeout(() => setDeletingUserId(null), 4000);
  }, [highlightUserId]);

  // Stats for selected node
  const selectedNodeStats = useMemo(() => {
    if (!selectedNode) return null;
    const inbound = mockProvenanceEdges.filter((e) => e.target === selectedNode.id);
    const outbound = mockProvenanceEdges.filter((e) => e.source === selectedNode.id);
    return { inbound, outbound };
  }, [selectedNode]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-zinc-200 tracking-wide">
            GDPR Compliance & Provenance
          </h2>
          <p className="text-[11px] text-zinc-600 mt-0.5">
            Interactive provenance graph · Deletion simulation · Right-to-erasure console
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="text-zinc-500">
            {mockProvenanceNodes.length} nodes · {mockProvenanceEdges.length} edges
          </span>
          <span className="text-zinc-500">·</span>
          <span className="text-zinc-500">
            {mockDeletionRequests.filter((d) => d.status === "pending" || d.status === "processing").length} active deletions
          </span>
        </div>
      </div>

      {/* Main Two-Panel Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6" style={{ minHeight: "calc(100vh - 200px)" }}>
        {/* ── Left: Graph Panel ──────────────────────────────────────── */}
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
          {/* Controls bar */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800 flex-wrap">
            {/* User search */}
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" />
                <input
                  type="text"
                  placeholder="user-XXXX"
                  value={userSearchInput}
                  onChange={(e) => setUserSearchInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleHighlightUser()}
                  className="pl-8 pr-3 py-1.5 text-[12px] font-mono bg-zinc-900 border border-zinc-700 rounded-md text-zinc-300 placeholder:text-zinc-600 w-[140px] focus:outline-none focus:border-zinc-500"
                />
              </div>
              <button
                onClick={handleHighlightUser}
                className="px-3 py-1.5 text-[11px] font-medium bg-zinc-800 border border-zinc-700 rounded-md text-zinc-300 hover:bg-zinc-700 transition-colors"
              >
                <Eye size={13} className="inline mr-1 -mt-0.5" />
                Highlight
              </button>
              {highlightUserId && (
                <button
                  onClick={handleSimulateDeletion}
                  disabled={!!deletingUserId}
                  className="px-3 py-1.5 text-[11px] font-medium bg-rose-500/10 border border-rose-500/30 rounded-md text-rose-400 hover:bg-rose-500/20 transition-colors disabled:opacity-40"
                >
                  <Trash2 size={13} className="inline mr-1 -mt-0.5" />
                  Simulate Deletion
                </button>
              )}
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Node type filters */}
            <div className="flex items-center gap-1.5">
              {ALL_NODE_TYPES.map((type) => {
                const active = visibleTypes.has(type);
                return (
                  <button
                    key={type}
                    onClick={() => toggleNodeType(type)}
                    className={`px-2 py-1 text-[10px] font-mono rounded border transition-colors ${
                      active
                        ? "border-zinc-600 bg-zinc-800 text-zinc-300"
                        : "border-zinc-800 bg-zinc-900/30 text-zinc-600 line-through"
                    }`}
                  >
                    {type}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Legend */}
          <div className="px-4 py-2 border-b border-zinc-800/50">
            <ProvenanceGraphLegend />
          </div>

          {/* Graph area */}
          <div className="flex-1 relative min-h-[400px]">
            <ProvenanceGraph
              selectedNodeId={selectedNode?.id ?? null}
              onSelectNode={setSelectedNode}
              highlightUserId={highlightUserId}
              deletingUserId={deletingUserId}
              visibleTypes={visibleTypes}
            />

            {/* Deletion animation overlay */}
            {deletingUserId && (
              <div className="absolute top-3 left-3 px-3 py-2 bg-rose-950/80 border border-rose-500/40 rounded-md animate-fade-in">
                <div className="flex items-center gap-2 text-[11px] text-rose-300">
                  <Loader2 size={13} className="animate-spin" />
                  Simulating cascade deletion for {deletingUserId}...
                </div>
              </div>
            )}

            {/* Highlight info */}
            {highlightUserId && !deletingUserId && (
              <div className="absolute top-3 left-3 px-3 py-2 bg-zinc-900/90 border border-zinc-700 rounded-md">
                <div className="text-[11px] text-zinc-300">
                  Highlighting footprint: <span className="font-mono text-blue-400">{highlightUserId}</span>
                  <button
                    onClick={() => {
                      setHighlightUserId(null);
                      setUserSearchInput("");
                    }}
                    className="ml-2 text-zinc-500 hover:text-zinc-300"
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Right: Side Panel ──────────────────────────────────────── */}
        <div className="space-y-5 overflow-y-auto" style={{ maxHeight: "calc(100vh - 200px)" }}>
          {/* Selected Node Details */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-800">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                Node Details
              </span>
            </div>

            {selectedNode ? (
              <div className="px-4 py-3 space-y-3">
                {/* Type + ID */}
                <div className="flex items-center gap-2">
                  <NodeTypeBadge type={selectedNode.type} />
                  <span className="text-[13px] font-mono text-zinc-200 font-medium">
                    {selectedNode.id}
                  </span>
                </div>

                {/* Label */}
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-zinc-600 block mb-0.5">
                    Label
                  </span>
                  <p className="text-[12px] text-zinc-300 leading-relaxed font-mono bg-zinc-900/50 p-2 rounded border border-zinc-800">
                    {selectedNode.label}
                  </p>
                </div>

                {/* Meta */}
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-zinc-600">Created:</span>{" "}
                    <span className="text-zinc-400 font-mono">{formatTimestamp(selectedNode.createdAt)}</span>
                  </div>
                  {selectedNode.userId && (
                    <div>
                      <span className="text-zinc-600">User:</span>{" "}
                      <button
                        onClick={() => {
                          setUserSearchInput(selectedNode.userId!);
                          setHighlightUserId(selectedNode.userId!);
                        }}
                        className="text-blue-400 font-mono hover:underline"
                      >
                        {selectedNode.userId}
                      </button>
                    </div>
                  )}
                </div>

                {/* Connected edges */}
                {selectedNodeStats && (
                  <div>
                    <span className="text-[10px] uppercase tracking-wider text-zinc-600 block mb-1.5">
                      Connections
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded px-2 py-1.5">
                        <span className="text-zinc-500">Inbound:</span>{" "}
                        <span className="text-zinc-300 font-mono">{selectedNodeStats.inbound.length}</span>
                      </div>
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded px-2 py-1.5">
                        <span className="text-zinc-500">Outbound:</span>{" "}
                        <span className="text-zinc-300 font-mono">{selectedNodeStats.outbound.length}</span>
                      </div>
                    </div>

                    {/* Edge breakdown */}
                    {selectedNodeStats.inbound.length + selectedNodeStats.outbound.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {selectedNodeStats.inbound.slice(0, 5).map((e) => (
                          <div key={e.id} className="flex items-center gap-1.5 text-[10px]">
                            <span className="text-zinc-600">←</span>
                            <EdgeTypeBadge type={e.type} />
                            <span className="text-zinc-500 font-mono truncate">{e.source}</span>
                          </div>
                        ))}
                        {selectedNodeStats.outbound.slice(0, 5).map((e) => (
                          <div key={e.id} className="flex items-center gap-1.5 text-[10px]">
                            <span className="text-zinc-600">→</span>
                            <EdgeTypeBadge type={e.type} />
                            <span className="text-zinc-500 font-mono truncate">{e.target}</span>
                          </div>
                        ))}
                        {(selectedNodeStats.inbound.length > 5 || selectedNodeStats.outbound.length > 5) && (
                          <div className="text-[10px] text-zinc-600 mt-1">
                            + {Math.max(0, selectedNodeStats.inbound.length - 5) + Math.max(0, selectedNodeStats.outbound.length - 5)} more
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="px-4 py-8 text-center text-[12px] text-zinc-600">
                Click a node in the graph to inspect it
              </div>
            )}
          </div>

          {/* Deletion Console */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowDeletionConsole(!showDeletionConsole)}
              className="w-full flex items-center justify-between px-4 py-3 border-b border-zinc-800 hover:bg-zinc-900/30 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Shield size={14} className="text-rose-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                  Deletion Console
                </span>
                <span className="text-[10px] font-mono text-zinc-600">
                  {mockDeletionRequests.length} requests
                </span>
              </div>
              {showDeletionConsole ? (
                <ChevronUp size={14} className="text-zinc-600" />
              ) : (
                <ChevronDown size={14} className="text-zinc-600" />
              )}
            </button>

            {showDeletionConsole && (
              <div className="divide-y divide-zinc-800/50">
                {mockDeletionRequests.map((dr) => (
                  <DeletionRequestRow
                    key={dr.id}
                    request={dr}
                    onHighlight={(userId) => {
                      setUserSearchInput(userId);
                      setHighlightUserId(userId);
                    }}
                  />
                ))}

                {/* New Deletion Request */}
                <div className="px-4 py-3">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-600 font-medium mb-2">
                    New Deletion Request
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="user-XXXX"
                      value={newDeletionUserId}
                      onChange={(e) => setNewDeletionUserId(e.target.value)}
                      className="flex-1 px-3 py-1.5 text-[12px] font-mono bg-zinc-900 border border-zinc-700 rounded-md text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
                    />
                    <button
                      disabled={!newDeletionUserId.trim()}
                      className="px-3 py-1.5 text-[11px] font-medium bg-rose-500/10 border border-rose-500/30 rounded-md text-rose-400 hover:bg-rose-500/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed whitespace-nowrap"
                    >
                      Submit Request
                    </button>
                  </div>
                  <p className="text-[10px] text-zinc-600 mt-1.5">
                    Initiates SISA-compliant erasure with provenance cascade analysis.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* User Footprints Summary */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-800">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                User Footprints
              </span>
            </div>
            <div className="divide-y divide-zinc-800/50">
              {userIds.map((uid) => {
                const nodeCount = mockProvenanceNodes.filter((n) => n.userId === uid).length;
                const edgeCount = mockProvenanceEdges.filter(
                  (e) =>
                    mockProvenanceNodes.some((n) => n.id === e.source && n.userId === uid) ||
                    mockProvenanceNodes.some((n) => n.id === e.target && n.userId === uid)
                ).length;
                const isActive = highlightUserId === uid;

                return (
                  <div
                    key={uid}
                    className={`px-4 py-2.5 flex items-center justify-between ${
                      isActive ? "bg-blue-500/5" : ""
                    }`}
                  >
                    <div>
                      <button
                        onClick={() => {
                          setUserSearchInput(uid);
                          setHighlightUserId(isActive ? null : uid);
                          if (isActive) setUserSearchInput("");
                        }}
                        className={`text-[12px] font-mono ${
                          isActive ? "text-blue-400" : "text-zinc-300 hover:text-blue-400"
                        } transition-colors`}
                      >
                        {uid}
                      </button>
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-zinc-500 font-mono">
                      <span>{nodeCount} nodes</span>
                      <span>{edgeCount} edges</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

function NodeTypeBadge({ type }: { type: ProvenanceNodeType }) {
  const colors: Record<ProvenanceNodeType, string> = {
    interaction: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    memory: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    summary: "text-violet-400 bg-violet-500/10 border-violet-500/30",
    embedding: "text-zinc-400 bg-zinc-500/10 border-zinc-500/30",
    response: "text-zinc-300 bg-zinc-500/10 border-zinc-500/30",
  };

  return (
    <span className={`px-1.5 py-0.5 text-[10px] font-mono rounded border ${colors[type]}`}>
      {type}
    </span>
  );
}

function EdgeTypeBadge({ type }: { type: ProvenanceEdgeType }) {
  const colors: Record<ProvenanceEdgeType, string> = {
    creation: "text-emerald-500",
    attribution: "text-blue-500",
    derivation: "text-zinc-500",
  };

  return (
    <span className={`text-[9px] font-mono ${colors[type]}`}>{type}</span>
  );
}

function DeletionRequestRow({
  request,
  onHighlight,
}: {
  request: DeletionRequest;
  onHighlight: (userId: string) => void;
}) {
  const config = STATUS_CONFIG[request.status];
  const StatusIcon = config.icon;

  return (
    <div className="px-4 py-3 space-y-2">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-mono text-zinc-300 font-medium">
            {request.id.toUpperCase()}
          </span>
          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono rounded ${config.bg} ${config.color}`}>
            <StatusIcon size={10} className={request.status === "processing" ? "animate-spin" : ""} />
            {config.label}
          </span>
        </div>
        <button
          onClick={() => onHighlight(request.userId)}
          className="text-[11px] font-mono text-blue-400 hover:underline"
        >
          {request.userId}
        </button>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-4 text-[10px]">
        <span className="text-zinc-600">
          Requested: <span className="text-zinc-500 font-mono">{formatTimestamp(request.requestedAt)}</span>
        </span>
        {request.completedAt && (
          <span className="text-zinc-600">
            Completed: <span className="text-zinc-500 font-mono">{formatTimestamp(request.completedAt)}</span>
          </span>
        )}
      </div>

      <div className="flex items-center gap-4 text-[10px]">
        <span className="text-zinc-600">
          Footprint: <span className="text-zinc-400 font-mono">{request.footprintSize}</span>
        </span>
        <span className="text-zinc-600">
          Deleted: <span className="text-zinc-400 font-mono">{request.nodesDeleted}</span> nodes
        </span>
        <span className="text-zinc-600">
          Affected: <span className="text-zinc-400 font-mono">{request.edgesAffected}</span> edges
        </span>
      </div>

      {/* Certificate hash */}
      {request.certificateHash && (
        <div className="flex items-center gap-1.5 text-[10px]">
          <FileText size={10} className="text-zinc-600" />
          <span className="text-zinc-600 font-mono truncate max-w-[200px]">
            {request.certificateHash}
          </span>
          <button
            onClick={() => navigator.clipboard.writeText(request.certificateHash!)}
            className="text-zinc-600 hover:text-zinc-400 transition-colors"
          >
            <Copy size={10} />
          </button>
        </div>
      )}
    </div>
  );
}

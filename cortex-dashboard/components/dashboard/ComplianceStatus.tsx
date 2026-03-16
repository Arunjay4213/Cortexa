"use client";

import { Shield, CheckCircle2, Clock, GitFork, AlertCircle } from "lucide-react";
import { mockDeletionRequests, mockProvenanceNodes, mockProvenanceEdges, mockMemories } from "@/lib/mock-data";
import { useMemo } from "react";

export function ComplianceStatus() {
  const pendingDeletions = useMemo(
    () => mockDeletionRequests.filter((d) => d.status === "pending" || d.status === "processing"),
    []
  );

  const avgAgeDays = useMemo(() => {
    if (pendingDeletions.length === 0) return 0;
    const now = new Date();
    const total = pendingDeletions.reduce((s, d) => {
      return s + (now.getTime() - new Date(d.requestedAt).getTime()) / (1000 * 60 * 60 * 24);
    }, 0);
    return Math.round(total / pendingDeletions.length);
  }, [pendingDeletions]);

  // Provenance coverage: memories with at least one provenance edge
  const memoriesWithProvenance = useMemo(() => {
    const memoryNodeIds = new Set(
      mockProvenanceNodes.filter((n) => n.type === "memory").map((n) => n.id)
    );
    const connectedIds = new Set<string>();
    for (const edge of mockProvenanceEdges) {
      if (memoryNodeIds.has(edge.source)) connectedIds.add(edge.source);
      if (memoryNodeIds.has(edge.target)) connectedIds.add(edge.target);
    }
    const totalMemoryNodes = memoryNodeIds.size;
    return totalMemoryNodes > 0 ? connectedIds.size / totalMemoryNodes : 0;
  }, []);

  const provenancePct = Math.round(memoriesWithProvenance * 100);

  // Unique user footprints
  const userFootprints = useMemo(() => {
    const userIds = new Set(
      mockProvenanceNodes.filter((n) => n.userId).map((n) => n.userId)
    );
    return userIds.size;
  }, []);

  const orphanedNodes = 0; // mock: no orphans

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800">
        <Shield size={14} className="text-zinc-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
          Compliance Status
        </span>
      </div>

      {/* Provenance coverage */}
      <div className="px-4 py-3 border-b border-zinc-800/50">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[12px] text-zinc-400">Provenance Coverage</span>
          <span className="text-[12px] font-mono text-zinc-300 tabular-nums">{provenancePct}%</span>
        </div>
        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 rounded-full transition-all duration-500"
            style={{ width: `${provenancePct}%` }}
          />
        </div>
        <p className="text-[11px] text-zinc-600 mt-1.5">
          {provenancePct}% of memories have complete provenance chains
        </p>
      </div>

      {/* Pending deletions */}
      <div className="px-4 py-3 border-b border-zinc-800/50 flex items-start gap-3">
        {pendingDeletions.length > 0 ? (
          <AlertCircle size={14} className="text-amber-500 shrink-0 mt-0.5" />
        ) : (
          <CheckCircle2 size={14} className="text-emerald-500 shrink-0 mt-0.5" />
        )}
        <div>
          <p className="text-[12px] text-zinc-400">
            <span className="text-zinc-200 font-medium">{pendingDeletions.length} deletion request{pendingDeletions.length !== 1 ? "s" : ""}</span>
            {" "}pending
            {pendingDeletions.length > 0 && (
              <span className="text-zinc-600"> (avg age: {avgAgeDays} day{avgAgeDays !== 1 ? "s" : ""})</span>
            )}
          </p>
          {pendingDeletions.map((d) => (
            <div key={d.id} className="flex items-center gap-2 mt-1.5 text-[11px]">
              <span className="font-mono text-zinc-500">{d.id.toUpperCase()}</span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium uppercase ${
                d.status === "processing"
                  ? "bg-amber-500/10 text-amber-500"
                  : "bg-zinc-800 text-zinc-500"
              }`}>
                {d.status}
              </span>
              <span className="text-zinc-600 font-mono">{d.footprintSize} nodes</span>
            </div>
          ))}
        </div>
      </div>

      {/* Last audit */}
      <div className="px-4 py-3 border-b border-zinc-800/50 flex items-center gap-3">
        <Clock size={14} className="text-zinc-500 shrink-0" />
        <div className="text-[12px] text-zinc-400">
          Last audit:{" "}
          <span className="text-zinc-300">Feb 18, 2026</span>
          <span className="ml-2 text-emerald-500 font-medium">PASSED</span>
          <CheckCircle2 size={11} className="inline ml-1 text-emerald-500" />
        </div>
      </div>

      {/* Mini summary */}
      <div className="px-4 py-3 border-b border-zinc-800/50">
        <div className="flex items-center gap-1.5 mb-2">
          <GitFork size={12} className="text-zinc-600" />
          <span className="text-[10px] uppercase tracking-wider text-zinc-600 font-medium">
            Graph Summary
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div className="text-center">
            <div className="text-[16px] font-mono font-medium text-zinc-300 tabular-nums">
              {userFootprints}
            </div>
            <div className="text-[10px] text-zinc-600">User footprints</div>
          </div>
          <div className="text-center">
            <div className="text-[16px] font-mono font-medium text-zinc-300 tabular-nums">
              {mockProvenanceEdges.length.toLocaleString()}
            </div>
            <div className="text-[10px] text-zinc-600">Prov. edges</div>
          </div>
          <div className="text-center">
            <div className="text-[16px] font-mono font-medium text-emerald-500 tabular-nums">
              {orphanedNodes}
            </div>
            <div className="text-[10px] text-zinc-600">Orphaned</div>
          </div>
        </div>
      </div>

      {/* Run compliance check button */}
      <div className="px-4 py-3">
        <button className="w-full py-2 rounded-md border border-zinc-700 text-[12px] font-medium text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 transition-all">
          Run Compliance Check
        </button>
      </div>
    </div>
  );
}

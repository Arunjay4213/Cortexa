"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Radio, ChevronDown, ChevronUp, AlertTriangle, Check } from "lucide-react";
import { mockQueryTraces } from "@/lib/mock-data";
import { formatTimestamp, formatMemoryId, truncateText, formatCurrency } from "@/lib/utils";
import type { QueryTrace, RetrievedMemory } from "@/lib/types";

// ── Status helpers ─────────────────────────────────────────────────────

function healthIcon(status: RetrievedMemory["healthStatus"]) {
  switch (status) {
    case "stale":
      return <span className="text-amber-500 text-[11px] font-medium">STALE</span>;
    case "contradictory":
      return <span className="text-rose-500 text-[11px] font-medium">CONFLICT</span>;
    case "drifted":
      return <span className="text-amber-500 text-[11px] font-medium">DRIFTED</span>;
    default:
      return <Check size={12} className="text-emerald-500" />;
  }
}

function riskBadge(risk: QueryTrace["hallucinationRisk"]) {
  switch (risk) {
    case "high":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <AlertTriangle size={10} /> High Risk
        </span>
      );
    case "medium":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <AlertTriangle size={10} /> Medium Risk
        </span>
      );
    case "low":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-zinc-800 text-zinc-400 border border-zinc-700">
          Low Risk
        </span>
      );
    default:
      return null;
  }
}

// ── Collapsed trace row ────────────────────────────────────────────────

function CollapsedRow({
  trace,
  onClick,
}: {
  trace: QueryTrace;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-zinc-800/30 transition-colors group"
    >
      <span className="text-[11px] font-mono text-zinc-600 w-14 shrink-0 tabular-nums">
        {formatTimestamp(trace.timestamp)}
      </span>
      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 shrink-0">
        {trace.agentId}
      </span>
      <span className="text-[13px] text-zinc-400 truncate flex-1 font-mono">
        &ldquo;{truncateText(trace.query, 55)}&rdquo;
      </span>
      <span className="text-[11px] text-zinc-600 font-mono shrink-0">
        {trace.memoriesRetrieved.length} mem
      </span>
      <span className="text-[11px] text-zinc-600 font-mono shrink-0">
        {formatCurrency(trace.totalCost)}
      </span>
      {trace.hallucinationRisk === "none" ? (
        <Check size={12} className="text-emerald-500/60 shrink-0" />
      ) : (
        <AlertTriangle size={12} className="text-amber-500 shrink-0" />
      )}
      <ChevronDown size={12} className="text-zinc-700 group-hover:text-zinc-500 shrink-0" />
    </button>
  );
}

// ── Expanded trace panel ───────────────────────────────────────────────

function ExpandedRow({
  trace,
  onClick,
}: {
  trace: QueryTrace;
  onClick: () => void;
}) {
  const hasRisk = trace.hallucinationRisk === "high" || trace.hallucinationRisk === "medium";
  const problematicMemories = trace.memoriesRetrieved.filter(
    (m) => m.healthStatus !== "ok"
  );
  const warningLine = problematicMemories.length > 0
    ? `${problematicMemories[0].healthStatus === "stale" ? "Stale" : problematicMemories[0].healthStatus === "contradictory" ? "Contradictory" : "Drifted"} memory ${formatMemoryId(problematicMemories[0].memoryId)} dominates attribution`
    : null;

  return (
    <div
      className={`
        border-l-[3px] rounded-r-lg
        ${hasRisk ? "border-l-rose-500 bg-rose-950/10" : "border-l-zinc-700 bg-zinc-900/30"}
      `}
    >
      {/* Header */}
      <button
        onClick={onClick}
        className="w-full flex items-center justify-between px-4 pt-3 pb-2 text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-[12px] font-mono text-zinc-500">
            {trace.id.toUpperCase()}
          </span>
          <span className="text-zinc-700">&middot;</span>
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
            {trace.agentId}
          </span>
          <span className="text-zinc-700">&middot;</span>
          <span className="text-[11px] font-mono text-zinc-600">
            {formatTimestamp(trace.timestamp)}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {riskBadge(trace.hallucinationRisk)}
          <ChevronUp size={14} className="text-zinc-600" />
        </div>
      </button>

      {/* Query text */}
      <div className="px-4 pb-3">
        <p className="text-[13px] text-zinc-300 font-mono">
          &ldquo;{trace.query}&rdquo;
        </p>
      </div>

      {/* Attribution table */}
      <div className="px-4 pb-3">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-zinc-600 border-b border-zinc-800">
              <th className="text-left py-1.5 font-medium">Memory</th>
              <th className="text-right py-1.5 font-medium w-16">Score</th>
              <th className="text-right py-1.5 font-medium w-20">Status</th>
            </tr>
          </thead>
          <tbody>
            {trace.memoriesRetrieved.map((mem) => {
              const isProblematic = mem.healthStatus !== "ok";
              return (
                <tr
                  key={mem.memoryId}
                  className={`border-b border-zinc-800/50 ${isProblematic ? "bg-rose-950/20" : ""}`}
                >
                  <td className="py-1.5 font-mono text-zinc-400">
                    <span className="text-zinc-500">{formatMemoryId(mem.memoryId)}</span>{" "}
                    <span className="text-zinc-500">{truncateText(mem.content, 45)}</span>
                  </td>
                  <td className="py-1.5 text-right font-mono text-zinc-300 tabular-nums">
                    {mem.attributionScore.toFixed(2)}
                  </td>
                  <td className="py-1.5 text-right">
                    {healthIcon(mem.healthStatus)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Warning line + View Trace link */}
      <div className="px-4 pb-3 flex items-center justify-between">
        {warningLine ? (
          <div className="flex items-center gap-1.5 text-[11px] text-amber-500">
            <AlertTriangle size={12} />
            <span>{warningLine}</span>
          </div>
        ) : (
          <div />
        )}
        <Link
          href={`/attribution/${trace.id}`}
          className="text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors font-medium"
        >
          View Trace &rarr;
        </Link>
      </div>
    </div>
  );
}

// ── Main LiveFeed ──────────────────────────────────────────────────────

export function LiveFeed() {
  const traces = useMemo(
    () =>
      [...mockQueryTraces]
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, 15),
    []
  );

  // Auto-expand traces with hallucination risk
  const defaultExpanded = new Set(
    traces.filter((t) => t.hallucinationRisk !== "none").map((t) => t.id)
  );
  const [expanded, setExpanded] = useState<Set<string>>(defaultExpanded);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <Radio size={14} className="text-zinc-500" />
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
            Live Attribution Feed
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] uppercase tracking-wider text-emerald-500/80 font-medium">
            Live
          </span>
        </div>
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto max-h-[480px] divide-y divide-zinc-800/50">
        {traces.map((trace) =>
          expanded.has(trace.id) ? (
            <ExpandedRow key={trace.id} trace={trace} onClick={() => toggle(trace.id)} />
          ) : (
            <CollapsedRow key={trace.id} trace={trace} onClick={() => toggle(trace.id)} />
          )
        )}
      </div>
    </div>
  );
}

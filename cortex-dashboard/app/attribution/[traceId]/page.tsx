"use client";

import { useMemo, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, AlertTriangle, Zap } from "lucide-react";
import Link from "next/link";
import { mockQueryTraces, mockMemories } from "@/lib/mock-data";
import {
  formatMemoryId,
  formatTimestamp,
  formatCurrency,
  truncateText,
} from "@/lib/utils";
import { AttributionWaterfall } from "@/components/dashboard/AttributionWaterfall";
import { StatementHeatmap } from "@/components/dashboard/StatementHeatmap";
import { MemoryDetailPanel } from "@/components/shared/MemoryDetailPanel";
import type { QueryTrace, RetrievedMemory, HallucinationRisk } from "@/lib/types";

// ── Risk badge helper ───────────────────────────────────────────────────

function riskBadge(risk: HallucinationRisk) {
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
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          Low
        </span>
      );
    default:
      return null;
  }
}

// ── Memory color map for statement underlines ────────────────────────────

const MEMORY_COLORS = [
  "#10b981", // emerald-500
  "#3b82f6", // blue-500
  "#f59e0b", // amber-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#06b6d4", // cyan-500
  "#f43f5e", // rose-500
  "#84cc16", // lime-500
];

function getMemoryColor(memoryId: string, allIds: string[]): string {
  const idx = allIds.indexOf(memoryId);
  return MEMORY_COLORS[idx % MEMORY_COLORS.length];
}

// ── Page component ──────────────────────────────────────────────────────

export default function TraceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const traceId = params.traceId as string;

  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);
  const [hoveredMemoryId, setHoveredMemoryId] = useState<string | null>(null);

  const trace = useMemo(
    () => mockQueryTraces.find((t) => t.id === traceId) ?? null,
    [traceId]
  );

  const handleMemoryClick = useCallback((memoryId: string) => {
    setSelectedMemoryId(memoryId);
  }, []);

  if (!trace) {
    return (
      <div className="space-y-4">
        <Link
          href="/attribution"
          className="inline-flex items-center gap-1.5 text-[13px] text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <ArrowLeft size={14} />
          Back to Attribution Explorer
        </Link>
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-8 text-center">
          <p className="text-zinc-400">Trace &ldquo;{traceId}&rdquo; not found.</p>
        </div>
      </div>
    );
  }

  // All unique memory IDs for color assignment
  const allMemoryIds = trace.memoriesRetrieved.map((m) => m.memoryId);

  // Compute primary memory for each statement (for underline coloring)
  const statementPrimaryMemory = trace.statementAttribution?.map((sa) => {
    if (sa.memoryScores.length === 0) return null;
    return sa.memoryScores.reduce((best, ms) =>
      ms.score > best.score ? ms : best
    );
  });

  return (
    <div className="space-y-6">
      {/* Back link + header */}
      <div className="flex items-center justify-between">
        <Link
          href="/attribution"
          className="inline-flex items-center gap-1.5 text-[13px] text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <ArrowLeft size={14} />
          Back to Explorer
        </Link>
        <div className="flex items-center gap-3">
          {riskBadge(trace.hallucinationRisk)}
          <span className="text-[11px] font-mono text-zinc-500">
            {trace.id.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Top Section: Query & Response */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Query */}
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center justify-between">
            <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
              Query
            </span>
            <div className="flex items-center gap-2 text-[11px] text-zinc-600">
              <span className="font-mono">{trace.agentId}</span>
              <span>&middot;</span>
              <span className="font-mono">{formatTimestamp(trace.timestamp)}</span>
              <span>&middot;</span>
              <span className="font-mono">{formatCurrency(trace.totalCost)}</span>
            </div>
          </div>
          <div className="px-4 py-3">
            <p className="text-[14px] text-zinc-200 leading-relaxed font-mono">
              {trace.query}
            </p>
          </div>
        </div>

        {/* Response */}
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center justify-between">
            <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
              Response
            </span>
            {trace.statementAttribution && (
              <span className="text-[10px] text-emerald-500/70">
                ContextCite attribution available
              </span>
            )}
          </div>
          <div className="px-4 py-3">
            {trace.statementAttribution ? (
              <AnnotatedResponse
                trace={trace}
                allMemoryIds={allMemoryIds}
                hoveredMemoryId={hoveredMemoryId}
                onHoverMemory={setHoveredMemoryId}
                onClickMemory={handleMemoryClick}
              />
            ) : (
              <p className="text-[14px] text-zinc-200 leading-relaxed font-mono">
                {trace.response}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Middle Section: Attribution Waterfall */}
      <AttributionWaterfall
        memories={trace.memoriesRetrieved}
        onMemoryClick={handleMemoryClick}
      />

      {/* Bottom Section: Statement-Level Attribution */}
      {trace.statementAttribution ? (
        <StatementHeatmap
          statements={trace.statementAttribution}
          onMemoryClick={handleMemoryClick}
        />
      ) : (
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-zinc-800">
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Statement-Level Attribution
            </span>
          </div>
          <div className="px-4 py-8 text-center">
            <p className="text-[13px] text-zinc-500 mb-3">
              Statement-level attribution not available for this trace.
              <br />
              <span className="text-zinc-600">
                ContextCite runs on ~1% of queries.
              </span>
            </p>
            <button className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md border border-zinc-700 text-[12px] font-medium text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 transition-all">
              <Zap size={14} />
              Trigger Deep Analysis
            </button>
          </div>
        </div>
      )}

      {/* Memory Detail Panel */}
      <MemoryDetailPanel
        memoryId={selectedMemoryId}
        onClose={() => setSelectedMemoryId(null)}
      />
    </div>
  );
}

// ── Annotated Response ──────────────────────────────────────────────────

function AnnotatedResponse({
  trace,
  allMemoryIds,
  hoveredMemoryId,
  onHoverMemory,
  onClickMemory,
}: {
  trace: QueryTrace;
  allMemoryIds: string[];
  hoveredMemoryId: string | null;
  onHoverMemory: (id: string | null) => void;
  onClickMemory: (id: string) => void;
}) {
  const statements = trace.statementAttribution!;

  // Find parts of the response that match each statement
  // and render with colored underlines
  return (
    <div className="text-[14px] text-zinc-200 leading-relaxed font-mono space-y-1">
      {statements.map((sa, idx) => {
        const primaryScore =
          sa.memoryScores.length > 0
            ? sa.memoryScores.reduce((best, ms) => (ms.score > best.score ? ms : best))
            : null;
        const underlineColor = primaryScore
          ? getMemoryColor(primaryScore.memoryId, allMemoryIds)
          : undefined;

        return (
          <span
            key={idx}
            className="relative inline group cursor-pointer"
            style={{
              borderBottom: underlineColor ? `2px solid ${underlineColor}` : undefined,
              paddingBottom: underlineColor ? 1 : undefined,
            }}
            onMouseEnter={() => primaryScore && onHoverMemory(primaryScore.memoryId)}
            onMouseLeave={() => onHoverMemory(null)}
            onClick={() => primaryScore && onClickMemory(primaryScore.memoryId)}
          >
            {sa.statement}
            {idx < statements.length - 1 ? ". " : "."}

            {/* Tooltip */}
            {primaryScore && (
              <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                <span className="bg-zinc-900 border border-zinc-700 rounded-md px-3 py-1.5 shadow-lg whitespace-nowrap flex items-center gap-2">
                  <span className="text-[11px] font-mono text-zinc-300">
                    {formatMemoryId(primaryScore.memoryId)}
                  </span>
                  <span className="text-[11px] font-mono text-zinc-500">
                    score: {primaryScore.score.toFixed(3)}
                  </span>
                </span>
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}

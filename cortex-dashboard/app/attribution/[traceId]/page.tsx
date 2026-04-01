"use client";

import { useMemo, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, AlertTriangle, Zap } from "lucide-react";
import { GrafanaPanel } from "@/components/dashboard/GrafanaPanel";
import { AttributionWaterfall } from "@/components/dashboard/AttributionWaterfall";
import { StatementHeatmap } from "@/components/dashboard/StatementHeatmap";
import { MemoryDetailPanel } from "@/components/shared/MemoryDetailPanel";
import { mockQueryTraces } from "@/lib/mock-data";
import {
  formatMemoryId,
  formatTimestamp,
  formatCurrency,
  truncateText,
} from "@/lib/utils";
import type { QueryTrace, HallucinationRisk } from "@/lib/types";

// ── Grafana data palette for memory color assignment ─────────────────────

const MEMORY_COLORS = [
  "#73bf69", // grafana green
  "#5794f2", // grafana blue
  "#ff9830", // grafana yellow/orange
  "#b877d9", // grafana purple
  "#8ab8ff", // grafana cyan
  "#f2495c", // grafana red
  "#ff6eb4", // pink
  "#fade2a", // lime
];

function getMemoryColor(memoryId: string, allIds: string[]): string {
  const idx = allIds.indexOf(memoryId);
  return MEMORY_COLORS[idx % MEMORY_COLORS.length];
}

// ── Risk badge ───────────────────────────────────────────────────────────

function riskBadge(risk: HallucinationRisk) {
  const map: Record<HallucinationRisk, { bg: string; color: string; border: string; label: string }> = {
    none:   { bg: "transparent", color: "#464c54", border: "transparent", label: "None" },
    low:    { bg: "rgba(115,191,105,0.10)", color: "#73bf69", border: "rgba(115,191,105,0.20)", label: "Low" },
    medium: { bg: "rgba(255,152,48,0.10)", color: "#ff9830", border: "rgba(255,152,48,0.20)", label: "Medium Risk" },
    high:   { bg: "rgba(242,73,92,0.10)", color: "#f2495c", border: "rgba(242,73,92,0.20)", label: "High Risk" },
  };
  const s = map[risk];
  if (risk === "none") return null;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wide"
      style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}
    >
      {(risk === "high" || risk === "medium") && <AlertTriangle size={10} />}
      {s.label}
    </span>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────

export default function TraceDetailPage() {
  const params = useParams();
  const traceId = params.traceId as string;

  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);

  const trace = useMemo(
    () => mockQueryTraces.find((t) => t.id === traceId) ?? null,
    [traceId]
  );

  const handleMemoryClick = useCallback((memoryId: string) => {
    setSelectedMemoryId(memoryId);
  }, []);

  if (!trace) {
    return (
      <div className="flex flex-col" style={{ gap: "var(--panel-gap)" }}>
        <Link
          href="/attribution"
          className="inline-flex items-center gap-1.5 text-[13px] transition-colors"
          style={{ color: "var(--grafana-text-muted)" }}
          onMouseEnter={(e) => e.currentTarget.style.color = "var(--grafana-text-primary)"}
          onMouseLeave={(e) => e.currentTarget.style.color = "var(--grafana-text-muted)"}
        >
          <ArrowLeft size={14} />
          Back to Attribution Explorer
        </Link>
        <GrafanaPanel title="Not Found">
          <p className="text-center py-8" style={{ color: "var(--grafana-text-muted)" }}>
            Trace &ldquo;{traceId}&rdquo; not found.
          </p>
        </GrafanaPanel>
      </div>
    );
  }

  const allMemoryIds = trace.memoriesRetrieved.map((m) => m.memoryId);

  return (
    <div className="flex flex-col" style={{ gap: "var(--panel-gap)" }}>
      {/* Back link + header */}
      <div className="flex items-center justify-between">
        <Link
          href="/attribution"
          className="inline-flex items-center gap-1.5 text-[13px] transition-colors"
          style={{ color: "var(--grafana-text-muted)" }}
          onMouseEnter={(e) => e.currentTarget.style.color = "var(--grafana-text-primary)"}
          onMouseLeave={(e) => e.currentTarget.style.color = "var(--grafana-text-muted)"}
        >
          <ArrowLeft size={14} />
          Back to Explorer
        </Link>
        <div className="flex items-center gap-3">
          {riskBadge(trace.hallucinationRisk)}
          <span className="text-[12px] font-mono" style={{ color: "var(--grafana-text-muted)" }}>
            {trace.id.toUpperCase()}
          </span>
        </div>
      </div>

      {/* ── Panel 1: Query & Response ────────────────────────────── */}
      <GrafanaPanel
        title={`Query & Response — Trace ${trace.id.toUpperCase()}`}
        headerRight={
          <div className="flex items-center gap-3 text-[11px] font-mono" style={{ color: "var(--grafana-text-muted)" }}>
            <span>{trace.agentId}</span>
            <span style={{ color: "var(--panel-border)" }}>&middot;</span>
            <span>{formatTimestamp(trace.timestamp)}</span>
            <span style={{ color: "var(--panel-border)" }}>&middot;</span>
            <span>{formatCurrency(trace.totalCost)}</span>
            <span style={{ color: "var(--panel-border)" }}>&middot;</span>
            <span>{trace.latencyMs}ms</span>
          </div>
        }
      >
        <div className="flex flex-col gap-4">
          {/* Query */}
          <div>
            <div className="text-[10px] uppercase tracking-wider font-medium mb-2" style={{ color: "var(--grafana-text-muted)" }}>
              Query
            </div>
            <div
              className="text-[13px] font-mono leading-relaxed p-3 rounded-sm"
              style={{
                background: "#0b0c0e",
                border: "1px solid var(--panel-border)",
                color: "var(--grafana-text-primary)",
              }}
            >
              {trace.query}
            </div>
          </div>

          {/* Response */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>
                Response
              </span>
              {trace.statementAttribution && (
                <span className="text-[10px]" style={{ color: "var(--grafana-green)" }}>
                  ContextCite attribution available
                </span>
              )}
            </div>
            <div
              className="text-[13px] font-mono leading-relaxed p-3 rounded-sm"
              style={{
                background: "#0b0c0e",
                border: "1px solid var(--panel-border)",
                color: "var(--grafana-text-primary)",
              }}
            >
              {trace.statementAttribution ? (
                <AnnotatedResponse
                  trace={trace}
                  allMemoryIds={allMemoryIds}
                  onClickMemory={handleMemoryClick}
                />
              ) : (
                trace.response
              )}
            </div>
          </div>
        </div>
      </GrafanaPanel>

      {/* ── Panel 2: Attribution Waterfall ────────────────────────── */}
      <AttributionWaterfall
        memories={trace.memoriesRetrieved}
        onMemoryClick={handleMemoryClick}
      />

      {/* ── Panel 3: Statement-Level Attribution (conditional) ──── */}
      {trace.statementAttribution ? (
        <StatementHeatmap
          statements={trace.statementAttribution}
          onMemoryClick={handleMemoryClick}
        />
      ) : (
        <GrafanaPanel title="Statement × Memory Heatmap (ContextCite)">
          <div className="py-8 text-center">
            <p className="text-[13px] mb-1" style={{ color: "var(--grafana-text-secondary)" }}>
              Statement-level attribution not available for this trace.
            </p>
            <p className="text-[12px] mb-4" style={{ color: "var(--grafana-text-muted)" }}>
              ContextCite runs on ~1% of queries.
            </p>
            <button
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-sm text-[12px] font-medium transition-colors"
              style={{
                background: "transparent",
                border: "1px solid var(--panel-border)",
                color: "var(--grafana-text-primary)",
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = "var(--panel-bg-hover)"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
            >
              <Zap size={14} />
              Trigger Deep Analysis
            </button>
          </div>
        </GrafanaPanel>
      )}

      {/* ── Panel 4: Memory Detail slide-out ────────────────────── */}
      <MemoryDetailPanel
        memoryId={selectedMemoryId}
        onClose={() => setSelectedMemoryId(null)}
      />
    </div>
  );
}

// ── Annotated Response ───────────────────────────────────────────────────

function AnnotatedResponse({
  trace,
  allMemoryIds,
  onClickMemory,
}: {
  trace: QueryTrace;
  allMemoryIds: string[];
  onClickMemory: (id: string) => void;
}) {
  const statements = trace.statementAttribution!;

  return (
    <span>
      {statements.map((sa, idx) => {
        const primaryScore =
          sa.memoryScores.length > 0
            ? sa.memoryScores.reduce((best, ms) => (ms.score > best.score ? ms : best))
            : null;
        const dotColor = primaryScore
          ? getMemoryColor(primaryScore.memoryId, allMemoryIds)
          : undefined;

        return (
          <span key={idx} className="relative inline">
            {/* Colored dot before each statement */}
            {dotColor && (
              <span
                className="inline-block w-[6px] h-[6px] rounded-full mr-1 align-middle cursor-pointer"
                style={{ background: dotColor }}
                onClick={() => primaryScore && onClickMemory(primaryScore.memoryId)}
                title={primaryScore ? `${formatMemoryId(primaryScore.memoryId)} (${primaryScore.score.toFixed(3)})` : undefined}
              />
            )}
            <span
              className={primaryScore ? "cursor-pointer" : ""}
              style={{
                borderBottom: dotColor ? `2px solid ${dotColor}` : undefined,
                paddingBottom: dotColor ? 1 : undefined,
              }}
              onClick={() => primaryScore && onClickMemory(primaryScore.memoryId)}
            >
              {sa.statement}
            </span>
            {idx < statements.length - 1 ? ". " : "."}
          </span>
        );
      })}
    </span>
  );
}

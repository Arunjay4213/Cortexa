"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import {
  useContradictions,
  useHealthSnapshots,
  useTimeSeries,
  useDashboardOverview,
  useContaminationScan,
} from "@/lib/hooks";
import {
  detectContradictions,
  resolveContradiction,
} from "@/lib/api/health";
import { scanContamination } from "@/lib/api/grounding";
import type { ContaminationScanResponse } from "@/lib/api/types";

import { PageTransition } from "@/components/primitives/PageTransition";
import { PageHeader } from "@/components/primitives/PageHeader";
import { SectionHeader } from "@/components/primitives/SectionHeader";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState } from "@/components/primitives/EmptyState";
import { ErrorFallback } from "@/components/primitives/ErrorFallback";
import {
  CardSkeleton,
  TableSkeleton,
} from "@/components/primitives/LoadingSkeleton";
import { EntityLink } from "@/components/primitives/EntityLink";
import { Sparkline } from "@/components/primitives/Sparkline";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

// -- Constants ----------------------------------------------------------------

const METRIC_OPTIONS = [
  { value: "avg_eas", label: "Avg EAS Score" },
  { value: "contradiction_rate", label: "Contradiction Rate" },
  { value: "retrieval_count", label: "Retrieval Count" },
  { value: "cost", label: "Cost" },
  { value: "tokens", label: "Tokens" },
];

const SEVERITY_BADGE: Record<string, string> = {
  semantic: "badge--error",
  factual: "badge--warning",
  temporal: "badge--info",
  logical: "badge--neutral",
};

function severityBadgeClass(type: string): string {
  return SEVERITY_BADGE[type] ?? "badge--neutral";
}

// -- Page ---------------------------------------------------------------------

export default function HealthPage() {
  const { mutate } = useSWRConfig();

  // -- Local state --
  const [agentFilter, setAgentFilter] = useState("");
  const [selectedMetric, setSelectedMetric] = useState("avg_eas");
  const [showAllContradictions, setShowAllContradictions] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [detectionCount, setDetectionCount] = useState<number | null>(null);
  const [resolvingIds, setResolvingIds] = useState<Set<string>>(new Set());
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ContaminationScanResponse | null>(null);

  // -- Data hooks --
  const {
    data: overview,
    error: overviewError,
    isLoading: overviewLoading,
  } = useDashboardOverview();

  const {
    data: healthSnapshots,
    error: healthError,
    isLoading: healthLoading,
  } = useHealthSnapshots(agentFilter || null);

  const {
    data: contradictions,
    error: contradictionsError,
    isLoading: contradictionsLoading,
  } = useContradictions(
    showAllContradictions
      ? agentFilter ? { agent_id: agentFilter } : undefined
      : agentFilter ? { agent_id: agentFilter, resolved: false } : { resolved: false }
  );

  const {
    data: timeSeries,
    error: timeSeriesError,
    isLoading: timeSeriesLoading,
  } = useTimeSeries({
    metric: selectedMetric,
    agent_id: agentFilter || undefined,
    days: 7,
    bucket: "1h",
  });

  const { data: contaminationScan } = useContaminationScan(agentFilter || null);

  // -- Derived data --
  const latestSnapshot =
    healthSnapshots && healthSnapshots.length > 0
      ? healthSnapshots[healthSnapshots.length - 1]
      : null;

  const chiScore = latestSnapshot
    ? ((1 - latestSnapshot.contradiction_rate) * latestSnapshot.retrieval_efficiency * latestSnapshot.memory_quality * 100).toFixed(1)
    : overview
      ? ((1 - overview.overall_waste_rate / 100) * 100).toFixed(1)
      : "--";

  const contradictionCount =
    contradictions?.filter((c) => !c.resolved).length ?? 0;

  const driftScore = latestSnapshot
    ? latestSnapshot.semantic_drift.toFixed(4)
    : "--";

  const coverageValue = latestSnapshot
    ? `${(latestSnapshot.retrieval_efficiency * 100).toFixed(1)}%`
    : overview
      ? `${(100 - overview.overall_waste_rate).toFixed(1)}%`
      : "--";

  const stalenessValue = contaminationScan
    ? `${(contaminationScan.system_contamination_rate * 100).toFixed(1)}%`
    : "--";

  // Sparkline data from health snapshots
  const driftSparkline =
    healthSnapshots && healthSnapshots.length > 1
      ? healthSnapshots.map((s) => s.semantic_drift)
      : [];

  const qualitySparkline =
    healthSnapshots && healthSnapshots.length > 1
      ? healthSnapshots.map((s) => s.memory_quality)
      : [];

  // -- Handlers --
  async function handleRunDetection() {
    setIsDetecting(true);
    setDetectionCount(null);
    try {
      const result = await detectContradictions(agentFilter || undefined);
      setDetectionCount(result.detected);
      mutate((key: string) =>
        typeof key === "string" && key.startsWith("/health/contradictions")
      );
    } catch {
      // detection failed silently
    } finally {
      setIsDetecting(false);
    }
  }

  async function handleResolve(id: string) {
    setResolvingIds((prev) => new Set(prev).add(id));
    try {
      await resolveContradiction(id);
      mutate((key: string) =>
        typeof key === "string" && key.startsWith("/health/contradictions")
      );
    } catch {
      // resolve failed silently
    } finally {
      setResolvingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  async function handleRunScan() {
    if (!agentFilter) return;
    setIsScanning(true);
    try {
      const result = await scanContamination(agentFilter);
      setScanResult(result);
    } catch {
      // scan failed silently
    } finally {
      setIsScanning(false);
    }
  }

  // -- Chart data --
  const chartData =
    timeSeries?.buckets.map((b) => ({
      time: new Date(b.timestamp).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }),
      value: b.value,
      count: b.count,
    })) ?? [];

  const activeScan = scanResult ?? contaminationScan;

  // -- Render -----------------------------------------------------------------

  return (
    <PageTransition>
      <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-secondary)] p-6">
        {/* Header */}
        <PageHeader
          title="Health"
          subtitle="System health, contradictions, and contamination monitoring"
        >
          <input
            type="text"
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            placeholder="Filter by agent_id..."
            className="input input--sm w-48 font-mono"
          />
        </PageHeader>

        {/* Metric Cards Row */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8 stagger-children">
          {overviewLoading || healthLoading ? (
            <>
              {Array.from({ length: 5 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </>
          ) : (
            <>
              <MetricCard
                label="CHI Score"
                value={chiScore}
                sparkline={
                  qualitySparkline.length > 1 ? (
                    <Sparkline data={qualitySparkline} color="#6366F1" />
                  ) : undefined
                }
              />
              <MetricCard
                label="Contradictions"
                value={contradictionCount}
                delta={
                  detectionCount !== null ? detectionCount : undefined
                }
                deltaLabel={detectionCount !== null ? "newly detected" : undefined}
              />
              <MetricCard
                label="Drift Score"
                value={driftScore}
                sparkline={
                  driftSparkline.length > 1 ? (
                    <Sparkline data={driftSparkline} color="#A78BFA" />
                  ) : undefined
                }
              />
              <MetricCard label="Coverage" value={coverageValue} />
              <MetricCard label="Staleness" value={stalenessValue} />
            </>
          )}
        </div>

        {overviewError && (
          <div className="mb-8">
            <ErrorFallback
              error={overviewError}
              onRetry={() => mutate("/dashboard/overview")}
            />
          </div>
        )}
        {healthError && (
          <div className="mb-8">
            <ErrorFallback
              error={healthError}
              onRetry={() =>
                mutate((key: string) =>
                  typeof key === "string" && key.startsWith("/health/")
                )
              }
            />
          </div>
        )}

        {/* Contradiction Detection Section */}
        <div className="card mb-8">
          <SectionHeader
            title="Contradictions"
            count={contradictions?.length}
          >
            <label className="flex items-center gap-2 text-xs text-[var(--text-tertiary)] cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showAllContradictions}
                onChange={(e) => setShowAllContradictions(e.target.checked)}
                className="accent-[var(--accent)]"
              />
              Show resolved
            </label>
            {detectionCount !== null && (
              <span className="badge badge--success font-mono">
                {detectionCount} detected
              </span>
            )}
            <button
              onClick={handleRunDetection}
              disabled={isDetecting}
              className="btn btn--primary"
            >
              {isDetecting ? "Detecting..." : "Run Detection"}
            </button>
          </SectionHeader>

          {contradictionsLoading ? (
            <TableSkeleton rows={5} cols={6} />
          ) : contradictionsError ? (
            <ErrorFallback
              error={contradictionsError}
              onRetry={() =>
                mutate((key: string) =>
                  typeof key === "string" &&
                  key.startsWith("/health/contradictions")
                )
              }
            />
          ) : contradictions && contradictions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="table table-compact">
                <thead>
                  <tr>
                    <th>Memory 1</th>
                    <th>Memory 2</th>
                    <th>Type</th>
                    <th>Severity</th>
                    <th>Resolved</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {contradictions.map((c) => {
                    const isResolving = resolvingIds.has(c.id);
                    return (
                      <tr key={c.id}>
                        <td>
                          <EntityLink type="memory" id={c.memory_id_1} truncate={12} />
                        </td>
                        <td>
                          <EntityLink type="memory" id={c.memory_id_2} truncate={12} />
                        </td>
                        <td>
                          <span className="uppercase font-mono text-xs">
                            {c.type}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${severityBadgeClass(c.type)}`}>
                            <span className="font-mono">
                              {(c.confidence * 100).toFixed(0)}%
                            </span>
                          </span>
                        </td>
                        <td>
                          {c.resolved ? (
                            <span className="badge badge--success">Resolved</span>
                          ) : (
                            <span className="badge badge--error">Unresolved</span>
                          )}
                        </td>
                        <td>
                          {!c.resolved && (
                            <button
                              onClick={() => handleResolve(c.id)}
                              disabled={isResolving}
                              className="btn btn--ghost text-xs"
                            >
                              {isResolving ? "..." : "Resolve"}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No contradictions found"
              description="Run detection to scan for conflicts between memories."
            />
          )}
        </div>

        {/* Time Series Chart Section */}
        <div className="card mb-8">
          <SectionHeader title="Time Series">
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value)}
              className="input input--sm w-44 font-mono"
            >
              {METRIC_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {agentFilter && (
              <span className="badge badge--info font-mono">
                {agentFilter}
              </span>
            )}
          </SectionHeader>

          {timeSeriesLoading ? (
            <TableSkeleton rows={4} cols={6} />
          ) : timeSeriesError ? (
            <ErrorFallback
              error={timeSeriesError}
              onRetry={() =>
                mutate((key: string) =>
                  typeof key === "string" &&
                  key.startsWith("/dashboard/timeseries")
                )
              }
            />
          ) : chartData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="healthAreaGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366F1" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#6366F1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1C1C1F" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 11, fill: "var(--text-ghost)", fontFamily: "var(--font-mono)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "var(--text-ghost)", fontFamily: "var(--font-mono)" }}
                    axisLine={false}
                    tickLine={false}
                    width={50}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#141416",
                      border: "1px solid var(--border-default)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "11px",
                      borderRadius: "8px",
                    }}
                    labelStyle={{ color: "var(--text-tertiary)" }}
                    itemStyle={{ color: "#6366F1" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#6366F1"
                    fill="url(#healthAreaGradient)"
                    strokeWidth={1.5}
                  />
                </AreaChart>
              </ResponsiveContainer>
              {timeSeries && timeSeries.buckets.length > 0 && (
                <div className="mt-3 flex justify-between text-[12px] font-mono text-[var(--text-ghost)]">
                  <span>
                    {new Date(timeSeries.buckets[0].timestamp).toLocaleDateString()}
                  </span>
                  <span>
                    {timeSeries.buckets.length} buckets / {timeSeries.days}d
                  </span>
                  <span>
                    {new Date(
                      timeSeries.buckets[timeSeries.buckets.length - 1].timestamp
                    ).toLocaleDateString()}
                  </span>
                </div>
              )}
            </>
          ) : (
            <EmptyState
              title="No time-series data"
              description="Select a metric and ensure data exists for the current time window."
            />
          )}
        </div>

        {/* Contamination Overview Section */}
        <div className="card mb-8">
          <SectionHeader title="Contamination Overview">
            <button
              onClick={handleRunScan}
              disabled={!agentFilter || isScanning}
              className="btn btn--primary"
            >
              {isScanning ? "Scanning..." : "Run Scan"}
            </button>
          </SectionHeader>

          {activeScan ? (
            <div className="space-y-6">
              {/* Summary metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Trusted", count: activeScan.trusted, badge: "badge--success" },
                  { label: "Uncertain", count: activeScan.uncertain, badge: "badge--warning" },
                  { label: "Suspect", count: activeScan.suspect, badge: "badge--error" },
                  { label: "Contaminated", count: activeScan.contaminated, badge: "badge--error" },
                ].map((r) => (
                  <div key={r.label} className="bg-[var(--bg-surface-2)] rounded-lg p-4">
                    <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-2">
                      {r.label}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xl font-bold font-mono text-[var(--text-primary)]">
                        {r.count}
                      </span>
                      <span className={`badge ${r.badge}`}>
                        {activeScan.total_memories > 0
                          ? ((r.count / activeScan.total_memories) * 100).toFixed(1)
                          : "0"}
                        %
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-[var(--bg-surface-3)] rounded-full mt-3 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--accent)]"
                        style={{
                          width: `${
                            activeScan.total_memories > 0
                              ? (r.count / activeScan.total_memories) * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Scan metadata */}
              <div className="flex items-center gap-4 text-xs text-[var(--text-ghost)]">
                <span>
                  <span className="font-mono">{activeScan.total_memories}</span> memories scanned
                </span>
                <span>
                  <span className="font-mono">{activeScan.compute_time_ms.toFixed(0)}</span>ms compute
                </span>
                <span>
                  System contamination rate:{" "}
                  <span className="font-mono">
                    {(activeScan.system_contamination_rate * 100).toFixed(2)}%
                  </span>
                </span>
              </div>

              {/* Flagged memories table */}
              {activeScan.flags && activeScan.flags.length > 0 && (
                <div>
                  <SectionHeader title="Flagged Memories" count={activeScan.flags.length} />
                  <div className="overflow-x-auto">
                    <table className="table table-compact">
                      <thead>
                        <tr>
                          <th>Memory ID</th>
                          <th>Grounding Score</th>
                          <th>Risk Level</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeScan.flags.slice(0, 10).map((flag) => {
                          const riskBadge =
                            flag.risk_level.toLowerCase() === "trusted"
                              ? "badge--success"
                              : flag.risk_level.toLowerCase() === "uncertain"
                                ? "badge--warning"
                                : "badge--error";
                          return (
                            <tr key={flag.memory_id}>
                              <td>
                                <EntityLink type="memory" id={flag.memory_id} truncate={12} />
                              </td>
                              <td>
                                <span className="font-mono">
                                  {(flag.grounding_score * 100).toFixed(1)}%
                                </span>
                              </td>
                              <td>
                                <span className={`badge ${riskBadge}`}>
                                  {flag.risk_level}
                                </span>
                              </td>
                              <td className="text-[var(--text-tertiary)] uppercase text-xs">
                                {flag.recommended_action}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <EmptyState
              title="No contamination data"
              description={
                agentFilter
                  ? "Click Run Scan to assess memory contamination risk."
                  : "Enter an agent ID above to scan for contamination."
              }
            />
          )}
        </div>
      </div>
    </PageTransition>
  );
}

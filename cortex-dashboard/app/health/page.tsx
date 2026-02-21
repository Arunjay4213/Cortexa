"use client";

import { useState, useMemo, useCallback } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronDown,
  ArrowUpDown,
  Eye,
  EyeOff,
  Activity,
} from "lucide-react";
import { mockHealthAlerts, mockMemories, mockDashboardKPIs } from "@/lib/mock-data";
import { formatTimestamp, formatMemoryId } from "@/lib/utils";
import { Sparkline } from "@/components/primitives/Sparkline";
import { CHITrendChart } from "@/components/dashboard/CHITrendChart";
import { ContradictionModal } from "@/components/dashboard/ContradictionModal";
import { MemoryDetailPanel } from "@/components/shared/MemoryDetailPanel";
import type { HealthAlert, AlertSeverity, AlertType } from "@/lib/types";

// ── Derived stats from mock data ─────────────────────────────────────────

const activeMemories = mockMemories.filter((m) => m.status === "active");
const contradictionCount = mockHealthAlerts.filter(
  (a) => a.type === "contradiction" && !a.resolved
).length;
const staleCount = activeMemories.filter((m) => m.stalenessScore > 0.7).length;
const coverageGapCount = mockHealthAlerts.filter(
  (a) => a.type === "coverage_gap" && !a.resolved
).length;

// 30-day CHI sparkline (simplified)
const chiSparkline = Array.from({ length: 15 }, (_, i) => {
  const base = 0.82;
  const noise = Math.sin(i * 0.7) * 0.03 + Math.cos(i * 1.3) * 0.02;
  return Math.max(0.6, Math.min(0.95, base + noise * (i / 15)));
});

// ── Sort & filter types ─────────────────────────────────────────────────

type SortKey = "severity" | "detected" | "type";
type SortDir = "asc" | "desc";

const SEVERITY_ORDER: Record<AlertSeverity, number> = {
  critical: 3,
  warning: 2,
  info: 1,
};

function severityIcon(severity: AlertSeverity) {
  switch (severity) {
    case "critical":
      return <AlertCircle size={14} className="text-rose-400" />;
    case "warning":
      return <AlertTriangle size={14} className="text-amber-400" />;
    case "info":
      return <Info size={14} className="text-blue-400" />;
  }
}

function typeBadge(type: AlertType) {
  const styles: Record<AlertType, string> = {
    contradiction: "bg-rose-500/10 text-rose-400 border-rose-500/20",
    stale: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    drift: "bg-violet-500/10 text-violet-400 border-violet-500/20",
    coverage_gap: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  };
  const labels: Record<AlertType, string> = {
    contradiction: "Contradiction",
    stale: "Stale",
    drift: "Drift",
    coverage_gap: "Coverage Gap",
  };
  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${styles[type]}`}
    >
      {labels[type]}
    </span>
  );
}

function actionLabel(type: AlertType): string {
  switch (type) {
    case "contradiction":
      return "Resolve";
    case "stale":
      return "Archive";
    case "drift":
      return "Re-embed";
    case "coverage_gap":
      return "Review";
  }
}

// ── Page ─────────────────────────────────────────────────────────────────

export default function HealthMonitorPage() {
  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [showResolved, setShowResolved] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("severity");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Modals
  const [contradictionAlert, setContradictionAlert] = useState<HealthAlert | null>(null);
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);

  // Filtered & sorted alerts
  const filteredAlerts = useMemo(() => {
    let alerts = [...mockHealthAlerts];

    if (!showResolved) {
      alerts = alerts.filter((a) => !a.resolved);
    }

    if (severityFilter !== "all") {
      alerts = alerts.filter((a) => a.severity === severityFilter);
    }

    if (typeFilter !== "all") {
      alerts = alerts.filter((a) => a.type === typeFilter);
    }

    alerts.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "severity":
          cmp = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
          break;
        case "detected":
          cmp = new Date(a.detectedAt).getTime() - new Date(b.detectedAt).getTime();
          break;
        case "type":
          cmp = a.type.localeCompare(b.type);
          break;
      }
      return sortDir === "desc" ? -cmp : cmp;
    });

    return alerts;
  }, [severityFilter, typeFilter, showResolved, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const handleAction = useCallback(
    (alert: HealthAlert) => {
      if (alert.type === "contradiction") {
        setContradictionAlert(alert);
      }
      // Other types: no-op for now (mock)
    },
    []
  );

  const handleMemoryClick = useCallback((memoryId: string) => {
    setSelectedMemoryId(memoryId);
  }, []);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">Health Monitor</h1>
        <p className="text-[13px] text-zinc-500 mt-0.5">
          Composite Health Index, contradictions, staleness, and drift monitoring
        </p>
      </div>

      {/* Top: Health Overview Cards */}
      <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
        <HealthCard
          label="CHI Score"
          value={mockDashboardKPIs.compositeHealthIndex.toFixed(3)}
          color="emerald"
          sparkline={chiSparkline}
        />
        <HealthCard
          label="Contradictions"
          value={String(contradictionCount)}
          sub="active"
          color="rose"
        />
        <HealthCard
          label="Stale Memories"
          value={String(staleCount)}
          sub={`of ${activeMemories.length}`}
          color="amber"
        />
        <HealthCard
          label="Coverage Gaps"
          value={String(coverageGapCount)}
          sub="topics"
          color="blue"
        />
      </div>

      {/* Middle: CHI Trend Chart */}
      <CHITrendChart />

      {/* Main: Problem List Table */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-zinc-800">
          <div className="flex items-center gap-1.5">
            <Activity size={14} className="text-zinc-500" />
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Health Alerts
            </span>
          </div>

          <div className="flex-1" />

          {/* Severity filter */}
          <div className="relative">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="appearance-none bg-zinc-900 border border-zinc-700 rounded-md pl-3 pr-7 py-1.5 text-[12px] text-zinc-300 focus:outline-none focus:border-zinc-500 transition-colors cursor-pointer"
            >
              <option value="all">All Severity</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
            <ChevronDown
              size={12}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
            />
          </div>

          {/* Type filter */}
          <div className="relative">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="appearance-none bg-zinc-900 border border-zinc-700 rounded-md pl-3 pr-7 py-1.5 text-[12px] text-zinc-300 focus:outline-none focus:border-zinc-500 transition-colors cursor-pointer"
            >
              <option value="all">All Types</option>
              <option value="contradiction">Contradiction</option>
              <option value="stale">Stale</option>
              <option value="drift">Drift</option>
              <option value="coverage_gap">Coverage Gap</option>
            </select>
            <ChevronDown
              size={12}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
            />
          </div>

          {/* Show resolved toggle */}
          <button
            onClick={() => setShowResolved((v) => !v)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] transition-colors border ${
              showResolved
                ? "border-zinc-600 bg-zinc-800 text-zinc-200"
                : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {showResolved ? <Eye size={12} /> : <EyeOff size={12} />}
            Resolved
          </button>

          {/* Sort controls */}
          <div className="flex items-center gap-1 text-[11px] text-zinc-500">
            <ArrowUpDown size={12} />
            {(["severity", "detected", "type"] as SortKey[]).map((key) => (
              <button
                key={key}
                onClick={() => toggleSort(key)}
                className={`px-2 py-1 rounded-md transition-colors capitalize ${
                  sortKey === key
                    ? "bg-zinc-800 text-zinc-200"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {key === "detected" ? "Date" : key}
                {sortKey === key && (
                  <span className="ml-0.5">{sortDir === "desc" ? "\u2193" : "\u2191"}</span>
                )}
              </button>
            ))}
          </div>

          <span className="text-[11px] text-zinc-600">
            {filteredAlerts.length} alert{filteredAlerts.length !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-[10px] font-medium uppercase tracking-wider text-zinc-600 border-b border-zinc-800">
                <th className="text-left px-4 py-2.5 w-8" />
                <th className="text-left px-2 py-2.5">Type</th>
                <th className="text-left px-2 py-2.5">Memory IDs</th>
                <th className="text-left px-2 py-2.5">Description</th>
                <th className="text-left px-2 py-2.5 w-20">Detected</th>
                <th className="text-center px-2 py-2.5 w-24">Status</th>
                <th className="text-center px-2 py-2.5 w-24">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {filteredAlerts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-[13px] text-zinc-600">
                    No alerts match your filters.
                  </td>
                </tr>
              ) : (
                filteredAlerts.map((alert) => (
                  <AlertRow
                    key={alert.id}
                    alert={alert}
                    onAction={() => handleAction(alert)}
                    onMemoryClick={handleMemoryClick}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Contradiction Modal */}
      <ContradictionModal
        alert={contradictionAlert}
        onClose={() => setContradictionAlert(null)}
      />

      {/* Memory Detail Panel */}
      <MemoryDetailPanel
        memoryId={selectedMemoryId}
        onClose={() => setSelectedMemoryId(null)}
      />
    </div>
  );
}

// ── Health Overview Card ─────────────────────────────────────────────────

function HealthCard({
  label,
  value,
  sub,
  color,
  sparkline,
}: {
  label: string;
  value: string;
  sub?: string;
  color: "emerald" | "rose" | "amber" | "blue";
  sparkline?: number[];
}) {
  const borderColors: Record<string, string> = {
    emerald: "border-l-emerald-500",
    rose: "border-l-rose-500",
    amber: "border-l-amber-500",
    blue: "border-l-blue-500",
  };

  const valueColors: Record<string, string> = {
    emerald: "text-emerald-400",
    rose: "text-rose-400",
    amber: "text-amber-400",
    blue: "text-blue-400",
  };

  const sparkColors: Record<string, string> = {
    emerald: "#10b981",
    rose: "#f43f5e",
    amber: "#f59e0b",
    blue: "#3b82f6",
  };

  return (
    <div
      className={`min-w-[220px] h-24 bg-zinc-950 border border-zinc-800 border-l-[3px] rounded-lg
        px-4 py-3 flex flex-col justify-between shrink-0 ${borderColors[color]}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wider text-zinc-500 font-medium leading-none">
          {label}
        </span>
        {sparkline && (
          <Sparkline data={sparkline} color={sparkColors[color]} width={60} height={16} />
        )}
      </div>
      <div className="flex items-end gap-2">
        <span className={`text-2xl font-mono font-medium leading-none tabular-nums ${valueColors[color]}`}>
          {value}
        </span>
        {sub && (
          <span className="text-[11px] font-mono text-zinc-500 leading-none mb-0.5">
            {sub}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Alert Row ────────────────────────────────────────────────────────────

function AlertRow({
  alert,
  onAction,
  onMemoryClick,
}: {
  alert: HealthAlert;
  onAction: () => void;
  onMemoryClick: (id: string) => void;
}) {
  const isCritical = alert.severity === "critical" && !alert.resolved;

  return (
    <tr className={isCritical ? "bg-rose-950/10" : ""}>
      {/* Severity icon */}
      <td className="px-4 py-2.5">
        {severityIcon(alert.severity)}
      </td>

      {/* Type badge */}
      <td className="px-2 py-2.5">
        {typeBadge(alert.type)}
      </td>

      {/* Memory IDs */}
      <td className="px-2 py-2.5">
        <div className="flex flex-wrap gap-1">
          {alert.memoryIds.length > 0 ? (
            alert.memoryIds.slice(0, 4).map((id) => (
              <button
                key={id}
                onClick={() => onMemoryClick(id)}
                className="text-[11px] font-mono text-zinc-400 hover:text-zinc-200 transition-colors px-1.5 py-0.5 rounded bg-zinc-800/50 hover:bg-zinc-800"
              >
                {formatMemoryId(id)}
              </button>
            ))
          ) : (
            <span className="text-[11px] text-zinc-600">&mdash;</span>
          )}
          {alert.memoryIds.length > 4 && (
            <span className="text-[10px] text-zinc-600">
              +{alert.memoryIds.length - 4}
            </span>
          )}
        </div>
      </td>

      {/* Description */}
      <td className="px-2 py-2.5">
        <p className="text-[12px] text-zinc-400 leading-relaxed max-w-[400px]">
          {alert.description.length > 140
            ? alert.description.slice(0, 140) + "\u2026"
            : alert.description}
        </p>
      </td>

      {/* Detected */}
      <td className="px-2 py-2.5">
        <span className="text-[11px] font-mono text-zinc-600 whitespace-nowrap">
          {formatTimestamp(alert.detectedAt)}
        </span>
      </td>

      {/* Status */}
      <td className="px-2 py-2.5 text-center">
        {alert.resolved ? (
          <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Resolved
          </span>
        ) : (
          <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
            Unresolved
          </span>
        )}
      </td>

      {/* Action */}
      <td className="px-2 py-2.5 text-center">
        {!alert.resolved && (
          <button
            onClick={onAction}
            className="px-3 py-1 rounded-md border border-zinc-700 text-[11px] font-medium text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 transition-all"
          >
            {actionLabel(alert.type)}
          </button>
        )}
      </td>
    </tr>
  );
}

"use client";

import { useState, useMemo, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { ChevronDown, ChevronRight, Check } from "lucide-react";

import { StatPanel } from "@/components/dashboard/StatPanel";
import { GrafanaPanel } from "@/components/dashboard/GrafanaPanel";
import { MemoryDetailPanel } from "@/components/shared/MemoryDetailPanel";
import {
  mockHealthAlerts,
  mockMemories,
  mockDashboardKPIs,
} from "@/lib/mock-data";
import { formatTimestamp, formatMemoryId } from "@/lib/utils";
import type {
  HealthAlert,
  AlertSeverity,
  AlertType,
  Memory,
} from "@/lib/types";

// ── Derived stats ────────────────────────────────────────────────────────

const activeMemories = mockMemories.filter((m) => m.status === "active");
const contradictionCount = mockHealthAlerts.filter(
  (a) => a.type === "contradiction" && !a.resolved
).length;
const staleCount = activeMemories.filter(
  (m) => m.stalenessScore > 0.7
).length;
const coverageGapCount = mockHealthAlerts.filter(
  (a) => a.type === "coverage_gap" && !a.resolved
).length;

// ── CHI 30-day data with annotations ─────────────────────────────────────

interface CHIPoint {
  dateLabel: string;
  chi: number;
  event?: string;
}

const CHI_EVENTS: Record<number, string> = {
  3: "Contradiction detected: mem-012 vs mem-038",
  8: "Bulk archive: 5 stale memories removed",
  14: "New memory cluster: notification preferences",
  19: "Drift spike: tech stack memories",
  25: "Health check passed: all critical memories verified",
};

function buildCHIData(): CHIPoint[] {
  const points: CHIPoint[] = [];
  const now = new Date("2026-02-20T12:00:00Z");
  let chi = 0.82;

  for (let i = 29; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const noise = Math.sin(i * 0.7) * 0.03 + Math.cos(i * 1.3) * 0.02;
    if (i === 19) chi -= 0.08;
    else if (i === 8) chi += 0.05;
    else if (i === 3) chi -= 0.04;
    else chi += noise * 0.3;
    chi = Math.max(0.55, Math.min(0.95, chi));

    points.push({
      dateLabel: d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      chi: Math.round(chi * 1000) / 1000,
      event: CHI_EVENTS[i],
    });
  }
  return points;
}

// ── Severity helpers ─────────────────────────────────────────────────────

const SEVERITY_ORDER: Record<AlertSeverity, number> = {
  critical: 3,
  warning: 2,
  info: 1,
};

function severityDot(severity: AlertSeverity) {
  const map: Record<AlertSeverity, string> = {
    critical: "#f2495c",
    warning: "#ff9830",
    info: "#5794f2",
  };
  return (
    <span
      className="inline-block w-[8px] h-[8px] rounded-full shrink-0"
      style={{ background: map[severity] }}
    />
  );
}

function typeBadge(type: AlertType) {
  const map: Record<
    AlertType,
    { bg: string; color: string; border: string; label: string }
  > = {
    contradiction: {
      bg: "rgba(242,73,92,0.10)",
      color: "#f2495c",
      border: "rgba(242,73,92,0.20)",
      label: "Contradiction",
    },
    stale: {
      bg: "rgba(255,152,48,0.10)",
      color: "#ff9830",
      border: "rgba(255,152,48,0.20)",
      label: "Stale",
    },
    drift: {
      bg: "rgba(184,119,217,0.10)",
      color: "#b877d9",
      border: "rgba(184,119,217,0.20)",
      label: "Drift",
    },
    coverage_gap: {
      bg: "rgba(87,148,242,0.10)",
      color: "#5794f2",
      border: "rgba(87,148,242,0.20)",
      label: "Coverage Gap",
    },
  };
  const s = map[type];
  return (
    <span
      className="inline-flex px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wide"
      style={{
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.border}`,
      }}
    >
      {s.label}
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
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [showResolved, setShowResolved] = useState(false);
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);
  const [expandedContradictions, setExpandedContradictions] = useState<
    Set<string>
  >(new Set());

  const kpis = mockDashboardKPIs;

  // Filtered alerts
  const filteredAlerts = useMemo(() => {
    let alerts = [...mockHealthAlerts];
    if (!showResolved) alerts = alerts.filter((a) => !a.resolved);
    if (severityFilter !== "all")
      alerts = alerts.filter((a) => a.severity === severityFilter);
    if (typeFilter !== "all")
      alerts = alerts.filter((a) => a.type === typeFilter);
    alerts.sort(
      (a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity]
    );
    return alerts;
  }, [severityFilter, typeFilter, showResolved]);

  // Contradiction pairs (unresolved only)
  const contradictions = useMemo(
    () =>
      mockHealthAlerts.filter(
        (a) => a.type === "contradiction" && !a.resolved && a.memoryIds.length >= 2
      ),
    []
  );

  const handleMemoryClick = useCallback((memoryId: string) => {
    setSelectedMemoryId(memoryId);
  }, []);

  const toggleContradiction = useCallback((alertId: string) => {
    setExpandedContradictions((prev) => {
      const next = new Set(prev);
      if (next.has(alertId)) next.delete(alertId);
      else next.add(alertId);
      return next;
    });
  }, []);

  return (
    <div className="flex flex-col" style={{ gap: "var(--panel-gap)" }}>
      {/* ── ROW 1: Stat panels ─────────────────────────────────── */}
      <div className="grid-4">
        <StatPanel
          label="CHI Score"
          value={kpis.compositeHealthIndex.toFixed(3)}
          color="green"
          sparkline={kpis.chiHistory}
        />
        <StatPanel
          label="Contradictions"
          value={`${contradictionCount} Active`}
          color="red"
        />
        <StatPanel
          label="Stale Memories"
          value={String(staleCount)}
          color="yellow"
        />
        <StatPanel
          label="Coverage Gaps"
          value={`${coverageGapCount} Topics`}
          color="blue"
        />
      </div>

      {/* ── ROW 2: CHI 30-day Trend ────────────────────────────── */}
      <GrafanaPanel
        title="Composite Health Index — 30 Day Trend"
        headerRight={
          <div
            className="flex items-center gap-4 text-[10px]"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            <span className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: "var(--grafana-green)" }}
              />
              &gt; 0.80
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: "var(--grafana-yellow)" }}
              />
              0.60–0.80
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: "var(--grafana-red)" }}
              />
              &lt; 0.60
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="w-2 h-[3px] rounded-sm"
                style={{ background: "var(--grafana-yellow)" }}
              />
              Annotations
            </span>
          </div>
        }
      >
        <CHITrendFull />
      </GrafanaPanel>

      {/* ── ROW 3: Health Alerts Table ──────────────────────────── */}
      <GrafanaPanel title="Health Alerts" noPadding>
        {/* Filter bar */}
        <div
          className="flex flex-wrap items-center gap-3 px-4 py-2.5"
          style={{ borderBottom: "1px solid var(--panel-border)" }}
        >
          {/* Severity tabs */}
          <SeverityTabs value={severityFilter} onChange={setSeverityFilter} />

          <div className="flex-1" />

          {/* Type dropdown */}
          <GrafanaSelect
            value={typeFilter}
            onChange={setTypeFilter}
            options={[
              { value: "all", label: "All Types" },
              { value: "contradiction", label: "Contradiction" },
              { value: "stale", label: "Stale" },
              { value: "drift", label: "Drift" },
              { value: "coverage_gap", label: "Coverage Gap" },
            ]}
          />

          {/* Show resolved toggle */}
          <GrafanaToggle
            checked={showResolved}
            onChange={setShowResolved}
            label="Show resolved"
          />

          <span
            className="text-[11px] font-mono"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            {filteredAlerts.length} alert
            {filteredAlerts.length !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr
                style={{ borderBottom: "1px solid var(--panel-border)" }}
              >
                <th
                  className="text-left px-4 py-2.5 w-8 text-[10px] uppercase tracking-wider font-medium"
                  style={{ color: "var(--grafana-text-muted)" }}
                />
                <th
                  className="text-left px-2 py-2.5 text-[10px] uppercase tracking-wider font-medium"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Type
                </th>
                <th
                  className="text-left px-2 py-2.5 text-[10px] uppercase tracking-wider font-medium"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Memory IDs
                </th>
                <th
                  className="text-left px-2 py-2.5 text-[10px] uppercase tracking-wider font-medium"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Description
                </th>
                <th
                  className="text-left px-2 py-2.5 w-24 text-[10px] uppercase tracking-wider font-medium"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Detected
                </th>
                <th
                  className="text-center px-2 py-2.5 w-24 text-[10px] uppercase tracking-wider font-medium"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Status
                </th>
                <th
                  className="text-center px-2 py-2.5 w-24 text-[10px] uppercase tracking-wider font-medium"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-8 text-center text-[13px]"
                    style={{ color: "var(--grafana-text-muted)" }}
                  >
                    No alerts match your filters.
                  </td>
                </tr>
              ) : (
                filteredAlerts.map((alert) => (
                  <AlertRow
                    key={alert.id}
                    alert={alert}
                    onMemoryClick={handleMemoryClick}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </GrafanaPanel>

      {/* ── ROW 4: Contradiction Resolver ──────────────────────── */}
      <GrafanaPanel
        title="Contradiction Details"
        headerRight={
          <span
            className="text-[10px] font-mono"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            {contradictions.length} active pair
            {contradictions.length !== 1 ? "s" : ""}
          </span>
        }
        noPadding
      >
        {contradictions.length === 0 ? (
          <div
            className="px-4 py-8 text-center text-[13px]"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            No active contradictions.
          </div>
        ) : (
          <div className="flex flex-col">
            {contradictions.map((alert) => (
              <ContradictionRow
                key={alert.id}
                alert={alert}
                expanded={expandedContradictions.has(alert.id)}
                onToggle={() => toggleContradiction(alert.id)}
                onMemoryClick={handleMemoryClick}
              />
            ))}
          </div>
        )}
      </GrafanaPanel>

      {/* Memory Detail slide-out */}
      <MemoryDetailPanel
        memoryId={selectedMemoryId}
        onClose={() => setSelectedMemoryId(null)}
      />
    </div>
  );
}

// ── CHI Trend Full Chart ─────────────────────────────────────────────────

function CHITrendFull() {
  const data = useMemo(() => buildCHIData(), []);

  return (
    <div className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <defs>
            <linearGradient id="chiAreaHealth" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#73bf69" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#73bf69" stopOpacity={0} />
            </linearGradient>
          </defs>

          {/* Threshold bands */}
          <ReferenceArea y1={0.8} y2={1.0} fill="#73bf69" fillOpacity={0.06} />
          <ReferenceArea y1={0.6} y2={0.8} fill="#ff9830" fillOpacity={0.04} />
          <ReferenceArea y1={0.5} y2={0.6} fill="#f2495c" fillOpacity={0.04} />

          <CartesianGrid
            stroke="var(--grid-line)"
            strokeDasharray="none"
            vertical={false}
          />

          <XAxis
            dataKey="dateLabel"
            tick={{
              fontSize: 11,
              fill: "var(--axis-text)",
              fontFamily: "var(--font-mono)",
            }}
            axisLine={{ stroke: "var(--panel-border)" }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0.5, 1]}
            ticks={[0.5, 0.6, 0.7, 0.8, 0.9, 1.0]}
            tick={{
              fontSize: 11,
              fill: "var(--axis-text)",
              fontFamily: "var(--font-mono)",
            }}
            axisLine={false}
            tickLine={false}
            width={36}
          />

          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const d = payload[0].payload as CHIPoint;
              const c =
                d.chi >= 0.8
                  ? "var(--grafana-green)"
                  : d.chi >= 0.6
                    ? "var(--grafana-yellow)"
                    : "var(--grafana-red)";
              return (
                <div
                  style={{
                    background: "var(--panel-bg)",
                    border: "1px solid var(--panel-border)",
                    borderRadius: "var(--panel-radius)",
                  }}
                  className="px-3 py-2 max-w-[260px]"
                >
                  <div className="flex items-center justify-between gap-4 mb-0.5">
                    <span
                      className="text-[11px]"
                      style={{ color: "var(--grafana-text-muted)" }}
                    >
                      {d.dateLabel}
                    </span>
                    <span
                      className="text-[13px] font-mono font-medium"
                      style={{ color: c }}
                    >
                      {d.chi.toFixed(3)}
                    </span>
                  </div>
                  {d.event && (
                    <div
                      className="text-[10px] mt-1 pt-1"
                      style={{
                        color: "var(--grafana-text-muted)",
                        borderTop: "1px solid var(--panel-border)",
                      }}
                    >
                      {d.event}
                    </div>
                  )}
                </div>
              );
            }}
          />

          <ReferenceLine
            y={0.8}
            stroke="var(--grafana-green)"
            strokeDasharray="4 4"
            strokeOpacity={0.35}
          />
          <ReferenceLine
            y={0.6}
            stroke="var(--grafana-yellow)"
            strokeDasharray="4 4"
            strokeOpacity={0.35}
          />

          {/* Annotation lines for events */}
          {data
            .filter((d) => d.event)
            .map((d) => (
              <ReferenceLine
                key={d.dateLabel}
                x={d.dateLabel}
                stroke="var(--grafana-yellow)"
                strokeDasharray="3 3"
                strokeOpacity={0.4}
                label={{
                  value: d.event!.split(":")[0],
                  position: "top",
                  fill: "var(--grafana-text-muted)",
                  fontSize: 9,
                }}
              />
            ))}

          <Line
            type="monotone"
            dataKey="chi"
            stroke="var(--grafana-green)"
            strokeWidth={2}
            fill="url(#chiAreaHealth)"
            dot={(props) => {
              const { cx, cy, payload } = props as {
                cx: number;
                cy: number;
                payload: CHIPoint;
              };
              if (!payload.event) return <g key={`d-${cx}`} />;
              return (
                <g key={`ev-${cx}`}>
                  <circle
                    cx={cx}
                    cy={cy}
                    r={5}
                    fill="var(--panel-bg)"
                    stroke="var(--grafana-yellow)"
                    strokeWidth={2}
                  />
                  <circle cx={cx} cy={cy} r={2} fill="var(--grafana-yellow)" />
                </g>
              );
            }}
            activeDot={{
              r: 4,
              fill: "var(--grafana-green)",
              stroke: "var(--panel-bg)",
              strokeWidth: 2,
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Severity Tab Bar ─────────────────────────────────────────────────────

function SeverityTabs({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const tabs = [
    { value: "all", label: "All" },
    { value: "critical", label: "Critical" },
    { value: "warning", label: "Warning" },
    { value: "info", label: "Info" },
  ];

  return (
    <div className="flex items-center gap-0.5">
      {tabs.map((tab) => {
        const active = value === tab.value;
        return (
          <button
            key={tab.value}
            onClick={() => onChange(tab.value)}
            className="px-2.5 py-1.5 text-[11px] font-medium transition-colors relative"
            style={{
              color: active
                ? "var(--grafana-text-primary)"
                : "var(--grafana-text-muted)",
              background: "transparent",
            }}
            onMouseEnter={(e) => {
              if (!active)
                e.currentTarget.style.color = "var(--grafana-text-secondary)";
            }}
            onMouseLeave={(e) => {
              if (!active)
                e.currentTarget.style.color = "var(--grafana-text-muted)";
            }}
          >
            {tab.label}
            {active && (
              <span
                className="absolute bottom-0 left-0 right-0 h-[2px]"
                style={{ background: "var(--grafana-green)" }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

// ── Grafana Select ───────────────────────────────────────────────────────

function GrafanaSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none pl-3 pr-7 py-1.5 text-[12px] font-mono cursor-pointer focus:outline-none transition-colors"
        style={{
          background: "#0b0c0e",
          border: "1px solid var(--panel-border)",
          borderRadius: "2px",
          color: "var(--grafana-text-secondary)",
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown
        size={12}
        className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none"
        style={{ color: "var(--grafana-text-muted)" }}
      />
    </div>
  );
}

// ── Grafana Toggle ───────────────────────────────────────────────────────

function GrafanaToggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className="flex items-center gap-2 text-[11px]"
      style={{ color: "var(--grafana-text-muted)" }}
    >
      <span
        className="relative inline-block w-[28px] h-[14px] rounded-full transition-colors"
        style={{
          background: checked ? "var(--grafana-green)" : "#464c54",
        }}
      >
        <span
          className="absolute top-[2px] w-[10px] h-[10px] rounded-full bg-white transition-transform"
          style={{
            left: checked ? 16 : 2,
          }}
        />
      </span>
      {label}
    </button>
  );
}

// ── Alert Row ────────────────────────────────────────────────────────────

function AlertRow({
  alert,
  onMemoryClick,
}: {
  alert: HealthAlert;
  onMemoryClick: (id: string) => void;
}) {
  const isCritical = alert.severity === "critical" && !alert.resolved;

  return (
    <tr
      style={{
        borderBottom: "1px solid var(--panel-border)",
        background: isCritical ? "rgba(242,73,92,0.04)" : undefined,
      }}
      className="transition-colors"
      onMouseEnter={(e) =>
        (e.currentTarget.style.background = isCritical
          ? "rgba(242,73,92,0.08)"
          : "var(--panel-bg-hover)")
      }
      onMouseLeave={(e) =>
        (e.currentTarget.style.background = isCritical
          ? "rgba(242,73,92,0.04)"
          : "transparent")
      }
    >
      {/* Severity dot */}
      <td className="px-4 py-2.5">{severityDot(alert.severity)}</td>

      {/* Type badge */}
      <td className="px-2 py-2.5">{typeBadge(alert.type)}</td>

      {/* Memory IDs */}
      <td className="px-2 py-2.5">
        <div className="flex flex-wrap gap-1">
          {alert.memoryIds.length > 0 ? (
            alert.memoryIds.slice(0, 4).map((id) => (
              <button
                key={id}
                onClick={() => onMemoryClick(id)}
                className="text-[11px] font-mono px-1.5 py-0.5 rounded-sm transition-colors cursor-pointer"
                style={{
                  background: "var(--panel-bg-hover)",
                  color: "#6e9fff",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "#2c3235";
                  e.currentTarget.style.color = "#8ab8ff";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--panel-bg-hover)";
                  e.currentTarget.style.color = "#6e9fff";
                }}
              >
                {formatMemoryId(id)}
              </button>
            ))
          ) : (
            <span
              className="text-[11px]"
              style={{ color: "var(--grafana-text-disabled)" }}
            >
              &mdash;
            </span>
          )}
          {alert.memoryIds.length > 4 && (
            <span
              className="text-[10px]"
              style={{ color: "var(--grafana-text-muted)" }}
            >
              +{alert.memoryIds.length - 4}
            </span>
          )}
        </div>
      </td>

      {/* Description */}
      <td className="px-2 py-2.5">
        <p
          className="text-[12px] leading-relaxed max-w-[400px]"
          style={{ color: "var(--grafana-text-secondary)" }}
        >
          {alert.description.length > 140
            ? alert.description.slice(0, 140) + "\u2026"
            : alert.description}
        </p>
      </td>

      {/* Detected */}
      <td className="px-2 py-2.5">
        <span
          className="text-[11px] font-mono whitespace-nowrap"
          style={{ color: "var(--grafana-text-muted)" }}
        >
          {formatTimestamp(alert.detectedAt)}
        </span>
      </td>

      {/* Status */}
      <td className="px-2 py-2.5 text-center">
        {alert.resolved ? (
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-medium"
            style={{
              background: "rgba(115,191,105,0.10)",
              color: "var(--grafana-green)",
              border: "1px solid rgba(115,191,105,0.20)",
            }}
          >
            <Check size={10} />
            Resolved
          </span>
        ) : (
          <span
            className="inline-flex px-2 py-0.5 rounded-sm text-[10px] font-medium"
            style={{
              background: "rgba(255,152,48,0.10)",
              color: "var(--grafana-yellow)",
              border: "1px solid rgba(255,152,48,0.20)",
            }}
          >
            Unresolved
          </span>
        )}
      </td>

      {/* Action */}
      <td className="px-2 py-2.5 text-center">
        {!alert.resolved && (
          <button
            className="px-3 py-1 rounded-sm text-[11px] font-medium transition-colors"
            style={{
              background: "transparent",
              border: "1px solid var(--panel-border)",
              color: "var(--grafana-text-primary)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = "var(--panel-bg-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "transparent")
            }
          >
            {actionLabel(alert.type)}
          </button>
        )}
      </td>
    </tr>
  );
}

// ── Contradiction Row ────────────────────────────────────────────────────

function ContradictionRow({
  alert,
  expanded,
  onToggle,
  onMemoryClick,
}: {
  alert: HealthAlert;
  expanded: boolean;
  onToggle: () => void;
  onMemoryClick: (id: string) => void;
}) {
  const memories = useMemo(() => {
    return alert.memoryIds
      .slice(0, 2)
      .map((id) => mockMemories.find((m) => m.id === id))
      .filter(Boolean) as Memory[];
  }, [alert.memoryIds]);

  if (memories.length < 2) return null;
  const [memA, memB] = memories;

  return (
    <div style={{ borderBottom: "1px solid var(--panel-border)" }}>
      {/* Collapsed header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 transition-colors text-left"
        style={{ background: "transparent" }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.background = "var(--panel-bg-hover)")
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.background = "transparent")
        }
      >
        <span
          className="inline-block w-[8px] h-[8px] rounded-full shrink-0"
          style={{ background: "#f2495c" }}
        />
        <span
          className="text-[12px] font-mono font-medium"
          style={{ color: "var(--grafana-text-primary)" }}
        >
          {formatMemoryId(memA.id)} vs {formatMemoryId(memB.id)}
        </span>
        <span
          className="text-[12px] flex-1 truncate"
          style={{ color: "var(--grafana-text-secondary)" }}
        >
          — {alert.description.split(".")[0]}
        </span>
        <span
          className="flex items-center gap-1 text-[11px] shrink-0"
          style={{ color: "var(--grafana-text-muted)" }}
        >
          {expanded ? "Collapse" : "Expand"}
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4">
          {/* Side-by-side memory cards */}
          <div
            className="grid grid-cols-2"
            style={{ gap: "var(--panel-gap)" }}
          >
            <ContradictionCard
              memory={memA}
              onMemoryClick={onMemoryClick}
            />
            <ContradictionCard
              memory={memB}
              onMemoryClick={onMemoryClick}
            />
          </div>

          {/* Actions */}
          <div
            className="mt-3 pt-3 flex flex-wrap gap-2"
            style={{ borderTop: "1px solid var(--panel-border)" }}
          >
            <span
              className="text-[10px] uppercase tracking-wider font-medium self-center mr-2"
              style={{ color: "var(--grafana-text-muted)" }}
            >
              Actions:
            </span>
            <GrafanaButton
              label={`Keep ${formatMemoryId(memA.id)}, Archive ${formatMemoryId(memB.id)}`}
            />
            <GrafanaButton
              label={`Keep ${formatMemoryId(memB.id)}, Archive ${formatMemoryId(memA.id)}`}
            />
            <GrafanaButton label="Keep Both (Preference Evolution)" />
            <GrafanaButton label="Consolidate" primary />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Contradiction Memory Card ────────────────────────────────────────────

function ContradictionCard({
  memory,
  onMemoryClick,
}: {
  memory: Memory;
  onMemoryClick: (id: string) => void;
}) {
  const healthLabel =
    memory.healthScore >= 0.8
      ? "HEALTHY"
      : memory.healthScore >= 0.5
        ? "DEGRADED"
        : "STALE";
  const healthColor =
    memory.healthScore >= 0.8
      ? "var(--grafana-green)"
      : memory.healthScore >= 0.5
        ? "var(--grafana-yellow)"
        : "var(--grafana-red)";

  // Average attribution score (simplified)
  const avgAttribution = useMemo(() => {
    const traces = mockMemories.find((m) => m.id === memory.id);
    return traces ? (memory.healthScore * 0.8 + 0.1).toFixed(2) : "—";
  }, [memory]);

  return (
    <div
      className="flex flex-col gap-2.5 p-3 rounded-sm"
      style={{
        background: "#111217",
        border: "1px solid var(--panel-border)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => onMemoryClick(memory.id)}
          className="text-[12px] font-mono font-medium transition-colors"
          style={{ color: "#6e9fff" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#8ab8ff")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#6e9fff")}
        >
          Memory {formatMemoryId(memory.id)}
        </button>
      </div>

      {/* Content */}
      <div
        className="text-[13px] font-mono leading-relaxed p-2.5 rounded-sm"
        style={{
          background: "#0b0c0e",
          border: "1px solid var(--panel-border)",
          color: "var(--grafana-text-primary)",
        }}
      >
        &ldquo;{memory.content}&rdquo;
      </div>

      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-1.5 text-[10px]">
        <div>
          <span style={{ color: "var(--grafana-text-muted)" }}>Created: </span>
          <span
            className="font-mono"
            style={{ color: "var(--grafana-text-secondary)" }}
          >
            {new Date(memory.createdAt).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--grafana-text-muted)" }}>
            Last Retrieved:{" "}
          </span>
          <span
            className="font-mono"
            style={{ color: "var(--grafana-text-secondary)" }}
          >
            {new Date(memory.lastRetrieved).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}
          </span>
        </div>
        <div>
          <span style={{ color: "var(--grafana-text-muted)" }}>Health: </span>
          <span className="font-mono" style={{ color: healthColor }}>
            {memory.healthScore.toFixed(2)} ({healthLabel})
          </span>
        </div>
        <div>
          <span style={{ color: "var(--grafana-text-muted)" }}>
            Attribution:{" "}
          </span>
          <span
            className="font-mono"
            style={{ color: "var(--grafana-text-secondary)" }}
          >
            {avgAttribution} avg
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Grafana Button ───────────────────────────────────────────────────────

function GrafanaButton({
  label,
  primary,
}: {
  label: string;
  primary?: boolean;
}) {
  return (
    <button
      className="px-3 py-1.5 rounded-sm text-[11px] font-medium transition-colors"
      style={{
        background: primary ? "rgba(115,191,105,0.10)" : "transparent",
        border: primary
          ? "1px solid rgba(115,191,105,0.30)"
          : "1px solid var(--panel-border)",
        color: primary
          ? "var(--grafana-green)"
          : "var(--grafana-text-primary)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = primary
          ? "rgba(115,191,105,0.18)"
          : "var(--panel-bg-hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = primary
          ? "rgba(115,191,105,0.10)"
          : "transparent";
      }}
    >
      {label}
    </button>
  );
}

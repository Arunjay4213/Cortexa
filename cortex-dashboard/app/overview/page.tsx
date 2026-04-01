"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import {
  AlertTriangle,
  Check,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  MoreHorizontal,
  Shield,
  Clock,
  CheckCircle2,
} from "lucide-react";

import { StatPanel } from "@/components/dashboard/StatPanel";
import { GrafanaPanel } from "@/components/dashboard/GrafanaPanel";
import { BarGauge } from "@/components/dashboard/BarGauge";
import {
  mockDashboardKPIs,
  mockQueryTraces,
  mockMemories,
  mockHealthAlerts,
  mockDeletionRequests,
  mockProvenanceNodes,
  mockProvenanceEdges,
} from "@/lib/mock-data";
import {
  formatTimestamp,
  formatMemoryId,
  truncateText,
  formatCurrency,
  formatPercentage,
} from "@/lib/utils";
import type { Memory, QueryTrace, RetrievedMemory } from "@/lib/types";

// ═══════════════════════════════════════════════════════════════════════════
// ROW 3 LEFT — Query Attribution Feed (table)
// ═══════════════════════════════════════════════════════════════════════════

function healthIcon(status: RetrievedMemory["healthStatus"]) {
  switch (status) {
    case "stale":
      return <span className="text-[10px] font-medium" style={{ color: "var(--grafana-yellow)" }}>STALE</span>;
    case "contradictory":
      return <span className="text-[10px] font-medium" style={{ color: "var(--grafana-red)" }}>CONFLICT</span>;
    case "drifted":
      return <span className="text-[10px] font-medium" style={{ color: "var(--grafana-yellow)" }}>DRIFT</span>;
    default:
      return <Check size={12} style={{ color: "var(--grafana-green)" }} />;
  }
}

function riskColor(risk: QueryTrace["hallucinationRisk"]) {
  switch (risk) {
    case "high": return "var(--grafana-red)";
    case "medium": return "var(--grafana-yellow)";
    case "low": return "var(--grafana-text-muted)";
    default: return "var(--grafana-green)";
  }
}

function QueryFeedTable() {
  const traces = useMemo(
    () =>
      [...mockQueryTraces]
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, 12),
    []
  );

  return (
    <div className="overflow-y-auto max-h-[420px]">
      <table className="w-full text-[12px]">
        <thead className="sticky top-0 z-10" style={{ background: "var(--panel-bg)" }}>
          <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
            <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Time</th>
            <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Agent</th>
            <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Query</th>
            <th className="text-right py-2 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Mem</th>
            <th className="text-right py-2 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Cost</th>
            <th className="text-right py-2 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Risk</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((t) => (
            <tr
              key={t.id}
              className="transition-colors hover:brightness-110"
              style={{ borderBottom: "1px solid var(--panel-border)" }}
              onMouseEnter={(e) => e.currentTarget.style.background = "var(--panel-bg-hover)"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
            >
              <td className="py-2 px-3 font-mono tabular-nums whitespace-nowrap" style={{ color: "var(--grafana-text-muted)" }}>
                {formatTimestamp(t.timestamp)}
              </td>
              <td className="py-2 px-3">
                <span className="px-1.5 py-0.5 rounded-sm text-[10px] font-medium" style={{ background: "var(--panel-bg-hover)", color: "var(--grafana-text-secondary)" }}>
                  {t.agentId}
                </span>
              </td>
              <td className="py-2 px-3 font-mono max-w-[220px] truncate" style={{ color: "var(--grafana-text-secondary)" }}>
                {truncateText(t.query, 45)}
              </td>
              <td className="py-2 px-3 text-right font-mono tabular-nums" style={{ color: "var(--grafana-text-secondary)" }}>
                {t.memoriesRetrieved.length}
              </td>
              <td className="py-2 px-3 text-right font-mono tabular-nums" style={{ color: "var(--grafana-text-muted)" }}>
                {formatCurrency(t.totalCost)}
              </td>
              <td className="py-2 px-3 text-right">
                <span className="text-[10px] font-bold uppercase" style={{ color: riskColor(t.hallucinationRisk) }}>
                  {t.hallucinationRisk === "none" ? "—" : t.hallucinationRisk}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ROW 3 RIGHT — Memory Health Donut
// ═══════════════════════════════════════════════════════════════════════════

function HealthDonut() {
  const kpis = mockDashboardKPIs;
  const h = kpis.memoriesByHealth;

  const data = [
    { name: "Healthy", value: h.healthy, color: "#73bf69" },
    { name: "Stale", value: h.stale, color: "#ff9830" },
    { name: "Contradictory", value: h.contradictory, color: "#f2495c" },
    { name: "Drifted", value: h.drifted, color: "#8e8e8e" },
    { name: "Archived", value: h.archived, color: "#464c54" },
  ];

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="flex flex-col h-full">
      {/* Donut */}
      <div className="relative flex-1 min-h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius="55%"
              outerRadius="80%"
              paddingAngle={2}
              dataKey="value"
              stroke="none"
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Center count */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-[24px] font-mono font-medium tabular-nums" style={{ color: "var(--grafana-text-primary)" }}>
            {total}
          </span>
          <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--grafana-text-muted)" }}>
            Total
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-col gap-1.5 pt-2" style={{ borderTop: "1px solid var(--panel-border)" }}>
        {data.map((item) => (
          <div key={item.name} className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: item.color }} />
              <span style={{ color: "var(--grafana-text-secondary)" }}>{item.name}</span>
            </div>
            <span className="font-mono tabular-nums" style={{ color: "var(--grafana-text-primary)" }}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ROW 4 LEFT — Memory P&L Table
// ═══════════════════════════════════════════════════════════════════════════

type SortKey = "roi" | "revenuePerDay" | "costPerDay" | "sharpeRatio";
type SortDir = "asc" | "desc";

function SortHeader({
  label, sortKey, currentKey, currentDir, onSort,
}: {
  label: string; sortKey: SortKey; currentKey: SortKey; currentDir: SortDir; onSort: (k: SortKey) => void;
}) {
  const active = sortKey === currentKey;
  return (
    <th
      className="py-2 px-3 text-right text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none"
      style={{ color: active ? "var(--grafana-text-primary)" : "var(--grafana-text-muted)" }}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1 justify-end">
        {label}
        {active ? (
          currentDir === "desc" ? <ArrowDown size={9} /> : <ArrowUp size={9} />
        ) : (
          <ArrowUpDown size={9} style={{ color: "var(--grafana-text-disabled)" }} />
        )}
      </span>
    </th>
  );
}

function PLTable() {
  const [sortKey, setSortKey] = useState<SortKey>("roi");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const active = useMemo(() => mockMemories.filter((m) => m.status === "active"), []);

  const sorted = useMemo(() => {
    return [...active]
      .sort((a, b) => sortDir === "desc" ? b[sortKey] - a[sortKey] : a[sortKey] - b[sortKey])
      .slice(0, 12);
  }, [active, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir("desc"); }
  };

  return (
    <div className="overflow-y-auto max-h-[420px]">
      <table className="w-full text-[12px]">
        <thead className="sticky top-0 z-10" style={{ background: "var(--panel-bg)" }}>
          <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
            <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Memory</th>
            <SortHeader label="Rev/d" sortKey="revenuePerDay" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
            <SortHeader label="Cost/d" sortKey="costPerDay" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
            <SortHeader label="ROI" sortKey="roi" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
            <SortHeader label="Sharpe" sortKey="sharpeRatio" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
          </tr>
        </thead>
        <tbody>
          {sorted.map((mem) => {
            const neg = mem.roi < 0;
            return (
              <tr
                key={mem.id}
                style={{ borderBottom: "1px solid var(--panel-border)", background: neg ? "rgba(242,73,92,0.04)" : undefined }}
                className="transition-colors"
                onMouseEnter={(e) => e.currentTarget.style.background = neg ? "rgba(242,73,92,0.08)" : "var(--panel-bg-hover)"}
                onMouseLeave={(e) => e.currentTarget.style.background = neg ? "rgba(242,73,92,0.04)" : "transparent"}
              >
                <td className="py-2 px-3" style={{ color: "var(--grafana-text-secondary)" }}>
                  <span className="font-mono" style={{ color: "var(--grafana-text-muted)" }}>{formatMemoryId(mem.id)}</span>
                  {" "}
                  <span className="text-[11px]">{truncateText(mem.content, 30)}</span>
                </td>
                <td className="py-2 px-3 text-right font-mono tabular-nums" style={{ color: mem.revenuePerDay > 0 ? "var(--grafana-green)" : "var(--grafana-text-muted)" }}>
                  {formatCurrency(mem.revenuePerDay)}
                </td>
                <td className="py-2 px-3 text-right font-mono tabular-nums" style={{ color: "var(--grafana-text-muted)" }}>
                  {formatCurrency(mem.costPerDay)}
                </td>
                <td className="py-2 px-3 text-right font-mono font-medium tabular-nums" style={{ color: neg ? "var(--grafana-red)" : "var(--grafana-green)" }}>
                  {mem.roi > 0 ? `+${mem.roi.toFixed(1)}` : mem.roi.toFixed(1)}x
                </td>
                <td className="py-2 px-3 text-right font-mono tabular-nums" style={{ color: "var(--grafana-text-muted)" }}>
                  {mem.sharpeRatio.toFixed(1)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ROW 4 RIGHT — Compliance & Lifecycle
// ═══════════════════════════════════════════════════════════════════════════

function CompliancePanel() {
  const pending = useMemo(
    () => mockDeletionRequests.filter((d) => d.status === "pending" || d.status === "processing"),
    []
  );

  const memoriesWithProv = useMemo(() => {
    const memNodeIds = new Set(mockProvenanceNodes.filter((n) => n.type === "memory").map((n) => n.id));
    const connected = new Set<string>();
    for (const e of mockProvenanceEdges) {
      if (memNodeIds.has(e.source)) connected.add(e.source);
      if (memNodeIds.has(e.target)) connected.add(e.target);
    }
    return memNodeIds.size > 0 ? Math.round((connected.size / memNodeIds.size) * 100) : 0;
  }, []);

  const unresolved = useMemo(() => mockHealthAlerts.filter((a) => !a.resolved).length, []);
  const negRoi = useMemo(() => mockMemories.filter((m) => m.status === "active" && m.roi < 0).length, []);

  return (
    <div className="flex flex-col gap-4">
      {/* Bar gauges */}
      <div className="flex flex-col gap-2.5">
        <BarGauge label="Provenance" value={memoriesWithProv} max={100} color="green" display={`${memoriesWithProv}%`} />
        <BarGauge label="Unresolved" value={unresolved} max={12} color="yellow" display={`${unresolved}`} />
        <BarGauge label="Neg-ROI Mem" value={negRoi} max={50} color="red" display={`${negRoi}`} />
        <BarGauge label="Pending Del" value={pending.length} max={5} color="yellow" display={`${pending.length}`} />
      </div>

      {/* Deletion requests */}
      <div style={{ borderTop: "1px solid var(--panel-border)" }} className="pt-3">
        <span className="text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>
          Deletion Requests
        </span>
        <div className="mt-2 flex flex-col gap-1.5">
          {pending.map((d) => (
            <div key={d.id} className="flex items-center gap-2 text-[11px]">
              <span className="font-mono" style={{ color: "var(--grafana-text-muted)" }}>{d.id.toUpperCase()}</span>
              <span
                className="px-1.5 py-0.5 rounded-sm text-[9px] font-medium uppercase"
                style={{
                  background: d.status === "processing" ? "var(--stat-yellow-bg)" : "var(--panel-bg-hover)",
                  color: d.status === "processing" ? "var(--grafana-yellow)" : "var(--grafana-text-muted)",
                }}
              >
                {d.status}
              </span>
              <span className="font-mono" style={{ color: "var(--grafana-text-muted)" }}>{d.footprintSize} nodes</span>
            </div>
          ))}
        </div>
      </div>

      {/* Last audit */}
      <div className="flex items-center gap-2 text-[11px]" style={{ color: "var(--grafana-text-secondary)" }}>
        <Clock size={12} style={{ color: "var(--grafana-text-muted)" }} />
        <span>Last audit: <span style={{ color: "var(--grafana-text-primary)" }}>Feb 18, 2026</span></span>
        <span style={{ color: "var(--grafana-green)" }} className="font-medium">PASSED</span>
        <CheckCircle2 size={11} style={{ color: "var(--grafana-green)" }} />
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ROW 5 — CHI Trend 30-day Line Chart
// ═══════════════════════════════════════════════════════════════════════════

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
      dateLabel: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      chi: Math.round(chi * 1000) / 1000,
      event: CHI_EVENTS[i],
    });
  }
  return points;
}

function CHIChart() {
  const data = useMemo(() => buildCHIData(), []);

  return (
    <div className="h-[260px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <defs>
            <linearGradient id="chiArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#73bf69" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#73bf69" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid stroke="var(--grid-line)" strokeDasharray="none" vertical={false} />

          <XAxis
            dataKey="dateLabel"
            tick={{ fontSize: 11, fill: "var(--axis-text)", fontFamily: "var(--font-mono)" }}
            axisLine={{ stroke: "var(--panel-border)" }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0.5, 1]}
            ticks={[0.5, 0.6, 0.7, 0.8, 0.9, 1.0]}
            tick={{ fontSize: 11, fill: "var(--axis-text)", fontFamily: "var(--font-mono)" }}
            axisLine={false}
            tickLine={false}
            width={36}
          />

          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const d = payload[0].payload as CHIPoint;
              const c = d.chi >= 0.8 ? "var(--grafana-green)" : d.chi >= 0.6 ? "var(--grafana-yellow)" : "var(--grafana-red)";
              return (
                <div style={{ background: "var(--panel-bg)", border: "1px solid var(--panel-border)", borderRadius: "var(--panel-radius)" }} className="px-3 py-2 max-w-[260px]">
                  <div className="flex items-center justify-between gap-4 mb-0.5">
                    <span className="text-[11px]" style={{ color: "var(--grafana-text-muted)" }}>{d.dateLabel}</span>
                    <span className="text-[13px] font-mono font-medium" style={{ color: c }}>{d.chi.toFixed(3)}</span>
                  </div>
                  {d.event && (
                    <div className="text-[10px] mt-1 pt-1" style={{ color: "var(--grafana-text-muted)", borderTop: "1px solid var(--panel-border)" }}>
                      {d.event}
                    </div>
                  )}
                </div>
              );
            }}
          />

          <ReferenceLine y={0.8} stroke="var(--grafana-green)" strokeDasharray="4 4" strokeOpacity={0.35} />
          <ReferenceLine y={0.6} stroke="var(--grafana-yellow)" strokeDasharray="4 4" strokeOpacity={0.35} />

          <Line
            type="monotone"
            dataKey="chi"
            stroke="var(--grafana-green)"
            strokeWidth={2}
            fill="url(#chiArea)"
            dot={(props) => {
              const { cx, cy, payload } = props as { cx: number; cy: number; payload: CHIPoint };
              if (!payload.event) return <g key={`d-${cx}`} />;
              return (
                <g key={`ev-${cx}`}>
                  <circle cx={cx} cy={cy} r={5} fill="var(--panel-bg)" stroke="var(--grafana-yellow)" strokeWidth={2} />
                  <circle cx={cx} cy={cy} r={2} fill="var(--grafana-yellow)" />
                </g>
              );
            }}
            activeDot={{ r: 4, fill: "var(--grafana-green)", stroke: "var(--panel-bg)", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE — Overview / Command Center
// ═══════════════════════════════════════════════════════════════════════════

export default function OverviewPage() {
  const kpis = mockDashboardKPIs;

  return (
    <div className="flex flex-col" style={{ gap: "var(--panel-gap)" }}>
      {/* ── ROW 1: Stat panels (4) ─────────────────────────────── */}
      <div className="grid-4">
        <StatPanel
          label="CHI Score"
          value={kpis.compositeHealthIndex.toFixed(2)}
          color={kpis.compositeHealthIndex >= 0.7 ? "green" : kpis.compositeHealthIndex >= 0.5 ? "yellow" : "red"}
          sparkline={kpis.chiHistory}
        />
        <StatPanel
          label="Hallucination Rate"
          value={formatPercentage(kpis.hallucinationRate)}
          color={kpis.hallucinationRate > 0.1 ? "red" : kpis.hallucinationRate > 0.05 ? "yellow" : "green"}
          sparkline={kpis.hallucinationHistory}
        />
        <StatPanel
          label="Token Waste"
          value={formatPercentage(kpis.tokenWasteRate)}
          color={kpis.tokenWasteRate > 0.3 ? "red" : kpis.tokenWasteRate > 0.15 ? "yellow" : "green"}
          sparkline={kpis.tokenWasteHistory}
        />
        <StatPanel
          label="Active Memories"
          value={kpis.activeMemories.toLocaleString()}
          color="blue"
          sub={`/ ${kpis.totalMemories}`}
        />
      </div>

      {/* ── ROW 2: Stat panels (4) ─────────────────────────────── */}
      <div className="grid-4">
        <StatPanel
          label="Memory ROI"
          value={`${kpis.memoryROI.toFixed(1)}x`}
          color={kpis.memoryROI > 5 ? "green" : kpis.memoryROI > 1 ? "yellow" : "red"}
        />
        <StatPanel
          label="Queries Today"
          value={kpis.queriesToday.toLocaleString()}
          color="blue"
          sparkline={kpis.queryVolumeHistory}
          sub={`${kpis.queriesPerSecond}/s`}
        />
        <StatPanel
          label="Attribution Confidence"
          value={(kpis.attributionConfidence * 100).toFixed(1) + "%"}
          color={kpis.attributionConfidence >= 0.8 ? "green" : "yellow"}
        />
        <StatPanel
          label="GDPR Status"
          value={kpis.gdprStatus === "compliant" ? "Compliant" : kpis.gdprStatus === "pending_deletions" ? `${kpis.pendingDeletions} Pending` : "Overdue"}
          color={kpis.gdprStatus === "compliant" ? "green" : kpis.gdprStatus === "overdue" ? "red" : "yellow"}
        />
      </div>

      {/* ── ROW 3: Query Feed (60%) + Health Donut (40%) ───────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5" style={{ gap: "var(--panel-gap)" }}>
        <div className="lg:col-span-3">
          <GrafanaPanel title="Query Attribution Feed" description="Latest traces" noPadding>
            <QueryFeedTable />
          </GrafanaPanel>
        </div>
        <div className="lg:col-span-2">
          <GrafanaPanel title="Memory Health">
            <HealthDonut />
          </GrafanaPanel>
        </div>
      </div>

      {/* ── ROW 4: Memory P&L (50%) + Compliance (50%) ─────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: "var(--panel-gap)" }}>
        <GrafanaPanel title="Memory P&L" description="Active memories" noPadding>
          <PLTable />
        </GrafanaPanel>
        <GrafanaPanel title="Compliance & Lifecycle">
          <CompliancePanel />
        </GrafanaPanel>
      </div>

      {/* ── ROW 5: CHI Trend (full width) ──────────────────────── */}
      <GrafanaPanel
        title="CHI Trend — 30 Days"
        headerRight={
          <div className="flex items-center gap-4 text-[10px]" style={{ color: "var(--grafana-text-muted)" }}>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: "var(--grafana-green)" }} />
              &gt; 0.80
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: "var(--grafana-yellow)" }} />
              0.60–0.80
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: "var(--grafana-red)" }} />
              &lt; 0.60
            </span>
          </div>
        }
      >
        <CHIChart />
      </GrafanaPanel>
    </div>
  );
}

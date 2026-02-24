"use client";

import { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { Activity, AlertTriangle, Clock, Info } from "lucide-react";
import { mockMemories, mockHealthAlerts } from "@/lib/mock-data";
import { formatTimestamp, formatMemoryId } from "@/lib/utils";
import type { HealthAlert } from "@/lib/types";

// ── Health category classification ─────────────────────────────────────

function classifyMemories() {
  const active = mockMemories.filter((m) => m.status === "active");
  const archived = mockMemories.filter((m) => m.status === "archived" || m.status === "deleted" || m.status === "pending_deletion");

  let healthy = 0;
  let stale = 0;
  let contradictory = 0;
  let drifted = 0;

  for (const m of active) {
    if (m.contradictionsWith.length > 0) {
      contradictory++;
    } else if (m.stalenessScore > 0.7) {
      stale++;
    } else if (m.driftScore > 0.5) {
      drifted++;
    } else {
      healthy++;
    }
  }

  return { healthy, stale, contradictory, drifted, archived: archived.length };
}

// ── Severity helpers ───────────────────────────────────────────────────

function severityIcon(severity: HealthAlert["severity"]) {
  switch (severity) {
    case "critical":
      return <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" />;
    case "warning":
      return <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />;
    default:
      return <span className="w-2 h-2 rounded-full bg-blue-400 shrink-0" />;
  }
}

function actionLabel(alert: HealthAlert): string {
  switch (alert.type) {
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

// ── Component ──────────────────────────────────────────────────────────

export function HealthSummary() {
  const counts = useMemo(classifyMemories, []);

  const chartData = [
    { name: "Healthy", value: counts.healthy, color: "#10b981" },
    { name: "Stale", value: counts.stale, color: "#f59e0b" },
    { name: "Contradictory", value: counts.contradictory, color: "#f43f5e" },
    { name: "Drifted", value: counts.drifted, color: "#a1a1aa" },
    { name: "Archived", value: counts.archived, color: "#3f3f46" },
  ];

  const topProblems = useMemo(
    () =>
      mockHealthAlerts
        .filter((a) => !a.resolved)
        .sort((a, b) => {
          const order = { critical: 0, warning: 1, info: 2 };
          return order[a.severity] - order[b.severity];
        })
        .slice(0, 5),
    []
  );

  const recentEvents = useMemo(
    () =>
      [...mockHealthAlerts]
        .sort((a, b) => new Date(b.detectedAt).getTime() - new Date(a.detectedAt).getTime())
        .slice(0, 5),
    []
  );

  const total = Object.values(counts).reduce((s, v) => s + v, 0);

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800">
        <Activity size={14} className="text-zinc-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
          Health Summary
        </span>
      </div>

      {/* Donut chart + legend */}
      <div className="flex items-center gap-4 px-4 py-4 border-b border-zinc-800/50">
        <div className="w-28 h-28 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={30}
                outerRadius={48}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {chartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-col gap-1.5 flex-1 min-w-0">
          {chartData.map((item) => (
            <div key={item.name} className="flex items-center justify-between text-[12px]">
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-zinc-400">{item.name}</span>
              </div>
              <span className="font-mono text-zinc-300 tabular-nums">{item.value}</span>
            </div>
          ))}
          <div className="flex items-center justify-between text-[12px] border-t border-zinc-800 pt-1.5 mt-0.5">
            <span className="text-zinc-500 font-medium">Total</span>
            <span className="font-mono text-zinc-300 font-medium tabular-nums">{total}</span>
          </div>
        </div>
      </div>

      {/* Top Problems */}
      <div className="border-b border-zinc-800/50">
        <div className="px-4 py-2.5 flex items-center gap-1.5">
          <AlertTriangle size={12} className="text-zinc-500" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">
            Top Problems
          </span>
        </div>
        <div className="divide-y divide-zinc-800/50">
          {topProblems.map((alert) => (
            <div
              key={alert.id}
              className="flex items-start gap-2.5 px-4 py-2 hover:bg-zinc-800/20 transition-colors"
            >
              {severityIcon(alert.severity)}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span className="text-zinc-500 uppercase font-medium">{alert.type.replace("_", " ")}</span>
                  {alert.memoryIds.length > 0 && (
                    <>
                      <span className="text-zinc-700">:</span>
                      <span className="text-zinc-400 font-mono">
                        {alert.memoryIds.slice(0, 2).map(formatMemoryId).join(" vs ")}
                      </span>
                    </>
                  )}
                </div>
                <p className="text-[11px] text-zinc-600 truncate mt-0.5">
                  {alert.description.length > 80
                    ? alert.description.slice(0, 80) + "\u2026"
                    : alert.description}
                </p>
              </div>
              <button className="text-[10px] font-medium text-zinc-600 hover:text-zinc-300 px-2 py-1 rounded border border-zinc-800 hover:border-zinc-700 transition-colors shrink-0">
                {actionLabel(alert)}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Recent health events */}
      <div>
        <div className="px-4 py-2.5 flex items-center gap-1.5">
          <Clock size={12} className="text-zinc-500" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500">
            Recent Events
          </span>
        </div>
        <div className="divide-y divide-zinc-800/30">
          {recentEvents.map((event) => (
            <div key={event.id} className="flex items-center gap-2.5 px-4 py-1.5">
              <span className="text-[10px] font-mono text-zinc-700 w-12 shrink-0 tabular-nums">
                {formatTimestamp(event.detectedAt)}
              </span>
              {severityIcon(event.severity)}
              <span className="text-[11px] text-zinc-500 truncate">
                {event.description.length > 65
                  ? event.description.slice(0, 65) + "\u2026"
                  : event.description}
              </span>
              {event.resolved && (
                <span className="text-[9px] font-medium text-emerald-500/60 uppercase shrink-0">
                  Resolved
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

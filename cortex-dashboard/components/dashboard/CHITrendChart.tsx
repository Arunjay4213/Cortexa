"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Dot,
} from "recharts";

// ── Mock CHI trend data (30 days) ────────────────────────────────────────

interface CHIDataPoint {
  date: string;
  dateLabel: string;
  chi: number;
  event?: string;
}

function generateCHITrend(): CHIDataPoint[] {
  const points: CHIDataPoint[] = [];
  const now = new Date("2026-02-20T12:00:00Z");
  let chi = 0.82;

  const events: Record<number, string> = {
    3: "Contradiction detected: mem-012 vs mem-038",
    8: "Bulk archive: 5 stale memories removed",
    14: "New memory cluster: notification preferences",
    19: "Drift spike: tech stack memories",
    25: "Health check passed: all critical memories verified",
  };

  for (let i = 29; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);

    // Simulate realistic CHI movement
    const noise = (Math.sin(i * 0.7) * 0.03) + (Math.cos(i * 1.3) * 0.02);
    if (i === 19) chi -= 0.08; // drift spike
    else if (i === 8) chi += 0.05; // bulk archive boost
    else if (i === 3) chi -= 0.04; // contradiction hit
    else chi += noise * 0.3;

    chi = Math.max(0.55, Math.min(0.95, chi));

    points.push({
      date: d.toISOString(),
      dateLabel: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      chi: Math.round(chi * 1000) / 1000,
      event: events[i],
    });
  }

  return points;
}

// ── Component ────────────────────────────────────────────────────────────

export function CHITrendChart() {
  const data = useMemo(() => generateCHITrend(), []);

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
          CHI Trend — 30 Days
        </span>
        <div className="flex items-center gap-4 text-[10px] text-zinc-600">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            &gt; 0.80
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            0.60–0.80
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            &lt; 0.60
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-0.5 bg-zinc-500" style={{ borderBottom: "2px dashed #52525b" }} />
            Events
          </span>
        </div>
      </div>

      {/* Chart */}
      <div className="px-4 py-4">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} margin={{ top: 10, right: 20, bottom: 4, left: 0 }}>
            <defs>
              <linearGradient id="chiGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#27272a"
              vertical={false}
            />

            <XAxis
              dataKey="dateLabel"
              tick={{ fontSize: 11, fill: "#71717a", fontFamily: "var(--font-mono)" }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
              interval="preserveStartEnd"
            />

            <YAxis
              domain={[0.5, 1]}
              ticks={[0.5, 0.6, 0.7, 0.8, 0.9, 1.0]}
              tick={{ fontSize: 11, fill: "#71717a", fontFamily: "var(--font-mono)" }}
              axisLine={false}
              tickLine={false}
              width={36}
            />

            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const d = payload[0].payload as CHIDataPoint;
                const chiColor =
                  d.chi >= 0.8
                    ? "text-emerald-400"
                    : d.chi >= 0.6
                      ? "text-amber-400"
                      : "text-rose-400";
                return (
                  <div className="bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 shadow-lg max-w-[260px]">
                    <div className="flex items-center justify-between gap-4 mb-0.5">
                      <span className="text-[11px] text-zinc-400">{d.dateLabel}</span>
                      <span className={`text-[13px] font-mono font-medium ${chiColor}`}>
                        {d.chi.toFixed(3)}
                      </span>
                    </div>
                    {d.event && (
                      <div className="text-[10px] text-zinc-500 mt-1 border-t border-zinc-800 pt-1">
                        {d.event}
                      </div>
                    )}
                  </div>
                );
              }}
            />

            {/* Threshold lines */}
            <ReferenceLine
              y={0.8}
              stroke="#10b981"
              strokeDasharray="4 4"
              strokeOpacity={0.4}
            />
            <ReferenceLine
              y={0.6}
              stroke="#f59e0b"
              strokeDasharray="4 4"
              strokeOpacity={0.4}
            />

            <Line
              type="monotone"
              dataKey="chi"
              stroke="#10b981"
              strokeWidth={2}
              dot={(props) => {
                const { cx, cy, payload } = props as {
                  cx: number;
                  cy: number;
                  payload: CHIDataPoint;
                };
                if (!payload.event) return <g key={`dot-${cx}`} />;
                // Event dot
                return (
                  <g key={`event-${cx}`}>
                    <circle
                      cx={cx}
                      cy={cy}
                      r={5}
                      fill="#18181b"
                      stroke="#f59e0b"
                      strokeWidth={2}
                    />
                    <circle cx={cx} cy={cy} r={2} fill="#f59e0b" />
                  </g>
                );
              }}
              activeDot={{
                r: 4,
                fill: "#10b981",
                stroke: "#18181b",
                strokeWidth: 2,
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

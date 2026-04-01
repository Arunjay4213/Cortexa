"use client";

import type { TimeSeriesPoint } from "@/lib/types";

type StatColor = "green" | "red" | "yellow" | "blue" | "purple" | "cyan";

interface StatPanelProps {
  label: string;
  value: string;
  color: StatColor;
  /** Optional sparkline data (TimeSeriesPoint[]) rendered behind the value */
  sparkline?: TimeSeriesPoint[];
  /** Small sub-label next to the value */
  sub?: string;
}

const COLOR_MAP: Record<StatColor, { text: string; bg: string; line: string }> = {
  green:  { text: "var(--grafana-green)",  bg: "var(--stat-green-bg)",  line: "#73bf69" },
  red:    { text: "var(--grafana-red)",    bg: "var(--stat-red-bg)",    line: "#f2495c" },
  yellow: { text: "var(--grafana-yellow)", bg: "var(--stat-yellow-bg)", line: "#ff9830" },
  blue:   { text: "var(--grafana-blue)",   bg: "var(--stat-blue-bg)",   line: "#5794f2" },
  purple: { text: "var(--grafana-purple)", bg: "rgba(184,119,217,0.15)", line: "#b877d9" },
  cyan:   { text: "var(--grafana-cyan)",   bg: "rgba(138,184,255,0.15)", line: "#8ab8ff" },
};

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;

  const w = 200;
  const h = 40;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x},${y}`;
  });

  const areaPath = `0,${h} ${points.join(" ")} ${w},${h}`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="absolute bottom-0 left-0 w-full"
      style={{ height: "60%" }}
    >
      <defs>
        <linearGradient id={`sp-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.25} />
          <stop offset="100%" stopColor={color} stopOpacity={0.02} />
        </linearGradient>
      </defs>
      <polygon points={areaPath} fill={`url(#sp-${color.replace("#", "")})`} />
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function StatPanel({ label, value, color, sparkline, sub }: StatPanelProps) {
  const c = COLOR_MAP[color];
  const sparkData = sparkline?.map((p) => p.value);

  return (
    <div
      className="relative overflow-hidden flex flex-col justify-between"
      style={{
        background: c.bg,
        border: "1px solid var(--panel-border)",
        borderRadius: "var(--panel-radius)",
        padding: "var(--panel-padding)",
        minHeight: 100,
      }}
    >
      {/* Sparkline behind everything */}
      {sparkData && sparkData.length > 1 && (
        <MiniSparkline data={sparkData} color={c.line} />
      )}

      {/* Label */}
      <span
        className="relative text-[11px] font-medium uppercase tracking-[0.06em] leading-none z-[1]"
        style={{ color: "var(--grafana-text-muted)" }}
      >
        {label}
      </span>

      {/* Value */}
      <div className="relative flex items-end gap-1.5 z-[1]">
        <span
          className="text-[28px] font-mono font-medium leading-none tabular-nums"
          style={{ color: c.text }}
        >
          {value}
        </span>
        {sub && (
          <span
            className="text-[12px] font-mono leading-none mb-0.5"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            {sub}
          </span>
        )}
      </div>
    </div>
  );
}

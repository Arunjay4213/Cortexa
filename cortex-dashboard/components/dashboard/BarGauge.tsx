"use client";

type GaugeColor = "green" | "red" | "yellow" | "blue";

interface BarGaugeProps {
  label: string;
  value: number;
  max: number;
  color: GaugeColor;
  /** Formatted display string — if omitted, raw value is shown */
  display?: string;
}

const BAR_COLORS: Record<GaugeColor, string> = {
  green:  "var(--grafana-green)",
  red:    "var(--grafana-red)",
  yellow: "var(--grafana-yellow)",
  blue:   "var(--grafana-blue)",
};

const BAR_BG: Record<GaugeColor, string> = {
  green:  "rgba(115,191,105,0.12)",
  red:    "rgba(242,73,92,0.12)",
  yellow: "rgba(255,152,48,0.12)",
  blue:   "rgba(87,148,242,0.12)",
};

export function BarGauge({ label, value, max, color, display }: BarGaugeProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;

  return (
    <div className="flex items-center gap-3">
      <span
        className="text-[12px] shrink-0 w-28 truncate"
        style={{ color: "var(--grafana-text-secondary)" }}
      >
        {label}
      </span>
      <div
        className="flex-1 h-[18px] rounded-sm overflow-hidden relative"
        style={{ background: BAR_BG[color] }}
      >
        <div
          className="absolute inset-y-0 left-0 rounded-sm transition-all duration-500"
          style={{ width: `${pct}%`, background: BAR_COLORS[color] }}
        />
      </div>
      <span
        className="text-[12px] font-mono tabular-nums shrink-0 w-14 text-right"
        style={{ color: BAR_COLORS[color] }}
      >
        {display ?? value}
      </span>
    </div>
  );
}

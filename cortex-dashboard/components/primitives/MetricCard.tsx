"use client";

import type { ReactNode } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string | number;
  delta?: number;
  deltaLabel?: string;
  sparkline?: ReactNode;
  accentColor?: string;
}

export function MetricCard({ label, value, delta, deltaLabel, sparkline, accentColor }: MetricCardProps) {
  const formatDelta = (d: number) => {
    const prefix = d >= 0 ? "+" : "";
    if (Math.abs(d) < 1 && Math.abs(d) > 0) {
      return prefix + (d * 100).toFixed(1) + "%";
    }
    return prefix + d.toFixed(1);
  };

  return (
    <div className="metric-card group">
      <div className="metric-card__label">{label}</div>
      <div className="flex items-end justify-between gap-4">
        <div
          className="metric-card__value font-mono transition-transform duration-300 group-hover:scale-[1.02] origin-left"
          style={accentColor ? { color: accentColor } : undefined}
        >
          {value}
        </div>
        {sparkline && (
          <div className="shrink-0 opacity-50 group-hover:opacity-80 transition-opacity duration-300">
            {sparkline}
          </div>
        )}
      </div>
      {delta !== undefined && (
        <div
          className={`metric-card__delta ${
            delta > 0
              ? "metric-card__delta--up"
              : delta < 0
              ? "metric-card__delta--down"
              : "text-[var(--text-tertiary)]"
          }`}
        >
          {delta > 0 ? (
            <TrendingUp size={14} />
          ) : delta < 0 ? (
            <TrendingDown size={14} />
          ) : (
            <Minus size={14} />
          )}
          <span className="font-mono">{formatDelta(delta)}</span>
          {deltaLabel && (
            <span className="text-[var(--text-ghost)] text-[12px] ml-1">{deltaLabel}</span>
          )}
        </div>
      )}
    </div>
  );
}

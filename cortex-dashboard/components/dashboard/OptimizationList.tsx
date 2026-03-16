"use client";

import { DollarSign, Eye, Play, TrendingDown, TrendingUp, Minus } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { OptimizationRecommendation, ImpactDirection } from "@/lib/types";

// ── Styling ──────────────────────────────────────────────────────────────

const PRIORITY_BORDER: Record<number, string> = {
  1: "border-l-rose-500",
  2: "border-l-amber-500",
  3: "border-l-blue-500",
  4: "border-l-emerald-500",
};

const PRIORITY_BADGE: Record<number, string> = {
  1: "bg-rose-500/10 text-rose-400",
  2: "bg-amber-500/10 text-amber-400",
  3: "bg-blue-500/10 text-blue-400",
  4: "bg-emerald-500/10 text-emerald-400",
};

const IMPACT_CONFIG: Record<ImpactDirection, { icon: typeof TrendingUp; color: string }> = {
  positive: { icon: TrendingUp, color: "text-emerald-400" },
  negative: { icon: TrendingDown, color: "text-rose-400" },
  neutral: { icon: Minus, color: "text-zinc-500" },
};

// ── Component ────────────────────────────────────────────────────────────

interface OptimizationListProps {
  recommendations: OptimizationRecommendation[];
  onPreview: (rec: OptimizationRecommendation) => void;
  onApply: (rec: OptimizationRecommendation) => void;
}

export function OptimizationList({ recommendations, onPreview, onApply }: OptimizationListProps) {
  return (
    <div className="space-y-4">
      {recommendations.map((rec) => {
        const borderClass = PRIORITY_BORDER[rec.priority] ?? "border-l-zinc-500";
        const badgeClass = PRIORITY_BADGE[rec.priority] ?? "bg-zinc-500/10 text-zinc-400";
        const impact = IMPACT_CONFIG[rec.impactDirection];
        const ImpactIcon = impact.icon;
        const isCost = rec.savingsPerMonth < 0;

        return (
          <div
            key={rec.id}
            className={`bg-zinc-950 border border-zinc-800 border-l-[3px] ${borderClass} rounded-lg px-5 py-4`}
          >
            {/* Top row: priority badge + title */}
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-2.5">
                <span className={`px-2 py-0.5 text-[10px] font-mono font-medium rounded ${badgeClass}`}>
                  P{rec.priority}
                </span>
                <h3 className="text-[13px] font-medium text-zinc-200">
                  {rec.title}
                </h3>
              </div>

              {/* Savings / cost */}
              <div className="flex items-center gap-1.5 shrink-0">
                <DollarSign size={13} className={isCost ? "text-amber-400" : "text-emerald-400"} />
                <span className={`text-[13px] font-mono font-medium ${isCost ? "text-amber-400" : "text-emerald-400"}`}>
                  {isCost ? `+${formatCurrency(Math.abs(rec.savingsPerMonth))}` : formatCurrency(rec.savingsPerMonth)}
                  <span className="text-zinc-600">/mo</span>
                </span>
                <span className="text-[10px] text-zinc-600 ml-1">
                  {isCost ? "cost" : "savings"}
                </span>
              </div>
            </div>

            {/* Description */}
            <p className="text-[12px] text-zinc-500 leading-relaxed mt-2 max-w-[85%]">
              {rec.description}
            </p>

            {/* Bottom row: impact + actions */}
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-zinc-800/50">
              {/* Impact */}
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider text-zinc-600 font-medium">
                  Impact:
                </span>
                <div className={`flex items-center gap-1 text-[12px] font-mono ${impact.color}`}>
                  <ImpactIcon size={13} />
                  {rec.impactLabel}
                </div>
                <span className="text-[10px] text-zinc-700 ml-2">
                  {rec.memoryIds.length} memories
                </span>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => onPreview(rec)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium bg-zinc-800 border border-zinc-700 rounded-md text-zinc-300 hover:bg-zinc-700 transition-colors"
                >
                  <Eye size={12} />
                  Preview
                </button>
                <button
                  onClick={() => onApply(rec)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium bg-emerald-500/10 border border-emerald-500/30 rounded-md text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                >
                  <Play size={12} />
                  Apply All
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

"use client";

import { mockDashboardKPIs } from "@/lib/mock-data";
import { ArrowUp, ArrowDown } from "lucide-react";

type BorderColor = "emerald" | "amber" | "rose" | "zinc";

interface KPICardProps {
  label: string;
  value: string;
  border: BorderColor;
  delta?: { value: string; direction: "up" | "down"; good: boolean };
  sub?: string;
}

const borderColors: Record<BorderColor, string> = {
  emerald: "border-l-emerald-500",
  amber: "border-l-amber-500",
  rose: "border-l-rose-500",
  zinc: "border-l-zinc-600",
};

function KPICard({ label, value, border, delta, sub }: KPICardProps) {
  return (
    <div
      className={`
        min-w-[190px] h-24 bg-zinc-950 border border-zinc-800 border-l-[3px] rounded-lg
        px-4 py-3 flex flex-col justify-between shrink-0
        ${borderColors[border]}
      `}
    >
      <span className="text-[11px] uppercase tracking-wider text-zinc-500 font-sans font-medium leading-none truncate">
        {label}
      </span>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-mono font-medium text-white leading-none tabular-nums">
          {value}
        </span>
        {sub && (
          <span className="text-[11px] font-mono text-zinc-500 leading-none mb-0.5">
            {sub}
          </span>
        )}
      </div>
      {delta && (
        <div className="flex items-center gap-1">
          {delta.direction === "up" ? (
            <ArrowUp size={10} className={delta.good ? "text-emerald-500" : "text-rose-500"} />
          ) : (
            <ArrowDown size={10} className={delta.good ? "text-emerald-500" : "text-rose-500"} />
          )}
          <span className={`text-[10px] font-mono ${delta.good ? "text-emerald-500" : "text-rose-500"}`}>
            {delta.value}
          </span>
        </div>
      )}
    </div>
  );
}

function gdprBorder(status: string): BorderColor {
  if (status === "compliant") return "emerald";
  if (status === "overdue") return "rose";
  return "amber";
}

function gdprLabel(status: string): string {
  if (status === "compliant") return "Compliant";
  if (status === "pending_deletions") return "2 Pending";
  return "Overdue";
}

function hallucinationBorder(rate: number): BorderColor {
  if (rate > 0.05) return "rose";
  if (rate > 0.01) return "amber";
  return "emerald";
}

function wasteBorder(rate: number): BorderColor {
  if (rate > 0.35) return "rose";
  if (rate > 0.2) return "amber";
  return "emerald";
}

export function KPIStrip() {
  const kpis = mockDashboardKPIs;

  const cards: KPICardProps[] = [
    {
      label: "CHI",
      value: kpis.compositeHealthIndex.toFixed(2),
      border: kpis.compositeHealthIndex >= 0.7 ? "emerald" : kpis.compositeHealthIndex >= 0.5 ? "amber" : "rose",
      delta: { value: "+0.03", direction: "up", good: true },
    },
    {
      label: "Memory ROI",
      value: `${kpis.memoryROI.toFixed(1)}x`,
      border: "emerald",
      delta: { value: "+0.4x", direction: "up", good: true },
    },
    {
      label: "Active Memories",
      value: kpis.activeMemories.toLocaleString(),
      border: "zinc",
    },
    {
      label: "Attribution Confidence",
      value: kpis.attributionConfidence.toFixed(2),
      border: kpis.attributionConfidence >= 0.8 ? "emerald" : "amber",
      delta: { value: "+0.02", direction: "up", good: true },
    },
    {
      label: "Hallucination Rate",
      value: `${(kpis.hallucinationRate * 100).toFixed(1)}%`,
      border: hallucinationBorder(kpis.hallucinationRate),
      delta: { value: "+0.8%", direction: "up", good: false },
    },
    {
      label: "Token Waste",
      value: `${(kpis.tokenWasteRate * 100).toFixed(1)}%`,
      border: wasteBorder(kpis.tokenWasteRate),
      delta: { value: "-2.1%", direction: "down", good: true },
    },
    {
      label: "GDPR Status",
      value: gdprLabel(kpis.gdprStatus),
      border: gdprBorder(kpis.gdprStatus),
    },
    {
      label: "Queries Today",
      value: kpis.queriesToday.toLocaleString(),
      border: "zinc",
      sub: `${kpis.queriesPerSecond}/s`,
    },
  ];

  return (
    <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
      {cards.map((card) => (
        <KPICard key={card.label} {...card} />
      ))}
    </div>
  );
}

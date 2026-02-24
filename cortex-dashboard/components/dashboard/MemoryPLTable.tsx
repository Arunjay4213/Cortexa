"use client";

import { useState, useMemo } from "react";
import { TrendingUp, ArrowUpDown, ArrowUp, ArrowDown, MoreHorizontal } from "lucide-react";
import { mockMemories } from "@/lib/mock-data";
import { formatMemoryId, truncateText, formatCurrency } from "@/lib/utils";
import type { Memory } from "@/lib/types";

// ── Sort logic ─────────────────────────────────────────────────────────

type SortKey = "roi" | "revenuePerDay" | "costPerDay" | "sharpeRatio";
type SortDir = "asc" | "desc";

function sortMemories(memories: Memory[], key: SortKey, dir: SortDir): Memory[] {
  return [...memories].sort((a, b) => {
    const av = a[key];
    const bv = b[key];
    return dir === "desc" ? bv - av : av - bv;
  });
}

// ── Action dropdown ────────────────────────────────────────────────────

function ActionMenu({ memoryId }: { memoryId: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="p-1 rounded hover:bg-zinc-800 transition-colors text-zinc-600 hover:text-zinc-400"
      >
        <MoreHorizontal size={14} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-50 bg-zinc-900 border border-zinc-700 rounded-md shadow-lg py-1 min-w-[120px]">
            {["Archive", "Protect", "Investigate"].map((action) => (
              <button
                key={action}
                onClick={() => setOpen(false)}
                className="w-full text-left px-3 py-1.5 text-[12px] text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
              >
                {action}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Sort header ────────────────────────────────────────────────────────

function SortHeader({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
  className = "",
}: {
  label: string;
  sortKey: SortKey;
  currentKey: SortKey;
  currentDir: SortDir;
  onSort: (key: SortKey) => void;
  className?: string;
}) {
  const isActive = sortKey === currentKey;
  return (
    <th
      className={`py-2 font-medium cursor-pointer select-none group ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <div className="flex items-center gap-1 justify-end">
        <span className={isActive ? "text-zinc-300" : ""}>{label}</span>
        {isActive ? (
          currentDir === "desc" ? (
            <ArrowDown size={10} className="text-zinc-400" />
          ) : (
            <ArrowUp size={10} className="text-zinc-400" />
          )
        ) : (
          <ArrowUpDown size={10} className="text-zinc-700 group-hover:text-zinc-500" />
        )}
      </div>
    </th>
  );
}

// ── Component ──────────────────────────────────────────────────────────

export function MemoryPLTable() {
  const [sortKey, setSortKey] = useState<SortKey>("roi");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [showNegativeOnly, setShowNegativeOnly] = useState(false);

  const activeMemories = useMemo(
    () => mockMemories.filter((m) => m.status === "active"),
    []
  );

  const negativeCount = useMemo(
    () => activeMemories.filter((m) => m.roi < 0).length,
    [activeMemories]
  );

  const portfolioROI = useMemo(() => {
    const rev = activeMemories.reduce((s, m) => s + m.revenuePerDay, 0);
    const cost = activeMemories.reduce((s, m) => s + m.costPerDay, 0);
    return cost > 0 ? rev / cost : 0;
  }, [activeMemories]);

  const monthlySavings = useMemo(() => {
    const waste = activeMemories
      .filter((m) => m.roi < 0)
      .reduce((s, m) => s + m.costPerDay, 0);
    return waste * 30;
  }, [activeMemories]);

  const filteredMemories = useMemo(() => {
    const base = showNegativeOnly
      ? activeMemories.filter((m) => m.roi < 0)
      : activeMemories;
    return sortMemories(base, sortKey, sortDir).slice(0, 15);
  }, [activeMemories, sortKey, sortDir, showNegativeOnly]);

  // Top 3 ROI IDs (when sorted by ROI desc and not filtered)
  const top3Ids = useMemo(() => {
    const sorted = sortMemories(activeMemories, "roi", "desc");
    return new Set(sorted.slice(0, 3).map((m) => m.id));
  }, [activeMemories]);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800">
        <TrendingUp size={14} className="text-zinc-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
          Memory P&L
        </span>
        <span className="text-[10px] text-zinc-600 font-mono ml-auto">
          {showNegativeOnly ? `${negativeCount} losing` : "Top 15"}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto flex-1 max-h-[380px] overflow-y-auto">
        <table className="w-full text-[12px]">
          <thead className="sticky top-0 bg-zinc-950 z-10">
            <tr className="text-[10px] uppercase tracking-wider text-zinc-600 border-b border-zinc-800">
              <th className="text-left py-2 pl-4 font-medium w-12">ID</th>
              <th className="text-left py-2 font-medium">Content</th>
              <SortHeader label="Rev/d" sortKey="revenuePerDay" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <SortHeader label="Cost/d" sortKey="costPerDay" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <SortHeader label="ROI" sortKey="roi" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <SortHeader label="Sharpe" sortKey="sharpeRatio" currentKey={sortKey} currentDir={sortDir} onSort={handleSort} />
              <th className="py-2 pr-4 font-medium w-8" />
            </tr>
          </thead>
          <tbody>
            {filteredMemories.map((mem) => {
              const isNegative = mem.roi < 0;
              const isTop3 = !showNegativeOnly && top3Ids.has(mem.id);
              return (
                <tr
                  key={mem.id}
                  className={[
                    "border-b border-zinc-800/30 hover:bg-zinc-800/20 transition-colors",
                    isNegative ? "bg-rose-950/10" : "",
                    isTop3 ? "bg-emerald-950/10" : "",
                  ].join(" ")}
                >
                  <td className="py-2 pl-4 font-mono text-zinc-500">
                    {formatMemoryId(mem.id)}
                  </td>
                  <td className="py-2 text-zinc-500 max-w-[180px] truncate">
                    {truncateText(mem.content, 40)}
                  </td>
                  <td className={`py-2 text-right font-mono tabular-nums ${mem.revenuePerDay > 0 ? "text-emerald-500" : "text-zinc-600"}`}>
                    {formatCurrency(mem.revenuePerDay)}
                  </td>
                  <td className="py-2 text-right font-mono text-zinc-500 tabular-nums">
                    {formatCurrency(mem.costPerDay)}
                  </td>
                  <td className={`py-2 text-right font-mono font-medium tabular-nums ${isNegative ? "text-rose-500" : "text-emerald-500"}`}>
                    {mem.roi > 0 ? `+${mem.roi.toFixed(1)}` : mem.roi.toFixed(1)}x
                  </td>
                  <td className="py-2 text-right font-mono text-zinc-500 tabular-nums">
                    {mem.sharpeRatio.toFixed(1)}
                  </td>
                  <td className="py-2 pr-4">
                    <ActionMenu memoryId={mem.id} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-zinc-800 flex items-center gap-4 text-[11px]">
        <span className="text-zinc-500">
          Portfolio ROI:{" "}
          <span className="font-mono text-zinc-300 font-medium">{portfolioROI.toFixed(1)}x</span>
        </span>
        <span className="text-zinc-700">|</span>
        <button
          onClick={() => setShowNegativeOnly(!showNegativeOnly)}
          className="text-rose-500 hover:text-rose-400 transition-colors font-medium"
        >
          {negativeCount} memories losing money
        </button>
        <span className="text-zinc-700">|</span>
        <span className="text-zinc-500">
          Archiving saves{" "}
          <span className="font-mono text-emerald-500">${monthlySavings.toFixed(0)}/mo</span>
        </span>
      </div>
    </div>
  );
}

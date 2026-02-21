"use client";

import { useState, useMemo, useCallback } from "react";
import {
  Search,
  ArrowUpDown,
  TrendingDown,
  RotateCcw,
  Zap,
  Database,
  DollarSign,
  Sparkles,
  ChevronDown,
} from "lucide-react";
import { OptimizationList } from "@/components/dashboard/OptimizationList";
import { Modal } from "@/components/primitives/Modal";
import { useToast } from "@/components/primitives/Toast";
import {
  mockBudgetStats,
  mockOptimizationRecommendations,
  mockArchivedMemories,
  mockMemories,
} from "@/lib/mock-data";
import {
  formatCurrency,
  formatTimestamp,
  formatMemoryId,
  truncateText,
  classForHealth,
  classForROI,
} from "@/lib/utils";
import type { OptimizationRecommendation, ArchiveReason } from "@/lib/types";

// ── Constants ─────────────────────────────────────────────────────────────

type SortField = "date" | "reason" | "tokens";

const REASON_LABELS: Record<ArchiveReason, { label: string; color: string }> = {
  "auto-archive": { label: "Auto", color: "bg-zinc-500/10 text-zinc-400" },
  manual: { label: "Manual", color: "bg-blue-500/10 text-blue-400" },
  consolidation: { label: "Consolidated", color: "bg-violet-500/10 text-violet-400" },
};

// ── Page ──────────────────────────────────────────────────────────────────

export default function LifecyclePage() {
  const { addToast } = useToast();

  // Preview modal state
  const [previewRec, setPreviewRec] = useState<OptimizationRecommendation | null>(null);

  // Archive manager state
  const [searchQuery, setSearchQuery] = useState("");
  const [reasonFilter, setReasonFilter] = useState<ArchiveReason | "all">("all");
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortAsc, setSortAsc] = useState(false);

  // Budget utilization
  const utilPct = Math.round((mockBudgetStats.usedTokens / mockBudgetStats.budgetTokens) * 100);

  // Handle apply recommendation
  const handleApply = useCallback(
    (rec: OptimizationRecommendation) => {
      addToast({
        type: "info",
        message: `Applied: ${rec.title}`,
        detail: `${rec.memoryIds.length} memories affected. Estimated savings: ${formatCurrency(Math.abs(rec.savingsPerMonth))}/mo`,
      });
    },
    [addToast]
  );

  // Handle restore archived memory
  const handleRestore = useCallback(
    (memoryId: string) => {
      addToast({
        type: "info",
        message: `Restored ${formatMemoryId(memoryId)}`,
        detail: "Memory moved back to active status. Re-embedding will start within 30s.",
      });
    },
    [addToast]
  );

  // Filtered + sorted archived memories
  const filteredArchived = useMemo(() => {
    let items = [...mockArchivedMemories];

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      items = items.filter(
        (m) =>
          m.memoryId.toLowerCase().includes(q) ||
          m.content.toLowerCase().includes(q)
      );
    }

    if (reasonFilter !== "all") {
      items = items.filter((m) => m.reason === reasonFilter);
    }

    items.sort((a, b) => {
      let cmp = 0;
      if (sortField === "date") {
        cmp = new Date(a.archivedAt).getTime() - new Date(b.archivedAt).getTime();
      } else if (sortField === "reason") {
        cmp = a.reason.localeCompare(b.reason);
      } else if (sortField === "tokens") {
        cmp = a.tokenCount - b.tokenCount;
      }
      return sortAsc ? cmp : -cmp;
    });

    return items;
  }, [searchQuery, reasonFilter, sortField, sortAsc]);

  // Stats
  const archivedCount = mockArchivedMemories.filter((m) => m.reason !== "consolidation").length;
  const consolidatedCount = mockArchivedMemories.filter((m) => m.reason === "consolidation").length;

  // Toggle sort
  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* ── Page Header ──────────────────────────────────────────── */}
      <div>
        <h2 className="text-sm font-bold text-zinc-200 tracking-wide">
          Lifecycle & Budget Optimizer
        </h2>
        <p className="text-[11px] text-zinc-600 mt-0.5">
          Token budget monitoring · Optimization recommendations · Archive management
        </p>
      </div>

      {/* ── Token Budget Dashboard ───────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: Budget Utilization */}
        <div className="bg-zinc-950 border border-zinc-800 border-l-[3px] border-l-blue-500 rounded-lg px-5 py-4">
          <div className="flex items-center gap-2 mb-2.5">
            <Database size={14} className="text-blue-400" />
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
              Budget Utilization
            </span>
          </div>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-xl font-mono font-bold text-zinc-100">
              {(mockBudgetStats.usedTokens / 1000).toFixed(0)}k
            </span>
            <span className="text-[12px] text-zinc-500 font-mono">
              / {(mockBudgetStats.budgetTokens / 1000).toFixed(0)}k tokens
            </span>
            <span className={`text-[12px] font-mono font-medium ${
              utilPct > 85 ? "text-rose-400" : utilPct > 70 ? "text-amber-400" : "text-emerald-400"
            }`}>
              ({utilPct}%)
            </span>
          </div>
          {/* Progress bar */}
          <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                utilPct > 85 ? "bg-rose-500" : utilPct > 70 ? "bg-amber-500" : "bg-emerald-500"
              }`}
              style={{ width: `${utilPct}%` }}
            />
          </div>
          <div className="flex justify-between mt-1.5 text-[10px] text-zinc-600 font-mono">
            <span>0</span>
            <span>{(mockBudgetStats.budgetTokens / 1000).toFixed(0)}k</span>
          </div>
        </div>

        {/* Card 2: Monthly Cost */}
        <div className="bg-zinc-950 border border-zinc-800 border-l-[3px] border-l-amber-500 rounded-lg px-5 py-4">
          <div className="flex items-center gap-2 mb-2.5">
            <DollarSign size={14} className="text-amber-400" />
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
              Monthly Cost
            </span>
          </div>
          <div className="flex items-baseline gap-2 mb-1">
            <span className="text-xl font-mono font-bold text-zinc-100">
              {formatCurrency(mockBudgetStats.monthlySpend)}
            </span>
            <span className="text-[12px] text-zinc-500">/mo</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px]">
            <TrendingDown size={12} className="text-emerald-400" />
            <span className="text-emerald-400 font-mono">-3.2%</span>
            <span className="text-zinc-600">vs last month</span>
          </div>
          <p className="text-[10px] text-zinc-600 mt-2">
            At current retrieval rate of 14.4 qps
          </p>
        </div>

        {/* Card 3: Projected Savings */}
        <div className="bg-zinc-950 border border-zinc-800 border-l-[3px] border-l-emerald-500 rounded-lg px-5 py-4">
          <div className="flex items-center gap-2 mb-2.5">
            <Sparkles size={14} className="text-emerald-400" />
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
              Projected Savings
            </span>
          </div>
          <div className="flex items-baseline gap-2 mb-1">
            <span className="text-xl font-mono font-bold text-emerald-400">
              {formatCurrency(mockBudgetStats.projectedSavings)}
            </span>
            <span className="text-[12px] text-zinc-500">/mo</span>
          </div>
          <p className="text-[11px] text-zinc-500">
            If all recommendations below are applied
          </p>
          <div className="flex items-center gap-1.5 mt-2 text-[10px] text-zinc-600">
            <Zap size={10} className="text-emerald-500" />
            <span>
              {mockOptimizationRecommendations.length} actions available
            </span>
          </div>
        </div>
      </div>

      {/* ── Optimization Recommendations ─────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Zap size={14} className="text-amber-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
            Optimization Recommendations
          </span>
          <span className="text-[10px] font-mono text-zinc-600 bg-zinc-800 px-1.5 py-0.5 rounded">
            {mockOptimizationRecommendations.length}
          </span>
        </div>
        <OptimizationList
          recommendations={mockOptimizationRecommendations}
          onPreview={setPreviewRec}
          onApply={handleApply}
        />
      </div>

      {/* ── Archive Manager ──────────────────────────────────────── */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-zinc-800">
          <div className="flex items-center gap-1.5">
            <Database size={14} className="text-zinc-500" />
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Archive Manager
            </span>
          </div>

          <div className="flex-1" />

          {/* Search */}
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" />
            <input
              type="text"
              placeholder="Search archived..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-[12px] font-mono bg-zinc-900 border border-zinc-700 rounded-md text-zinc-300 placeholder:text-zinc-600 w-[160px] focus:outline-none focus:border-zinc-500"
            />
          </div>

          {/* Reason filter */}
          <div className="relative">
            <select
              value={reasonFilter}
              onChange={(e) => setReasonFilter(e.target.value as ArchiveReason | "all")}
              className="appearance-none bg-zinc-900 border border-zinc-700 rounded-md pl-3 pr-7 py-1.5 text-[12px] text-zinc-300 focus:outline-none focus:border-zinc-500"
            >
              <option value="all">All reasons</option>
              <option value="auto-archive">Auto-archive</option>
              <option value="manual">Manual</option>
              <option value="consolidation">Consolidation</option>
            </select>
            <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
          </div>

          {/* Stats */}
          <span className="text-[11px] text-zinc-600">
            {archivedCount} archived · {consolidatedCount} consolidated
          </span>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-[10px] font-medium uppercase tracking-wider text-zinc-600 border-b border-zinc-800">
                <th className="px-4 py-2.5 text-left w-[90px]">Memory ID</th>
                <th className="px-4 py-2.5 text-left">Content</th>
                <th className="px-4 py-2.5 text-left w-[110px]">Status</th>
                <th
                  className="px-4 py-2.5 text-left w-[120px] cursor-pointer hover:text-zinc-400 transition-colors"
                  onClick={() => toggleSort("date")}
                >
                  <span className="flex items-center gap-1">
                    Archived
                    <ArrowUpDown size={10} className={sortField === "date" ? "text-zinc-400" : ""} />
                  </span>
                </th>
                <th
                  className="px-4 py-2.5 text-left w-[100px] cursor-pointer hover:text-zinc-400 transition-colors"
                  onClick={() => toggleSort("reason")}
                >
                  <span className="flex items-center gap-1">
                    Reason
                    <ArrowUpDown size={10} className={sortField === "reason" ? "text-zinc-400" : ""} />
                  </span>
                </th>
                <th
                  className="px-4 py-2.5 text-right w-[70px] cursor-pointer hover:text-zinc-400 transition-colors"
                  onClick={() => toggleSort("tokens")}
                >
                  <span className="flex items-center gap-1 justify-end">
                    Tokens
                    <ArrowUpDown size={10} className={sortField === "tokens" ? "text-zinc-400" : ""} />
                  </span>
                </th>
                <th className="px-4 py-2.5 text-right w-[80px]">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {filteredArchived.map((entry) => {
                const reasonCfg = REASON_LABELS[entry.reason];
                return (
                  <tr
                    key={entry.memoryId}
                    className="hover:bg-zinc-800/20 transition-colors"
                  >
                    <td className="px-4 py-2.5 font-mono text-zinc-300 font-medium">
                      {formatMemoryId(entry.memoryId)}
                    </td>
                    <td className="px-4 py-2.5 text-zinc-400 max-w-[300px]">
                      <span className="truncate block">
                        {truncateText(entry.content, 70)}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-zinc-500">{entry.originalStatus}</span>
                      <span className="text-zinc-700 mx-1">→</span>
                      <span className="text-zinc-400">archived</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-zinc-500">
                      {formatTimestamp(entry.archivedAt)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`px-1.5 py-0.5 text-[10px] font-mono rounded ${reasonCfg.color}`}>
                        {reasonCfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-zinc-500">
                      {entry.tokenCount}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => handleRestore(entry.memoryId)}
                        className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-zinc-800 border border-zinc-700 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
                      >
                        <RotateCcw size={10} />
                        Restore
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {filteredArchived.length === 0 && (
            <div className="px-4 py-8 text-center text-[12px] text-zinc-600">
              No archived memories match your filters.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-4 py-2.5 border-t border-zinc-800 text-[10px] text-zinc-600">
          <span>
            Showing {filteredArchived.length} of {mockArchivedMemories.length} entries
          </span>
          <span className="text-zinc-700">·</span>
          <span>
            Total tokens freed: {mockArchivedMemories.reduce((sum, m) => sum + m.tokenCount, 0)}
          </span>
        </div>
      </div>

      {/* ── Preview Modal ────────────────────────────────────────── */}
      <Modal
        open={!!previewRec}
        onClose={() => setPreviewRec(null)}
        title={previewRec?.title ?? "Preview"}
        wide
      >
        {previewRec && <PreviewModalContent rec={previewRec} />}
      </Modal>
    </div>
  );
}

// ── Preview Modal Content ─────────────────────────────────────────────────

function PreviewModalContent({ rec }: { rec: OptimizationRecommendation }) {
  const memories = useMemo(() => {
    return rec.memoryIds
      .map((id) => mockMemories.find((m) => m.id === id))
      .filter(Boolean) as (typeof mockMemories)[number][];
  }, [rec.memoryIds]);

  return (
    <div className="space-y-4">
      <p className="text-[12px] text-zinc-400 leading-relaxed">
        {rec.description}
      </p>

      <div className="flex items-center gap-4 text-[11px]">
        <span className="text-zinc-500">
          Affected: <span className="text-zinc-300 font-mono">{rec.memoryIds.length} memories</span>
        </span>
        <span className="text-zinc-500">
          Savings: <span className="text-emerald-400 font-mono">
            {rec.savingsPerMonth >= 0 ? formatCurrency(rec.savingsPerMonth) : `+${formatCurrency(Math.abs(rec.savingsPerMonth))}`}/mo
          </span>
        </span>
      </div>

      {/* Memory list */}
      <div className="max-h-[360px] overflow-y-auto border border-zinc-800 rounded-lg divide-y divide-zinc-800/50">
        {memories.map((mem) => (
          <div key={mem.id} className="px-4 py-2.5 flex items-start gap-4">
            <div className="shrink-0 w-[70px]">
              <span className="text-[12px] font-mono text-zinc-300 font-medium">
                {formatMemoryId(mem.id)}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] text-zinc-400 truncate">
                {truncateText(mem.content, 80)}
              </p>
            </div>
            <div className="shrink-0 flex items-center gap-3 text-[11px] font-mono">
              <span className={classForROI(mem.roi)}>
                ROI: {mem.roi.toFixed(1)}
              </span>
              <span className={classForHealth(mem.healthScore)}>
                {mem.healthScore.toFixed(2)}
              </span>
            </div>
          </div>
        ))}

        {/* Show IDs not found in mockMemories */}
        {rec.memoryIds.length > memories.length && (
          <div className="px-4 py-2.5 text-[11px] text-zinc-600">
            + {rec.memoryIds.length - memories.length} memories not shown (archived or deleted)
          </div>
        )}
      </div>
    </div>
  );
}

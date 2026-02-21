"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Filter,
  ArrowUpDown,
  AlertTriangle,
  ChevronDown,
} from "lucide-react";
import { mockQueryTraces } from "@/lib/mock-data";
import {
  formatTimestamp,
  formatMemoryId,
  formatCurrency,
  truncateText,
} from "@/lib/utils";
import type { QueryTrace, HallucinationRisk } from "@/lib/types";

// ── Sort types ──────────────────────────────────────────────────────────

type SortKey = "timestamp" | "cost" | "risk";
type SortDir = "asc" | "desc";

const RISK_ORDER: Record<HallucinationRisk, number> = {
  none: 0,
  low: 1,
  medium: 2,
  high: 3,
};

function riskBadge(risk: HallucinationRisk) {
  switch (risk) {
    case "high":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <AlertTriangle size={10} /> High
        </span>
      );
    case "medium":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <AlertTriangle size={10} /> Medium
        </span>
      );
    case "low":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          Low
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide bg-zinc-800 text-zinc-500">
          None
        </span>
      );
  }
}

// ── Page ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 15;

export default function AttributionListPage() {
  const router = useRouter();

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState<string>("all");
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Pagination
  const [page, setPage] = useState(0);

  // Unique agent IDs
  const agentIds = useMemo(() => {
    const ids = new Set(mockQueryTraces.map((t) => t.agentId));
    return Array.from(ids).sort();
  }, []);

  // Filtered & sorted traces
  const filteredTraces = useMemo(() => {
    let traces = [...mockQueryTraces];

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      traces = traces.filter((t) => t.query.toLowerCase().includes(q));
    }

    // Agent filter
    if (agentFilter !== "all") {
      traces = traces.filter((t) => t.agentId === agentFilter);
    }

    // Risk filter
    if (riskFilter !== "all") {
      traces = traces.filter((t) => t.hallucinationRisk === riskFilter);
    }

    // Sort
    traces.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "timestamp":
          cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
        case "cost":
          cmp = a.totalCost - b.totalCost;
          break;
        case "risk":
          cmp = RISK_ORDER[a.hallucinationRisk] - RISK_ORDER[b.hallucinationRisk];
          break;
      }
      return sortDir === "desc" ? -cmp : cmp;
    });

    return traces;
  }, [searchQuery, agentFilter, riskFilter, sortKey, sortDir]);

  const totalPages = Math.ceil(filteredTraces.length / PAGE_SIZE);
  const paginatedTraces = filteredTraces.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
    setPage(0);
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">Attribution Explorer</h1>
        <p className="text-[13px] text-zinc-500 mt-0.5">
          {mockQueryTraces.length} query traces &middot; Search, filter, and drill into attribution data
        </p>
      </div>

      {/* Filters bar */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[220px]">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500"
          />
          <input
            type="text"
            placeholder="Search query text..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(0);
            }}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-md pl-9 pr-3 py-1.5 text-[13px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 transition-colors font-mono"
          />
        </div>

        {/* Agent filter */}
        <div className="relative">
          <Filter size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
          <select
            value={agentFilter}
            onChange={(e) => {
              setAgentFilter(e.target.value);
              setPage(0);
            }}
            className="appearance-none bg-zinc-900 border border-zinc-700 rounded-md pl-7 pr-7 py-1.5 text-[12px] text-zinc-300 focus:outline-none focus:border-zinc-500 transition-colors cursor-pointer"
          >
            <option value="all">All Agents</option>
            {agentIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          <ChevronDown
            size={12}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
          />
        </div>

        {/* Risk filter */}
        <div className="relative">
          <AlertTriangle size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
          <select
            value={riskFilter}
            onChange={(e) => {
              setRiskFilter(e.target.value);
              setPage(0);
            }}
            className="appearance-none bg-zinc-900 border border-zinc-700 rounded-md pl-7 pr-7 py-1.5 text-[12px] text-zinc-300 focus:outline-none focus:border-zinc-500 transition-colors cursor-pointer"
          >
            <option value="all">All Risk Levels</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="none">None</option>
          </select>
          <ChevronDown
            size={12}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
          />
        </div>

        {/* Sort controls */}
        <div className="flex items-center gap-1 text-[11px] text-zinc-500">
          <ArrowUpDown size={12} />
          <span>Sort:</span>
          {(["timestamp", "cost", "risk"] as SortKey[]).map((key) => (
            <button
              key={key}
              onClick={() => toggleSort(key)}
              className={`px-2 py-1 rounded-md transition-colors ${
                sortKey === key
                  ? "bg-zinc-800 text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {key === "timestamp" ? "Time" : key === "cost" ? "Cost" : "Risk"}
              {sortKey === key && (
                <span className="ml-0.5">{sortDir === "desc" ? "\u2193" : "\u2191"}</span>
              )}
            </button>
          ))}
        </div>

        {/* Count */}
        <span className="text-[11px] text-zinc-600 ml-auto">
          {filteredTraces.length} result{filteredTraces.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Query list */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
        {/* Column headers */}
        <div className="grid grid-cols-[80px_1fr_100px_auto_70px_70px_90px_140px] gap-2 px-4 py-2.5 border-b border-zinc-800 text-[10px] font-medium uppercase tracking-wider text-zinc-600">
          <span>Trace</span>
          <span>Query</span>
          <span>Agent</span>
          <span>Time</span>
          <span className="text-right"># Mem</span>
          <span className="text-right">Cost</span>
          <span className="text-center">Risk</span>
          <span>Top Attribution</span>
        </div>

        {/* Rows */}
        {paginatedTraces.length === 0 ? (
          <div className="px-4 py-8 text-center text-[13px] text-zinc-600">
            No traces match your filters.
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/50">
            {paginatedTraces.map((trace) => (
              <TraceRow
                key={trace.id}
                trace={trace}
                onClick={() => router.push(`/attribution/${trace.id}`)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-[12px]">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 rounded-md border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-zinc-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-3 py-1.5 rounded-md border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

// ── Trace Row ────────────────────────────────────────────────────────────

function TraceRow({
  trace,
  onClick,
}: {
  trace: QueryTrace;
  onClick: () => void;
}) {
  const isHighlighted =
    trace.hallucinationRisk === "medium" || trace.hallucinationRisk === "high";

  const topMemory = trace.memoriesRetrieved.length > 0
    ? [...trace.memoriesRetrieved].sort((a, b) => b.attributionScore - a.attributionScore)[0]
    : null;

  return (
    <button
      onClick={onClick}
      className={`w-full grid grid-cols-[80px_1fr_100px_auto_70px_70px_90px_140px] gap-2 px-4 py-2.5 text-left transition-colors group ${
        isHighlighted
          ? "bg-rose-950/10 hover:bg-rose-950/20"
          : "hover:bg-zinc-800/30"
      }`}
    >
      {/* Trace ID */}
      <span className="text-[12px] font-mono text-zinc-500 truncate">
        {trace.id.toUpperCase()}
      </span>

      {/* Query */}
      <span className="text-[13px] text-zinc-300 truncate font-mono group-hover:text-zinc-100 transition-colors">
        {truncateText(trace.query, 65)}
      </span>

      {/* Agent */}
      <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 self-center truncate text-center">
        {trace.agentId}
      </span>

      {/* Timestamp */}
      <span className="text-[11px] font-mono text-zinc-600 self-center whitespace-nowrap">
        {formatTimestamp(trace.timestamp)}
      </span>

      {/* # Memories */}
      <span className="text-[12px] font-mono text-zinc-500 text-right self-center tabular-nums">
        {trace.memoriesRetrieved.length}
      </span>

      {/* Cost */}
      <span className="text-[12px] font-mono text-zinc-500 text-right self-center tabular-nums">
        {formatCurrency(trace.totalCost)}
      </span>

      {/* Risk */}
      <span className="self-center text-center">
        {riskBadge(trace.hallucinationRisk)}
      </span>

      {/* Top Attribution */}
      <span className="text-[11px] font-mono text-zinc-400 self-center truncate">
        {topMemory
          ? `${formatMemoryId(topMemory.memoryId)} (${topMemory.attributionScore.toFixed(2)})`
          : "\u2014"}
      </span>
    </button>
  );
}

"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  Search,
  ChevronDown,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  AlertTriangle,
  Clock,
} from "lucide-react";
import { GrafanaPanel } from "@/components/dashboard/GrafanaPanel";
import { mockQueryTraces } from "@/lib/mock-data";
import {
  formatTimestamp,
  formatCurrency,
  truncateText,
} from "@/lib/utils";
import type { HallucinationRisk } from "@/lib/types";

// ── Sort types ───────────────────────────────────────────────────────────

type SortKey = "timestamp" | "totalCost" | "latencyMs" | "hallucinationRisk";
type SortDir = "asc" | "desc";

const RISK_ORDER: Record<HallucinationRisk, number> = {
  none: 0,
  low: 1,
  medium: 2,
  high: 3,
};

// ── Risk badge ───────────────────────────────────────────────────────────

function riskBadge(risk: HallucinationRisk) {
  const map: Record<HallucinationRisk, { bg: string; color: string; border: string; label: string }> = {
    none:   { bg: "transparent", color: "#464c54", border: "transparent", label: "None" },
    low:    { bg: "rgba(115,191,105,0.10)", color: "#73bf69", border: "rgba(115,191,105,0.20)", label: "Low" },
    medium: { bg: "rgba(255,152,48,0.10)", color: "#ff9830", border: "rgba(255,152,48,0.20)", label: "Medium" },
    high:   { bg: "rgba(242,73,92,0.10)", color: "#f2495c", border: "rgba(242,73,92,0.20)", label: "High" },
  };
  const s = map[risk];
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wide"
      style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}
    >
      {(risk === "high" || risk === "medium") && <AlertTriangle size={10} />}
      {s.label}
    </span>
  );
}

// ── Sort header ──────────────────────────────────────────────────────────

function SortTh({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
  align = "left",
}: {
  label: string;
  sortKey: SortKey;
  currentKey: SortKey;
  currentDir: SortDir;
  onSort: (k: SortKey) => void;
  align?: "left" | "right" | "center";
}) {
  const active = sortKey === currentKey;
  const textAlign = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  const justify = align === "right" ? "justify-end" : align === "center" ? "justify-center" : "justify-start";
  return (
    <th
      className={`py-2.5 px-3 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none ${textAlign}`}
      style={{ color: active ? "var(--grafana-text-primary)" : "var(--grafana-text-muted)" }}
      onClick={() => onSort(sortKey)}
    >
      <span className={`inline-flex items-center gap-1 ${justify}`}>
        {label}
        {active ? (
          currentDir === "desc" ? <ArrowDown size={9} /> : <ArrowUp size={9} />
        ) : (
          <ArrowUpDown size={9} style={{ opacity: 0.4 }} />
        )}
      </span>
    </th>
  );
}

// ── Grafana-style select ─────────────────────────────────────────────────

function GrafanaSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none text-[12px] font-mono pl-2.5 pr-6 py-1.5 cursor-pointer focus:outline-none"
        style={{
          background: "#0b0c0e",
          border: "1px solid var(--panel-border)",
          borderRadius: "var(--panel-radius)",
          color: "var(--grafana-text-primary)",
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown
        size={12}
        className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none"
        style={{ color: "var(--grafana-text-muted)" }}
      />
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 15;

export default function AttributionListPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(0);

  const agentIds = useMemo(() => {
    const ids = new Set(mockQueryTraces.map((t) => t.agentId));
    return Array.from(ids).sort();
  }, []);

  const filtered = useMemo(() => {
    let traces = [...mockQueryTraces];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      traces = traces.filter(
        (t) => t.query.toLowerCase().includes(q) || t.id.toLowerCase().includes(q)
      );
    }
    if (agentFilter !== "all") traces = traces.filter((t) => t.agentId === agentFilter);
    if (riskFilter !== "all") traces = traces.filter((t) => t.hallucinationRisk === riskFilter);

    traces.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "timestamp":
          cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
        case "totalCost":
          cmp = a.totalCost - b.totalCost;
          break;
        case "latencyMs":
          cmp = a.latencyMs - b.latencyMs;
          break;
        case "hallucinationRisk":
          cmp = RISK_ORDER[a.hallucinationRisk] - RISK_ORDER[b.hallucinationRisk];
          break;
      }
      return sortDir === "desc" ? -cmp : cmp;
    });
    return traces;
  }, [searchQuery, agentFilter, riskFilter, sortKey, sortDir]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const rangeStart = page * PAGE_SIZE + 1;
  const rangeEnd = Math.min((page + 1) * PAGE_SIZE, filtered.length);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir("desc"); }
    setPage(0);
  };

  return (
    <div className="flex flex-col" style={{ gap: "var(--panel-gap)" }}>
      {/* ── Filters panel ──────────────────────────────────────── */}
      <GrafanaPanel title="Filters" noPadding>
        <div className="flex flex-wrap items-center gap-3 px-4 py-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[220px]">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: "var(--grafana-text-muted)" }}
            />
            <input
              type="text"
              placeholder="Search query text or trace ID..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
              className="w-full pl-9 pr-3 py-1.5 text-[13px] font-mono focus:outline-none"
              style={{
                background: "#0b0c0e",
                border: "1px solid var(--panel-border)",
                borderRadius: "var(--panel-radius)",
                color: "var(--grafana-text-primary)",
              }}
            />
          </div>

          {/* Agent dropdown */}
          <GrafanaSelect
            value={agentFilter}
            onChange={(v) => { setAgentFilter(v); setPage(0); }}
            options={[
              { value: "all", label: "All Agents" },
              ...agentIds.map((id) => ({ value: id, label: id })),
            ]}
          />

          {/* Risk dropdown */}
          <GrafanaSelect
            value={riskFilter}
            onChange={(v) => { setRiskFilter(v); setPage(0); }}
            options={[
              { value: "all", label: "All Risk" },
              { value: "high", label: "High" },
              { value: "medium", label: "Medium" },
              { value: "low", label: "Low" },
              { value: "none", label: "None" },
            ]}
          />

          {/* Time range display */}
          <div
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-mono"
            style={{
              background: "#0b0c0e",
              border: "1px solid var(--panel-border)",
              borderRadius: "var(--panel-radius)",
              color: "var(--grafana-text-secondary)",
            }}
          >
            <Clock size={12} style={{ color: "var(--grafana-text-muted)" }} />
            Last 14 days
          </div>

          {/* Result count */}
          <span className="text-[11px] font-mono ml-auto" style={{ color: "var(--grafana-text-muted)" }}>
            {filtered.length} trace{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>
      </GrafanaPanel>

      {/* ── Query Traces table ─────────────────────────────────── */}
      <GrafanaPanel title="Query Traces" noPadding>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
                <th className="text-left py-2.5 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Trace ID</th>
                <SortTh label="Time" sortKey="timestamp" currentKey={sortKey} currentDir={sortDir} onSort={toggleSort} />
                <th className="text-left py-2.5 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Agent</th>
                <th className="text-left py-2.5 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Query</th>
                <th className="text-right py-2.5 px-3 text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--grafana-text-muted)" }}>Memories</th>
                <SortTh label="Cost" sortKey="totalCost" currentKey={sortKey} currentDir={sortDir} onSort={toggleSort} align="right" />
                <SortTh label="Latency" sortKey="latencyMs" currentKey={sortKey} currentDir={sortDir} onSort={toggleSort} align="right" />
                <SortTh label="Risk" sortKey="hallucinationRisk" currentKey={sortKey} currentDir={sortDir} onSort={toggleSort} align="center" />
              </tr>
            </thead>
            <tbody>
              {paginated.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-[13px]" style={{ color: "var(--grafana-text-muted)" }}>
                    No traces match your filters.
                  </td>
                </tr>
              ) : (
                paginated.map((trace) => {
                  const isHigh = trace.hallucinationRisk === "high";
                  return (
                    <tr
                      key={trace.id}
                      className="transition-colors"
                      style={{
                        borderBottom: "1px solid var(--panel-border)",
                        borderLeft: isHigh ? "3px solid #f2495c" : "3px solid transparent",
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = "var(--panel-bg-hover)"}
                      onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                    >
                      <td className="py-2.5 px-3">
                        <Link href={`/attribution/${trace.id}`} className="font-mono text-[12px] hover:underline" style={{ color: "#6e9fff" }}>
                          {trace.id.toUpperCase()}
                        </Link>
                      </td>
                      <td className="py-2.5 px-3 font-mono tabular-nums whitespace-nowrap" style={{ color: "var(--grafana-text-muted)" }}>
                        {formatTimestamp(trace.timestamp)}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-1.5 py-0.5 rounded-sm text-[10px] font-medium" style={{ background: "var(--panel-bg-hover)", color: "var(--grafana-text-secondary)" }}>
                          {trace.agentId}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono max-w-[280px] truncate" style={{ color: "var(--grafana-text-secondary)" }}>
                        {truncateText(trace.query, 55)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums" style={{ color: "var(--grafana-text-secondary)" }}>
                        {trace.memoriesRetrieved.length}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums" style={{ color: "var(--grafana-text-muted)" }}>
                        {formatCurrency(trace.totalCost)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono tabular-nums" style={{ color: "var(--grafana-text-muted)" }}>
                        {trace.latencyMs}ms
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        {riskBadge(trace.hallucinationRisk)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination footer */}
        {filtered.length > 0 && (
          <div className="flex items-center justify-between px-4 py-2.5" style={{ borderTop: "1px solid var(--panel-border)" }}>
            <span className="text-[11px] font-mono" style={{ color: "var(--grafana-text-muted)" }}>
              Showing {rangeStart}–{rangeEnd} of {filtered.length}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1 text-[11px] font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                style={{ background: "transparent", border: "1px solid var(--panel-border)", borderRadius: "var(--panel-radius)", color: "var(--grafana-text-primary)" }}
                onMouseEnter={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.background = "var(--panel-bg-hover)"; }}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1 text-[11px] font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                style={{ background: "transparent", border: "1px solid var(--panel-border)", borderRadius: "var(--panel-radius)", color: "var(--grafana-text-primary)" }}
                onMouseEnter={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.background = "var(--panel-bg-hover)"; }}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </GrafanaPanel>
    </div>
  );
}

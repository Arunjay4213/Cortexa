"use client";

import { useState, useMemo, useCallback } from "react";
import {
  Search,
  RotateCcw,
  TrendingDown,
  TrendingUp,
  Minus,
  ChevronDown,
  Eye,
  Play,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
} from "lucide-react";
import { StatPanel } from "@/components/dashboard/StatPanel";
import { GrafanaPanel } from "@/components/dashboard/GrafanaPanel";
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
} from "@/lib/utils";
import type {
  OptimizationRecommendation,
  ArchiveReason,
  ImpactDirection,
} from "@/lib/types";

// ── Derived stats ────────────────────────────────────────────────────────

const utilPct = Math.round(
  (mockBudgetStats.usedTokens / mockBudgetStats.budgetTokens) * 100
);
const archivedCount = mockArchivedMemories.filter(
  (m) => m.reason !== "consolidation"
).length;
const consolidatedCount = mockArchivedMemories.filter(
  (m) => m.reason === "consolidation"
).length;

// ── Sort types ───────────────────────────────────────────────────────────

type SortField = "date" | "reason" | "tokens";

// ── Page ─────────────────────────────────────────────────────────────────

export default function LifecyclePage() {
  // Preview state
  const [previewRecId, setPreviewRecId] = useState<string | null>(null);

  // Archive manager state
  const [searchQuery, setSearchQuery] = useState("");
  const [reasonFilter, setReasonFilter] = useState<ArchiveReason | "all">(
    "all"
  );
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortAsc, setSortAsc] = useState(false);

  // Toggle sort
  const toggleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) setSortAsc((a) => !a);
      else {
        setSortField(field);
        setSortAsc(false);
      }
    },
    [sortField]
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
      if (sortField === "date")
        cmp =
          new Date(a.archivedAt).getTime() -
          new Date(b.archivedAt).getTime();
      else if (sortField === "reason")
        cmp = a.reason.localeCompare(b.reason);
      else if (sortField === "tokens") cmp = a.tokenCount - b.tokenCount;
      return sortAsc ? cmp : -cmp;
    });

    return items;
  }, [searchQuery, reasonFilter, sortField, sortAsc]);

  return (
    <div className="flex flex-col" style={{ gap: "var(--panel-gap)" }}>
      {/* ── ROW 1: Three stat panels ───────────────────────────── */}
      <div
        className="grid grid-cols-1 md:grid-cols-3"
        style={{ gap: "var(--panel-gap)" }}
      >
        <StatPanel
          label="Token Budget"
          value={`${utilPct}%`}
          color={utilPct > 80 ? "red" : utilPct > 60 ? "yellow" : "green"}
          sub={`${(mockBudgetStats.usedTokens / 1000).toFixed(0)}k / ${(mockBudgetStats.budgetTokens / 1000).toFixed(0)}k tokens`}
        />
        <StatPanel
          label="Monthly Cost"
          value={`$${mockBudgetStats.monthlySpend.toLocaleString()}/mo`}
          color="red"
        />
        <StatPanel
          label="Potential Savings"
          value={`$${mockBudgetStats.projectedSavings}/mo`}
          color="green"
        />
      </div>

      {/* ── ROW 2: Optimization Recommendations ────────────────── */}
      <GrafanaPanel
        title="Optimization Recommendations"
        headerRight={
          <span
            className="text-[10px] font-mono"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            {mockOptimizationRecommendations.length} actions available
          </span>
        }
        noPadding
      >
        <div className="flex flex-col">
          {mockOptimizationRecommendations.map((rec, idx) => (
            <RecommendationRow
              key={rec.id}
              rec={rec}
              isLast={
                idx === mockOptimizationRecommendations.length - 1
              }
              previewOpen={previewRecId === rec.id}
              onTogglePreview={() =>
                setPreviewRecId(
                  previewRecId === rec.id ? null : rec.id
                )
              }
            />
          ))}
        </div>
      </GrafanaPanel>

      {/* ── ROW 3: Archive Manager ─────────────────────────────── */}
      <GrafanaPanel
        title="Archive Manager"
        headerRight={
          <span
            className="text-[10px] font-mono"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            {archivedCount} archived &middot; {consolidatedCount}{" "}
            consolidated
          </span>
        }
        noPadding
      >
        {/* Filter bar */}
        <div
          className="flex flex-wrap items-center gap-3 px-4 py-2.5"
          style={{ borderBottom: "1px solid var(--panel-border)" }}
        >
          {/* Search */}
          <div className="relative">
            <Search
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
              style={{ color: "var(--grafana-text-muted)" }}
            />
            <input
              type="text"
              placeholder="Search archived..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-[12px] font-mono w-[160px] focus:outline-none transition-colors"
              style={{
                background: "#0b0c0e",
                border: "1px solid var(--panel-border)",
                borderRadius: "2px",
                color: "var(--grafana-text-secondary)",
              }}
            />
          </div>

          {/* Reason filter */}
          <div className="relative">
            <select
              value={reasonFilter}
              onChange={(e) =>
                setReasonFilter(
                  e.target.value as ArchiveReason | "all"
                )
              }
              className="appearance-none pl-3 pr-7 py-1.5 text-[12px] font-mono cursor-pointer focus:outline-none transition-colors"
              style={{
                background: "#0b0c0e",
                border: "1px solid var(--panel-border)",
                borderRadius: "2px",
                color: "var(--grafana-text-secondary)",
              }}
            >
              <option value="all">All Reasons</option>
              <option value="auto-archive">Auto-archive</option>
              <option value="manual">Manual</option>
              <option value="consolidation">Consolidation</option>
            </select>
            <ChevronDown
              size={12}
              className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none"
              style={{ color: "var(--grafana-text-muted)" }}
            />
          </div>

          <div className="flex-1" />

          <span
            className="text-[11px] font-mono"
            style={{ color: "var(--grafana-text-muted)" }}
          >
            Showing {filteredArchived.length} of{" "}
            {mockArchivedMemories.length}
          </span>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid var(--panel-border)",
                }}
              >
                <th
                  className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-medium w-[80px]"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  ID
                </th>
                <th
                  className="text-left px-2 py-2.5 text-[10px] uppercase tracking-wider font-medium"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Content
                </th>
                <th
                  className="text-left px-2 py-2.5 text-[10px] uppercase tracking-wider font-medium w-[110px]"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Prev Status
                </th>
                <SortTh
                  label="Archived"
                  field="date"
                  currentField={sortField}
                  asc={sortAsc}
                  onSort={toggleSort}
                  width="w-[100px]"
                />
                <SortTh
                  label="Reason"
                  field="reason"
                  currentField={sortField}
                  asc={sortAsc}
                  onSort={toggleSort}
                  width="w-[110px]"
                />
                <SortTh
                  label="Tokens"
                  field="tokens"
                  currentField={sortField}
                  asc={sortAsc}
                  onSort={toggleSort}
                  width="w-[70px]"
                  align="right"
                />
                <th
                  className="text-right px-4 py-2.5 text-[10px] uppercase tracking-wider font-medium w-[80px]"
                  style={{ color: "var(--grafana-text-muted)" }}
                >
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredArchived.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-8 text-center text-[13px]"
                    style={{
                      color: "var(--grafana-text-muted)",
                    }}
                  >
                    No archived memories match your filters.
                  </td>
                </tr>
              ) : (
                filteredArchived.map((entry) => (
                  <tr
                    key={entry.memoryId}
                    style={{
                      borderBottom:
                        "1px solid var(--panel-border)",
                    }}
                    className="transition-colors"
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background =
                        "var(--panel-bg-hover)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background =
                        "transparent")
                    }
                  >
                    <td
                      className="px-4 py-2.5 font-mono font-medium"
                      style={{
                        color: "var(--grafana-text-primary)",
                      }}
                    >
                      {formatMemoryId(entry.memoryId)}
                    </td>
                    <td
                      className="px-2 py-2.5 max-w-[300px]"
                      style={{
                        color: "var(--grafana-text-secondary)",
                      }}
                    >
                      <span className="truncate block">
                        {truncateText(entry.content, 70)}
                      </span>
                    </td>
                    <td className="px-2 py-2.5">
                      <span
                        style={{
                          color: "var(--grafana-text-muted)",
                        }}
                      >
                        {entry.originalStatus}
                      </span>
                    </td>
                    <td
                      className="px-2 py-2.5 font-mono"
                      style={{
                        color: "var(--grafana-text-muted)",
                      }}
                    >
                      {formatTimestamp(entry.archivedAt)}
                    </td>
                    <td className="px-2 py-2.5">
                      <ReasonBadge reason={entry.reason} />
                    </td>
                    <td
                      className="px-2 py-2.5 text-right font-mono tabular-nums"
                      style={{
                        color: "var(--grafana-text-muted)",
                      }}
                    >
                      {entry.tokenCount}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-sm transition-colors"
                        style={{
                          background: "transparent",
                          border: "1px solid var(--panel-border)",
                          color: "var(--grafana-text-primary)",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background =
                            "var(--panel-bg-hover)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background =
                            "transparent")
                        }
                      >
                        <RotateCcw size={10} />
                        Restore
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div
          className="flex items-center gap-4 px-4 py-2.5 text-[10px]"
          style={{
            borderTop: "1px solid var(--panel-border)",
            color: "var(--grafana-text-muted)",
          }}
        >
          <span>
            Total tokens freed:{" "}
            {mockArchivedMemories
              .reduce((sum, m) => sum + m.tokenCount, 0)
              .toLocaleString()}
          </span>
        </div>
      </GrafanaPanel>
    </div>
  );
}

// ── Recommendation Row ───────────────────────────────────────────────────

function RecommendationRow({
  rec,
  isLast,
  previewOpen,
  onTogglePreview,
}: {
  rec: OptimizationRecommendation;
  isLast: boolean;
  previewOpen: boolean;
  onTogglePreview: () => void;
}) {
  const impactColor: Record<ImpactDirection, string> = {
    positive: "var(--grafana-green)",
    negative: "var(--grafana-red)",
    neutral: "var(--grafana-text-muted)",
  };

  const ImpactIcon =
    rec.impactDirection === "positive"
      ? TrendingUp
      : rec.impactDirection === "negative"
        ? TrendingDown
        : Minus;

  const previewMemories = useMemo(() => {
    if (!previewOpen) return [];
    return rec.memoryIds
      .map((id) => mockMemories.find((m) => m.id === id))
      .filter(Boolean) as (typeof mockMemories)[number][];
  }, [rec.memoryIds, previewOpen]);

  return (
    <div
      style={{
        borderBottom: isLast
          ? undefined
          : "1px solid var(--panel-border)",
      }}
    >
      <div className="flex items-center gap-4 px-4 py-3">
        {/* Priority badge */}
        <span
          className="w-6 h-6 flex items-center justify-center rounded-full text-[11px] font-mono font-bold shrink-0"
          style={{
            background: "rgba(87,148,242,0.15)",
            color: "#5794f2",
          }}
        >
          {rec.priority}
        </span>

        {/* Title + impact */}
        <div className="flex-1 min-w-0">
          <div
            className="text-[14px] font-medium"
            style={{ color: "#d8d9da" }}
          >
            {rec.title}
          </div>
          <div
            className="flex items-center gap-3 mt-0.5 text-[12px]"
            style={{ color: "#8e8e8e" }}
          >
            <span className="flex items-center gap-1">
              <ImpactIcon
                size={12}
                style={{
                  color: impactColor[rec.impactDirection],
                }}
              />
              Impact: {rec.impactLabel}
            </span>
            <span>
              Savings:{" "}
              <span
                className="font-mono"
                style={{
                  color:
                    rec.savingsPerMonth >= 0
                      ? "#73bf69"
                      : "var(--grafana-yellow)",
                }}
              >
                {rec.savingsPerMonth >= 0
                  ? `$${rec.savingsPerMonth}`
                  : `+$${Math.abs(rec.savingsPerMonth)}`}
                /mo
              </span>
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={onTogglePreview}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-sm transition-colors"
            style={{
              background: "transparent",
              border: "1px solid #2c3235",
              color: "#d8d9da",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background =
                "var(--panel-bg-hover)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "transparent")
            }
          >
            <Eye size={12} />
            Preview
          </button>
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-sm transition-colors"
            style={{
              background: "#73bf69",
              border: "1px solid #73bf69",
              color: "#0b0c0e",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = "#5fa857")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = "#73bf69")
            }
          >
            <Play size={12} />
            Apply
          </button>
        </div>
      </div>

      {/* Preview expansion */}
      {previewOpen && previewMemories.length > 0 && (
        <div
          className="px-4 pb-3"
          style={{ marginLeft: 40 }}
        >
          <div
            className="rounded-sm overflow-hidden"
            style={{
              border: "1px solid var(--panel-border)",
            }}
          >
            {previewMemories.map((mem, i) => (
              <div
                key={mem.id}
                className="flex items-center gap-3 px-3 py-2 text-[11px]"
                style={{
                  borderBottom:
                    i < previewMemories.length - 1
                      ? "1px solid var(--panel-border)"
                      : undefined,
                  background: "#0b0c0e",
                }}
              >
                <span
                  className="font-mono font-medium shrink-0 w-[50px]"
                  style={{ color: "#6e9fff" }}
                >
                  {formatMemoryId(mem.id)}
                </span>
                <span
                  className="flex-1 truncate"
                  style={{
                    color: "var(--grafana-text-secondary)",
                  }}
                >
                  {truncateText(mem.content, 60)}
                </span>
                <span
                  className="font-mono shrink-0"
                  style={{
                    color:
                      mem.roi < 0
                        ? "var(--grafana-red)"
                        : "var(--grafana-green)",
                  }}
                >
                  ROI: {mem.roi.toFixed(1)}x
                </span>
                <span
                  className="font-mono shrink-0"
                  style={{
                    color:
                      mem.healthScore >= 0.7
                        ? "var(--grafana-green)"
                        : mem.healthScore >= 0.4
                          ? "var(--grafana-yellow)"
                          : "var(--grafana-red)",
                  }}
                >
                  {mem.healthScore.toFixed(2)}
                </span>
              </div>
            ))}
            {rec.memoryIds.length > previewMemories.length && (
              <div
                className="px-3 py-2 text-[10px]"
                style={{
                  background: "#0b0c0e",
                  color: "var(--grafana-text-muted)",
                }}
              >
                +{rec.memoryIds.length - previewMemories.length}{" "}
                memories not shown (archived or deleted)
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Reason Badge ─────────────────────────────────────────────────────────

function ReasonBadge({ reason }: { reason: ArchiveReason }) {
  const map: Record<
    ArchiveReason,
    { bg: string; color: string; border: string; label: string }
  > = {
    "auto-archive": {
      bg: "var(--panel-bg-hover)",
      color: "var(--grafana-text-muted)",
      border: "var(--panel-border)",
      label: "Auto",
    },
    manual: {
      bg: "rgba(87,148,242,0.10)",
      color: "#5794f2",
      border: "rgba(87,148,242,0.20)",
      label: "Manual",
    },
    consolidation: {
      bg: "rgba(184,119,217,0.10)",
      color: "#b877d9",
      border: "rgba(184,119,217,0.20)",
      label: "Consolidated",
    },
  };
  const s = map[reason];
  return (
    <span
      className="inline-flex px-1.5 py-0.5 text-[10px] font-mono rounded-sm"
      style={{
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.border}`,
      }}
    >
      {s.label}
    </span>
  );
}

// ── Sort Header ──────────────────────────────────────────────────────────

function SortTh({
  label,
  field,
  currentField,
  asc,
  onSort,
  width,
  align = "left",
}: {
  label: string;
  field: SortField;
  currentField: SortField;
  asc: boolean;
  onSort: (f: SortField) => void;
  width?: string;
  align?: "left" | "right";
}) {
  const active = field === currentField;
  return (
    <th
      className={`px-2 py-2.5 text-[10px] uppercase tracking-wider font-medium cursor-pointer select-none ${width ?? ""} text-${align}`}
      style={{
        color: active
          ? "var(--grafana-text-primary)"
          : "var(--grafana-text-muted)",
      }}
      onClick={() => onSort(field)}
    >
      <span
        className={`inline-flex items-center gap-1 ${align === "right" ? "justify-end" : ""}`}
      >
        {label}
        {active ? (
          asc ? (
            <ArrowUp size={9} />
          ) : (
            <ArrowDown size={9} />
          )
        ) : (
          <ArrowUpDown
            size={9}
            style={{ color: "var(--grafana-text-disabled)" }}
          />
        )}
      </span>
    </th>
  );
}

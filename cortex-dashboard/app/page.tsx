"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  useDashboardOverview,
  useContradictions,
  useTopMemories,
  useTimeSeries,
  useContaminationScan,
  useCostSummary,
} from "@/lib/hooks";
import { PageTransition } from "@/components/primitives/PageTransition";
import { PageHeader } from "@/components/primitives/PageHeader";
import { SectionHeader } from "@/components/primitives/SectionHeader";
import { MetricCard } from "@/components/primitives/MetricCard";
import { Sparkline } from "@/components/primitives/Sparkline";
import { EntityLink } from "@/components/primitives/EntityLink";
import { ErrorFallback } from "@/components/primitives/ErrorFallback";
import { CardSkeleton } from "@/components/primitives/LoadingSkeleton";
import { EmptyState } from "@/components/primitives/EmptyState";
import { AlertTriangle, ShieldAlert, Database } from "lucide-react";
import type { AgentSummary, Contradiction, TopMemoryResponse } from "@/lib/api/types";

/* ── Formatting helpers ─────────────────────────────────────────────── */

function fmt2(v: number | undefined | null): string {
  if (v === undefined || v === null) return "--";
  return v.toFixed(2);
}

function fmt4(v: number | undefined | null): string {
  if (v === undefined || v === null) return "--";
  return v.toFixed(4);
}

function fmtPct(v: number | undefined | null): string {
  if (v === undefined || v === null) return "--";
  return (v * 100).toFixed(1) + "%";
}

function fmtDollar(v: number | undefined | null): string {
  if (v === undefined || v === null) return "--";
  if (v >= 1000) {
    return "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }
  return "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "--";
  try {
    return new Date(iso).toISOString().slice(11, 19) + "Z";
  } catch {
    return "--";
  }
}

function tierBadge(tier: string): string {
  switch (tier) {
    case "hot":
      return "badge badge--error";
    case "warm":
      return "badge badge--warning";
    case "cold":
      return "badge badge--info";
    default:
      return "badge badge--neutral";
  }
}

function healthBadge(contradictions: number): {
  cls: string;
  label: string;
} {
  if (contradictions === 0) return { cls: "badge badge--success", label: "Healthy" };
  if (contradictions <= 3) return { cls: "badge badge--warning", label: "Warning" };
  return { cls: "badge badge--error", label: "Critical" };
}

/* ── Monthly savings calc ───────────────────────────────────────────── */

const AVG_TOKENS = 100;
const INPUT_TOKEN_COST = 0.00001;
const QUERIES_PER_DAY = 100;
const DAYS_PER_MONTH = 30;

function calcMonthlySavings(agents: AgentSummary[]): number {
  return agents.reduce((total, a) => {
    const waste = a.waste_rate ?? 0;
    const mems = a.total_memories ?? 0;
    return total + waste * mems * AVG_TOKENS * INPUT_TOKEN_COST * QUERIES_PER_DAY * DAYS_PER_MONTH;
  }, 0);
}

/* ── CHI (Cortex Health Index) ──────────────────────────────────────── */

function calcCHI(overview: {
  overall_gini: number;
  overall_snr_db: number;
  overall_waste_rate: number;
} | null, contradictionCount: number, totalMemories: number): number | null {
  if (!overview) return null;
  const giniScore = Math.max(0, 1 - overview.overall_gini);
  const snrNormalized = Math.min(1, Math.max(0, (overview.overall_snr_db + 10) / 30));
  const wasteScore = Math.max(0, 1 - overview.overall_waste_rate);
  const contradictionRate = totalMemories > 0 ? contradictionCount / totalMemories : 0;
  const contradictionScore = Math.max(0, 1 - contradictionRate * 10);
  return (giniScore * 0.25 + snrNormalized * 0.25 + wasteScore * 0.25 + contradictionScore * 0.25);
}

/* ══════════════════════════════════════════════════════════════════════
   Overview Page
   ══════════════════════════════════════════════════════════════════════ */

export default function OverviewPage() {
  /* ── Data fetching ──────────────────────────────────────────────── */

  const {
    data: overview,
    error: overviewError,
    isLoading: overviewLoading,
    mutate: mutateOverview,
  } = useDashboardOverview();

  const {
    data: contradictions,
    error: contradictionsError,
    isLoading: contradictionsLoading,
    mutate: mutateContradictions,
  } = useContradictions({ resolved: false });

  const {
    data: topMemories,
    error: topMemoriesError,
    isLoading: topMemoriesLoading,
    mutate: mutateTopMemories,
  } = useTopMemories({ n: 10 });

  const { data: timeSeries } = useTimeSeries({
    metric: "attribution",
    days: 7,
    bucket: "1h",
  });

  const { data: costData } = useCostSummary();

  const firstAgentId = overview?.agents?.[0]?.agent_id ?? null;
  const { data: contaminationScan } = useContaminationScan(firstAgentId);

  /* ── Derived values ─────────────────────────────────────────────── */

  const agents = overview?.agents ?? [];

  const monthlySavings = useMemo(() => calcMonthlySavings(agents), [agents]);

  const avgCost = useMemo(() => {
    if (!costData || costData.length === 0) return null;
    const totalCost = costData.reduce((s, c) => s + c.total_cost, 0);
    const totalTxns = costData.reduce((s, c) => s + c.transaction_count, 0);
    return totalTxns > 0 ? totalCost / totalTxns : 0;
  }, [costData]);

  const chiScore = useMemo(
    () =>
      calcCHI(
        overview ?? null,
        contradictions?.length ?? 0,
        overview?.total_memories ?? 0
      ),
    [overview, contradictions]
  );

  const coveragePct = useMemo(() => {
    if (!overview || overview.total_memories === 0) return null;
    const memoriesWithAttribution = agents.reduce(
      (s, a) => s + (a.avg_attribution > 0 ? a.total_memories : 0),
      0
    );
    return memoriesWithAttribution / overview.total_memories;
  }, [overview, agents]);

  const chartData = useMemo(() => {
    if (!timeSeries?.buckets?.length) return [];
    return timeSeries.buckets.map((b) => ({
      time: new Date(b.timestamp).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }),
      value: b.value,
      count: b.count,
    }));
  }, [timeSeries]);

  const hasContradictions = contradictions && contradictions.length > 0;

  /* ── Loading state ──────────────────────────────────────────────── */

  if (overviewLoading) {
    return (
      <PageTransition>
        <div className="p-8">
          <PageHeader title="Overview" subtitle="Memory observability at a glance" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {Array.from({ length: 8 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        </div>
      </PageTransition>
    );
  }

  /* ── Error state ────────────────────────────────────────────────── */

  if (overviewError) {
    return (
      <PageTransition>
        <div className="p-8">
          <PageHeader title="Overview" subtitle="Memory observability at a glance" />
          <ErrorFallback error={overviewError} onRetry={() => mutateOverview()} />
        </div>
      </PageTransition>
    );
  }

  /* ── Render ─────────────────────────────────────────────────────── */

  return (
    <PageTransition>
      <div className="p-8 min-h-screen">
        {/* ── Page Header ───────────────────────────────────────── */}
        <PageHeader title="Overview" subtitle="Memory observability at a glance" />

        {/* ── Contradiction Alert Banner ────────────────────────── */}
        {hasContradictions && (
          <div
            className="callout callout--error mb-8"
          >
            <ShieldAlert
              size={20}
              className="text-[var(--status-error)] shrink-0"
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-[var(--text-primary)] font-medium">
                {contradictions.length} unresolved contradiction
                {contradictions.length !== 1 ? "s" : ""} detected
              </p>
              {contradictions[0] && (
                <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                  Highest confidence:{" "}
                  <EntityLink type="memory" id={contradictions[0].memory_id_1} />
                  <span className="mx-1 text-[var(--text-ghost)]">&harr;</span>
                  <EntityLink type="memory" id={contradictions[0].memory_id_2} />
                  <span className="ml-2 font-mono text-[var(--text-secondary)]">
                    {fmt4(contradictions[0].confidence)}
                  </span>
                </p>
              )}
            </div>
            <Link
              href="/health"
              className="btn btn--ghost text-xs shrink-0"
            >
              View All &rarr;
            </Link>
          </div>
        )}

        {/* ── KPI Grid (8 cards, 2 rows of 4) ──────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8 stagger-children">
          <MetricCard
            label="Total Memories"
            value={overview?.total_memories?.toLocaleString() ?? "--"}
            sparkline={
              <Sparkline
                data={agents.map((a) => a.total_memories).slice(0, 7)}
              />
            }
          />
          <MetricCard
            label="Active Agents"
            value={agents.length}
          />
          <MetricCard
            label="Transactions"
            value={overview?.total_transactions?.toLocaleString() ?? "--"}
          />
          <MetricCard
            label="Avg EAS Score"
            value={
              agents.length > 0
                ? fmt4(
                    agents.reduce((s, a) => s + a.avg_attribution, 0) /
                      agents.length
                  )
                : "--"
            }
          />
          <MetricCard
            label="Contradictions"
            value={contradictions?.length ?? "--"}
            delta={
              hasContradictions
                ? contradictions.length * -1
                : undefined
            }
            deltaLabel={hasContradictions ? "unresolved" : undefined}
          />
          <MetricCard
            label="Coverage"
            value={coveragePct !== null ? fmtPct(coveragePct) : "--"}
          />
          <MetricCard
            label="Avg Cost"
            value={avgCost !== null ? fmtDollar(avgCost) : "--"}
          />
          <MetricCard
            label="CHI Score"
            value={chiScore !== null ? fmt2(chiScore) : "--"}
          />
        </div>

        {/* ── Attribution Trend Chart ───────────────────────────── */}
        {chartData.length > 0 && (
          <div className="card mb-8 p-6">
            <SectionHeader title="Attribution Trend" count={chartData.length}>
              <span className="text-xs text-[var(--text-ghost)]">7-day window</span>
            </SectionHeader>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="attrGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366F1" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#6366F1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1C1C1F" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: "#5C5C66", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "#5C5C66", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={48}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#141416",
                      border: "1px solid #1E1E22",
                      borderRadius: 12,
                    }}
                    labelStyle={{ color: "#5C5C66", fontSize: 11 }}
                    itemStyle={{ color: "#6366F1" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#6366F1"
                    fill="url(#attrGradient)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, fill: "#6366F1", strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* ── Bottom Section: Agent Table (60%) + Right Column (40%) */}
        <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-6">
          {/* ── Agent Table ────────────────────────────────────── */}
          <div className="card overflow-hidden">
            <div className="p-5 pb-0">
              <SectionHeader title="Agent Fleet" count={agents.length} />
            </div>
            {agents.length === 0 ? (
              <EmptyState
                title="No agents found"
                description="Agents will appear here once they start processing memories."
                icon={<Database size={36} strokeWidth={1} />}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="table w-full">
                  <thead>
                    <tr>
                      <th className="text-left pl-5">Agent</th>
                      <th className="text-right">Memories</th>
                      <th className="text-right">Txns</th>
                      <th className="text-right">Avg EAS</th>
                      <th className="text-right">Gini</th>
                      <th className="text-right">SNR</th>
                      <th className="text-right">Waste</th>
                      <th className="text-center">Health</th>
                      <th className="text-right pr-5">Last Active</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((agent: AgentSummary) => {
                      const hb = healthBadge(agent.contradiction_count ?? 0);
                      return (
                        <tr key={agent.agent_id}>
                          <td className="pl-5">
                            <EntityLink type="agent" id={agent.agent_id} />
                          </td>
                          <td className="text-right font-mono text-[var(--text-primary)]">
                            {agent.total_memories?.toLocaleString() ?? "--"}
                          </td>
                          <td className="text-right font-mono text-[var(--text-primary)]">
                            {agent.total_transactions?.toLocaleString() ?? "--"}
                          </td>
                          <td className="text-right font-mono">
                            {fmt4(agent.avg_attribution)}
                          </td>
                          <td className="text-right font-mono">
                            {fmt4(agent.gini_coefficient)}
                          </td>
                          <td className="text-right font-mono">
                            {fmt2(agent.snr_db)}
                          </td>
                          <td className="text-right font-mono">
                            {fmtPct(agent.waste_rate)}
                          </td>
                          <td className="text-center">
                            <span className={hb.cls}>{hb.label}</span>
                          </td>
                          <td className="text-right pr-5 font-mono text-[var(--text-tertiary)] text-xs">
                            {fmtTime(agent.last_active)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Right Column: Contradictions + Top Memories ──── */}
          <div className="flex flex-col gap-6">
            {/* Contradictions Card */}
            <div className="card overflow-hidden">
              <div className="p-5 pb-0">
                <SectionHeader
                  title="Contradictions"
                  count={contradictions?.length ?? 0}
                >
                  <Link href="/health" className="btn btn--ghost text-xs">
                    View All
                  </Link>
                </SectionHeader>
              </div>

              {contradictionsLoading ? (
                <div className="p-5">
                  <CardSkeleton />
                </div>
              ) : contradictionsError ? (
                <div className="p-5">
                  <ErrorFallback
                    error={contradictionsError}
                    onRetry={() => mutateContradictions()}
                  />
                </div>
              ) : !contradictions || contradictions.length === 0 ? (
                <EmptyState
                  title="No contradictions"
                  description="Memory bank is consistent."
                />
              ) : (
                <div className="divide-y divide-[var(--border-default)]">
                  {contradictions.slice(0, 5).map((c: Contradiction) => (
                    <div
                      key={c.id}
                      className="px-5 py-3 flex items-center gap-3 hover:bg-[var(--bg-surface-2)] transition-colors"
                    >
                      <AlertTriangle
                        size={14}
                        className="text-[var(--status-error)] shrink-0"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 text-xs">
                          <EntityLink type="memory" id={c.memory_id_1} />
                          <span className="text-[var(--text-ghost)]">&harr;</span>
                          <EntityLink type="memory" id={c.memory_id_2} />
                        </div>
                        <div className="text-[12px] text-[var(--text-tertiary)] mt-0.5">
                          <span className="badge badge--error text-[11px] mr-1.5">{c.type}</span>
                          <span className="font-mono">
                            conf: {fmt4(c.confidence)}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Top Memories Card */}
            <div className="card overflow-hidden">
              <div className="p-5 pb-0">
                <SectionHeader
                  title="Top Memories"
                  count={topMemories?.length ?? 0}
                >
                  <Link href="/memories" className="btn btn--ghost text-xs">
                    View All
                  </Link>
                </SectionHeader>
              </div>

              {topMemoriesLoading ? (
                <div className="p-5">
                  <CardSkeleton />
                </div>
              ) : topMemoriesError ? (
                <div className="p-5">
                  <ErrorFallback
                    error={topMemoriesError}
                    onRetry={() => mutateTopMemories()}
                  />
                </div>
              ) : !topMemories || topMemories.length === 0 ? (
                <EmptyState
                  title="No memory data"
                  description="Memories will be ranked here by attribution score."
                />
              ) : (
                <div className="divide-y divide-[var(--border-default)]">
                  {topMemories.slice(0, 6).map((m: TopMemoryResponse, idx: number) => (
                    <div
                      key={m.memory_id}
                      className="px-5 py-3 hover:bg-[var(--bg-surface-2)] transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[12px] text-[var(--text-ghost)] font-mono w-4">
                            {idx + 1}.
                          </span>
                          <EntityLink type="memory" id={m.memory_id} />
                        </div>
                        <span className={tierBadge(m.tier)}>{m.tier}</span>
                      </div>
                      <div className="flex items-center gap-4 text-[12px] text-[var(--text-tertiary)] ml-6">
                        <span>
                          attr:{" "}
                          <span className="font-mono text-[var(--text-secondary)]">
                            {fmt4(m.total_attribution)}
                          </span>
                        </span>
                        <span>
                          mean:{" "}
                          <span className="font-mono text-[var(--text-secondary)]">
                            {fmt4(m.mean_attribution)}
                          </span>
                        </span>
                        <span>
                          retrievals:{" "}
                          <span className="font-mono text-[var(--text-secondary)]">
                            {m.retrieval_count}
                          </span>
                        </span>
                        <EntityLink type="agent" id={m.agent_id} truncate={6} className="text-[12px]" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </PageTransition>
  );
}

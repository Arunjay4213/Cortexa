"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useSWRConfig } from "swr";
import {
  useAgents,
  useAgent,
  useCostSummary,
  useLifecycleRecommendations,
} from "@/lib/hooks";
import { upsertCostConfig } from "@/lib/api/agents";
import { executeRecommendations } from "@/lib/api/lifecycle";
import type {
  AgentSummary,
  AgentDetail,
  LifecycleRecommendations,
  ArchiveRecommendation,
  ConsolidationRecommendation,
  TierRecommendation,
  CostSummaryResponse,
} from "@/lib/api/types";
import { motion, AnimatePresence } from "framer-motion";
import {
  LoadingSkeleton,
  CardSkeleton,
  TableSkeleton,
} from "@/components/primitives/LoadingSkeleton";
import { ErrorFallback } from "@/components/primitives/ErrorFallback";
import { PageTransition } from "@/components/primitives/PageTransition";
import { EntityLink } from "@/components/primitives/EntityLink";

/* ── Helpers ─────────────────────────────────────────────────────────── */

function formatRelative(iso: string | null): string {
  if (!iso) return "--";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function tierBadgeClass(tier: string): string {
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

/* ── Page Shell (Suspense boundary for useSearchParams) ──────────────── */

export default function FleetPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center text-[var(--text-ghost)] font-mono text-xs">
          Loading fleet...
        </div>
      }
    >
      <FleetPageInner />
    </Suspense>
  );
}

/* ── Main Page ────────────────────────────────────────────────────────── */

function FleetPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialAgent = searchParams.get("selected");

  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(
    initialAgent,
  );
  const [costPerMemoryPerDay, setCostPerMemoryPerDay] = useState("0.00");
  const [budgetLimit, setBudgetLimit] = useState("0.00");
  const [isSaving, setIsSaving] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  const { mutate } = useSWRConfig();

  /* ── Data Hooks ──────────────────────────────────────────────────── */

  const {
    data: agents,
    error: agentsError,
    isLoading: agentsLoading,
  } = useAgents();

  const {
    data: agentDetail,
    error: agentDetailError,
    isLoading: agentDetailLoading,
  } = useAgent(selectedAgentId);

  const {
    data: costSummary,
    error: costError,
    isLoading: costLoading,
  } = useCostSummary();

  const {
    data: lifecycleRecs,
    isLoading: lifecycleLoading,
    mutate: mutateLifecycle,
  } = useLifecycleRecommendations(selectedAgentId);

  /* ── Sync URL param ─────────────────────────────────────────────── */

  function selectAgent(agentId: string) {
    setSelectedAgentId(agentId);
    const url = new URL(window.location.href);
    url.searchParams.set("selected", agentId);
    router.replace(url.pathname + url.search, { scroll: false });
  }

  function clearSelection() {
    setSelectedAgentId(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("selected");
    router.replace(url.pathname + url.search, { scroll: false });
  }

  /* ── Populate cost form when agent detail loads ─────────────────── */

  useEffect(() => {
    if (agentDetail?.cost_config) {
      setCostPerMemoryPerDay(
        String(agentDetail.cost_config.input_token_cost ?? "0.00"),
      );
      setBudgetLimit(
        String(agentDetail.cost_config.output_token_cost ?? "0.00"),
      );
    } else {
      setCostPerMemoryPerDay("0.00");
      setBudgetLimit("0.00");
    }
  }, [agentDetail]);

  /* ── Cost Config Save ───────────────────────────────────────────── */

  async function handleSaveCostConfig() {
    if (!selectedAgentId) return;
    setIsSaving(true);
    try {
      await upsertCostConfig(selectedAgentId, {
        agent_id: selectedAgentId,
        input_token_cost: parseFloat(costPerMemoryPerDay) || 0,
        output_token_cost: parseFloat(budgetLimit) || 0,
        provider: agentDetail?.cost_config?.provider ?? null,
        model_id: agentDetail?.cost_config?.model_id ?? null,
      });
      mutate(`/agents/${selectedAgentId}`);
      mutate("/dashboard/cost-summary");
    } catch (err) {
      console.error("Failed to save cost config:", err);
    } finally {
      setIsSaving(false);
    }
  }

  /* ── Execute Lifecycle Recommendations ──────────────────────────── */

  async function handleExecuteRecommendations() {
    if (!selectedAgentId || !lifecycleRecs) return;
    setIsExecuting(true);
    try {
      await executeRecommendations(selectedAgentId, {
        archive_memory_ids: lifecycleRecs.archive.map((r) => r.memory_id),
        tier_changes: Object.fromEntries(
          lifecycleRecs.tier_changes.map((r) => [
            r.memory_id,
            r.recommended_tier,
          ]),
        ),
        consolidate_groups: lifecycleRecs.consolidate.map((c) => [
          c.canonical_memory_id,
          ...c.duplicate_memory_ids,
        ]),
      });
      mutate(`/agents/${selectedAgentId}`);
      mutateLifecycle();
    } catch (err) {
      console.error("Failed to execute recommendations:", err);
    } finally {
      setIsExecuting(false);
    }
  }

  /* ── Derived data ───────────────────────────────────────────────── */

  const recentTxns = agentDetail?.recent_transactions?.slice(0, 8) ?? [];

  const totalRecommendations =
    (lifecycleRecs?.archive.length ?? 0) +
    (lifecycleRecs?.consolidate.length ?? 0) +
    (lifecycleRecs?.tier_changes.length ?? 0);

  /* ── Render ─────────────────────────────────────────────────────── */

  return (
    <PageTransition>
      <div className="min-h-screen bg-[var(--bg-base)]">
        {/* ================================================================
            PAGE HEADER
            ================================================================ */}
        <header className="border-b border-[var(--border-default)] px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-[var(--text-primary)] tracking-tight">
                Fleet
              </h1>
              <p className="text-sm text-[var(--text-tertiary)] mt-1">
                Agent fleet management and optimization
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
                <span
                  className="inline-block w-2 h-2 rounded-full bg-[var(--status-success)]"
                  aria-hidden
                />
                <span className="font-mono">
                  {agents?.length ?? 0}
                </span>{" "}
                agents tracked
              </div>
            </div>
          </div>
        </header>

        {/* ================================================================
            AGENT GRID
            ================================================================ */}
        <section className="px-8 py-8">
          <div className="mb-5">
            <h2 className="text-sm font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Agent Registry
            </h2>
          </div>

          {agentsLoading && (
            <div className="grid-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          )}

          {agentsError && (
            <ErrorFallback
              error={agentsError}
              onRetry={() => mutate("/agents")}
            />
          )}

          {agents && agents.length === 0 && (
            <div className="card text-center py-12">
              <p className="text-sm text-[var(--text-ghost)]">
                No agents found. Create transactions to register agents.
              </p>
            </div>
          )}

          {agents && agents.length > 0 && (
            <div className="grid-3 stagger-children">
              {agents.map((agent) => {
                const isSelected = selectedAgentId === agent.agent_id;
                const dist = agent.tier_distribution ?? {};
                const hot = dist.hot ?? 0;
                const warm = dist.warm ?? 0;
                const cold = dist.cold ?? 0;

                return (
                  <button
                    key={agent.agent_id}
                    onClick={() => selectAgent(agent.agent_id)}
                    className={`card card-interactive text-left transition-all ${
                      isSelected
                        ? "border-[var(--accent)] shadow-[0_0_0_1px_var(--accent)]"
                        : ""
                    }`}
                  >
                    {/* Agent ID */}
                    <div className="flex items-center justify-between mb-4">
                      <span className="font-mono text-[var(--accent)] font-semibold text-sm truncate max-w-[200px]">
                        {agent.agent_id}
                      </span>
                      <span className="text-xs text-[var(--text-ghost)] font-mono">
                        {formatRelative(agent.last_active)}
                      </span>
                    </div>

                    {/* Key Stats Row */}
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div>
                        <div className="caption mb-1">Memories</div>
                        <div className="text-lg font-bold text-[var(--text-primary)] font-mono tabular-nums">
                          {agent.total_memories.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <div className="caption mb-1">Transactions</div>
                        <div className="text-lg font-bold text-[var(--text-primary)] font-mono tabular-nums">
                          {agent.total_transactions.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <div className="caption mb-1">Avg EAS</div>
                        <div className="text-lg font-bold text-[var(--text-primary)] font-mono tabular-nums">
                          {agent.avg_attribution.toFixed(3)}
                        </div>
                      </div>
                    </div>

                    {/* Tier Distribution Bar */}
                    <div className="mb-3">
                      <div className="caption mb-1.5">Tier Distribution</div>
                      {hot + warm + cold > 0 ? (
                        <>
                          <div className="flex h-2 rounded-full overflow-hidden bg-[var(--bg-surface-3)]">
                            {hot > 0 && (
                              <div
                                className="bg-[var(--status-error)] transition-all"
                                style={{
                                  width: `${(hot / (hot + warm + cold)) * 100}%`,
                                }}
                              />
                            )}
                            {warm > 0 && (
                              <div
                                className="bg-[var(--status-warning)] transition-all"
                                style={{
                                  width: `${(warm / (hot + warm + cold)) * 100}%`,
                                }}
                              />
                            )}
                            {cold > 0 && (
                              <div
                                className="bg-[var(--accent)] transition-all"
                                style={{
                                  width: `${(cold / (hot + warm + cold)) * 100}%`,
                                }}
                              />
                            )}
                          </div>
                          <div className="flex items-center gap-3 mt-2">
                            <span className={tierBadgeClass("hot")}>
                              hot {hot}
                            </span>
                            <span className={tierBadgeClass("warm")}>
                              warm {warm}
                            </span>
                            <span className={tierBadgeClass("cold")}>
                              cold {cold}
                            </span>
                          </div>
                        </>
                      ) : (
                        <div className="text-xs text-[var(--text-ghost)] italic">
                          No tier data
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        {/* ================================================================
            SELECTED AGENT DETAIL PANEL
            ================================================================ */}
        <AnimatePresence>
          {selectedAgentId && (
            <motion.section
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="border-t border-[var(--border-default)] px-8 py-8"
            >
              {/* Detail Header */}
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h2 className="text-sm font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Agent Detail
                  </h2>
                  <div className="text-lg font-bold text-[var(--accent)] font-mono mt-1">
                    {selectedAgentId}
                  </div>
                </div>
                <button
                  onClick={clearSelection}
                  className="btn btn--ghost text-xs"
                >
                  Close
                </button>
              </div>

              {agentDetailLoading && (
                <div className="space-y-6">
                  <div className="grid-4">
                    {Array.from({ length: 8 }).map((_, i) => (
                      <CardSkeleton key={i} />
                    ))}
                  </div>
                  <LoadingSkeleton rows={4} />
                </div>
              )}

              {agentDetailError && (
                <ErrorFallback
                  error={agentDetailError}
                  onRetry={() => mutate(`/agents/${selectedAgentId}`)}
                />
              )}

              {agentDetail && (
                <div className="space-y-10">
                  {/* ── Metric Cards ──────────────────────────────── */}
                  <div className="grid-4">
                    {[
                      {
                        label: "Memories",
                        value: agentDetail.total_memories.toLocaleString(),
                      },
                      {
                        label: "Transactions",
                        value:
                          agentDetail.total_transactions.toLocaleString(),
                      },
                      {
                        label: "Avg Attribution",
                        value: agentDetail.avg_attribution.toFixed(4),
                      },
                      {
                        label: "Gini Coefficient",
                        value: agentDetail.gini_coefficient.toFixed(4),
                      },
                      {
                        label: "SNR (dB)",
                        value: agentDetail.snr_db.toFixed(1),
                      },
                      {
                        label: "Waste Rate",
                        value: `${(agentDetail.waste_rate * 100).toFixed(1)}%`,
                      },
                      {
                        label: "Contradictions",
                        value: String(agentDetail.contradiction_count),
                      },
                      {
                        label: "Last Active",
                        value: formatRelative(agentDetail.last_active),
                      },
                    ].map((stat) => (
                      <div key={stat.label} className="metric-card">
                        <div className="metric-card__label">{stat.label}</div>
                        <div className="metric-card__value text-xl font-mono">
                          {stat.value}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* ── Tier Distribution Bar ────────────────────── */}
                  <div className="card">
                    <h3 className="text-sm font-medium text-[var(--text-tertiary)] uppercase tracking-wider mb-4">
                      Memory Tier Distribution
                    </h3>
                    {(() => {
                      const dist = agentDetail.tier_distribution ?? {};
                      const hot = dist.hot ?? 0;
                      const warm = dist.warm ?? 0;
                      const cold = dist.cold ?? 0;
                      const total = hot + warm + cold;

                      if (total === 0) {
                        return (
                          <p className="text-sm text-[var(--text-ghost)] italic">
                            No tier data available
                          </p>
                        );
                      }

                      return (
                        <div>
                          <div className="flex h-4 rounded-full overflow-hidden bg-[var(--bg-surface-3)] mb-4">
                            {hot > 0 && (
                              <div
                                className="bg-[var(--status-error)] flex items-center justify-center text-[12px] text-white font-bold transition-all"
                                style={{
                                  width: `${(hot / total) * 100}%`,
                                }}
                              >
                                {hot > total * 0.08 && hot}
                              </div>
                            )}
                            {warm > 0 && (
                              <div
                                className="bg-[var(--status-warning)] flex items-center justify-center text-[12px] text-black font-bold transition-all"
                                style={{
                                  width: `${(warm / total) * 100}%`,
                                }}
                              >
                                {warm > total * 0.08 && warm}
                              </div>
                            )}
                            {cold > 0 && (
                              <div
                                className="bg-[var(--accent)] flex items-center justify-center text-[12px] text-white font-bold transition-all"
                                style={{
                                  width: `${(cold / total) * 100}%`,
                                }}
                              >
                                {cold > total * 0.08 && cold}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-4">
                            <span className={tierBadgeClass("hot")}>
                              Hot: {hot} (
                              {((hot / total) * 100).toFixed(0)}%)
                            </span>
                            <span className={tierBadgeClass("warm")}>
                              Warm: {warm} (
                              {((warm / total) * 100).toFixed(0)}%)
                            </span>
                            <span className={tierBadgeClass("cold")}>
                              Cold: {cold} (
                              {((cold / total) * 100).toFixed(0)}%)
                            </span>
                            <span className="ml-auto text-xs text-[var(--text-ghost)] font-mono">
                              {total.toLocaleString()} total
                            </span>
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  {/* ── Cost Configuration ────────────────────────── */}
                  <div className="card">
                    <h3 className="text-sm font-medium text-[var(--text-tertiary)] uppercase tracking-wider mb-4">
                      Cost Configuration
                    </h3>
                    <div className="grid grid-cols-2 gap-6 max-w-lg">
                      <div>
                        <label className="caption block mb-2">
                          cost_per_memory_per_day
                        </label>
                        <input
                          type="text"
                          value={costPerMemoryPerDay}
                          onChange={(e) =>
                            setCostPerMemoryPerDay(e.target.value)
                          }
                          className="input input--sm font-mono"
                          placeholder="0.00"
                        />
                      </div>
                      <div>
                        <label className="caption block mb-2">
                          budget_limit
                        </label>
                        <input
                          type="text"
                          value={budgetLimit}
                          onChange={(e) => setBudgetLimit(e.target.value)}
                          className="input input--sm font-mono"
                          placeholder="0.00"
                        />
                      </div>
                    </div>
                    <div className="mt-5">
                      <button
                        onClick={handleSaveCostConfig}
                        disabled={isSaving}
                        className="btn btn--primary text-xs"
                      >
                        {isSaving ? "Saving..." : "Save Configuration"}
                      </button>
                    </div>
                  </div>

                  {/* ── Recent Transactions ───────────────────────── */}
                  <div className="card">
                    <h3 className="text-sm font-medium text-[var(--text-tertiary)] uppercase tracking-wider mb-4">
                      Recent Transactions
                    </h3>
                    {recentTxns.length === 0 ? (
                      <p className="text-sm text-[var(--text-ghost)] italic">
                        No recent transactions
                      </p>
                    ) : (
                      <table className="table table-compact">
                        <thead>
                          <tr>
                            <th>Query</th>
                            <th>Status</th>
                            <th>Memories</th>
                            <th>Created</th>
                          </tr>
                        </thead>
                        <tbody>
                          {recentTxns.map((txn) => (
                            <tr key={txn.id}>
                              <td className="max-w-[320px] truncate">
                                <EntityLink
                                  type="transaction"
                                  id={txn.id}
                                  truncate={8}
                                  className="mr-2 text-xs"
                                />
                                <span className="text-[var(--text-tertiary)] text-xs">
                                  {txn.query_text.length > 60
                                    ? txn.query_text.slice(0, 60) + "..."
                                    : txn.query_text}
                                </span>
                              </td>
                              <td>
                                <span
                                  className={`badge ${
                                    txn.status === "completed"
                                      ? "badge--success"
                                      : "badge--warning"
                                  }`}
                                >
                                  {txn.status}
                                </span>
                              </td>
                              <td className="font-mono tabular-nums">
                                {txn.retrieved_memory_ids.length}
                              </td>
                              <td className="font-mono text-[var(--text-ghost)]">
                                {formatRelative(txn.created_at)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>

                  {/* ── Lifecycle Recommendations ─────────────────── */}
                  <div className="card">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                        Lifecycle Recommendations
                      </h3>
                      {lifecycleRecs && totalRecommendations > 0 && (
                        <button
                          onClick={handleExecuteRecommendations}
                          disabled={isExecuting}
                          className="btn btn--primary text-xs"
                        >
                          {isExecuting
                            ? "Executing..."
                            : `Execute All (${totalRecommendations})`}
                        </button>
                      )}
                    </div>

                    {lifecycleLoading && <LoadingSkeleton rows={4} />}

                    {!lifecycleLoading &&
                      !lifecycleRecs && (
                        <p className="text-sm text-[var(--text-ghost)] italic">
                          No recommendations available
                        </p>
                      )}

                    {lifecycleRecs && (
                      <div className="space-y-6">
                        {/* Estimated Savings */}
                        <div className="flex items-center gap-3 text-sm">
                          <span className="text-[var(--text-tertiary)]">
                            Estimated monthly savings:
                          </span>
                          <span className="font-mono font-bold text-[var(--status-success)]">
                            $
                            {lifecycleRecs.estimated_monthly_savings.toFixed(
                              4,
                            )}
                          </span>
                        </div>

                        {/* Archive Recommendations */}
                        {lifecycleRecs.archive.length > 0 && (
                          <div>
                            <h4 className="caption mb-3">
                              Archive ({lifecycleRecs.archive.length})
                            </h4>
                            <div className="space-y-2">
                              {lifecycleRecs.archive.map((rec) => (
                                <div
                                  key={rec.memory_id}
                                  className="flex items-center gap-4 p-3 bg-[var(--bg-surface-2)] rounded-lg border border-[var(--border-default)]"
                                >
                                  <EntityLink
                                    type="memory"
                                    id={rec.memory_id}
                                    truncate={12}
                                    className="text-xs"
                                  />
                                  <span className="text-xs text-[var(--status-success)] font-mono">
                                    Rev: ${rec.revenue.toFixed(4)}
                                  </span>
                                  <span className="text-xs text-[var(--status-error)] font-mono">
                                    Cost: ${rec.cost.toFixed(4)}
                                  </span>
                                  <span
                                    className={`text-xs font-bold font-mono ${
                                      rec.pnl < 0
                                        ? "text-[var(--status-error)]"
                                        : "text-[var(--status-success)]"
                                    }`}
                                  >
                                    P&L: ${rec.pnl.toFixed(4)}
                                  </span>
                                  <span className="ml-auto text-xs text-[var(--text-ghost)]">
                                    {rec.reason}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Consolidation Recommendations */}
                        {lifecycleRecs.consolidate.length > 0 && (
                          <div>
                            <h4 className="caption mb-3">
                              Consolidate (
                              {lifecycleRecs.consolidate.length})
                            </h4>
                            <div className="space-y-2">
                              {lifecycleRecs.consolidate.map((rec) => (
                                <div
                                  key={rec.canonical_memory_id}
                                  className="p-3 bg-[var(--bg-surface-2)] rounded-lg border border-[var(--border-default)]"
                                >
                                  <div className="flex items-center gap-2 text-xs mb-1">
                                    <span className="text-[var(--text-tertiary)]">
                                      Keep:
                                    </span>
                                    <EntityLink
                                      type="memory"
                                      id={rec.canonical_memory_id}
                                      truncate={12}
                                    />
                                  </div>
                                  <div className="text-xs text-[var(--text-ghost)]">
                                    Remove{" "}
                                    {rec.duplicate_memory_ids.length}{" "}
                                    duplicate
                                    {rec.duplicate_memory_ids.length > 1
                                      ? "s"
                                      : ""}
                                    :{" "}
                                    <span className="font-mono">
                                      {rec.duplicate_memory_ids
                                        .map((id) => id.slice(0, 8))
                                        .join(", ")}
                                    </span>
                                  </div>
                                  <div className="text-xs text-[var(--text-ghost)] mt-1">
                                    Method:{" "}
                                    <span className="badge badge--neutral">
                                      {rec.method}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Tier Change Recommendations */}
                        {lifecycleRecs.tier_changes.length > 0 && (
                          <div>
                            <h4 className="caption mb-3">
                              Tier Changes (
                              {lifecycleRecs.tier_changes.length})
                            </h4>
                            <div className="space-y-2">
                              {lifecycleRecs.tier_changes.map((rec) => (
                                <div
                                  key={rec.memory_id}
                                  className="flex items-center gap-4 p-3 bg-[var(--bg-surface-2)] rounded-lg border border-[var(--border-default)]"
                                >
                                  <EntityLink
                                    type="memory"
                                    id={rec.memory_id}
                                    truncate={12}
                                    className="text-xs"
                                  />
                                  <span
                                    className={tierBadgeClass(
                                      rec.current_tier,
                                    )}
                                  >
                                    {rec.current_tier}
                                  </span>
                                  <span className="text-xs text-[var(--text-ghost)]">
                                    &rarr;
                                  </span>
                                  <span
                                    className={tierBadgeClass(
                                      rec.recommended_tier,
                                    )}
                                  >
                                    {rec.recommended_tier}
                                  </span>
                                  <span className="ml-auto text-xs text-[var(--text-ghost)]">
                                    {rec.reason}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Empty state */}
                        {totalRecommendations === 0 && (
                          <p className="text-sm text-[var(--text-ghost)] italic">
                            No optimization actions recommended at this
                            time.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </motion.section>
          )}
        </AnimatePresence>

        {/* ================================================================
            COST COMPARISON TABLE
            ================================================================ */}
        <section className="border-t border-[var(--border-default)] px-8 py-8">
          <div className="mb-5">
            <h2 className="text-sm font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
              Cost Comparison
            </h2>
          </div>

          {costLoading && <TableSkeleton rows={4} cols={6} />}

          {costError && (
            <ErrorFallback
              error={costError}
              onRetry={() => mutate("/dashboard/cost-summary")}
            />
          )}

          {costSummary && costSummary.length === 0 && (
            <div className="card text-center py-8">
              <p className="text-sm text-[var(--text-ghost)] italic">
                No cost data available. Configure cost settings for agents.
              </p>
            </div>
          )}

          {costSummary && costSummary.length > 0 && (
            <div className="card overflow-hidden p-0">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Agent</th>
                      <th>Total Cost</th>
                      <th>Input Cost</th>
                      <th>Output Cost</th>
                      <th>Transactions</th>
                      <th>Avg Cost / Txn</th>
                    </tr>
                  </thead>
                  <tbody>
                    {costSummary.map((row, idx) => (
                      <tr
                        key={row.agent_id ?? `aggregate-${idx}`}
                        className={
                          !row.agent_id
                            ? "bg-[var(--bg-surface-2)] font-semibold"
                            : ""
                        }
                      >
                        <td>
                          {row.agent_id ? (
                            <EntityLink
                              type="agent"
                              id={row.agent_id}
                              truncate={16}
                            />
                          ) : (
                            <span className="text-[var(--text-primary)] font-semibold">
                              ALL
                            </span>
                          )}
                        </td>
                        <td className="font-mono tabular-nums">
                          ${row.total_cost.toFixed(4)}
                        </td>
                        <td className="font-mono tabular-nums text-[var(--text-tertiary)]">
                          ${row.input_cost.toFixed(4)}
                        </td>
                        <td className="font-mono tabular-nums text-[var(--text-tertiary)]">
                          ${row.output_cost.toFixed(4)}
                        </td>
                        <td className="font-mono tabular-nums">
                          {row.transaction_count.toLocaleString()}
                        </td>
                        <td className="font-mono tabular-nums text-[var(--status-warning)]">
                          ${row.avg_cost_per_transaction.toFixed(6)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </div>
    </PageTransition>
  );
}

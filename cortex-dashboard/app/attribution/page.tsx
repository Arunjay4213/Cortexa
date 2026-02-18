"use client";

import { Suspense, useState, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  useTransactions,
  useAttributionByTransaction,
  useTopMemories,
} from "@/lib/hooks";
import { triggerExactAttribution } from "@/lib/api/attribution";
import {
  LoadingSkeleton,
  CardSkeleton,
  TableSkeleton,
} from "@/components/primitives/LoadingSkeleton";
import { ErrorFallback } from "@/components/primitives/ErrorFallback";
import { PageTransition } from "@/components/primitives/PageTransition";
import { PageHeader } from "@/components/primitives/PageHeader";
import { SectionHeader } from "@/components/primitives/SectionHeader";
import { EmptyState } from "@/components/primitives/EmptyState";
import { EntityLink } from "@/components/primitives/EntityLink";
import { MetricCard } from "@/components/primitives/MetricCard";
import { Search, Zap } from "lucide-react";
import type {
  ExactAttributionResult,
  AttributionScore,
  Transaction,
  TopMemoryResponse,
} from "@/lib/api/types";

export default function AttributionPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 space-y-6">
          <div className="h-8 bg-[var(--bg-surface-2)] rounded-md shimmer w-48" />
          <div className="flex gap-6">
            <CardSkeleton className="w-[400px]" />
            <CardSkeleton className="flex-1" />
          </div>
        </div>
      }
    >
      <AttributionPageInner />
    </Suspense>
  );
}

function AttributionPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const selectedTxnId = searchParams.get("selected");

  const [searchQuery, setSearchQuery] = useState("");
  const [exactLoading, setExactLoading] = useState(false);
  const [exactResult, setExactResult] = useState<ExactAttributionResult | null>(
    null
  );
  const [exactError, setExactError] = useState<string | null>(null);

  const {
    data: txnData,
    error: txnError,
    isLoading: txnLoading,
    mutate: mutateTxns,
  } = useTransactions({ limit: 50 });

  const {
    data: scores,
    error: scoresError,
    isLoading: scoresLoading,
    mutate: mutateScores,
  } = useAttributionByTransaction(selectedTxnId);

  const {
    data: topMemories,
    error: topMemError,
    isLoading: topMemLoading,
  } = useTopMemories({ n: 10 });

  const transactions = txnData?.items ?? [];

  const filteredTransactions = useMemo(() => {
    if (!searchQuery.trim()) return transactions;
    const q = searchQuery.toLowerCase();
    return transactions.filter(
      (txn) =>
        txn.id.toLowerCase().includes(q) ||
        txn.query_text.toLowerCase().includes(q) ||
        txn.agent_id.toLowerCase().includes(q)
    );
  }, [transactions, searchQuery]);

  const selectedTransaction = useMemo(
    () => transactions.find((t) => t.id === selectedTxnId) ?? null,
    [transactions, selectedTxnId]
  );

  function selectTransaction(id: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("selected", id);
    router.push(`/attribution?${params.toString()}`);
    setExactResult(null);
    setExactError(null);
  }

  async function handleRunExact() {
    if (!selectedTxnId) return;
    setExactLoading(true);
    setExactError(null);
    setExactResult(null);
    try {
      const result = await triggerExactAttribution(selectedTxnId);
      setExactResult(result);
      mutateScores();
    } catch (err: unknown) {
      setExactError(
        err instanceof Error ? err.message : "Exact attribution failed"
      );
    } finally {
      setExactLoading(false);
    }
  }

  function formatTimestamp(iso: string): string {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  return (
    <PageTransition>
      <div className="p-8 space-y-6">
        <PageHeader
          title="Attribution"
          subtitle="EAS attribution scores for every transaction"
        />

        {/* Two-column layout */}
        <div className="flex gap-6" style={{ minHeight: "calc(100vh - 240px)" }}>
          {/* Left panel: Transaction list */}
          <div className="w-[400px] shrink-0 card flex flex-col overflow-hidden p-0">
            {/* Search input */}
            <div className="p-3 border-b border-[var(--bg-surface-2)]">
              <div className="relative">
                <Search
                  size={14}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-ghost)]"
                />
                <input
                  type="text"
                  placeholder="Search transactions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input w-full pl-8 text-sm"
                />
              </div>
            </div>

            {/* Transaction list */}
            <div className="flex-1 overflow-y-auto">
              {txnLoading && (
                <div className="p-4">
                  <LoadingSkeleton rows={8} />
                </div>
              )}

              {txnError && (
                <div className="p-4">
                  <ErrorFallback
                    error={txnError}
                    onRetry={() => mutateTxns()}
                  />
                </div>
              )}

              {!txnLoading && !txnError && filteredTransactions.length === 0 && (
                <div className="p-6">
                  <EmptyState
                    title="No transactions found"
                    description={
                      searchQuery
                        ? "Try a different search query"
                        : "Transactions will appear here once created"
                    }
                  />
                </div>
              )}

              <div className="divide-y divide-[var(--border-default)]">
                {filteredTransactions.map((txn) => (
                  <TransactionCard
                    key={txn.id}
                    transaction={txn}
                    isActive={selectedTxnId === txn.id}
                    onClick={() => selectTransaction(txn.id)}
                    formatTimestamp={formatTimestamp}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Right panel: Detail view */}
          <div className="flex-1 min-w-0 flex flex-col gap-6">
            {!selectedTxnId && (
              <div className="card flex-1 flex items-center justify-center">
                <EmptyState
                  title="Select a transaction to view attribution scores"
                  description="Click a transaction in the left panel to inspect its EAS attribution breakdown"
                />
              </div>
            )}

            {selectedTxnId && (
              <>
                {/* Attribution Scores table */}
                <div className="card">
                  <SectionHeader
                    title="Attribution Scores"
                    count={scores?.length}
                  >
                    <button
                      onClick={handleRunExact}
                      disabled={exactLoading}
                      className="btn btn--primary text-xs"
                    >
                      <Zap size={13} />
                      {exactLoading ? "Running..." : "Run Exact Attribution"}
                    </button>
                  </SectionHeader>

                  {scoresLoading && <TableSkeleton rows={5} cols={3} />}

                  {scoresError && (
                    <ErrorFallback
                      error={scoresError}
                      onRetry={() => mutateScores()}
                    />
                  )}

                  {!scoresLoading && !scoresError && scores && scores.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="table w-full">
                        <thead>
                          <tr>
                            <th className="text-left text-xs text-[var(--text-tertiary)]">
                              Source ID
                            </th>
                            <th className="text-right text-xs text-[var(--text-tertiary)]">
                              EAS Score
                            </th>
                            <th className="text-right text-xs text-[var(--text-tertiary)]">
                              Rank
                            </th>
                            <th className="text-left text-xs text-[var(--text-tertiary)]">
                              Method
                            </th>
                            <th className="text-right text-xs text-[var(--text-tertiary)]">
                              Confidence
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {scores
                            .sort((a, b) => b.score - a.score)
                            .map((s, idx) => (
                              <tr key={s.id}>
                                <td>
                                  <EntityLink
                                    type="memory"
                                    id={s.memory_id}
                                    truncate={12}
                                  />
                                </td>
                                <td className="text-right">
                                  <span className="font-mono text-[var(--text-primary)]">
                                    {s.score.toFixed(4)}
                                  </span>
                                </td>
                                <td className="text-right">
                                  <span className="font-mono text-[var(--text-secondary)]">
                                    #{idx + 1}
                                  </span>
                                </td>
                                <td>
                                  <span
                                    className={`badge ${
                                      s.method === "eas"
                                        ? "badge--info"
                                        : s.method === "exact"
                                          ? "badge--warning"
                                          : s.method === "contextcite"
                                            ? "badge--neutral"
                                            : "badge--success"
                                    }`}
                                  >
                                    {s.method}
                                  </span>
                                </td>
                                <td className="text-right">
                                  <span className="font-mono text-[var(--text-tertiary)]">
                                    {s.confidence.toFixed(4)}
                                  </span>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {!scoresLoading &&
                    !scoresError &&
                    scores &&
                    scores.length === 0 && (
                      <EmptyState
                        title="No attribution scores"
                        description="Run exact attribution to generate scores for this transaction"
                      />
                    )}
                </div>

                {/* Exact Attribution result (if available) */}
                {exactError && (
                  <ErrorFallback error={exactError} onRetry={handleRunExact} />
                )}

                {exactResult && (
                  <div className="card">
                    <SectionHeader title="Exact Attribution Result" />
                    <div className="grid grid-cols-4 gap-4 mb-6">
                      <MetricCard
                        label="LDS Score"
                        value={exactResult.lds.toFixed(4)}
                      />
                      <MetricCard
                        label="Cost"
                        value={`$${exactResult.cost_usd.toFixed(4)}`}
                      />
                      <MetricCard
                        label="Compute"
                        value={`${exactResult.compute_ms.toFixed(1)}ms`}
                      />
                      <MetricCard
                        label="Samples"
                        value={exactResult.num_samples}
                      />
                    </div>

                    {/* LDS interpretation */}
                    <div className="p-3 rounded-lg bg-[var(--bg-surface-2)] text-sm text-[var(--text-secondary)]">
                      {exactResult.lds > 0.85 ? (
                        <span className="text-[var(--status-success)]">
                          LDS &gt; 0.85 -- EAS fast path is trustworthy for this
                          query type
                        </span>
                      ) : exactResult.lds > 0.6 ? (
                        <span className="text-[var(--status-warning)]">
                          LDS 0.6-0.85 -- EAS approximation is reasonable but
                          consider calibration
                        </span>
                      ) : (
                        <span className="text-[var(--status-error)]">
                          LDS &lt; 0.6 -- EAS diverges significantly, exact
                          attribution recommended
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Bottom section: Top Memories */}
        <div className="card">
          <SectionHeader title="Top Memories" count={topMemories?.length} />

          {topMemLoading && (
            <div className="flex gap-4 overflow-hidden">
              {Array.from({ length: 5 }).map((_, i) => (
                <CardSkeleton key={i} className="w-[240px] shrink-0" />
              ))}
            </div>
          )}

          {topMemError && <ErrorFallback error={topMemError} />}

          {!topMemLoading && !topMemError && topMemories && topMemories.length > 0 && (
            <div className="flex gap-4 overflow-x-auto pb-2 stagger-children">
              {topMemories.map((mem, idx) => (
                <TopMemoryCard
                  key={mem.memory_id}
                  memory={mem}
                  rank={idx + 1}
                />
              ))}
            </div>
          )}

          {!topMemLoading &&
            !topMemError &&
            topMemories &&
            topMemories.length === 0 && (
              <EmptyState
                title="No top memories"
                description="Top memories will appear once transactions produce attribution scores"
              />
            )}
        </div>
      </div>
    </PageTransition>
  );
}

/* ── Transaction Card ──────────────────────────────────────────────── */

function TransactionCard({
  transaction,
  isActive,
  onClick,
  formatTimestamp,
}: {
  transaction: Transaction;
  isActive: boolean;
  onClick: () => void;
  formatTimestamp: (iso: string) => string;
}) {
  const preview =
    transaction.query_text.length > 80
      ? transaction.query_text.slice(0, 80) + "..."
      : transaction.query_text;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 transition-colors border-l-2 ${
        isActive
          ? "bg-[var(--accent-muted)] border-l-[var(--accent)]"
          : "border-l-transparent hover:bg-[var(--bg-surface-2)]"
      }`}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <EntityLink type="transaction" id={transaction.id} truncate={8} />
        <span className="text-[12px] text-[var(--text-ghost)] font-mono">
          {transaction.agent_id}
        </span>
        <span
          className={`badge text-[11px] ml-auto ${
            transaction.status === "completed"
              ? "badge--success"
              : "badge--warning"
          }`}
        >
          {transaction.status}
        </span>
      </div>
      <p className="text-xs text-[var(--text-tertiary)] leading-relaxed mb-1.5 line-clamp-2">
        {preview}
      </p>
      <div className="text-[12px] text-[var(--text-ghost)] font-mono">
        {formatTimestamp(transaction.created_at)}
      </div>
    </button>
  );
}

/* ── Top Memory Card ───────────────────────────────────────────────── */

function TopMemoryCard({
  memory,
  rank,
}: {
  memory: TopMemoryResponse;
  rank: number;
}) {
  const tierBadge =
    memory.tier === "hot"
      ? "badge--error"
      : memory.tier === "warm"
        ? "badge--warning"
        : "badge--info";

  return (
    <div className="card w-[240px] shrink-0 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-mono text-[var(--text-ghost)]">
          #{rank}
        </span>
        <span className={`badge text-[11px] ${tierBadge}`}>{memory.tier}</span>
      </div>
      <div>
        <EntityLink type="memory" id={memory.memory_id} truncate={12} />
      </div>
      <p className="text-xs text-[var(--text-tertiary)] line-clamp-2 leading-relaxed">
        {memory.content.length > 80
          ? memory.content.slice(0, 80) + "..."
          : memory.content}
      </p>
      <div className="space-y-1 text-[12px]">
        <div className="flex justify-between">
          <span className="text-[var(--text-ghost)]">Total Attribution</span>
          <span className="font-mono text-[var(--text-primary)]">
            {memory.total_attribution.toFixed(4)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--text-ghost)]">Mean Attribution</span>
          <span className="font-mono text-[var(--text-secondary)]">
            {memory.mean_attribution.toFixed(4)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--text-ghost)]">Retrievals</span>
          <span className="font-mono text-[var(--text-secondary)]">
            {memory.retrieval_count}x
          </span>
        </div>
      </div>
    </div>
  );
}

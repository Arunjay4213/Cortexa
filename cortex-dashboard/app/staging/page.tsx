"use client";

import { useState } from "react";
import { useAgents } from "@/lib/hooks";
import {
  stageCounterfactual,
  commitSession,
  discardSession,
} from "@/lib/api/counterfactual";
import type {
  CounterfactualChange,
  CounterfactualChangeAction,
  CounterfactualResult,
} from "@/lib/api/types";
import { PageTransition } from "@/components/primitives/PageTransition";
import { PageHeader } from "@/components/primitives/PageHeader";
import { SectionHeader } from "@/components/primitives/SectionHeader";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState } from "@/components/primitives/EmptyState";
import { ErrorFallback } from "@/components/primitives/ErrorFallback";
import { CardSkeleton } from "@/components/primitives/LoadingSkeleton";
import { Modal } from "@/components/primitives/Modal";
import {
  Plus,
  Trash2,
  Pencil,
  Play,
  Check,
  X,
  FlaskConical,
  Loader2,
} from "lucide-react";

/* ── Helpers ────────────────────────────────────────────────────────── */

const ACTION_META: Record<
  CounterfactualChangeAction,
  { badge: string; label: string; icon: typeof Plus }
> = {
  add: { badge: "badge badge--success", label: "Add", icon: Plus },
  remove: { badge: "badge badge--error", label: "Remove", icon: Trash2 },
  edit: { badge: "badge badge--warning", label: "Edit", icon: Pencil },
};

function fmtDelta(v: number): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(4)}`;
}

function deltaClass(v: number): string {
  if (v > 0) return "text-[var(--status-success)]";
  if (v < 0) return "text-[var(--status-error)]";
  return "text-[var(--text-ghost)]";
}

/* ── Page ───────────────────────────────────────────────────────────── */

export default function StagingPage() {
  const { data: agents } = useAgents();

  const [selectedAgent, setSelectedAgent] = useState("");

  // Change builder
  const [changes, setChanges] = useState<CounterfactualChange[]>([]);
  const [currentAction, setCurrentAction] =
    useState<CounterfactualChangeAction>("add");
  const [currentMemoryId, setCurrentMemoryId] = useState("");
  const [currentContent, setCurrentContent] = useState("");

  // Session state
  const [isStaging, setIsStaging] = useState(false);
  const [sessionResult, setSessionResult] =
    useState<CounterfactualResult | null>(null);
  const [stagingError, setStagingError] = useState<string | null>(null);
  const [isCommitting, setIsCommitting] = useState(false);
  const [isDiscarding, setIsDiscarding] = useState(false);
  const [commitDone, setCommitDone] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<
    "commit" | "discard" | null
  >(null);

  /* ── Change builder handlers ─────────────────────────────────────── */

  function addChange() {
    const change: CounterfactualChange = { action: currentAction };

    if (currentAction === "add") {
      if (!currentContent.trim()) return;
      change.content = currentContent;
    } else if (currentAction === "remove") {
      if (!currentMemoryId.trim()) return;
      change.memory_id = currentMemoryId;
    } else if (currentAction === "edit") {
      if (!currentMemoryId.trim() || !currentContent.trim()) return;
      change.memory_id = currentMemoryId;
      change.content = currentContent;
    }

    setChanges((prev) => [...prev, change]);
    setCurrentMemoryId("");
    setCurrentContent("");
  }

  function removeChange(index: number) {
    setChanges((prev) => prev.filter((_, i) => i !== index));
  }

  /* ── Staging handlers ────────────────────────────────────────────── */

  async function handleStage() {
    if (!selectedAgent || changes.length === 0) return;
    setIsStaging(true);
    setStagingError(null);
    setSessionResult(null);
    setCommitDone(false);
    try {
      const result = await stageCounterfactual({
        agent_id: selectedAgent,
        changes,
      });
      setSessionResult(result);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Staging failed";
      setStagingError(message);
    } finally {
      setIsStaging(false);
    }
  }

  async function handleCommit() {
    if (!sessionResult) return;
    setIsCommitting(true);
    try {
      await commitSession(sessionResult.session_id);
      setCommitDone(true);
      setSessionResult(null);
      setChanges([]);
    } catch {
      /* handled silently */
    } finally {
      setIsCommitting(false);
      setConfirmDialog(null);
    }
  }

  async function handleDiscard() {
    if (!sessionResult) return;
    setIsDiscarding(true);
    try {
      await discardSession(sessionResult.session_id);
      setSessionResult(null);
    } catch {
      /* handled silently */
    } finally {
      setIsDiscarding(false);
      setConfirmDialog(null);
    }
  }

  /* ── Derived ─────────────────────────────────────────────────────── */

  const impact = sessionResult?.impact;
  const summary = impact?.summary;
  const deltas = impact?.attribution_deltas ?? [];

  /* ── Render ──────────────────────────────────────────────────────── */

  return (
    <PageTransition>
      <div className="page-container">
        {/* ── Header ──────────────────────────────────────────────── */}
        <PageHeader
          title="Staging"
          subtitle="Counterfactual analysis — test memory changes before committing"
        >
          <select
            value={selectedAgent}
            onChange={(e) => {
              setSelectedAgent(e.target.value);
              setSessionResult(null);
              setStagingError(null);
              setCommitDone(false);
            }}
            className="input input--sm w-52"
          >
            <option value="">Select agent...</option>
            {(agents ?? []).map((a: { agent_id: string }) => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.agent_id}
              </option>
            ))}
          </select>

          <button
            onClick={handleStage}
            disabled={!selectedAgent || changes.length === 0 || isStaging}
            className="btn btn--primary"
          >
            {isStaging ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Play size={14} />
            )}
            {isStaging ? "Staging..." : "Stage & Analyze"}
          </button>
        </PageHeader>

        {/* ── Success banner ──────────────────────────────────────── */}
        {commitDone && (
          <div className="card flex items-center justify-between mb-6 border-[rgba(52,211,153,0.2)]">
            <span className="text-[var(--status-success)] text-sm font-medium">
              Changes committed successfully.
            </span>
            <button
              onClick={() => setCommitDone(false)}
              className="btn btn--ghost p-1"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* ── Staging error ───────────────────────────────────────── */}
        {stagingError && (
          <div className="mb-6">
            <ErrorFallback error={stagingError} onRetry={handleStage} />
          </div>
        )}

        {/* ── Change Builder ──────────────────────────────────────── */}
        <section className="mb-8">
          <SectionHeader title="Change Builder" count={changes.length} />

          <div className="card">
            {/* Input row */}
            <div className="flex flex-wrap items-end gap-3 mb-5">
              <div>
                <label className="caption block mb-1.5">Action</label>
                <select
                  value={currentAction}
                  onChange={(e) =>
                    setCurrentAction(
                      e.target.value as CounterfactualChangeAction
                    )
                  }
                  className="input input--sm w-32"
                >
                  <option value="add">Add Memory</option>
                  <option value="remove">Remove Memory</option>
                  <option value="edit">Edit Memory</option>
                </select>
              </div>

              {(currentAction === "remove" || currentAction === "edit") && (
                <div className="flex-1 min-w-[200px]">
                  <label className="caption block mb-1.5">Memory ID</label>
                  <input
                    type="text"
                    value={currentMemoryId}
                    onChange={(e) => setCurrentMemoryId(e.target.value)}
                    placeholder="mem_abc123..."
                    className="input input--sm font-mono"
                  />
                </div>
              )}

              {(currentAction === "add" || currentAction === "edit") && (
                <div className="flex-[2] min-w-[300px]">
                  <label className="caption block mb-1.5">Content</label>
                  <textarea
                    value={currentContent}
                    onChange={(e) => setCurrentContent(e.target.value)}
                    placeholder="Memory content..."
                    rows={1}
                    className="input input--sm resize-none"
                  />
                </div>
              )}

              <button onClick={addChange} className="btn btn--secondary">
                <Plus size={14} />
                Add Change
              </button>
            </div>

            {/* Queued changes */}
            {changes.length > 0 ? (
              <div className="space-y-2">
                {changes.map((change, i) => {
                  const meta = ACTION_META[change.action];
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-3 px-4 py-2.5 rounded-[var(--radius-md)] bg-[var(--bg-surface-2)] transition-colors hover:bg-[var(--bg-surface-3)]"
                    >
                      <span className={meta.badge}>{meta.label}</span>

                      {change.memory_id && (
                        <span className="font-mono text-[var(--accent)] text-sm">
                          {change.memory_id.length > 16
                            ? `${change.memory_id.slice(0, 16)}...`
                            : change.memory_id}
                        </span>
                      )}

                      {change.content && (
                        <span className="text-sm text-[var(--text-tertiary)] truncate flex-1">
                          {change.content.length > 80
                            ? `${change.content.slice(0, 80)}...`
                            : change.content}
                        </span>
                      )}

                      <button
                        onClick={() => removeChange(i)}
                        className="btn btn--ghost p-1 ml-auto"
                        aria-label="Remove change"
                      >
                        <X size={14} className="text-[var(--text-tertiary)] hover:text-[var(--status-error)]" />
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-ghost)] text-center py-4">
                No changes queued. Use the form above to add memory changes.
              </p>
            )}
          </div>
        </section>

        {/* ── Loading skeleton ────────────────────────────────────── */}
        {isStaging && (
          <section className="mb-8">
            <SectionHeader title="Analyzing Impact" />
            <div className="grid-4">
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
              <CardSkeleton />
            </div>
          </section>
        )}

        {/* ── Impact Dashboard ────────────────────────────────────── */}
        {sessionResult && impact && (
          <section className="space-y-8 animate-fadeIn">
            {/* Session meta */}
            <div className="flex items-center flex-wrap gap-x-6 gap-y-2 text-sm">
              <span className="text-[var(--text-tertiary)]">
                Session{" "}
                <span className="font-mono text-[var(--accent)]">
                  {sessionResult.session_id.slice(0, 12)}...
                </span>
              </span>
              <span className="text-[var(--text-tertiary)]">
                Status{" "}
                <span
                  className={
                    sessionResult.status === "completed"
                      ? "text-[var(--status-success)]"
                      : "text-[var(--status-warning)]"
                  }
                >
                  {sessionResult.status.toUpperCase()}
                </span>
              </span>
              <span className="text-[var(--text-tertiary)]">
                Transactions{" "}
                <span className="font-mono text-[var(--text-secondary)]">
                  {sessionResult.transactions_analyzed}
                </span>
              </span>
              <span className="text-[var(--text-tertiary)]">
                Compute{" "}
                <span className="font-mono text-[var(--text-secondary)]">
                  {sessionResult.compute_time_ms.toFixed(0)}ms
                </span>
              </span>
            </div>

            {/* ── Metric cards ────────────────────────────────────── */}
            {summary && (
              <div className="grid-4">
                <MetricCard
                  label="Avg Score Delta"
                  value={fmtDelta(summary.avg_score_delta)}
                  delta={summary.avg_score_delta}
                  deltaLabel="attribution"
                />
                <MetricCard
                  label="Max Score Delta"
                  value={fmtDelta(summary.max_score_delta)}
                  delta={summary.max_score_delta}
                  deltaLabel="peak shift"
                />
                <MetricCard
                  label="Txns Affected"
                  value={summary.transactions_affected.toString()}
                />
                <MetricCard
                  label="New in Top-3"
                  value={summary.new_memories_in_top3.toString()}
                />
              </div>
            )}

            {/* ── Additional impact cards ─────────────────────────── */}
            <div className="grid-4">
              {impact.contradictions && (
                <div className="card space-y-3">
                  <h4>Contradictions</h4>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--text-tertiary)]">New</span>
                    <span className="font-mono text-[var(--status-error)]">
                      {impact.contradictions.new_contradictions.length}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--text-tertiary)]">
                      Resolved
                    </span>
                    <span className="font-mono text-[var(--status-success)]">
                      {impact.contradictions.resolved_contradictions.length}
                    </span>
                  </div>
                  <div className="border-t border-[var(--border-default)] pt-3 flex justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">Net</span>
                    <span
                      className={`font-mono font-semibold ${deltaClass(
                        impact.contradictions.net_change
                      )}`}
                    >
                      {impact.contradictions.net_change > 0 ? "+" : ""}
                      {impact.contradictions.net_change}
                    </span>
                  </div>
                </div>
              )}

              {impact.coverage && (
                <div className="card space-y-3">
                  <h4>Coverage</h4>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--text-tertiary)]">
                      Gaps Before
                    </span>
                    <span className="font-mono text-[var(--text-secondary)]">
                      {impact.coverage.gaps_before}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--text-tertiary)]">
                      Gaps After
                    </span>
                    <span className="font-mono text-[var(--text-secondary)]">
                      {impact.coverage.gaps_after}
                    </span>
                  </div>
                  <div className="border-t border-[var(--border-default)] pt-3 flex justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">
                      Change
                    </span>
                    <span
                      className={`font-mono font-semibold ${deltaClass(
                        -impact.coverage.gap_change
                      )}`}
                    >
                      {impact.coverage.gap_change > 0 ? "+" : ""}
                      {impact.coverage.gap_change}
                    </span>
                  </div>
                </div>
              )}

              {impact.chi && (
                <div className="card space-y-3">
                  <h4>CHI</h4>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--text-tertiary)]">Before</span>
                    <span className="font-mono text-[var(--text-secondary)]">
                      {impact.chi.before.toFixed(4)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--text-tertiary)]">After</span>
                    <span className="font-mono text-[var(--text-secondary)]">
                      {impact.chi.after.toFixed(4)}
                    </span>
                  </div>
                  <div className="border-t border-[var(--border-default)] pt-3 flex justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">Delta</span>
                    <span
                      className={`font-mono font-semibold ${deltaClass(
                        impact.chi.delta
                      )}`}
                    >
                      {fmtDelta(impact.chi.delta)}
                    </span>
                  </div>
                  {/* Mini gauge */}
                  <div className="flex gap-1.5 items-center pt-1">
                    <div className="flex-1 h-1.5 bg-[var(--bg-surface-2)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[var(--bg-surface-3)] rounded-full"
                        style={{ width: `${impact.chi.before * 100}%` }}
                      />
                    </div>
                    <span className="micro">&rarr;</span>
                    <div className="flex-1 h-1.5 bg-[var(--bg-surface-2)] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${impact.chi.after * 100}%`,
                          backgroundColor:
                            impact.chi.delta >= 0
                              ? "var(--status-success)"
                              : "var(--status-error)",
                        }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {impact.financial && (
                <div className="card space-y-3">
                  <h4>Financial Impact</h4>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--text-tertiary)]">
                      ROI Before
                    </span>
                    <span className="font-mono text-[var(--text-secondary)]">
                      {(impact.financial.portfolio_roi_before * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--text-tertiary)]">
                      ROI After
                    </span>
                    <span
                      className={`font-mono ${
                        impact.financial.portfolio_roi_after >=
                        impact.financial.portfolio_roi_before
                          ? "text-[var(--status-success)]"
                          : "text-[var(--status-error)]"
                      }`}
                    >
                      {(impact.financial.portfolio_roi_after * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="border-t border-[var(--border-default)] pt-3 flex justify-between text-sm">
                    <span className="text-[var(--text-secondary)]">
                      Savings/mo
                    </span>
                    <span className="font-mono font-semibold text-[var(--status-success)]">
                      ${impact.financial.estimated_monthly_savings.toFixed(2)}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* ── Per-transaction delta table ─────────────────────── */}
            {deltas.length > 0 && (
              <div>
                <SectionHeader
                  title="Per-Transaction Attribution Deltas"
                  count={deltas.length}
                />
                <div className="card p-0 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="table table-compact">
                      <thead>
                        <tr>
                          <th>Txn ID</th>
                          <th>Query</th>
                          <th className="text-right">Before Top</th>
                          <th className="text-right">After Top</th>
                          <th className="text-right">Max Delta</th>
                          <th className="text-center">Top Changed</th>
                        </tr>
                      </thead>
                      <tbody>
                        {deltas.map((d) => {
                          const beforeEntries = Object.entries(d.before).sort(
                            ([, a], [, b]) => b - a
                          );
                          const afterEntries = Object.entries(d.after).sort(
                            ([, a], [, b]) => b - a
                          );
                          const topBefore = beforeEntries[0];
                          const topAfter = afterEntries[0];

                          return (
                            <tr key={d.transaction_id}>
                              <td className="font-mono text-[var(--accent)]">
                                {d.transaction_id.slice(0, 10)}...
                              </td>
                              <td className="max-w-[250px] truncate">
                                {d.query_text.length > 60
                                  ? `${d.query_text.slice(0, 60)}...`
                                  : d.query_text}
                              </td>
                              <td className="text-right font-mono">
                                {topBefore
                                  ? topBefore[1].toFixed(4)
                                  : "--"}
                              </td>
                              <td className="text-right font-mono">
                                {topAfter
                                  ? topAfter[1].toFixed(4)
                                  : "--"}
                              </td>
                              <td
                                className={`text-right font-mono ${deltaClass(d.max_score_delta)}`}
                              >
                                {fmtDelta(d.max_score_delta)}
                              </td>
                              <td className="text-center">
                                {d.top_memory_changed ? (
                                  <span className="badge badge--warning">
                                    Yes
                                  </span>
                                ) : (
                                  <span className="badge badge--neutral">
                                    No
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* ── Session error ───────────────────────────────────── */}
            {sessionResult.error && (
              <ErrorFallback error={sessionResult.error} />
            )}

            {/* ── Action bar ──────────────────────────────────────── */}
            {sessionResult.status === "completed" && (
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  onClick={() => setConfirmDialog("discard")}
                  disabled={isDiscarding}
                  className="btn btn--danger"
                >
                  <Trash2 size={14} />
                  {isDiscarding ? "Discarding..." : "Discard"}
                </button>
                <button
                  onClick={() => setConfirmDialog("commit")}
                  disabled={isCommitting}
                  className="btn btn--primary"
                >
                  <Check size={14} />
                  {isCommitting ? "Committing..." : "Commit Changes"}
                </button>
              </div>
            )}
          </section>
        )}

        {/* ── Empty state ─────────────────────────────────────────── */}
        {!sessionResult && !isStaging && changes.length === 0 && (
          <EmptyState
            icon={<FlaskConical size={40} strokeWidth={1} />}
            title="No staging session"
            description="Build a set of memory changes above, then stage them to preview attribution impact before committing."
          />
        )}

        {/* ── Confirmation modal ──────────────────────────────────── */}
        <Modal
          open={confirmDialog !== null}
          onClose={() => setConfirmDialog(null)}
          title={
            confirmDialog === "commit"
              ? "Commit Changes?"
              : "Discard Session?"
          }
        >
          <p className="text-sm text-[var(--text-tertiary)] mb-6">
            {confirmDialog === "commit"
              ? "This will apply all staged changes to the database. This action cannot be undone."
              : "This will discard the staging session and all previewed changes."}
          </p>
          <div className="flex justify-end gap-3">
            <button
              onClick={() => setConfirmDialog(null)}
              className="btn btn--secondary"
            >
              Cancel
            </button>
            <button
              onClick={
                confirmDialog === "commit" ? handleCommit : handleDiscard
              }
              className={
                confirmDialog === "commit"
                  ? "btn btn--primary"
                  : "btn btn--danger"
              }
            >
              {confirmDialog === "commit" ? "Commit" : "Discard"}
            </button>
          </div>
        </Modal>
      </div>
    </PageTransition>
  );
}

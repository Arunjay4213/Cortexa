"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { motion, AnimatePresence } from "framer-motion";
import { useAgents, useSnapshots, useSnapshotDiff, useBranches } from "@/lib/hooks";
import { createSnapshot, restoreSnapshot, createBranch } from "@/lib/api/snapshots";
import { LoadingSkeleton, CardSkeleton } from "@/components/primitives/LoadingSkeleton";
import { ErrorFallback } from "@/components/primitives/ErrorFallback";
import { PageTransition } from "@/components/primitives/PageTransition";
import type { SnapshotResponse, DiffEntry, BranchResponse } from "@/lib/api/types";

// ── Helpers ──────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

const staggerContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};
const staggerChild = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2 } },
};

// ── Page ─────────────────────────────────────────────────────────────

export default function SnapshotsPage() {
  const { mutate } = useSWRConfig();
  const { data: agents } = useAgents();

  // Selection state
  const [selectedAgent, setSelectedAgent] = useState("");
  const [selectedSnapshot, setSelectedSnapshot] = useState<string | null>(null);
  const [compareSnapshot, setCompareSnapshot] = useState<string | null>(null);

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showBranchModal, setShowBranchModal] = useState(false);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState<string | null>(null);

  // Create snapshot form
  const [createVersionTag, setCreateVersionTag] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Create branch form
  const [branchName, setBranchName] = useState("");
  const [branchBaseSnapshotId, setBranchBaseSnapshotId] = useState("");

  // Restore state
  const [isRestoring, setIsRestoring] = useState(false);

  const agentId = selectedAgent || null;

  const {
    data: snapshots,
    error: snapError,
    isLoading: snapLoading,
  } = useSnapshots(agentId);

  const {
    data: diff,
    isLoading: diffLoading,
  } = useSnapshotDiff(agentId, selectedSnapshot, compareSnapshot);

  const {
    data: branches,
    isLoading: branchesLoading,
  } = useBranches(agentId);

  // ── Handlers ──────────────────────────────────────────────────────

  async function handleCreateSnapshot() {
    if (!agentId || !createVersionTag.trim()) return;
    setIsCreating(true);
    try {
      await createSnapshot(agentId, {
        name: createVersionTag.trim(),
        description: createDescription.trim() || undefined,
      });
      mutate((key: string) => typeof key === "string" && key.startsWith("/snapshots"));
      setShowCreateModal(false);
      setCreateVersionTag("");
      setCreateDescription("");
    } catch (err) {
      console.error("Create snapshot failed", err);
    } finally {
      setIsCreating(false);
    }
  }

  async function handleRestore(snapshotId: string) {
    if (!agentId) return;
    setIsRestoring(true);
    try {
      await restoreSnapshot(agentId, snapshotId);
      mutate((key: string) =>
        typeof key === "string" &&
        (key.startsWith("/memories") || key.startsWith("/snapshots"))
      );
      setShowRestoreConfirm(null);
    } catch (err) {
      console.error("Restore failed", err);
    } finally {
      setIsRestoring(false);
    }
  }

  async function handleCreateBranch() {
    if (!agentId || !branchName.trim() || !branchBaseSnapshotId) return;
    try {
      await createBranch(agentId, {
        name: branchName.trim(),
        snapshot_id: branchBaseSnapshotId,
      });
      mutate((key: string) => typeof key === "string" && key.startsWith("/branches"));
      setShowBranchModal(false);
      setBranchName("");
      setBranchBaseSnapshotId("");
    } catch (err) {
      console.error("Create branch failed", err);
    }
  }

  function handleSelectSnapshot(snapId: string) {
    if (!selectedSnapshot || selectedSnapshot === snapId) {
      setSelectedSnapshot(snapId);
      setCompareSnapshot(null);
    } else {
      setCompareSnapshot(snapId);
    }
  }

  function clearDiffSelection() {
    setSelectedSnapshot(null);
    setCompareSnapshot(null);
  }

  // ── Diff badge helper ─────────────────────────────────────────────

  function diffBadgeClass(status: string): string {
    switch (status) {
      case "added":
        return "badge badge--success";
      case "removed":
        return "badge badge--error";
      case "modified":
        return "badge badge--warning";
      default:
        return "badge badge--neutral";
    }
  }

  function diffRowTint(status: string): string {
    switch (status) {
      case "added":
        return "bg-[rgba(52,211,153,0.04)] border-l-2 border-l-[var(--status-success)]";
      case "removed":
        return "bg-[rgba(248,113,113,0.04)] border-l-2 border-l-[var(--status-error)]";
      case "modified":
        return "bg-[rgba(251,191,36,0.04)] border-l-2 border-l-[var(--status-warning)]";
      default:
        return "";
    }
  }

  // ── Render ────────────────────────────────────────────────────────

  return (
    <PageTransition>
      <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-secondary)]">
        {/* ── Page Header ──────────────────────────────────────────── */}
        <div className="border-b border-[var(--border-default)] px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-[var(--text-primary)] tracking-tight">
                Snapshots
              </h1>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Memory versioning, diffs, and branching
              </p>
            </div>
            <div className="flex items-center gap-3">
              {/* Agent Selector */}
              <select
                value={selectedAgent}
                onChange={(e) => {
                  setSelectedAgent(e.target.value);
                  clearDiffSelection();
                }}
                className="input input--sm w-52 font-mono"
              >
                <option value="">Select agent...</option>
                {(agents ?? []).map((a) => (
                  <option key={a.agent_id} value={a.agent_id}>
                    {a.agent_id}
                  </option>
                ))}
              </select>

              {agentId && (
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="btn btn--primary text-xs"
                >
                  Create Snapshot
                </button>
              )}
            </div>
          </div>
        </div>

        {/* ── No Agent Selected ────────────────────────────────────── */}
        {!agentId && (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <div className="text-[40px] mb-4 opacity-15">&#128247;</div>
            <div className="text-sm text-[var(--text-ghost)] mb-1">
              Select an agent to view snapshots
            </div>
            <div className="text-xs text-[var(--text-ghost)]">
              Snapshots capture your agent&apos;s complete memory state for versioning and rollback
            </div>
          </div>
        )}

        {/* ── Main Content (two-column) ────────────────────────────── */}
        {agentId && (
          <div className="flex h-[calc(100vh-120px)]">
            {/* ── Left Panel: Snapshot Timeline + Branches ── */}
            <div className="w-[380px] border-r border-[var(--border-default)] flex flex-col overflow-hidden">
              {/* Snapshot section header */}
              <div className="px-5 py-3 border-b border-[var(--border-default)] flex items-center justify-between">
                <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                  Snapshot Timeline
                </span>
                <span className="badge badge--neutral font-mono">
                  {snapshots?.length ?? 0}
                </span>
              </div>

              {/* Snapshot list (scrollable) */}
              <div className="flex-1 overflow-y-auto">
                {snapLoading && (
                  <div className="p-5">
                    <LoadingSkeleton rows={6} />
                  </div>
                )}

                {snapError && (
                  <div className="p-5">
                    <ErrorFallback error={snapError} />
                  </div>
                )}

                {snapshots && snapshots.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-16 text-center px-6">
                    <div className="text-xs text-[var(--text-ghost)]">
                      No snapshots yet. Create your first snapshot to start versioning.
                    </div>
                  </div>
                )}

                {snapshots && snapshots.length > 0 && (
                  <motion.div
                    variants={staggerContainer}
                    initial="hidden"
                    animate="show"
                  >
                    {snapshots.map((snap: SnapshotResponse) => {
                      const isSelected = selectedSnapshot === snap.id;
                      const isCompare = compareSnapshot === snap.id;

                      return (
                        <motion.div
                          key={snap.id}
                          variants={staggerChild}
                          onClick={() => handleSelectSnapshot(snap.id)}
                          className={`px-5 py-4 border-b border-[var(--border-default)] cursor-pointer transition-all hover:bg-[var(--bg-surface-1)] ${
                            isSelected
                              ? "bg-[var(--bg-surface-2)] border-l-2 border-l-[var(--accent)]"
                              : isCompare
                              ? "bg-[var(--bg-surface-2)] border-l-2 border-l-[var(--status-warning)]"
                              : ""
                          }`}
                        >
                          {/* Top row: name + memory count */}
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-sm font-medium text-[var(--text-primary)]">
                              {snap.name}
                            </span>
                            <span className="badge badge--neutral font-mono">
                              {snap.memory_count} memories
                            </span>
                          </div>

                          {/* Snapshot ID */}
                          <div className="text-xs font-mono text-[var(--accent)] mb-1">
                            {snap.id.slice(0, 12)}...
                          </div>

                          {/* Description */}
                          {snap.description && (
                            <div className="text-xs text-[var(--text-tertiary)] mb-1.5 truncate">
                              {snap.description}
                            </div>
                          )}

                          {/* Timestamp + creator */}
                          <div className="flex items-center gap-2 text-xs text-[var(--text-ghost)] mb-2.5">
                            <span className="font-mono">
                              {formatDate(snap.created_at)}
                            </span>
                            <span>({relativeTime(snap.created_at)})</span>
                            {snap.created_by && (
                              <>
                                <span className="text-[var(--border-active)]">&middot;</span>
                                <span>{snap.created_by}</span>
                              </>
                            )}
                          </div>

                          {/* Action buttons */}
                          <div className="flex gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setShowRestoreConfirm(snap.id);
                              }}
                              className="btn btn--danger text-xs py-1 px-2.5"
                            >
                              Restore
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setBranchBaseSnapshotId(snap.id);
                                setShowBranchModal(true);
                              }}
                              className="btn btn--secondary text-xs py-1 px-2.5"
                            >
                              Branch
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (selectedSnapshot && selectedSnapshot !== snap.id) {
                                  setCompareSnapshot(snap.id);
                                } else {
                                  setSelectedSnapshot(snap.id);
                                }
                              }}
                              className="btn btn--ghost text-xs py-1 px-2.5 text-[var(--accent)]"
                            >
                              Diff
                            </button>
                          </div>
                        </motion.div>
                      );
                    })}
                  </motion.div>
                )}

                {/* ── Branches Section ── */}
                <div className="px-5 py-3 border-b border-[var(--border-default)] border-t border-[var(--border-hover)] flex items-center justify-between">
                  <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Branches
                  </span>
                  <button
                    onClick={() => {
                      if (snapshots && snapshots.length > 0) {
                        setBranchBaseSnapshotId(snapshots[0].id);
                      }
                      setShowBranchModal(true);
                    }}
                    className="btn btn--ghost text-xs py-0.5 px-2"
                  >
                    + Create Branch
                  </button>
                </div>

                {branchesLoading && (
                  <div className="p-5">
                    <LoadingSkeleton rows={3} />
                  </div>
                )}

                {branches && branches.length === 0 && (
                  <div className="px-5 py-6 text-xs text-[var(--text-ghost)] text-center">
                    No branches yet
                  </div>
                )}

                {branches &&
                  branches.map((br: BranchResponse) => (
                    <div
                      key={br.id}
                      className="px-5 py-3.5 border-b border-[var(--border-default)] hover:bg-[var(--bg-surface-1)] transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-[var(--text-primary)]">
                          {br.name}
                        </span>
                        <span className="text-xs text-[var(--text-ghost)] font-mono">
                          {relativeTime(br.created_at)}
                        </span>
                      </div>
                      <div className="text-xs text-[var(--text-ghost)]">
                        Base:{" "}
                        <span className="font-mono text-[var(--accent)]">
                          {br.parent_snapshot_id.slice(0, 12)}
                        </span>
                      </div>
                      {br.description && (
                        <div className="text-xs text-[var(--text-tertiary)] mt-1 truncate">
                          {br.description}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            </div>

            {/* ── Right Panel: Diff Viewer ── */}
            <div className="flex-1 overflow-y-auto">
              {selectedSnapshot && compareSnapshot ? (
                <div className="p-6 space-y-5">
                  {/* Diff header */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2 text-xs">
                        <span className="badge badge--info font-mono">
                          {selectedSnapshot.slice(0, 10)}
                        </span>
                        <span className="text-[var(--text-ghost)]">vs</span>
                        <span className="badge badge--warning font-mono">
                          {compareSnapshot.slice(0, 10)}
                        </span>
                      </div>
                    </div>
                    <button onClick={clearDiffSelection} className="btn btn--ghost text-xs">
                      Clear Selection
                    </button>
                  </div>

                  {diffLoading && <LoadingSkeleton rows={10} />}

                  {diff && (
                    <>
                      {/* Diff summary counters */}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="card flex flex-col items-center py-4">
                          <span className="text-2xl font-bold font-mono text-[var(--status-success)]">
                            +{diff.added.length}
                          </span>
                          <span className="text-xs text-[var(--text-tertiary)] mt-1">Added</span>
                        </div>
                        <div className="card flex flex-col items-center py-4">
                          <span className="text-2xl font-bold font-mono text-[var(--status-error)]">
                            -{diff.removed.length}
                          </span>
                          <span className="text-xs text-[var(--text-tertiary)] mt-1">Removed</span>
                        </div>
                        <div className="card flex flex-col items-center py-4">
                          <span className="text-2xl font-bold font-mono text-[var(--status-warning)]">
                            ~{diff.modified.length}
                          </span>
                          <span className="text-xs text-[var(--text-tertiary)] mt-1">Modified</span>
                        </div>
                      </div>

                      {/* Diff entries */}
                      {diff.added.length === 0 &&
                        diff.removed.length === 0 &&
                        diff.modified.length === 0 && (
                          <div className="card text-center py-12">
                            <div className="text-sm text-[var(--text-ghost)]">
                              No differences between these snapshots
                            </div>
                          </div>
                        )}

                      {[...diff.added, ...diff.removed, ...diff.modified].length > 0 && (
                        <motion.div
                          variants={staggerContainer}
                          initial="hidden"
                          animate="show"
                          className="space-y-3"
                        >
                          {[...diff.added, ...diff.removed, ...diff.modified].map(
                            (entry: DiffEntry) => (
                              <motion.div
                                key={entry.memory_id}
                                variants={staggerChild}
                                className={`card ${diffRowTint(entry.status)} rounded-[var(--radius-lg)] p-4`}
                              >
                                {/* Entry header */}
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs font-medium font-mono text-[var(--text-primary)]">
                                    {entry.memory_id.slice(0, 16)}
                                  </span>
                                  <span className={diffBadgeClass(entry.status)}>
                                    {entry.status}
                                  </span>
                                </div>

                                {/* Content diff */}
                                {entry.content_a && (
                                  <div className="text-xs font-mono text-[var(--status-error)] bg-[rgba(248,113,113,0.06)] border border-[rgba(248,113,113,0.1)] rounded-[var(--radius-sm)] p-2.5 mt-2 line-through">
                                    {entry.content_a.slice(0, 200)}
                                    {entry.content_a.length > 200 ? "..." : ""}
                                  </div>
                                )}
                                {entry.content_b && (
                                  <div className="text-xs font-mono text-[var(--status-success)] bg-[rgba(52,211,153,0.06)] border border-[rgba(52,211,153,0.1)] rounded-[var(--radius-sm)] p-2.5 mt-2">
                                    {entry.content_b.slice(0, 200)}
                                    {entry.content_b.length > 200 ? "..." : ""}
                                  </div>
                                )}

                                {/* Tier change */}
                                {entry.tier_a &&
                                  entry.tier_b &&
                                  entry.tier_a !== entry.tier_b && (
                                    <div className="text-xs text-[var(--text-ghost)] mt-2 font-mono">
                                      Tier: {entry.tier_a} &rarr; {entry.tier_b}
                                    </div>
                                  )}
                              </motion.div>
                            )
                          )}
                        </motion.div>
                      )}
                    </>
                  )}
                </div>
              ) : selectedSnapshot ? (
                <div className="flex flex-col items-center justify-center h-full text-center px-6">
                  <div className="text-sm text-[var(--text-ghost)] mb-2">
                    Select a second snapshot to compare
                  </div>
                  <div className="text-xs text-[var(--text-ghost)]">
                    Click another snapshot in the timeline, or use the Diff button
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center px-6">
                  <div className="text-[40px] mb-4 opacity-15">&#128203;</div>
                  <div className="text-sm text-[var(--text-ghost)] mb-2">
                    Select snapshots to compare
                  </div>
                  <div className="text-xs text-[var(--text-ghost)]">
                    Click a snapshot to start, then select a second to view the diff
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Create Snapshot Modal ──────────────────────────────────── */}
        <AnimatePresence>
          {showCreateModal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
              onClick={() => setShowCreateModal(false)}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                onClick={(e) => e.stopPropagation()}
                className="card w-[420px] max-w-[90vw] space-y-5"
              >
                <div>
                  <h3 className="text-base font-semibold text-[var(--text-primary)]">
                    Create Snapshot
                  </h3>
                  <p className="text-xs text-[var(--text-tertiary)] mt-1">
                    Capture the current memory state for{" "}
                    <span className="font-mono text-[var(--accent)]">
                      {agentId}
                    </span>
                  </p>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-[var(--text-tertiary)] block mb-1.5">
                      Version Tag
                    </label>
                    <input
                      type="text"
                      value={createVersionTag}
                      onChange={(e) => setCreateVersionTag(e.target.value)}
                      placeholder="e.g. v1.2.0 or pre-deploy"
                      className="input input--sm font-mono"
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className="text-xs text-[var(--text-tertiary)] block mb-1.5">
                      Description
                    </label>
                    <textarea
                      value={createDescription}
                      onChange={(e) => setCreateDescription(e.target.value)}
                      placeholder="What changed? (optional)"
                      rows={3}
                      className="input input--sm resize-none"
                    />
                  </div>
                </div>

                <div className="flex gap-2 justify-end pt-1">
                  <button
                    onClick={() => setShowCreateModal(false)}
                    className="btn btn--secondary text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateSnapshot}
                    disabled={isCreating || !createVersionTag.trim()}
                    className="btn btn--primary text-xs"
                  >
                    {isCreating ? "Creating..." : "Create Snapshot"}
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Restore Confirmation Modal ─────────────────────────────── */}
        <AnimatePresence>
          {showRestoreConfirm && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
              onClick={() => setShowRestoreConfirm(null)}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                onClick={(e) => e.stopPropagation()}
                className="card w-[420px] max-w-[90vw] space-y-4 border-[var(--status-warning)]/30"
              >
                <div>
                  <h3 className="text-base font-semibold text-[var(--status-warning)]">
                    Confirm Restore
                  </h3>
                  <p className="text-xs text-[var(--text-tertiary)] mt-1">
                    This will replace all current memories for this agent with the
                    snapshot state. This action cannot be undone.
                  </p>
                </div>

                <div className="text-xs text-[var(--text-ghost)] font-mono bg-[var(--bg-surface-2)] rounded-[var(--radius-md)] p-3">
                  {showRestoreConfirm}
                </div>

                <div className="flex gap-2 justify-end pt-1">
                  <button
                    onClick={() => setShowRestoreConfirm(null)}
                    className="btn btn--secondary text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleRestore(showRestoreConfirm)}
                    disabled={isRestoring}
                    className="btn btn--danger text-xs"
                  >
                    {isRestoring ? "Restoring..." : "Restore Snapshot"}
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Create Branch Modal ────────────────────────────────────── */}
        <AnimatePresence>
          {showBranchModal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
              onClick={() => setShowBranchModal(false)}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                onClick={(e) => e.stopPropagation()}
                className="card w-[420px] max-w-[90vw] space-y-5"
              >
                <div>
                  <h3 className="text-base font-semibold text-[var(--text-primary)]">
                    Create Branch
                  </h3>
                  <p className="text-xs text-[var(--text-tertiary)] mt-1">
                    Fork memory state from a snapshot into a named branch
                  </p>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-[var(--text-tertiary)] block mb-1.5">
                      Branch Name
                    </label>
                    <input
                      type="text"
                      value={branchName}
                      onChange={(e) => setBranchName(e.target.value)}
                      placeholder="e.g. experiment-v2"
                      className="input input--sm font-mono"
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className="text-xs text-[var(--text-tertiary)] block mb-1.5">
                      Base Snapshot
                    </label>
                    <select
                      value={branchBaseSnapshotId}
                      onChange={(e) => setBranchBaseSnapshotId(e.target.value)}
                      className="input input--sm font-mono"
                    >
                      <option value="">Select snapshot...</option>
                      {(snapshots ?? []).map((snap: SnapshotResponse) => (
                        <option key={snap.id} value={snap.id}>
                          {snap.name} ({snap.id.slice(0, 8)})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex gap-2 justify-end pt-1">
                  <button
                    onClick={() => setShowBranchModal(false)}
                    className="btn btn--secondary text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateBranch}
                    disabled={!branchName.trim() || !branchBaseSnapshotId}
                    className="btn btn--primary text-xs"
                  >
                    Create Branch
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </PageTransition>
  );
}

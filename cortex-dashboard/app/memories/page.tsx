"use client";

import { Suspense, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useSWRConfig } from "swr";
import { useMemories, useMemory, useMemorySearch } from "@/lib/hooks";
import { createMemory, updateMemory, deleteMemory } from "@/lib/api/memories";
import { LoadingSkeleton, TableSkeleton } from "@/components/primitives/LoadingSkeleton";
import { ErrorFallback } from "@/components/primitives/ErrorFallback";
import { PageTransition } from "@/components/primitives/PageTransition";
import { PageHeader } from "@/components/primitives/PageHeader";
import { Modal } from "@/components/primitives/Modal";
import { EmptyState } from "@/components/primitives/EmptyState";
import { EntityLink } from "@/components/primitives/EntityLink";
import { Database, Search, X, ChevronLeft, ChevronRight, Pencil, Trash2, Save, XCircle } from "lucide-react";
import type { MemoryTier, MemoryUnit } from "@/lib/api/types";

const PAGE_SIZE = 25;

const TIER_BADGE: Record<string, string> = {
  hot: "badge badge--error",
  warm: "badge badge--warning",
  cold: "badge badge--info",
};

function truncate(str: string, len: number): string {
  return str.length > len ? str.slice(0, len) + "..." : str;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toISOString().replace("T", " ").slice(0, 19);
}

export default function MemoriesPage() {
  return (
    <Suspense
      fallback={
        <div className="page-container">
          <LoadingSkeleton rows={6} />
        </div>
      }
    >
      <MemoriesPageInner />
    </Suspense>
  );
}

function MemoriesPageInner() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const searchParams = useSearchParams();

  // URL-driven state
  const selectedMemoryId = searchParams.get("selected");
  const showCreateModal = searchParams.get("create") === "true";

  // Local state
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("newest");
  const [offset, setOffset] = useState(0);

  // Detail panel edit state
  const [editTier, setEditTier] = useState<MemoryTier | null>(null);
  const [editCriticality, setEditCriticality] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Create form state
  const [createAgentId, setCreateAgentId] = useState("");
  const [createContent, setCreateContent] = useState("");
  const [createTier, setCreateTier] = useState<MemoryTier>("warm");
  const [createCriticality, setCreateCriticality] = useState("0.5");
  const [createSource, setCreateSource] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Delete confirmation
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Derive sort_by / order from the sort dropdown value
  const sortConfig = sortBy === "newest"
    ? { sort_by: "created_at", order: "desc" as const }
    : sortBy === "oldest"
    ? { sort_by: "created_at", order: "asc" as const }
    : { sort_by: "criticality", order: "desc" as const };

  // Data hooks
  const {
    data: memoriesData,
    error: memoriesError,
    isLoading: memoriesLoading,
  } = useMemories({
    tier: tierFilter !== "all" ? tierFilter : undefined,
    sort_by: sortConfig.sort_by,
    order: sortConfig.order,
    offset,
    limit: PAGE_SIZE,
  });

  const {
    data: selectedData,
    error: selectedError,
    isLoading: selectedLoading,
  } = useMemory(selectedMemoryId);

  const {
    data: searchResults,
    error: searchError,
    isLoading: searchLoading,
  } = useMemorySearch(activeSearch);

  const isSearchMode = activeSearch !== null && activeSearch.length > 0;
  const selectedMemory = selectedData?.memory ?? null;
  const selectedProfile = selectedData?.profile ?? null;

  // Pagination
  const total = memoriesData?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  // URL helpers
  const setSelectedParam = useCallback(
    (id: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (id) {
        params.set("selected", id);
      } else {
        params.delete("selected");
      }
      params.delete("create");
      router.replace(`/memories?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const openCreateModal = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("create", "true");
    params.delete("selected");
    router.replace(`/memories?${params.toString()}`, { scroll: false });
  }, [router, searchParams]);

  const closeCreateModal = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("create");
    router.replace(`/memories?${params.toString()}`, { scroll: false });
  }, [router, searchParams]);

  // Handlers
  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      const q = searchQuery.trim();
      setActiveSearch(q.length > 0 ? q : null);
      setSelectedParam(null);
    }
  }

  function clearSearch() {
    setSearchQuery("");
    setActiveSearch(null);
  }

  function handleTierFilter(tier: string) {
    setTierFilter(tier);
    setOffset(0);
    setSelectedParam(null);
    clearSearch();
  }

  function handleSelectMemory(id: string) {
    setSelectedParam(id);
    setEditTier(null);
    setEditCriticality("");
  }

  function closePanel() {
    setSelectedParam(null);
    setEditTier(null);
    setEditCriticality("");
  }

  function startEditing() {
    if (!selectedMemory) return;
    setEditTier(selectedMemory.tier);
    setEditCriticality(String(selectedMemory.criticality));
  }

  function cancelEdit() {
    setEditTier(null);
    setEditCriticality("");
  }

  async function handleSave() {
    if (!selectedMemoryId || editTier === null) return;
    setIsSaving(true);
    try {
      await updateMemory(selectedMemoryId, {
        tier: editTier,
        criticality: parseFloat(editCriticality) || 0,
      });
      mutate((key: string) => typeof key === "string" && key.startsWith("/memories"));
      setEditTier(null);
      setEditCriticality("");
    } catch (err) {
      console.error("Update failed", err);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteMemory(id);
      mutate((key: string) => typeof key === "string" && key.startsWith("/memories"));
      if (selectedMemoryId === id) setSelectedParam(null);
      setDeleteConfirmId(null);
    } catch (err) {
      console.error("Delete failed", err);
    }
  }

  async function handleCreate() {
    if (!createContent.trim()) return;
    setIsCreating(true);
    try {
      await createMemory({
        content: createContent.trim(),
        agent_id: createAgentId.trim() || undefined,
        tier: createTier,
        criticality: parseFloat(createCriticality) || 0.5,
        metadata: createSource.trim() ? { source: createSource.trim() } : undefined,
      });
      mutate((key: string) => typeof key === "string" && key.startsWith("/memories"));
      closeCreateModal();
      setCreateContent("");
      setCreateAgentId("");
      setCreateTier("warm");
      setCreateCriticality("0.5");
      setCreateSource("");
    } catch (err) {
      console.error("Create failed", err);
    } finally {
      setIsCreating(false);
    }
  }

  // Table rows to display
  const displayItems: MemoryUnit[] = isSearchMode
    ? (searchResults ?? []).map((sr) => sr.memory)
    : (memoriesData?.items ?? []);

  const isLoading = isSearchMode ? searchLoading : memoriesLoading;
  const loadError = isSearchMode ? searchError : memoriesError;

  return (
    <PageTransition>
      <div className="page-container">
        {/* Page Header */}
        <PageHeader
          title="Memories"
          subtitle="Browse, search, and manage memory units"
        >
          <button className="btn btn--primary" onClick={openCreateModal}>
            Create Memory
          </button>
        </PageHeader>

        {/* Search + Filters Bar */}
        <div className="card mb-6">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[240px]">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-ghost)]"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder="Search memories (press Enter)..."
                className="input pl-9 pr-8"
              />
              {isSearchMode && (
                <button
                  onClick={clearSearch}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-ghost)] hover:text-[var(--text-tertiary)] transition-colors"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Tier Filter */}
            <div className="flex items-center gap-1.5">
              <span className="caption mr-1">Tier</span>
              {(["all", "hot", "warm", "cold"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => handleTierFilter(t)}
                  className={`btn text-xs px-3 py-1.5 ${
                    tierFilter === t ? "btn--primary" : "btn--ghost"
                  }`}
                >
                  {t === "all" ? "All" : t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {/* Sort Dropdown */}
            <div className="flex items-center gap-1.5">
              <span className="caption mr-1">Sort</span>
              <select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setOffset(0);
                }}
                className="input input--sm w-auto"
              >
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="score">Score</option>
              </select>
            </div>
          </div>

          {/* Active search indicator */}
          {isSearchMode && (
            <div className="mt-3 flex items-center gap-2">
              <span className="badge badge--info">
                Search: &quot;{activeSearch}&quot;
              </span>
              {searchResults && (
                <span className="caption">{searchResults.length} results</span>
              )}
              <button onClick={clearSearch} className="btn btn--ghost text-xs py-1 px-2">
                Clear
              </button>
            </div>
          )}
        </div>

        {/* Main Content Area */}
        <div className="relative">
          {/* Table */}
          {isLoading ? (
            <div className="card">
              <TableSkeleton rows={10} cols={6} />
            </div>
          ) : loadError ? (
            <ErrorFallback
              error={loadError}
              onRetry={() =>
                mutate((key: string) =>
                  typeof key === "string" && key.startsWith("/memories"),
                )
              }
            />
          ) : displayItems.length === 0 ? (
            <EmptyState
              icon={<Database size={40} strokeWidth={1} />}
              title={isSearchMode ? "No search results" : "No memories found"}
              description={
                isSearchMode
                  ? `No memories matched "${activeSearch}". Try a different query.`
                  : "Create your first memory to get started."
              }
            >
              {!isSearchMode && (
                <button className="btn btn--primary" onClick={openCreateModal}>
                  Create Memory
                </button>
              )}
            </EmptyState>
          ) : (
            <div className="card p-0 overflow-hidden">
              <table className="table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Content</th>
                    <th>Tier</th>
                    <th>Criticality</th>
                    <th>Agent</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {displayItems.map((m) => {
                    const isActive = selectedMemoryId === m.id;
                    const similarity = isSearchMode
                      ? searchResults?.find((sr) => sr.memory.id === m.id)?.similarity
                      : undefined;
                    return (
                      <tr
                        key={m.id}
                        onClick={() => handleSelectMemory(m.id)}
                        className={`cursor-pointer transition-colors ${
                          isActive
                            ? "!bg-[var(--accent-muted)]"
                            : ""
                        }`}
                      >
                        <td>
                          <EntityLink type="memory" id={m.id} truncate={8} />
                        </td>
                        <td className="max-w-[300px]">
                          <span className="truncate block text-[var(--text-secondary)]">
                            {truncate(m.content, 60)}
                          </span>
                          {similarity !== undefined && (
                            <span className="caption text-[var(--status-success)] font-mono">
                              sim: {similarity.toFixed(3)}
                            </span>
                          )}
                        </td>
                        <td>
                          <span className={TIER_BADGE[m.tier] ?? "badge badge--neutral"}>
                            {m.tier}
                          </span>
                        </td>
                        <td>
                          <span className="font-mono text-[var(--text-secondary)]">
                            {m.criticality.toFixed(2)}
                          </span>
                        </td>
                        <td>
                          <span className="text-[var(--text-tertiary)]">
                            {m.agent_id || "--"}
                          </span>
                        </td>
                        <td>
                          <span className="font-mono text-[var(--text-tertiary)] text-xs">
                            {formatDate(m.created_at)}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination (non-search mode only) */}
          {!isSearchMode && displayItems.length > 0 && (
            <div className="flex items-center justify-between mt-4">
              <span className="caption">
                {total} total &middot; page {currentPage} of {totalPages}
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  className="btn btn--secondary text-xs"
                >
                  <ChevronLeft size={14} />
                  Prev
                </button>
                <button
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                  className="btn btn--secondary text-xs"
                >
                  Next
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}

          {/* Slide-over Detail Panel */}
          {selectedMemoryId && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-40 bg-black/30"
                onClick={closePanel}
              />

              {/* Panel */}
              <div className="fixed top-0 right-0 z-50 h-full w-[480px] bg-[var(--bg-surface-1)] border-l border-[var(--border-default)] overflow-y-auto animate-slide-in-right">
                {selectedLoading ? (
                  <div className="p-6">
                    <LoadingSkeleton rows={8} />
                  </div>
                ) : selectedError ? (
                  <div className="p-6">
                    <ErrorFallback
                      error={selectedError}
                      onRetry={() => mutate(`/memories/${selectedMemoryId}`)}
                    />
                  </div>
                ) : selectedMemory ? (
                  <div className="flex flex-col h-full">
                    {/* Panel Header */}
                    <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-default)] shrink-0">
                      <div>
                        <span className="caption block mb-0.5">Memory</span>
                        <span className="font-mono text-[var(--accent)] text-sm">
                          {selectedMemory.id.slice(0, 12)}...
                        </span>
                      </div>
                      <button
                        onClick={closePanel}
                        className="btn btn--ghost p-2"
                      >
                        <X size={16} />
                      </button>
                    </div>

                    {/* Panel Body */}
                    <div className="flex-1 overflow-y-auto p-6 space-y-6">
                      {/* Full ID */}
                      <div>
                        <label className="caption block mb-1">Memory ID</label>
                        <div className="font-mono text-[var(--accent)] text-xs break-all bg-[var(--bg-surface-2)] rounded-lg p-3 border border-[var(--border-default)]">
                          {selectedMemory.id}
                        </div>
                      </div>

                      {/* Content */}
                      <div>
                        <label className="caption block mb-1">Content</label>
                        <div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap bg-[var(--bg-surface-2)] border border-[var(--border-default)] rounded-lg p-3 max-h-[200px] overflow-y-auto leading-relaxed">
                          {selectedMemory.content}
                        </div>
                      </div>

                      {/* Tier + Criticality */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="caption block mb-1.5">Tier</label>
                          {editTier !== null ? (
                            <div className="flex gap-1.5">
                              {(["hot", "warm", "cold"] as MemoryTier[]).map((t) => (
                                <button
                                  key={t}
                                  onClick={() => setEditTier(t)}
                                  className={`text-xs px-3 py-1 rounded-full transition-colors ${
                                    editTier === t
                                      ? TIER_BADGE[t]
                                      : "badge badge--neutral"
                                  }`}
                                >
                                  {t}
                                </button>
                              ))}
                            </div>
                          ) : (
                            <span className={TIER_BADGE[selectedMemory.tier] ?? "badge badge--neutral"}>
                              {selectedMemory.tier}
                            </span>
                          )}
                        </div>
                        <div>
                          <label className="caption block mb-1.5">Criticality</label>
                          {editTier !== null ? (
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              max="1"
                              value={editCriticality}
                              onChange={(e) => setEditCriticality(e.target.value)}
                              className="input input--sm font-mono"
                            />
                          ) : (
                            <span className="font-mono text-[var(--text-secondary)]">
                              {selectedMemory.criticality.toFixed(2)}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Stats Grid */}
                      <div className="grid grid-cols-2 gap-4">
                        {[
                          { label: "Tokens", value: String(selectedMemory.tokens) },
                          { label: "Retrievals", value: String(selectedMemory.retrieval_count) },
                          { label: "Created", value: formatDate(selectedMemory.created_at) },
                          {
                            label: "Last Accessed",
                            value: selectedMemory.last_accessed
                              ? formatDate(selectedMemory.last_accessed)
                              : "Never",
                          },
                        ].map((s) => (
                          <div key={s.label}>
                            <span className="caption block mb-0.5">{s.label}</span>
                            <span className="font-mono text-[var(--text-secondary)] text-sm">
                              {s.value}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* Agent */}
                      <div>
                        <label className="caption block mb-1">Agent ID</label>
                        <span className="font-mono text-[var(--text-secondary)] text-sm">
                          {selectedMemory.agent_id || "None"}
                        </span>
                      </div>

                      {/* Metadata */}
                      <div>
                        <label className="caption block mb-1">Metadata</label>
                        <pre className="text-xs font-mono text-[var(--text-tertiary)] bg-[var(--bg-surface-2)] border border-[var(--border-default)] rounded-lg p-3 max-h-[160px] overflow-y-auto whitespace-pre-wrap break-all">
                          {JSON.stringify(selectedMemory.metadata, null, 2)}
                        </pre>
                      </div>

                      {/* Attribution Profile */}
                      {selectedProfile && (
                        <div>
                          <label className="caption block mb-1">Attribution Profile</label>
                          <pre className="text-xs font-mono text-[var(--status-success)] bg-[var(--bg-surface-2)] border border-[var(--border-default)] rounded-lg p-3 max-h-[160px] overflow-y-auto whitespace-pre-wrap break-all">
                            {JSON.stringify(selectedProfile, null, 2)}
                          </pre>
                        </div>
                      )}

                      {/* Soft-deleted indicator */}
                      {selectedMemory.deleted_at && (
                        <div className="badge badge--error text-xs">
                          Soft deleted: {formatDate(selectedMemory.deleted_at)}
                        </div>
                      )}
                    </div>

                    {/* Panel Footer Actions */}
                    <div className="shrink-0 border-t border-[var(--border-default)] px-6 py-4 flex items-center gap-2">
                      {editTier === null ? (
                        <>
                          <button onClick={startEditing} className="btn btn--secondary text-xs">
                            <Pencil size={13} />
                            Edit
                          </button>
                          <button
                            onClick={() => setDeleteConfirmId(selectedMemory.id)}
                            className="btn btn--danger text-xs"
                          >
                            <Trash2 size={13} />
                            Delete
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={handleSave}
                            disabled={isSaving}
                            className="btn btn--primary text-xs"
                          >
                            <Save size={13} />
                            {isSaving ? "Saving..." : "Save"}
                          </button>
                          <button onClick={cancelEdit} className="btn btn--secondary text-xs">
                            <XCircle size={13} />
                            Cancel
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="p-6">
                    <EmptyState title="Memory not found" description="This memory may have been deleted." />
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <Modal
        open={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        title="Delete Memory"
      >
        <div className="space-y-4">
          <p className="text-sm text-[var(--text-secondary)]">
            Are you sure you want to soft-delete this memory?
          </p>
          <div className="font-mono text-xs text-[var(--accent)] bg-[var(--bg-surface-2)] border border-[var(--border-default)] rounded-lg p-3 break-all">
            {deleteConfirmId}
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              onClick={() => setDeleteConfirmId(null)}
              className="btn btn--secondary"
            >
              Cancel
            </button>
            <button
              onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}
              className="btn btn--danger"
            >
              Delete
            </button>
          </div>
        </div>
      </Modal>

      {/* Create Memory Modal */}
      <Modal
        open={showCreateModal}
        onClose={closeCreateModal}
        title="Create Memory"
      >
        <div className="space-y-4">
          {/* Agent ID */}
          <div>
            <label className="caption block mb-1.5">Agent ID</label>
            <input
              type="text"
              value={createAgentId}
              onChange={(e) => setCreateAgentId(e.target.value)}
              placeholder="agent-001 (optional)"
              className="input font-mono"
            />
          </div>

          {/* Content */}
          <div>
            <label className="caption block mb-1.5">Content</label>
            <textarea
              value={createContent}
              onChange={(e) => setCreateContent(e.target.value)}
              rows={4}
              placeholder="Memory content..."
              className="input font-mono resize-none"
            />
          </div>

          {/* Tier */}
          <div>
            <label className="caption block mb-1.5">Tier</label>
            <div className="flex gap-1.5">
              {(["hot", "warm", "cold"] as MemoryTier[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setCreateTier(t)}
                  className={`text-xs px-4 py-1.5 rounded-full transition-colors ${
                    createTier === t
                      ? TIER_BADGE[t]
                      : "badge badge--neutral"
                  }`}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Criticality */}
          <div>
            <label className="caption block mb-1.5">Criticality (0 - 1)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={createCriticality}
              onChange={(e) => setCreateCriticality(e.target.value)}
              className="input font-mono"
            />
          </div>

          {/* Source */}
          <div>
            <label className="caption block mb-1.5">Source</label>
            <input
              type="text"
              value={createSource}
              onChange={(e) => setCreateSource(e.target.value)}
              placeholder="e.g. manual, api, ingestion (optional)"
              className="input"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button onClick={closeCreateModal} className="btn btn--secondary">
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={isCreating || !createContent.trim()}
              className="btn btn--primary"
            >
              {isCreating ? "Creating..." : "Create Memory"}
            </button>
          </div>
        </div>
      </Modal>
    </PageTransition>
  );
}

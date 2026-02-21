"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Home,
  Search,
  BarChart3,
  Activity,
  Layers,
  Network,
  Shield,
  Database,
  Target,
  Zap,
  FileText,
  Archive,
  Trash2,
  Download,
} from "lucide-react";
import { mockMemories, mockQueryTraces } from "@/lib/mock-data";
import { formatMemoryId, formatTimestamp, truncateText } from "@/lib/utils";
import type { MemoryStatus } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────

type ResultCategory = "Pages" | "Memories" | "Traces" | "Actions";

interface CommandResult {
  id: string;
  category: ResultCategory;
  icon: React.ReactNode;
  label: string;
  detail?: string;
  badge?: { text: string; color: string };
  href?: string;
  memoryId?: string;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onSelectMemory: (memoryId: string) => void;
}

// ── Static entries ────────────────────────────────────────────────────────

const PAGE_ENTRIES: CommandResult[] = [
  { id: "p-overview", category: "Pages", icon: <Home size={15} />, label: "Command Center", href: "/overview" },
  { id: "p-attribution", category: "Pages", icon: <Search size={15} />, label: "Attribution Explorer", href: "/attribution" },
  { id: "p-leaderboard", category: "Pages", icon: <BarChart3 size={15} />, label: "Memory Leaderboard", href: "/attribution/leaderboard" },
  { id: "p-health", category: "Pages", icon: <Activity size={15} />, label: "Health Monitor", href: "/health" },
  { id: "p-lifecycle", category: "Pages", icon: <Layers size={15} />, label: "Budget Optimizer", href: "/lifecycle" },
  { id: "p-compliance", category: "Pages", icon: <Network size={15} />, label: "Provenance Graph", href: "/compliance" },
  { id: "p-audit", category: "Pages", icon: <Shield size={15} />, label: "Audit Trail", href: "/compliance/audit" },
];

const ACTION_ENTRIES: CommandResult[] = [
  { id: "a-archive", category: "Actions", icon: <Archive size={15} />, label: "Archive memory...", detail: "Move a memory to cold storage", href: "/lifecycle" },
  { id: "a-compliance", category: "Actions", icon: <Shield size={15} />, label: "Run compliance check", detail: "Scan for GDPR violations", href: "/compliance" },
  { id: "a-deletion", category: "Actions", icon: <Trash2 size={15} />, label: "New deletion request", detail: "Initiate SISA-compliant erasure", href: "/compliance" },
  { id: "a-export", category: "Actions", icon: <Download size={15} />, label: "Export audit trail", detail: "Download compliance report as JSON", href: "/compliance/audit" },
];

// ── Status badge config ──────────────────────────────────────────────────

const STATUS_BADGE: Record<MemoryStatus, { text: string; color: string }> = {
  active: { text: "active", color: "bg-emerald-500/15 text-emerald-400" },
  archived: { text: "archived", color: "bg-zinc-500/15 text-zinc-400" },
  deleted: { text: "deleted", color: "bg-rose-500/15 text-rose-400" },
  pending_deletion: { text: "pending", color: "bg-amber-500/15 text-amber-400" },
};

// ── Fuzzy match ──────────────────────────────────────────────────────────

function fuzzyMatch(query: string, text: string): boolean {
  if (!query) return true;
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
  const t = text.toLowerCase();
  return tokens.every((tok) => t.includes(tok));
}

// ── Component ─────────────────────────────────────────────────────────────

export function CommandPalette({ open, onClose, onSelectMemory }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Build memory entries
  const memoryEntries = useMemo<CommandResult[]>(() => {
    return mockMemories.map((m) => ({
      id: `mem-${m.id}`,
      category: "Memories" as const,
      icon: <Database size={15} />,
      label: `${formatMemoryId(m.id)} — "${truncateText(m.content, 50)}"`,
      badge: STATUS_BADGE[m.status],
      memoryId: m.id,
    }));
  }, []);

  // Build trace entries
  const traceEntries = useMemo<CommandResult[]>(() => {
    return mockQueryTraces.map((t) => ({
      id: `trace-${t.id}`,
      category: "Traces" as const,
      icon: <Target size={15} />,
      label: `Trace ${t.id.toUpperCase()} — "${truncateText(t.query, 45)}"`,
      detail: `${t.agentId} · ${formatTimestamp(t.timestamp)}`,
      href: `/attribution/${t.id}`,
    }));
  }, []);

  // Filtered results by category with limits
  const grouped = useMemo(() => {
    const groups: { category: ResultCategory; items: CommandResult[] }[] = [];

    const matchPages = PAGE_ENTRIES.filter(
      (e) => fuzzyMatch(query, e.label)
    );
    if (matchPages.length > 0) groups.push({ category: "Pages", items: matchPages });

    const matchMem = memoryEntries.filter(
      (e) => fuzzyMatch(query, e.label) || (e.memoryId && fuzzyMatch(query, e.memoryId))
    ).slice(0, 5);
    if (matchMem.length > 0) groups.push({ category: "Memories", items: matchMem });

    const matchTraces = traceEntries.filter(
      (e) => fuzzyMatch(query, e.label) || (e.detail && fuzzyMatch(query, e.detail))
    ).slice(0, 5);
    if (matchTraces.length > 0) groups.push({ category: "Traces", items: matchTraces });

    const matchActions = ACTION_ENTRIES.filter(
      (e) => fuzzyMatch(query, e.label) || (e.detail && fuzzyMatch(query, e.detail))
    );
    if (matchActions.length > 0) groups.push({ category: "Actions", items: matchActions });

    return groups;
  }, [query, memoryEntries, traceEntries]);

  const flatItems = useMemo(() => grouped.flatMap((g) => g.items), [grouped]);

  // Reset selection when query changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Auto-focus input on open
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
    if (el) el.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  // Select an item
  const selectItem = useCallback(
    (item: CommandResult) => {
      onClose();
      if (item.memoryId) {
        onSelectMemory(item.memoryId);
      } else if (item.href) {
        router.push(item.href);
      }
    },
    [onClose, onSelectMemory, router]
  );

  // Keyboard handler for the palette
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, flatItems.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const item = flatItems[selectedIndex];
        if (item) selectItem(item);
        return;
      }
    },
    [flatItems, selectedIndex, selectItem, onClose]
  );

  let runningIndex = 0;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

          {/* Panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="relative w-full max-w-2xl bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={handleKeyDown}
          >
            {/* Search input */}
            <div className="border-b border-zinc-800 px-5 py-4 flex items-center gap-3">
              <Search size={18} strokeWidth={1.5} className="text-zinc-500 shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search memories, traces, pages..."
                className="flex-1 bg-transparent text-lg font-mono text-zinc-100 placeholder:text-zinc-600 outline-none focus:ring-0"
              />
              <kbd className="hidden sm:inline-block text-[11px] text-zinc-600 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 font-mono">
                ESC
              </kbd>
            </div>

            {/* Results */}
            <div ref={listRef} className="max-h-[360px] overflow-y-auto">
              {grouped.length === 0 && (
                <div className="px-5 py-10 text-center text-zinc-600 text-[13px]">
                  No results for &ldquo;{query}&rdquo;
                </div>
              )}

              {grouped.map((group) => (
                <div key={group.category}>
                  {/* Category header */}
                  <div className="px-5 py-1.5 bg-zinc-900/50 sticky top-0">
                    <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-500">
                      {group.category}
                    </span>
                  </div>

                  {/* Items */}
                  {group.items.map((item) => {
                    const idx = runningIndex++;
                    const isActive = idx === selectedIndex;

                    return (
                      <button
                        key={item.id}
                        data-index={idx}
                        className={`w-full text-left px-5 py-2.5 flex items-center gap-3 transition-colors cursor-pointer ${
                          isActive
                            ? "bg-zinc-800"
                            : "hover:bg-zinc-800/40"
                        }`}
                        onClick={() => selectItem(item)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        role="option"
                        aria-selected={isActive}
                      >
                        {/* Icon */}
                        <span className={`shrink-0 ${isActive ? "text-emerald-400" : "text-zinc-500"}`}>
                          {item.icon}
                        </span>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <span className={`text-[13px] ${isActive ? "text-zinc-100" : "text-zinc-300"} truncate block`}>
                            {item.label}
                          </span>
                          {item.detail && (
                            <span className="text-[11px] text-zinc-600 truncate block mt-0.5">
                              {item.detail}
                            </span>
                          )}
                        </div>

                        {/* Badge */}
                        {item.badge && (
                          <span className={`shrink-0 px-1.5 py-0.5 text-[9px] font-mono rounded ${item.badge.color}`}>
                            {item.badge.text}
                          </span>
                        )}

                        {/* Shortcut hint for pages */}
                        {item.category === "Pages" && isActive && (
                          <kbd className="shrink-0 text-[10px] text-zinc-600 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 font-mono">
                            ↵
                          </kbd>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="border-t border-zinc-800 px-5 py-2.5 flex items-center justify-between text-[11px] text-zinc-600">
              <div className="flex items-center gap-4">
                <span>
                  <kbd className="bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 mr-1 font-mono text-[10px]">↑↓</kbd>
                  Navigate
                </span>
                <span>
                  <kbd className="bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 mr-1 font-mono text-[10px]">↵</kbd>
                  Select
                </span>
                <span>
                  <kbd className="bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 mr-1 font-mono text-[10px]">esc</kbd>
                  Close
                </span>
              </div>
              <span className="font-mono">
                {flatItems.length} result{flatItems.length !== 1 ? "s" : ""}
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

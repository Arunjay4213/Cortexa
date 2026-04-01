"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Target,
  Database,
  HeartPulse,
  Users,
  Cpu,
  Shield,
  FlaskConical,
  GitBranch,
  Search,
  Zap,
  Plus,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CommandPaletteProps {
  memories?: { id: string; content: string }[];
  agents?: { agent_id: string }[];
  transactions?: { id: string; query_text: string }[];
}

interface CommandResult {
  id: string;
  label: string;
  detail?: string;
  category: "Pages" | "Entities" | "Actions";
  href: string;
  icon?: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Static entries
// ---------------------------------------------------------------------------

const PAGE_ENTRIES: CommandResult[] = [
  { id: "page-overview", label: "Overview", category: "Pages", href: "/", icon: <LayoutDashboard size={14} /> },
  { id: "page-attribution", label: "Attribution", category: "Pages", href: "/attribution", icon: <Target size={14} /> },
  { id: "page-memories", label: "Memories", category: "Pages", href: "/memories", icon: <Database size={14} /> },
  { id: "page-health", label: "Health", category: "Pages", href: "/health", icon: <HeartPulse size={14} /> },
  { id: "page-fleet", label: "Fleet", category: "Pages", href: "/fleet", icon: <Users size={14} /> },
  { id: "page-engine", label: "Engine", category: "Pages", href: "/engine", icon: <Cpu size={14} /> },
  { id: "page-grounding", label: "Grounding", category: "Pages", href: "/grounding", icon: <Shield size={14} /> },
  { id: "page-staging", label: "Staging", category: "Pages", href: "/staging", icon: <FlaskConical size={14} /> },
  { id: "page-snapshots", label: "Snapshots", category: "Pages", href: "/snapshots", icon: <GitBranch size={14} /> },
];

const ACTION_ENTRIES: CommandResult[] = [
  {
    id: "action-contradiction",
    label: "Run contradiction detection",
    category: "Actions",
    href: "/health",
    icon: <Zap size={14} />,
  },
  {
    id: "action-create-memory",
    label: "Create memory",
    category: "Actions",
    href: "/memories?create=true",
    icon: <Plus size={14} />,
  },
];

// ---------------------------------------------------------------------------
// Fuzzy match
// ---------------------------------------------------------------------------

function fuzzyMatch(query: string, text: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  const tokens = q.split(/\s+/).filter(Boolean);
  return tokens.every((tok) => t.includes(tok));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CommandPalette({ memories = [], agents = [], transactions = [] }: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const entityEntries = useMemo<CommandResult[]>(() => {
    const entries: CommandResult[] = [];
    for (const m of memories) {
      entries.push({
        id: `memory-${m.id}`,
        label: `Memory ${m.id.slice(0, 8)}`,
        detail: m.content.length > 60 ? m.content.slice(0, 60) + "..." : m.content,
        category: "Entities",
        href: `/memories?selected=${m.id}`,
        icon: <Database size={14} />,
      });
    }
    for (const a of agents) {
      entries.push({
        id: `agent-${a.agent_id}`,
        label: `Agent ${a.agent_id}`,
        category: "Entities",
        href: `/fleet?selected=${a.agent_id}`,
        icon: <Users size={14} />,
      });
    }
    for (const t of transactions) {
      entries.push({
        id: `txn-${t.id}`,
        label: `Transaction ${t.id.slice(0, 8)}`,
        detail: t.query_text.length > 60 ? t.query_text.slice(0, 60) + "..." : t.query_text,
        category: "Entities",
        href: `/attribution?selected=${t.id}`,
        icon: <Target size={14} />,
      });
    }
    return entries;
  }, [memories, agents, transactions]);

  const allEntries = useMemo(
    () => [...PAGE_ENTRIES, ...entityEntries, ...ACTION_ENTRIES],
    [entityEntries]
  );

  const filtered = useMemo(() => {
    return allEntries.filter(
      (e) =>
        fuzzyMatch(query, e.label) ||
        (e.detail && fuzzyMatch(query, e.detail))
    );
  }, [allEntries, query]);

  const grouped = useMemo(() => {
    const order: CommandResult["category"][] = ["Pages", "Entities", "Actions"];
    const groups: { category: string; items: CommandResult[] }[] = [];
    for (const cat of order) {
      const items = filtered.filter((r) => r.category === cat);
      if (items.length > 0) {
        groups.push({ category: cat, items });
      }
    }
    return groups;
  }, [filtered]);

  const flatItems = useMemo(() => grouped.flatMap((g) => g.items), [grouped]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    function handleGlobalKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => {
          if (!prev) {
            setQuery("");
            setSelectedIndex(0);
          }
          return !prev;
        });
      }
    }
    window.addEventListener("keydown", handleGlobalKey);
    return () => window.removeEventListener("keydown", handleGlobalKey);
  }, []);

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const selectItem = useCallback(
    (item: CommandResult) => {
      setOpen(false);
      router.push(item.href);
    },
    [router]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
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
    [flatItems, selectedIndex, selectItem]
  );

  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
    if (el) {
      el.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  let runningIndex = 0;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="relative w-full max-w-2xl bg-[var(--bg-surface-1)] border border-[var(--border-default)] rounded-2xl shadow-xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={handleKeyDown}
          >
            {/* Search input */}
            <div className="border-b border-[var(--border-default)] px-5 py-3.5 flex items-center gap-3">
              <Search size={16} className="text-[var(--text-ghost)] shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type a command or search..."
                className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-ghost)] outline-none"
                aria-label="Search commands"
              />
              <kbd className="hidden sm:inline-block text-[12px] text-[var(--text-ghost)] bg-[var(--bg-surface-3)] rounded-md px-1.5 py-0.5 font-mono">
                ESC
              </kbd>
            </div>

            {/* Results */}
            <div ref={listRef} className="max-h-[50vh] overflow-y-auto">
              {grouped.length === 0 && (
                <div className="px-5 py-10 text-center text-[var(--text-ghost)] text-sm">
                  No results found
                </div>
              )}

              {grouped.map((group) => (
                <div key={group.category}>
                  <div className="px-5 py-2 bg-[var(--bg-surface-2)]/50">
                    <span className="text-[12px] font-medium text-[var(--text-ghost)] uppercase tracking-wider">
                      {group.category}
                    </span>
                  </div>

                  {group.items.map((item) => {
                    const idx = runningIndex++;
                    const isSelected = idx === selectedIndex;

                    return (
                      <button
                        key={item.id}
                        data-index={idx}
                        className={`w-full text-left px-5 py-2.5 flex items-center gap-3 transition-colors cursor-pointer ${
                          isSelected
                            ? "bg-[var(--accent-muted)]"
                            : "hover:bg-[var(--bg-surface-2)]/50"
                        }`}
                        onClick={() => selectItem(item)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        role="option"
                        aria-selected={isSelected}
                      >
                        <span className={`shrink-0 ${isSelected ? "text-[var(--accent)]" : "text-[var(--text-ghost)]"}`}>
                          {item.icon}
                        </span>
                        <div className="flex-1 min-w-0">
                          <span
                            className={`text-[13px] ${
                              isSelected ? "text-[var(--text-primary)]" : "text-[var(--text-secondary)]"
                            }`}
                          >
                            {item.label}
                          </span>
                          {item.detail && (
                            <span className="block text-[12px] text-[var(--text-ghost)] truncate mt-0.5">
                              {item.detail}
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>

            {/* Footer */}
            <div className="border-t border-[var(--border-default)] px-5 py-2.5 flex items-center justify-between text-[12px] text-[var(--text-ghost)]">
              <div className="flex items-center gap-3">
                <span>
                  <kbd className="bg-[var(--bg-surface-3)] rounded-md px-1.5 py-0.5 mr-1 font-mono">&#8593;&#8595;</kbd>
                  Navigate
                </span>
                <span>
                  <kbd className="bg-[var(--bg-surface-3)] rounded-md px-1.5 py-0.5 mr-1 font-mono">&#8629;</kbd>
                  Select
                </span>
                <span>
                  <kbd className="bg-[var(--bg-surface-3)] rounded-md px-1.5 py-0.5 mr-1 font-mono">ESC</kbd>
                  Close
                </span>
              </div>
              <span>{flatItems.length} result{flatItems.length !== 1 ? "s" : ""}</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default CommandPalette;

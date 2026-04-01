"use client";

import { useMemo } from "react";
import { X, AlertTriangle } from "lucide-react";
import { mockMemories } from "@/lib/mock-data";
import { formatMemoryId, formatTimestamp } from "@/lib/utils";
import type { HealthAlert } from "@/lib/types";

interface ContradictionModalProps {
  alert: HealthAlert | null;
  onClose: () => void;
}

export function ContradictionModal({ alert, onClose }: ContradictionModalProps) {
  const memories = useMemo(() => {
    if (!alert || alert.memoryIds.length < 2) return [];
    return alert.memoryIds
      .map((id) => mockMemories.find((m) => m.id === id))
      .filter(Boolean) as (typeof mockMemories)[number][];
  }, [alert]);

  if (!alert || memories.length < 2) return null;

  const [memA, memB] = memories;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="bg-zinc-950 border border-zinc-800 rounded-lg w-full max-w-[700px] max-h-[85vh] overflow-y-auto shadow-2xl animate-scale-in"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 sticky top-0 bg-zinc-950 z-10">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-rose-400" />
              <span className="text-sm font-medium text-zinc-200">
                Resolve Contradiction
              </span>
              <span className="text-[11px] font-mono text-zinc-500">
                {alert.id.toUpperCase()}
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Description */}
          <div className="px-5 py-3 border-b border-zinc-800/50">
            <p className="text-[12px] text-zinc-400 leading-relaxed">
              {alert.description}
            </p>
          </div>

          {/* Side-by-side memory comparison */}
          <div className="grid grid-cols-2 gap-3 px-5 py-4">
            <MemoryCard memory={memA} label="Memory A" />
            <MemoryCard memory={memB} label="Memory B" />
          </div>

          {/* Resolution Options */}
          <div className="px-5 py-4 border-t border-zinc-800 space-y-2">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium mb-3">
              Resolution Options
            </div>

            <ResolutionOption
              label={`Keep ${formatMemoryId(memA.id)}, archive ${formatMemoryId(memB.id)}`}
              description={`${formatMemoryId(memA.id)} is considered canonical. ${formatMemoryId(memB.id)} will be archived and excluded from future retrievals.`}
              variant="default"
            />
            <ResolutionOption
              label={`Keep ${formatMemoryId(memB.id)}, archive ${formatMemoryId(memA.id)}`}
              description={`${formatMemoryId(memB.id)} is considered canonical. ${formatMemoryId(memA.id)} will be archived and excluded from future retrievals.`}
              variant="default"
            />
            <ResolutionOption
              label="Keep both (mark as preference evolution)"
              description="Both memories are valid but represent different points in time. The system will use temporal ordering to determine which is current."
              variant="default"
            />
            <ResolutionOption
              label="Consolidate into new memory"
              description="Merge both memories into a single consolidated memory that captures the full context and evolution of the information."
              variant="primary"
            />
          </div>
        </div>
      </div>
    </>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────

function MemoryCard({ memory, label }: { memory: (typeof mockMemories)[number]; label: string }) {
  const healthColor =
    memory.healthScore >= 0.8
      ? "text-emerald-400"
      : memory.healthScore >= 0.5
        ? "text-amber-400"
        : "text-rose-400";

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-md p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
            {label}
          </span>
          <span className="text-[12px] font-mono text-zinc-300 font-medium">
            {formatMemoryId(memory.id)}
          </span>
        </div>
        <span className={`text-[11px] font-mono ${healthColor}`}>
          {memory.healthScore.toFixed(2)}
        </span>
      </div>

      <p className="text-[13px] text-zinc-300 leading-relaxed font-mono mb-3 p-2 bg-zinc-800/50 rounded border border-zinc-700/50">
        {memory.content}
      </p>

      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <div>
          <span className="text-zinc-600">Created:</span>{" "}
          <span className="text-zinc-400 font-mono">{formatTimestamp(memory.createdAt)}</span>
        </div>
        <div>
          <span className="text-zinc-600">Last retrieved:</span>{" "}
          <span className="text-zinc-400 font-mono">{formatTimestamp(memory.lastRetrieved)}</span>
        </div>
        <div>
          <span className="text-zinc-600">Staleness:</span>{" "}
          <span className={`font-mono ${memory.stalenessScore > 0.5 ? "text-rose-400" : "text-zinc-400"}`}>
            {memory.stalenessScore.toFixed(2)}
          </span>
        </div>
        <div>
          <span className="text-zinc-600">Retrievals:</span>{" "}
          <span className="text-zinc-400 font-mono">{memory.retrievalCount}</span>
        </div>
      </div>
    </div>
  );
}

function ResolutionOption({
  label,
  description,
  variant = "default",
}: {
  label: string;
  description: string;
  variant?: "default" | "primary";
}) {
  return (
    <button
      className={`w-full text-left px-4 py-3 rounded-md border transition-all group ${
        variant === "primary"
          ? "border-emerald-500/30 bg-emerald-500/5 hover:bg-emerald-500/10 hover:border-emerald-500/50"
          : "border-zinc-800 hover:border-zinc-600 hover:bg-zinc-800/30"
      }`}
    >
      <div className={`text-[13px] font-medium mb-0.5 ${
        variant === "primary" ? "text-emerald-400" : "text-zinc-300"
      }`}>
        {label}
      </div>
      <div className="text-[11px] text-zinc-500 leading-relaxed">
        {description}
      </div>
    </button>
  );
}

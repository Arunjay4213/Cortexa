"use client";

import { useEffect, useRef, useMemo } from "react";
import { X, Archive, ShieldOff, AlertTriangle } from "lucide-react";
import { BarGauge } from "@/components/dashboard/BarGauge";
import { mockMemories, mockQueryTraces } from "@/lib/mock-data";
import {
  formatMemoryId,
  formatCurrency,
  formatTimestamp,
} from "@/lib/utils";

interface MemoryDetailPanelProps {
  memoryId: string | null;
  onClose: () => void;
}

export function MemoryDetailPanel({ memoryId, onClose }: MemoryDetailPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) onClose();
    };
    if (memoryId) {
      document.addEventListener("mousedown", handler);
      return () => document.removeEventListener("mousedown", handler);
    }
  }, [memoryId, onClose]);

  const memory = useMemo(
    () => (memoryId ? mockMemories.find((m) => m.id === memoryId) ?? null : null),
    [memoryId]
  );

  const attributionHistory = useMemo(() => {
    if (!memoryId) return [];
    return mockQueryTraces
      .filter((t) => t.memoriesRetrieved.some((m) => m.memoryId === memoryId))
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      .slice(-10)
      .map((t) => {
        const mem = t.memoriesRetrieved.find((m) => m.memoryId === memoryId)!;
        return { traceId: t.id, score: mem.attributionScore, timestamp: t.timestamp };
      });
  }, [memoryId]);

  if (!memoryId || !memory) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-40" />

      {/* Panel */}
      <div
        ref={panelRef}
        className="fixed top-0 right-0 h-screen w-[320px] z-50 flex flex-col animate-slide-in-right"
        style={{
          background: "var(--panel-bg)",
          borderLeft: "1px solid var(--panel-border)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 shrink-0"
          style={{ height: 44, borderBottom: "1px solid var(--panel-border)" }}
        >
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-mono font-medium" style={{ color: "var(--grafana-text-primary)" }}>
              {formatMemoryId(memory.id)}
            </span>
            <StatusBadge status={memory.status} />
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-sm transition-colors"
            style={{ color: "var(--grafana-text-muted)" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--panel-bg-hover)"; e.currentTarget.style.color = "var(--grafana-text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--grafana-text-muted)"; }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-5">
          {/* Full content */}
          <PanelSection label="Content">
            <p
              className="text-[13px] font-mono leading-relaxed p-3 rounded-sm"
              style={{
                background: "#0b0c0e",
                border: "1px solid var(--panel-border)",
                color: "var(--grafana-text-primary)",
              }}
            >
              {memory.content}
            </p>
            <div className="flex items-center gap-2 mt-2 text-[10px] font-mono" style={{ color: "var(--grafana-text-muted)" }}>
              <span>{memory.tokenCount} tokens</span>
              <span style={{ color: "var(--panel-border)" }}>&middot;</span>
              <span>{memory.type}</span>
              <span style={{ color: "var(--panel-border)" }}>&middot;</span>
              <span>Created {formatTimestamp(memory.createdAt)}</span>
            </div>
          </PanelSection>

          {/* Health */}
          <PanelSection label="Health">
            <div className="flex flex-col gap-2">
              <BarGauge
                label="Staleness"
                value={memory.stalenessScore}
                max={1}
                color={memory.stalenessScore > 0.7 ? "red" : memory.stalenessScore > 0.3 ? "yellow" : "green"}
                display={memory.stalenessScore.toFixed(2)}
              />
              <BarGauge
                label="Drift"
                value={memory.driftScore}
                max={1}
                color={memory.driftScore > 0.5 ? "red" : memory.driftScore > 0.2 ? "yellow" : "green"}
                display={memory.driftScore.toFixed(2)}
              />
              <BarGauge
                label="Health"
                value={memory.healthScore}
                max={1}
                color={memory.healthScore >= 0.7 ? "green" : memory.healthScore >= 0.4 ? "yellow" : "red"}
                display={memory.healthScore.toFixed(2)}
              />
            </div>

            {memory.contradictionsWith.length > 0 && (
              <div
                className="mt-3 flex items-center gap-2 px-3 py-2 rounded-sm"
                style={{ background: "var(--stat-red-bg)", border: "1px solid rgba(242,73,92,0.25)" }}
              >
                <AlertTriangle size={13} style={{ color: "var(--grafana-red)" }} className="shrink-0" />
                <span className="text-[11px]" style={{ color: "var(--grafana-red)" }}>
                  Contradicts: {memory.contradictionsWith.map((id) => formatMemoryId(id)).join(", ")}
                </span>
              </div>
            )}
          </PanelSection>

          {/* Financial */}
          <PanelSection label="Financial">
            <div className="grid grid-cols-2 gap-2">
              <MiniStat label="Revenue/day" value={formatCurrency(memory.revenuePerDay)} color="var(--grafana-green)" />
              <MiniStat label="Cost/day" value={formatCurrency(memory.costPerDay)} color="var(--grafana-red)" />
              <MiniStat label="ROI" value={`${memory.roi > 0 ? "+" : ""}${memory.roi.toFixed(1)}x`} color={memory.roi >= 0 ? "var(--grafana-green)" : "var(--grafana-red)"} />
              <MiniStat label="Sharpe" value={memory.sharpeRatio.toFixed(1)} color={memory.sharpeRatio >= 1 ? "var(--grafana-green)" : memory.sharpeRatio >= 0 ? "var(--grafana-text-primary)" : "var(--grafana-red)"} />
            </div>
          </PanelSection>

          {/* Retrieval stats */}
          <PanelSection label="Retrieval">
            <div className="grid grid-cols-2 gap-2">
              <MiniStat label="Last Retrieved" value={formatTimestamp(memory.lastRetrieved)} color="var(--grafana-text-primary)" />
              <MiniStat label="Count" value={memory.retrievalCount.toLocaleString()} color="var(--grafana-text-primary)" />
            </div>
          </PanelSection>

          {/* Attribution history */}
          {attributionHistory.length > 0 && (
            <PanelSection label="Attribution History">
              <div className="flex flex-col gap-1">
                {attributionHistory.map((h) => (
                  <div key={h.traceId} className="flex items-center justify-between text-[11px]">
                    <span className="font-mono" style={{ color: "#6e9fff" }}>{h.traceId.toUpperCase()}</span>
                    <div className="flex items-center gap-3">
                      <span className="font-mono" style={{ color: "var(--grafana-text-muted)" }}>{formatTimestamp(h.timestamp)}</span>
                      <span className="font-mono tabular-nums w-10 text-right" style={{ color: "var(--grafana-text-primary)" }}>{h.score.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </PanelSection>
          )}
        </div>

        {/* Actions */}
        <div className="px-4 py-3 flex gap-2 shrink-0" style={{ borderTop: "1px solid var(--panel-border)" }}>
          <GrafanaButton icon={Archive} label="Archive" />
          <GrafanaButton icon={ShieldOff} label="Invalidate" />
        </div>
      </div>
    </>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────

function PanelSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider font-medium mb-2" style={{ color: "var(--grafana-text-muted)" }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function MiniStat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="p-2.5 rounded-sm" style={{ background: "#0b0c0e", border: "1px solid var(--panel-border)" }}>
      <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--grafana-text-muted)" }}>{label}</div>
      <div className="text-[14px] font-mono tabular-nums" style={{ color }}>{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    active: { bg: "var(--stat-green-bg)", color: "var(--grafana-green)" },
    archived: { bg: "var(--panel-bg-hover)", color: "var(--grafana-text-muted)" },
    deleted: { bg: "var(--panel-bg-hover)", color: "var(--grafana-text-disabled)" },
    pending_deletion: { bg: "var(--stat-red-bg)", color: "var(--grafana-red)" },
  };
  const s = map[status] ?? map.active;
  return (
    <span className="text-[9px] font-medium uppercase px-1.5 py-0.5 rounded-sm" style={{ background: s.bg, color: s.color }}>
      {status.replace("_", " ")}
    </span>
  );
}

function GrafanaButton({ icon: Icon, label }: { icon: React.ComponentType<{ size?: number }>; label: string }) {
  return (
    <button
      className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-sm text-[12px] font-medium transition-colors"
      style={{ background: "transparent", border: "1px solid var(--panel-border)", color: "var(--grafana-text-primary)" }}
      onMouseEnter={(e) => e.currentTarget.style.background = "var(--panel-bg-hover)"}
      onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

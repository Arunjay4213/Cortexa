"use client";

import { useState, useMemo, useCallback } from "react";
import { GrafanaPanel } from "@/components/dashboard/GrafanaPanel";
import { formatMemoryId, truncateText } from "@/lib/utils";
import type { StatementAttribution } from "@/lib/types";

interface StatementHeatmapProps {
  statements: StatementAttribution[];
  onMemoryClick: (memoryId: string) => void;
}

function scoreToColor(score: number): string {
  if (score <= 0) return "transparent";
  const intensity = Math.min(score, 1);
  return `rgba(115, 191, 105, ${intensity * 0.8})`;
}

function scoreToTextColor(score: number): string {
  if (score > 0.5) return "#d8d9da";
  if (score > 0.2) return "#8e8e8e";
  return "#464c54";
}

export function StatementHeatmap({ statements, onMemoryClick }: StatementHeatmapProps) {
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: string } | null>(null);

  const allMemoryIds = useMemo(() => {
    const ids = new Set<string>();
    for (const s of statements) {
      for (const ms of s.memoryScores) ids.add(ms.memoryId);
    }
    return Array.from(ids);
  }, [statements]);

  const scoreMatrix = useMemo(() => {
    return statements.map((s) => {
      const map: Record<string, number> = {};
      for (const ms of s.memoryScores) map[ms.memoryId] = ms.score;
      return map;
    });
  }, [statements]);

  const handleCellClick = useCallback(
    (_stmtIdx: number, memoryId: string) => {
      onMemoryClick(memoryId);
    },
    [onMemoryClick]
  );

  if (statements.length === 0) return null;

  return (
    <GrafanaPanel
      title="Statement × Memory Heatmap (ContextCite)"
      headerRight={
        <span className="text-[10px] font-mono" style={{ color: "var(--grafana-text-muted)" }}>
          {statements.length} statements × {allMemoryIds.length} memories
        </span>
      }
      noPadding
    >
      <div className="overflow-x-auto px-4 py-4">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th
                className="text-left text-[11px] font-medium pb-2 pr-3 min-w-[200px]"
                style={{ color: "var(--grafana-text-secondary)" }}
              >
                Statement
              </th>
              {allMemoryIds.map((id) => (
                <th
                  key={id}
                  className="text-center text-[10px] font-mono font-medium pb-2 px-1 min-w-[64px] cursor-pointer transition-colors"
                  style={{ color: hoveredCell?.col === id ? "var(--grafana-green)" : "var(--grafana-text-secondary)" }}
                  onClick={() => onMemoryClick(id)}
                >
                  {formatMemoryId(id)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {statements.map((stmt, stmtIdx) => (
              <tr key={stmtIdx}>
                <td
                  className="py-1.5 pr-3 text-[12px] font-mono align-top"
                  style={{ color: hoveredCell?.row === stmtIdx ? "var(--grafana-text-primary)" : "var(--grafana-text-secondary)" }}
                  title={stmt.statement}
                >
                  {truncateText(stmt.statement, 50)}
                </td>
                {allMemoryIds.map((memId) => {
                  const score = scoreMatrix[stmtIdx][memId] ?? 0;
                  const isHovered = hoveredCell?.row === stmtIdx && hoveredCell?.col === memId;
                  return (
                    <td key={memId} className="py-1.5 px-1">
                      <button
                        onClick={() => handleCellClick(stmtIdx, memId)}
                        onMouseEnter={() => setHoveredCell({ row: stmtIdx, col: memId })}
                        onMouseLeave={() => setHoveredCell(null)}
                        className="w-full h-8 rounded-sm text-[11px] font-mono tabular-nums transition-all"
                        style={{
                          backgroundColor: score > 0 ? scoreToColor(score) : "var(--panel-bg)",
                          color: scoreToTextColor(score),
                          border: isHovered ? "1px solid var(--grafana-green)" : "1px solid var(--panel-border)",
                        }}
                        title={`${truncateText(stmt.statement, 40)}\n${formatMemoryId(memId)}: ${score.toFixed(3)}`}
                      >
                        {score > 0 ? score.toFixed(2) : ""}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="px-4 pb-3 flex items-center gap-4 text-[10px]" style={{ color: "var(--grafana-text-muted)" }}>
        <span>Intensity = attribution score</span>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm" style={{ background: "rgba(115,191,105,0.16)" }} />
          <span>Low</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm" style={{ background: "rgba(115,191,105,0.48)" }} />
          <span>Medium</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm" style={{ background: "rgba(115,191,105,0.80)" }} />
          <span>High</span>
        </div>
      </div>
    </GrafanaPanel>
  );
}

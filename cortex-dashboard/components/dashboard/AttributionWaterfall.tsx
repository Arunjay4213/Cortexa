"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { GrafanaPanel } from "@/components/dashboard/GrafanaPanel";
import { formatMemoryId, truncateText } from "@/lib/utils";
import type { RetrievedMemory } from "@/lib/types";

interface AttributionWaterfallProps {
  memories: RetrievedMemory[];
  onMemoryClick: (memoryId: string) => void;
}

function barColor(healthStatus: RetrievedMemory["healthStatus"]): string {
  switch (healthStatus) {
    case "stale":
    case "contradictory":
      return "#f2495c";
    case "drifted":
      return "#ff9830";
    default:
      return "#73bf69";
  }
}

export function AttributionWaterfall({ memories, onMemoryClick }: AttributionWaterfallProps) {
  const sorted = useMemo(
    () => [...memories].sort((a, b) => b.attributionScore - a.attributionScore),
    [memories]
  );

  const chartData = useMemo(
    () =>
      sorted.map((m) => ({
        memoryId: m.memoryId,
        label: `${formatMemoryId(m.memoryId)} ${truncateText(m.content, 28)}`,
        score: m.attributionScore,
        healthStatus: m.healthStatus,
        content: m.content,
      })),
    [sorted]
  );

  return (
    <GrafanaPanel
      title="Memory Attribution Scores"
      headerRight={
        <span className="text-[10px] font-mono" style={{ color: "var(--grafana-text-muted)" }}>
          {memories.length} memories &middot; threshold 0.10
        </span>
      }
    >
      <ResponsiveContainer width="100%" height={Math.max(sorted.length * 44, 120)}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 4, right: 16, bottom: 4, left: 0 }}
          barCategoryGap="20%"
        >
          <CartesianGrid
            stroke="var(--grid-line)"
            strokeDasharray="none"
            horizontal={false}
          />
          <XAxis
            type="number"
            domain={[0, 1]}
            tickCount={6}
            tick={{ fontSize: 11, fill: "var(--axis-text)", fontFamily: "var(--font-mono)" }}
            axisLine={{ stroke: "var(--panel-border)" }}
            tickLine={{ stroke: "var(--panel-border)" }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={200}
            tick={{ fontSize: 11, fill: "var(--grafana-text-secondary)", fontFamily: "var(--font-mono)" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.03)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const d = payload[0].payload as (typeof chartData)[number];
              return (
                <div
                  className="px-3 py-2"
                  style={{
                    background: "var(--panel-bg)",
                    border: "1px solid var(--panel-border)",
                    borderRadius: "var(--panel-radius)",
                  }}
                >
                  <div className="text-[12px] font-mono" style={{ color: "var(--grafana-text-primary)" }}>
                    {formatMemoryId(d.memoryId)}
                  </div>
                  <div className="text-[11px] mt-0.5" style={{ color: "var(--grafana-text-secondary)" }}>
                    Score: <span className="font-mono" style={{ color: "var(--grafana-text-primary)" }}>{d.score.toFixed(3)}</span>
                  </div>
                  <div className="text-[11px] mt-0.5" style={{ color: "var(--grafana-text-muted)" }}>
                    {truncateText(d.content, 60)}
                  </div>
                </div>
              );
            }}
          />
          <ReferenceLine
            x={0.1}
            stroke="#464c54"
            strokeDasharray="5 3"
            label={{
              value: "threshold",
              position: "top",
              fill: "#464c54",
              fontSize: 10,
            }}
          />
          <Bar
            dataKey="score"
            radius={[0, 2, 2, 0]}
            onClick={(data) => onMemoryClick((data as unknown as { memoryId: string }).memoryId)}
            style={{ cursor: "pointer" }}
          >
            {chartData.map((entry) => (
              <Cell key={entry.memoryId} fill={barColor(entry.healthStatus)} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </GrafanaPanel>
  );
}

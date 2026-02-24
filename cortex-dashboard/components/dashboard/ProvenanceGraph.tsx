"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import * as d3 from "d3";
import { mockProvenanceNodes, mockProvenanceEdges } from "@/lib/mock-data";
import type {
  ProvenanceNode,
  ProvenanceEdge,
  ProvenanceNodeType,
  ProvenanceEdgeType,
} from "@/lib/types";

// ── Grafana-palette styling maps ─────────────────────────────────────────

const NODE_COLORS: Record<ProvenanceNodeType, string> = {
  interaction: "#5794f2",
  memory: "#73bf69",
  summary: "#b877d9",
  embedding: "#464c54",
  response: "#d8d9da",
};

const NODE_SIZES: Record<ProvenanceNodeType, number> = {
  interaction: 8,
  memory: 7,
  summary: 6,
  embedding: 4,
  response: 7,
};

const EDGE_COLORS: Record<ProvenanceEdgeType, string> = {
  creation: "#73bf69",
  attribution: "#5794f2",
  derivation: "#464c54",
};

const EDGE_DASHES: Record<ProvenanceEdgeType, string> = {
  creation: "",
  attribution: "4 3",
  derivation: "2 2",
};

// ── Types ────────────────────────────────────────────────────────────────

interface SimNode extends ProvenanceNode {
  x: number;
  y: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimEdge {
  id: string;
  source: SimNode;
  target: SimNode;
  type: ProvenanceEdgeType;
  weight?: number;
}

interface ProvenanceGraphProps {
  selectedNodeId: string | null;
  onSelectNode: (node: ProvenanceNode | null) => void;
  highlightUserId: string | null;
  deletingUserId: string | null;
  visibleTypes: Set<ProvenanceNodeType>;
}

// ── Component ────────────────────────────────────────────────────────────

export function ProvenanceGraph({
  selectedNodeId,
  onSelectNode,
  highlightUserId,
  deletingUserId,
  visibleTypes,
}: ProvenanceGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const gRef = useRef<SVGGElement>(null);
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [simEdges, setSimEdges] = useState<SimEdge[]>([]);
  const [initialized, setInitialized] = useState(false);

  // Compute the set of reachable nodes for the highlighted user
  const highlightedNodeIds = useMemo(() => {
    if (!highlightUserId) return null;
    const ids = new Set<string>();
    for (const n of mockProvenanceNodes) {
      if (n.userId === highlightUserId) ids.add(n.id);
    }
    let frontier = new Set(ids);
    for (let depth = 0; depth < 4; depth++) {
      const next = new Set<string>();
      for (const e of mockProvenanceEdges) {
        if (frontier.has(e.source) && !ids.has(e.target)) {
          ids.add(e.target);
          next.add(e.target);
        }
      }
      if (next.size === 0) break;
      frontier = next;
    }
    return ids;
  }, [highlightUserId]);

  // Deleting animation: which nodes to fade
  const deletingNodeIds = useMemo(() => {
    if (!deletingUserId) return null;
    const ids = new Set<string>();
    for (const n of mockProvenanceNodes) {
      if (n.userId === deletingUserId) ids.add(n.id);
    }
    let frontier = new Set(ids);
    for (let depth = 0; depth < 4; depth++) {
      const next = new Set<string>();
      for (const e of mockProvenanceEdges) {
        if (frontier.has(e.source) && !ids.has(e.target)) {
          const hasOtherSource = mockProvenanceEdges.some(
            (oe) =>
              oe.target === e.target && !ids.has(oe.source) && oe.id !== e.id
          );
          if (!hasOtherSource) {
            ids.add(e.target);
            next.add(e.target);
          }
        }
      }
      if (next.size === 0) break;
      frontier = next;
    }
    return ids;
  }, [deletingUserId]);

  // Run force simulation once
  useEffect(() => {
    const nodeMap = new Map<string, SimNode>();
    const nodes: SimNode[] = mockProvenanceNodes.map((n) => {
      const sn = { ...n, x: 0, y: 0 } as SimNode;
      nodeMap.set(n.id, sn);
      return sn;
    });

    const edges: SimEdge[] = [];
    for (const e of mockProvenanceEdges) {
      const src = nodeMap.get(e.source);
      const tgt = nodeMap.get(e.target);
      if (src && tgt) {
        edges.push({
          id: e.id,
          source: src,
          target: tgt,
          type: e.type,
          weight: e.weight,
        });
      }
    }

    const sim = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(edges)
          .id((d) => (d as SimNode).id)
          .distance(25)
          .strength(0.3)
      )
      .force(
        "charge",
        d3.forceManyBody().strength(-30).distanceMax(150)
      )
      .force("center", d3.forceCenter(0, 0))
      .force("collision", d3.forceCollide().radius(8))
      .force("x", d3.forceX().strength(0.02))
      .force("y", d3.forceY().strength(0.02))
      .alphaDecay(0.02)
      .stop();

    for (let i = 0; i < 250; i++) sim.tick();

    setSimNodes([...nodes]);
    setSimEdges([...edges]);
    setInitialized(true);
  }, []);

  // D3 zoom
  useEffect(() => {
    if (!svgRef.current || !gRef.current || !initialized) return;

    const svg = d3.select(svgRef.current);
    const g = d3.select(gRef.current);

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    const bounds = gRef.current.getBBox();
    if (bounds.width > 0) {
      const svgRect = svgRef.current.getBoundingClientRect();
      const scale = Math.min(
        svgRect.width / (bounds.width + 60),
        svgRect.height / (bounds.height + 60),
        1.5
      );
      const tx =
        svgRect.width / 2 - (bounds.x + bounds.width / 2) * scale;
      const ty =
        svgRect.height / 2 - (bounds.y + bounds.height / 2) * scale;
      svg.call(
        zoom.transform,
        d3.zoomIdentity.translate(tx, ty).scale(scale)
      );
    }

    return () => {
      svg.on(".zoom", null);
    };
  }, [initialized]);

  const handleNodeClick = useCallback(
    (node: SimNode) => {
      const original =
        mockProvenanceNodes.find((n) => n.id === node.id) ?? null;
      onSelectNode(original);
    },
    [onSelectNode]
  );

  if (!initialized) {
    return (
      <div
        className="w-full h-full flex items-center justify-center text-[13px]"
        style={{ color: "var(--grafana-text-muted)" }}
      >
        Computing graph layout...
      </div>
    );
  }

  return (
    <svg
      ref={svgRef}
      className="w-full h-full"
      style={{ background: "var(--panel-bg)", cursor: "grab" }}
    >
      <g ref={gRef}>
        {/* Edges */}
        {simEdges.map((edge) => {
          const srcVisible = visibleTypes.has(edge.source.type);
          const tgtVisible = visibleTypes.has(edge.target.type);
          if (!srcVisible || !tgtVisible) return null;

          const isHighlighted =
            highlightedNodeIds &&
            highlightedNodeIds.has(edge.source.id) &&
            highlightedNodeIds.has(edge.target.id);
          const isDeleting =
            deletingNodeIds &&
            (deletingNodeIds.has(edge.source.id) ||
              deletingNodeIds.has(edge.target.id));
          const isDimmed = highlightedNodeIds && !isHighlighted;

          return (
            <line
              key={edge.id}
              x1={edge.source.x}
              y1={edge.source.y}
              x2={edge.target.x}
              y2={edge.target.y}
              stroke={EDGE_COLORS[edge.type]}
              strokeWidth={isHighlighted ? 1.5 : 0.6}
              strokeDasharray={EDGE_DASHES[edge.type]}
              opacity={
                isDeleting ? 0.1 : isDimmed ? 0.08 : isHighlighted ? 0.7 : 0.2
              }
              style={
                isDeleting
                  ? { transition: "opacity 1.5s ease" }
                  : undefined
              }
            />
          );
        })}

        {/* Nodes */}
        {simNodes.map((node) => {
          if (!visibleTypes.has(node.type)) return null;

          const isSelected = selectedNodeId === node.id;
          const isHighlighted = highlightedNodeIds
            ? highlightedNodeIds.has(node.id)
            : false;
          const isDimmed = highlightedNodeIds && !isHighlighted;
          const isDeleting = deletingNodeIds
            ? deletingNodeIds.has(node.id)
            : false;
          const r = NODE_SIZES[node.type];
          let fill = NODE_COLORS[node.type];

          if (node.type === "memory" && deletingNodeIds?.has(node.id)) {
            fill = "#f2495c";
          }

          return (
            <g
              key={node.id}
              transform={`translate(${node.x},${node.y})`}
              onClick={() => handleNodeClick(node)}
              style={{
                cursor: "pointer",
                opacity: isDeleting ? 0.1 : isDimmed ? 0.15 : 1,
                transition: isDeleting ? "opacity 1.5s ease" : undefined,
              }}
            >
              {(isSelected || (isHighlighted && highlightedNodeIds)) && (
                <circle
                  r={r + 3}
                  fill="none"
                  stroke={isSelected ? "#ff9830" : fill}
                  strokeWidth={1.5}
                  opacity={0.5}
                />
              )}
              <circle
                r={r}
                fill={fill}
                opacity={isDimmed ? 0.3 : 0.85}
              />
            </g>
          );
        })}
      </g>
    </svg>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────

export function ProvenanceGraphLegend() {
  const nodeTypes: { type: ProvenanceNodeType; label: string }[] = [
    { type: "interaction", label: "Interaction" },
    { type: "memory", label: "Memory" },
    { type: "summary", label: "Summary" },
    { type: "embedding", label: "Embedding" },
    { type: "response", label: "Response" },
  ];

  const edgeTypes: {
    type: ProvenanceEdgeType;
    label: string;
    dash: string;
  }[] = [
    { type: "creation", label: "Creation", dash: "" },
    { type: "attribution", label: "Attribution", dash: "4 3" },
    { type: "derivation", label: "Derivation", dash: "2 2" },
  ];

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px]"
      style={{ color: "var(--grafana-text-muted)" }}
    >
      {nodeTypes.map(({ type, label }) => (
        <div key={type} className="flex items-center gap-1.5">
          <svg width={10} height={10}>
            <circle
              cx={5}
              cy={5}
              r={NODE_SIZES[type]}
              fill={NODE_COLORS[type]}
            />
          </svg>
          <span>{label}</span>
        </div>
      ))}
      <span style={{ color: "var(--panel-border)" }}>|</span>
      {edgeTypes.map(({ type, label, dash }) => (
        <div key={type} className="flex items-center gap-1.5">
          <svg width={20} height={10}>
            <line
              x1={0}
              y1={5}
              x2={20}
              y2={5}
              stroke={EDGE_COLORS[type]}
              strokeWidth={1.5}
              strokeDasharray={dash}
            />
          </svg>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

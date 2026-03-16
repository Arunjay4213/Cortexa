"use client";

import React, { useState, useMemo, useCallback } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { PageTransition } from "@/components/primitives/PageTransition";
import { PageHeader } from "@/components/primitives/PageHeader";
import { SectionHeader } from "@/components/primitives/SectionHeader";

// -- Math helpers (EAS calculator) -----------------------------------------------

function cosineSim(a: number[], b: number[]): number {
  let dot = 0,
    na = 0,
    nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  const d = Math.sqrt(na) * Math.sqrt(nb);
  return d === 0 ? 0 : dot / d;
}

function computeEAS(M: number[][], q: number[], r: number[]) {
  const raw = M.map(
    (m) => Math.max(cosineSim(m, r), 0) * Math.max(cosineSim(m, q), 0)
  );
  const total = raw.reduce((s, v) => s + v, 0);
  const scores =
    total > 0 ? raw.map((v) => v / total) : raw.map(() => 1 / M.length);
  return { scores, raw, total };
}

function gini(scores: number[]): number {
  if (scores.length === 0) return 0;
  const n = scores.length;
  const mean = scores.reduce((a, b) => a + b, 0) / n;
  if (mean === 0) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++)
    for (let j = 0; j < n; j++) sum += Math.abs(scores[i] - scores[j]);
  return sum / (2 * n * n * mean);
}

function snrDb(scores: number[]): number {
  const signal = scores
    .filter((s) => s > 0)
    .reduce((a, s) => a + s * s, 0);
  const noise =
    scores.filter((s) => s <= 0).reduce((a, s) => a + s * s, 0) + 1e-10;
  return 10 * Math.log10(signal / noise);
}

function normalize(v: number[]): number[] {
  const n = Math.sqrt(v.reduce((s, x) => s + x * x, 0));
  return n > 0 ? v.map((x) => x / n) : v;
}

function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// -- Data -----------------------------------------------------------------------

const FILE_TREE: {
  depth: number;
  name: string;
  type: "file" | "dir";
}[] = [
  { depth: 0, name: "pyproject.toml", type: "file" },
  { depth: 0, name: "alembic.ini", type: "file" },
  { depth: 0, name: "alembic/", type: "dir" },
  { depth: 1, name: "env.py", type: "file" },
  { depth: 1, name: "versions/", type: "dir" },
  { depth: 2, name: "001_initial_schema.py", type: "file" },
  { depth: 2, name: "002_calibration_and_cost_configs.py", type: "file" },
  { depth: 2, name: "003_phase2_additions.py", type: "file" },
  { depth: 0, name: "cortex/", type: "dir" },
  { depth: 1, name: "config.py", type: "file" },
  { depth: 1, name: "models.py", type: "file" },
  { depth: 1, name: "database.py", type: "file" },
  { depth: 1, name: "sdk/", type: "dir" },
  { depth: 2, name: "wrapper.py", type: "file" },
  { depth: 1, name: "attribution/", type: "dir" },
  { depth: 2, name: "__init__.py (attribution)", type: "file" },
  { depth: 2, name: "eas.py", type: "file" },
  { depth: 2, name: "contextcite.py", type: "file" },
  { depth: 2, name: "llm_provider.py", type: "file" },
  { depth: 2, name: "calibrator.py", type: "file" },
  { depth: 2, name: "contradiction.py", type: "file" },
  { depth: 1, name: "metrics/", type: "dir" },
  { depth: 2, name: "calculator.py", type: "file" },
  { depth: 1, name: "api/", type: "dir" },
  { depth: 2, name: "app.py", type: "file" },
  { depth: 2, name: "memories.py", type: "file" },
  { depth: 2, name: "transactions.py", type: "file" },
  { depth: 2, name: "attribution.py", type: "file" },
  { depth: 2, name: "health.py", type: "file" },
  { depth: 2, name: "dashboard.py", type: "file" },
  { depth: 2, name: "agents.py", type: "file" },
  { depth: 2, name: "websocket.py", type: "file" },
  { depth: 1, name: "db/", type: "dir" },
  { depth: 2, name: "tables.py", type: "file" },
  { depth: 0, name: "tests/", type: "dir" },
  { depth: 1, name: "test_eas.py", type: "file" },
  { depth: 1, name: "test_models.py", type: "file" },
  { depth: 1, name: "test_api.py", type: "file" },
  { depth: 1, name: "test_two_phase.py", type: "file" },
  { depth: 1, name: "test_contextcite.py", type: "file" },
  { depth: 1, name: "test_calibrator.py", type: "file" },
  { depth: 1, name: "test_contradiction.py", type: "file" },
  { depth: 1, name: "test_websocket.py", type: "file" },
];

const FILE_DESCRIPTIONS: Record<string, string> = {
  "pyproject.toml":
    "10 deps: fastapi, uvicorn, pydantic, sqlalchemy, asyncpg, numpy, sentence-transformers, httpx, otel, alembic",
  "config.py":
    "pydantic-settings with CORTEX_ env prefix. DB URL, embedding model, token pricing, CORS origins.",
  "models.py":
    "16 Pydantic models mapping paper math. MemoryUnit=(M,\u03c6,\u03c4), Transaction=\u03be=(q,S,C,r,t), AttributionScore=a\u1d62",
  "database.py":
    "AsyncPG engine + session factory. Pool size 5, expire_on_commit=False.",
  "tables.py":
    "9 SQLAlchemy tables: memories, transactions, attribution_scores, memory_profiles, contradictions, health_snapshots, calibration_pairs, agent_cost_configs",
  "eas.py":
    "EAS computation \u2014 numpy vectorized. a\u1d62 = cosim(\u03c6(m\u1d62),\u03c6(r))\u00b7cosim(\u03c6(m\u1d62),\u03c6(q)) / \u03a3\u2c7c[...]. O(kd), microsecond-scale.",
  "__init__.py (attribution)":
    "Lazy-loaded all-MiniLM-L6-v2 via @lru_cache. embed(texts) \u2192 batch 384-dim vectors.",
  "calculator.py":
    "Ported from calculator.ts: transaction_cost, memory_pnl, gini_coefficient, snr_db, token_waste_rate, contradiction_risk",
  "app.py":
    "FastAPI factory with CORS, lifespan (calibrator warmup + engine dispose), 7 routers under /api/v1",
  "memories.py":
    "CRUD + semantic search: POST/GET/GET/{id}/PATCH/DELETE/search. Auto-embeds. Sort/filter params.",
  "transactions.py":
    "Critical path: embed\u2192EAS\u2192calibrate\u2192store\u2192Welford. Single-shot + two-phase. Calibration-aware.",
  "attribution.py":
    "Score queries + POST /{txn_id}/exact for ContextCite slow-path. Stores calibration pairs.",
  "dashboard.py":
    "Aggregated overview + timeseries + top-memories + cost-summary endpoints.",
  "health.py":
    "Agent health + NLI contradiction detection + resolve endpoint.",
  "agents.py": "Agent fleet CRUD: list, detail, cost config upsert/get.",
  "websocket.py":
    "WebSocket real-time layer. ConnectionManager with channels + monotonic sequence_id.",
  "contextcite.py":
    "Slow-path attribution: ablation masks \u2192 LLM log-probs \u2192 LASSO \u2192 LDS. 64 forward passes.",
  "llm_provider.py":
    "LLM provider abstraction: OpenAI/Anthropic/Mock. score_response() + cost tracking.",
  "calibrator.py":
    "Isotonic regression calibrator. Fits on (EAS, exact) pairs. Two-speed bridge.",
  "contradiction.py":
    "NLI-based contradiction detection. Cosine candidates \u2192 DeBERTa bidirectional check.",
  "wrapper.py":
    "CortexMemory SDK: wraps Mem0 with OTel spans. Two-phase: search()\u2192txn_id, report_response()\u2192EAS.",
  "001_initial_schema.py":
    "Creates 6 base tables with indexes. FLOAT8[] embeddings (pgvector Phase 3).",
  "002_calibration_and_cost_configs.py":
    "Adds calibration_pairs, agent_cost_configs. Renames variance\u2192m2. Adds transaction status.",
  "003_phase2_additions.py":
    "Adds content_hash, resolved_at/by, compound index, agent description/status.",
};

const DB_TABLES = [
  {
    name: "memories",
    cols: "id, content, embedding[], tokens, agent_id, tier, deleted_at",
  },
  {
    name: "transactions",
    cols: "id, query, response, memory_ids[], status, agent_id",
  },
  {
    name: "attribution_scores",
    cols: "id, memory_id, transaction_id, score, method",
  },
  {
    name: "memory_profiles",
    cols: "memory_id, mean, m2, count, trend (Welford)",
  },
  {
    name: "calibration_pairs",
    cols: "eas_score, exact_score (\u00a73.4 two-speed)",
  },
  {
    name: "agent_cost_configs",
    cols: "agent_id, input/output costs, provider",
  },
  {
    name: "contradictions",
    cols: "memory_id_1, memory_id_2, type, confidence",
  },
  {
    name: "health_snapshots",
    cols: "agent_id, rates, drift, quality",
  },
];

const PROJECT_STATS: [string, string][] = [
  ["Source Files", "32"],
  ["Pydantic Models", "23"],
  ["DB Tables", "9"],
  ["API Endpoints", "28"],
  ["Tests Passing", "50+"],
  ["Test Coverage", "EAS + ContextCite + Calibrator + NLI + WS"],
];

interface Endpoint {
  method: string;
  path: string;
  desc: string;
  tag: string;
}

const ENDPOINTS: Endpoint[] = [
  {
    method: "POST",
    path: "/api/v1/memories",
    desc: "Create memory (auto-embeds content)",
    tag: "memories",
  },
  {
    method: "GET",
    path: "/api/v1/memories",
    desc: "List memories (paginated, filterable by agent_id/tier)",
    tag: "memories",
  },
  {
    method: "GET",
    path: "/api/v1/memories/{id}",
    desc: "Get memory with profile",
    tag: "memories",
  },
  {
    method: "PATCH",
    path: "/api/v1/memories/{id}",
    desc: "Update tier/metadata",
    tag: "memories",
  },
  {
    method: "DELETE",
    path: "/api/v1/memories/{id}",
    desc: "Soft delete (GDPR)",
    tag: "memories",
  },
  {
    method: "GET",
    path: "/api/v1/memories/search",
    desc: "Semantic search: embed query \u2192 cosine similarity \u2192 top-k",
    tag: "memories",
  },
  {
    method: "POST",
    path: "/api/v1/transactions",
    desc: "Single-shot: embed \u2192 EAS \u2192 store \u2192 Welford \u2192 return scores",
    tag: "transactions",
  },
  {
    method: "POST",
    path: "/api/v1/transactions/initiate",
    desc: "Phase 1: Create pending transaction at search time",
    tag: "transactions",
  },
  {
    method: "POST",
    path: "/api/v1/transactions/{id}/complete",
    desc: "Phase 2: Complete with response, triggers EAS",
    tag: "transactions",
  },
  {
    method: "GET",
    path: "/api/v1/transactions",
    desc: "List transactions (filterable by status)",
    tag: "transactions",
  },
  {
    method: "GET",
    path: "/api/v1/transactions/{id}",
    desc: "Get transaction with attribution scores",
    tag: "transactions",
  },
  {
    method: "GET",
    path: "/api/v1/attribution/{txn_id}",
    desc: "Scores for a transaction",
    tag: "attribution",
  },
  {
    method: "GET",
    path: "/api/v1/attribution/memory/{id}",
    desc: "All scores + profile for a memory",
    tag: "attribution",
  },
  {
    method: "POST",
    path: "/api/v1/attribution/{txn_id}/exact",
    desc: "Trigger ContextCite exact attribution (64 LLM calls, ~$0.77)",
    tag: "attribution",
  },
  {
    method: "GET",
    path: "/api/v1/health/{agent_id}",
    desc: "Recent health snapshots",
    tag: "health",
  },
  {
    method: "GET",
    path: "/api/v1/health/contradictions",
    desc: "List contradictions (filterable by agent_id)",
    tag: "health",
  },
  {
    method: "POST",
    path: "/api/v1/health/contradictions/detect",
    desc: "Trigger NLI-based contradiction detection batch",
    tag: "health",
  },
  {
    method: "PATCH",
    path: "/api/v1/health/contradictions/{id}/resolve",
    desc: "Mark contradiction resolved",
    tag: "health",
  },
  {
    method: "GET",
    path: "/api/v1/agents",
    desc: "List all agents with summary stats",
    tag: "agents",
  },
  {
    method: "GET",
    path: "/api/v1/agents/{agent_id}",
    desc: "Detailed agent view with cost config",
    tag: "agents",
  },
  {
    method: "PUT",
    path: "/api/v1/agents/{agent_id}/cost-config",
    desc: "Upsert agent cost configuration",
    tag: "agents",
  },
  {
    method: "GET",
    path: "/api/v1/dashboard/overview",
    desc: "Aggregated view matching frontend AgentSummary",
    tag: "dashboard",
  },
  {
    method: "GET",
    path: "/api/v1/dashboard/metrics/timeseries",
    desc: "Time-bucketed health metrics for charting",
    tag: "dashboard",
  },
  {
    method: "GET",
    path: "/api/v1/dashboard/top-memories",
    desc: "Top N memories by total attribution",
    tag: "dashboard",
  },
  {
    method: "GET",
    path: "/api/v1/dashboard/cost-summary",
    desc: "Aggregated cost across agents",
    tag: "dashboard",
  },
  {
    method: "GET",
    path: "/api/v1/lifecycle/rules",
    desc: "List lifecycle rules for memory tier promotion/demotion",
    tag: "lifecycle",
  },
  {
    method: "POST",
    path: "/api/v1/lifecycle/rules",
    desc: "Create a new lifecycle rule",
    tag: "lifecycle",
  },
  {
    method: "POST",
    path: "/api/v1/lifecycle/evaluate",
    desc: "Evaluate all rules against current memory state",
    tag: "lifecycle",
  },
  {
    method: "POST",
    path: "/api/v1/grounding/verify",
    desc: "Verify a response against its source memories",
    tag: "grounding",
  },
  {
    method: "GET",
    path: "/api/v1/grounding/report/{txn_id}",
    desc: "Get grounding verification report for a transaction",
    tag: "grounding",
  },
  {
    method: "POST",
    path: "/api/v1/snapshots",
    desc: "Capture a point-in-time snapshot of agent memory state",
    tag: "snapshots",
  },
  {
    method: "GET",
    path: "/api/v1/snapshots/{agent_id}",
    desc: "List snapshots for an agent",
    tag: "snapshots",
  },
  {
    method: "WS",
    path: "/api/v1/ws/{channel}",
    desc: "WebSocket real-time updates (dashboard, agent:{id})",
    tag: "websocket",
  },
];

function methodBadgeClass(method: string): string {
  switch (method) {
    case "GET":
      return "badge badge--success";
    case "POST":
      return "badge badge--info";
    case "PUT":
    case "PATCH":
      return "badge badge--warning";
    case "DELETE":
      return "badge badge--error";
    case "WS":
      return "badge badge--neutral";
    default:
      return "badge badge--neutral";
  }
}

const TAG_ORDER = [
  "memories",
  "transactions",
  "attribution",
  "health",
  "agents",
  "lifecycle",
  "grounding",
  "snapshots",
  "dashboard",
  "websocket",
] as const;

function groupEndpoints(eps: Endpoint[]) {
  const grouped: Record<string, Endpoint[]> = {};
  for (const tag of TAG_ORDER) {
    const matches = eps.filter((e) => e.tag === tag);
    if (matches.length > 0) grouped[tag] = matches;
  }
  return grouped;
}

// -- Component ------------------------------------------------------------------

export default function EnginePage() {
  const [hoveredFile, setHoveredFile] = useState<string | null>(null);

  // EAS calculator state
  const [memoryCount, setMemoryCount] = useState(5);
  const [seed, setSeed] = useState(42);

  // Live API tester state
  const [liveMethod, setLiveMethod] = useState("GET");
  const [liveEndpoint, setLiveEndpoint] = useState("/healthz");
  const [liveBody, setLiveBody] = useState("");
  const [liveResponse, setLiveResponse] = useState("");
  const [liveLoading, setLiveLoading] = useState(false);

  // API status
  const [apiStatus, setApiStatus] = useState<
    "unknown" | "online" | "offline"
  >("unknown");

  React.useEffect(() => {
    fetch("http://localhost:8000/healthz")
      .then((r) => (r.ok ? setApiStatus("online") : setApiStatus("offline")))
      .catch(() => setApiStatus("offline"));
  }, []);

  // EAS computation (3D demo vectors)
  const rng = seededRandom(seed);
  const q3d = useMemo(
    () => normalize([rng() - 0.5, rng() - 0.5, rng() - 0.5]),
    [seed]
  );
  const r3d = useMemo(
    () => normalize([rng() - 0.5, rng() - 0.5, rng() - 0.5]),
    [seed]
  );
  const M3d = useMemo(
    () =>
      Array.from({ length: memoryCount }, () =>
        normalize([rng() - 0.5, rng() - 0.5, rng() - 0.5])
      ),
    [seed, memoryCount]
  );
  const eas = useMemo(() => computeEAS(M3d, q3d, r3d), [M3d, q3d, r3d]);
  const giniVal = useMemo(() => gini(eas.scores), [eas.scores]);
  const snrVal = useMemo(() => snrDb(eas.scores), [eas.scores]);

  const sendLiveRequest = useCallback(async () => {
    setLiveLoading(true);
    try {
      const hasBody = liveMethod !== "GET" && liveBody.trim();
      const res = await fetch(`http://localhost:8000${liveEndpoint}`, {
        method: liveMethod,
        headers: { "Content-Type": "application/json" },
        ...(hasBody ? { body: liveBody } : {}),
      });
      const data = await res.json();
      setLiveResponse(JSON.stringify(data, null, 2));
    } catch (err: unknown) {
      setLiveResponse(
        `Error: ${err instanceof Error ? err.message : "Request failed"}`
      );
    }
    setLiveLoading(false);
  }, [liveMethod, liveEndpoint, liveBody]);

  const grouped = useMemo(() => groupEndpoints(ENDPOINTS), []);

  return (
    <PageTransition>
      <div className="page-container">
        <PageHeader
          title="Engine"
          subtitle="CortexOS architecture, EAS algorithm, and API explorer"
        >
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                apiStatus === "online"
                  ? "bg-[var(--status-success)]"
                  : apiStatus === "offline"
                    ? "bg-[var(--status-error)]"
                    : "bg-[var(--text-ghost)]"
              }`}
            />
            <span
              className={`text-xs font-mono ${
                apiStatus === "online"
                  ? "text-[var(--status-success)]"
                  : "text-[var(--text-tertiary)]"
              }`}
            >
              {apiStatus === "online"
                ? "API Online"
                : apiStatus === "offline"
                  ? "API Offline"
                  : "Checking..."}
            </span>
          </div>
        </PageHeader>

        <Tabs.Root defaultValue="architecture">
          {/* -- Tab List -------------------------------------------------- */}
          <Tabs.List className="flex gap-1 bg-[var(--bg-surface-2)] rounded-lg p-1 mb-8">
            {[
              { value: "architecture", label: "Architecture" },
              { value: "eas", label: "EAS Calculator" },
              { value: "api", label: "API Explorer" },
              { value: "live", label: "Live API Tester" },
            ].map((tab) => (
              <Tabs.Trigger
                key={tab.value}
                value={tab.value}
                className="px-4 py-2 text-sm rounded-md text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-secondary)] data-[state=active]:bg-[var(--accent-muted)] data-[state=active]:text-[var(--accent)]"
              >
                {tab.label}
              </Tabs.Trigger>
            ))}
          </Tabs.List>

          {/* ============================================================
              TAB 1 — Architecture
              ============================================================ */}
          <Tabs.Content value="architecture">
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">
              {/* File tree */}
              <div className="card">
                <SectionHeader title="Project Structure" />
                <div className="font-mono text-xs text-[var(--text-secondary)] mb-4">
                  cortex-engine/
                </div>
                <div className="space-y-0.5">
                  {FILE_TREE.map((item, i) => (
                    <div
                      key={i}
                      style={{ paddingLeft: `${item.depth * 20 + 8}px` }}
                      className={`py-1.5 px-2 rounded-md cursor-pointer transition-colors text-xs font-mono ${
                        hoveredFile === item.name
                          ? "bg-[var(--accent-muted)] text-[var(--accent)]"
                          : item.type === "dir"
                            ? "text-[var(--text-tertiary)]"
                            : "text-[var(--text-secondary)] hover:bg-[var(--bg-surface-2)]"
                      }`}
                      onMouseEnter={() =>
                        item.type === "file"
                          ? setHoveredFile(item.name)
                          : null
                      }
                      onMouseLeave={() => setHoveredFile(null)}
                    >
                      <span className="text-[var(--text-ghost)] mr-2">
                        {item.type === "dir" ? "/" : " "}
                      </span>
                      {item.name}
                    </div>
                  ))}
                </div>
              </div>

              {/* Right column */}
              <div className="space-y-6">
                {/* File details */}
                <div className="card">
                  <SectionHeader title="File Details" />
                  {hoveredFile && FILE_DESCRIPTIONS[hoveredFile] ? (
                    <div>
                      <div className="text-sm font-semibold text-[var(--accent)] mb-2 font-mono">
                        {hoveredFile}
                      </div>
                      <p className="text-xs text-[var(--text-tertiary)] leading-relaxed">
                        {FILE_DESCRIPTIONS[hoveredFile]}
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--text-ghost)] italic">
                      Hover over a file to see details
                    </p>
                  )}
                </div>

                {/* Project stats */}
                <div className="card">
                  <SectionHeader title="Project Stats" />
                  <div className="space-y-2">
                    {PROJECT_STATS.map(([label, value]) => (
                      <div
                        key={label}
                        className="flex justify-between text-xs"
                      >
                        <span className="text-[var(--text-tertiary)]">
                          {label}
                        </span>
                        <span className="text-[var(--text-primary)] font-semibold font-mono">
                          {value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Database schema */}
                <div className="card">
                  <SectionHeader title="Database Schema" count={DB_TABLES.length} />
                  <div className="space-y-2 text-xs font-mono">
                    {DB_TABLES.map((t) => (
                      <div key={t.name}>
                        <span className="text-[var(--status-warning)] font-semibold">
                          {t.name}
                        </span>
                        <span className="text-[var(--text-ghost)] ml-2">
                          &mdash; {t.cols}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Two-Phase Flow section */}
            <div className="mt-8">
              <SectionHeader title="Two-Phase Attribution Flow" />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Single-shot */}
                <div className="card">
                  <h3 className="text-[var(--accent)] mb-1">
                    Single-Shot Flow
                  </h3>
                  <p className="text-xs text-[var(--text-tertiary)] font-mono mb-4">
                    POST /api/v1/transactions
                  </p>
                  <div className="space-y-0">
                    {[
                      "Receive query + response + memory_ids",
                      "Batch embed(query, response) \u2192 384-dim vectors",
                      "Fetch memory embeddings from DB",
                      "compute_eas(M, q, r) \u2192 scores",
                      "Store transaction + attribution scores",
                      "Atomic Welford UPSERT on profiles",
                      "Return TransactionWithScores + cost",
                    ].map((label, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 py-2"
                      >
                        <div className="w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-semibold shrink-0 mt-0.5 font-mono bg-[var(--accent-muted)] text-[var(--accent)] border border-[var(--accent)]/30">
                          {i + 1}
                        </div>
                        <span className="text-xs text-[var(--text-tertiary)]">
                          {label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Two-phase */}
                <div className="card">
                  <h3 className="text-[var(--status-warning)] mb-1">
                    Two-Phase Flow
                  </h3>
                  <p className="text-xs text-[var(--text-tertiary)] font-mono mb-4">
                    {"search() \u2192 ... time passes ... \u2192 report_response()"}
                  </p>

                  <div className="text-[12px] text-[var(--text-ghost)] uppercase tracking-widest mb-2 px-9">
                    Phase 1: At Search Time
                  </div>
                  {[
                    "SDK search() \u2192 Mem0 retrieves memories",
                    "POST /initiate \u2192 embed(query), store pending txn",
                    "Return transaction_id to caller",
                  ].map((label, i) => (
                    <div
                      key={`p1-${i}`}
                      className="flex items-start gap-3 py-2"
                    >
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-semibold shrink-0 mt-0.5 font-mono bg-[rgba(251,191,36,0.12)] text-[var(--status-warning)] border border-[rgba(251,191,36,0.3)]">
                        {i + 1}
                      </div>
                      <span className="text-xs text-[var(--text-tertiary)]">
                        {label}
                      </span>
                    </div>
                  ))}

                  <div className="mx-9 my-3 border-t border-dashed border-[var(--border-default)] relative">
                    <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 bg-[var(--bg-surface-1)] px-3 text-[12px] text-[var(--text-ghost)]">
                      LLM processing gap
                    </span>
                  </div>

                  <div className="text-[12px] text-[var(--text-ghost)] uppercase tracking-widest mb-2 px-9">
                    Phase 2: After LLM Response
                  </div>
                  {[
                    "SDK report_response(txn_id, response_text)",
                    "POST /{id}/complete \u2192 embed(response)",
                    "Fetch snapshotted memory set (ignores deletions)",
                    "compute_eas \u2192 identical scores to single-shot",
                  ].map((label, i) => (
                    <div
                      key={`p2-${i}`}
                      className="flex items-start gap-3 py-2"
                    >
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-semibold shrink-0 mt-0.5 font-mono bg-[var(--accent-muted)] text-[var(--accent)] border border-[var(--accent)]/30">
                        {i + 4}
                      </div>
                      <span className="text-xs text-[var(--text-tertiary)]">
                        {label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Snapshot contract */}
            <div className="card mt-6">
              <h4 className="mb-2">Snapshot Contract</h4>
              <div className="text-xs text-[var(--text-tertiary)] space-y-2">
                <p>
                  Memory IDs are{" "}
                  <span className="text-[var(--text-primary)] font-semibold">
                    snapshotted at initiate time
                  </span>{" "}
                  (stored in the transaction row). When completing:
                </p>
                <ul className="list-disc list-inside space-y-1 pl-2">
                  <li>
                    <code className="text-[12px] font-mono text-[var(--status-success)]">
                      snapshot=True
                    </code>{" "}
                    &mdash; skips{" "}
                    <code className="text-[12px] font-mono text-[var(--status-warning)]">
                      deleted_at
                    </code>{" "}
                    filter. Memories deleted between phases still get
                    scored.
                  </li>
                  <li>
                    <code className="text-[12px] font-mono text-[var(--accent)]">
                      ORDER BY id
                    </code>{" "}
                    &mdash; deterministic row ordering so scores map to
                    correct memories across separate queries.
                  </li>
                  <li>
                    Scores are{" "}
                    <span className="text-[var(--text-primary)] font-semibold">
                      byte-identical
                    </span>{" "}
                    to single-shot given same (M, q, r) &mdash; verified
                    by 10 randomized test scenarios.
                  </li>
                </ul>
              </div>
            </div>

            {/* Welford UPSERT */}
            <div className="card mt-6">
              <h4 className="text-[var(--status-warning)] mb-3">
                Atomic Welford UPSERT (Race-Free)
              </h4>
              <div className="bg-[var(--bg-surface-2)] rounded-lg p-4 font-mono">
                <pre className="text-[12px] text-[var(--text-tertiary)] overflow-x-auto whitespace-pre">
                  {`INSERT INTO memory_profiles (memory_id, mean_attribution, m2, retrieval_count, ...)
VALUES ($1, $2, 0, 1, ...)
ON CONFLICT (memory_id) DO UPDATE SET
  retrieval_count = memory_profiles.retrieval_count + 1,
  mean_attribution = memory_profiles.mean_attribution +
    ($2 - memory_profiles.mean_attribution) / (memory_profiles.retrieval_count + 1),
  m2 = memory_profiles.m2 +
    ($2 - memory_profiles.mean_attribution) *
    ($2 - (memory_profiles.mean_attribution +
      ($2 - memory_profiles.mean_attribution) / (memory_profiles.retrieval_count + 1)))`}
                </pre>
              </div>
              <p className="text-[12px] text-[var(--text-ghost)] mt-3">
                Single atomic statement &mdash; no SELECT...FOR UPDATE
                needed. Concurrent transactions produce correct running
                mean/variance.
              </p>
            </div>
          </Tabs.Content>

          {/* ============================================================
              TAB 2 — EAS Calculator
              ============================================================ */}
          <Tabs.Content value="eas">
            <div className="space-y-6">
              {/* Formula display */}
              <div className="card">
                <SectionHeader title="EAS Formula (Section 3.3)" />
                <div className="bg-[var(--bg-surface-2)] rounded-lg p-4 font-mono">
                  <div className="text-base text-[var(--text-primary)] font-semibold" style={{ fontFamily: "serif" }}>
                    a<sub>i</sub>
                    <sup>fast</sup> = [ cos(&#966;(m<sub>i</sub>),
                    &#966;(r)) &middot; cos(&#966;(m<sub>i</sub>),
                    &#966;(q)) ] / &Sigma;<sub>j</sub>[ cos(&#966;(m
                    <sub>j</sub>), &#966;(r)) &middot; cos(&#966;(m
                    <sub>j</sub>), &#966;(q)) ]
                  </div>
                </div>
                <p className="text-xs text-[var(--text-tertiary)] mt-3">
                  O(kd) complexity &mdash; zero LLM calls &mdash;
                  microsecond-scale for k=10, d=384
                </p>
              </div>

              {/* Controls */}
              <div className="flex flex-wrap gap-4">
                <div className="card flex items-center gap-4">
                  <span className="text-xs text-[var(--text-tertiary)]">
                    Memories (k):
                  </span>
                  <input
                    type="range"
                    min={2}
                    max={20}
                    value={memoryCount}
                    onChange={(e) =>
                      setMemoryCount(Number(e.target.value))
                    }
                    className="w-32 accent-[var(--accent)]"
                  />
                  <span className="text-sm text-[var(--text-primary)] font-semibold w-6 font-mono">
                    {memoryCount}
                  </span>
                </div>
                <div className="card flex items-center gap-4">
                  <span className="text-xs text-[var(--text-tertiary)]">
                    Seed:
                  </span>
                  <input
                    type="range"
                    min={1}
                    max={200}
                    value={seed}
                    onChange={(e) => setSeed(Number(e.target.value))}
                    className="w-32 accent-[var(--status-warning)]"
                  />
                  <span className="text-sm text-[var(--text-primary)] font-semibold w-6 font-mono">
                    {seed}
                  </span>
                </div>
                <button
                  onClick={() =>
                    setSeed(Math.floor(Math.random() * 200))
                  }
                  className="btn btn--secondary"
                >
                  Randomize
                </button>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
                {/* Score bars */}
                <div className="card">
                  <SectionHeader
                    title="Attribution Scores"
                    count={eas.scores.length}
                  />
                  <div className="space-y-2">
                    {eas.scores.map((score, i) => {
                      const isMax =
                        score === Math.max(...eas.scores);
                      const barColor = isMax
                        ? "var(--status-success)"
                        : score > 0.01
                          ? "var(--accent)"
                          : "var(--status-error)";
                      return (
                        <div
                          key={i}
                          className="flex items-center gap-3"
                        >
                          <div className="text-xs text-[var(--text-tertiary)] w-12 text-right font-mono">
                            m<sub>{i}</sub>
                          </div>
                          <div className="flex-1 bg-[var(--bg-surface-2)] rounded-md h-6 relative overflow-hidden">
                            <div
                              className="h-full rounded-md transition-all duration-500"
                              style={{
                                width: `${Math.max(score * 100, 0.5)}%`,
                                backgroundColor: barColor,
                                opacity: 0.8,
                              }}
                            />
                            <div className="absolute inset-0 flex items-center px-2">
                              <span className="text-[12px] text-[var(--text-primary)] font-semibold tabular-nums font-mono">
                                {(score * 100).toFixed(2)}%
                              </span>
                            </div>
                          </div>
                          <div className="text-[12px] text-[var(--text-ghost)] w-16 tabular-nums font-mono">
                            raw: {eas.raw[i].toFixed(4)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-3 text-[12px] text-[var(--text-ghost)] font-mono">
                    &Sigma; scores ={" "}
                    {eas.scores
                      .reduce((a, b) => a + b, 0)
                      .toFixed(6)}{" "}
                    | &Sigma; raw = {eas.total.toFixed(6)}
                  </p>
                </div>

                {/* Metrics side panel */}
                <div className="space-y-6">
                  <div className="card">
                    <SectionHeader title="Live Metrics" />
                    <div className="space-y-4">
                      {[
                        {
                          label: "Gini Coefficient",
                          value: giniVal.toFixed(4),
                          desc: "0=equal, 1=concentrated",
                          color:
                            giniVal > 0.6
                              ? "var(--status-error)"
                              : giniVal > 0.3
                                ? "var(--status-warning)"
                                : "var(--status-success)",
                        },
                        {
                          label: "SNR (dB)",
                          value: snrVal.toFixed(1),
                          desc: "Signal-to-noise ratio",
                          color:
                            snrVal > 20
                              ? "var(--status-success)"
                              : snrVal > 10
                                ? "var(--status-warning)"
                                : "var(--status-error)",
                        },
                        {
                          label: "Waste Rate",
                          value: `${(
                            (eas.scores.filter((s) => s < 0.01)
                              .length /
                              eas.scores.length) *
                            100
                          ).toFixed(0)}%`,
                          desc: "Memories with <1% attribution",
                          color: "var(--status-warning)",
                        },
                        {
                          label: "Max Attribution",
                          value: `${(Math.max(...eas.scores) * 100).toFixed(1)}%`,
                          desc: "Highest single memory",
                          color: "var(--accent)",
                        },
                      ].map((m) => (
                        <div key={m.label}>
                          <div className="flex justify-between items-baseline">
                            <span className="text-xs text-[var(--text-tertiary)]">
                              {m.label}
                            </span>
                            <span
                              className="text-base font-semibold tabular-nums font-mono"
                              style={{ color: m.color }}
                            >
                              {m.value}
                            </span>
                          </div>
                          <p className="text-[12px] text-[var(--text-ghost)]">
                            {m.desc}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="card">
                    <SectionHeader title="Vectors (3D Demo)" />
                    <div className="text-[12px] text-[var(--text-ghost)] space-y-1 font-mono">
                      <div>
                        <span className="text-[var(--accent)]">q</span>{" "}
                        = [
                        {q3d
                          .map((v) => v.toFixed(3))
                          .join(", ")}
                        ]
                      </div>
                      <div>
                        <span className="text-[var(--status-success)]">
                          r
                        </span>{" "}
                        = [
                        {r3d
                          .map((v) => v.toFixed(3))
                          .join(", ")}
                        ]
                      </div>
                      <p className="text-[var(--text-ghost)] mt-2">
                        Production uses d=384 (all-MiniLM-L6-v2)
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Tabs.Content>

          {/* ============================================================
              TAB 3 — API Explorer
              ============================================================ */}
          <Tabs.Content value="api">
            <div className="space-y-8">
              {Object.entries(grouped).map(([tag, eps]) => (
                <div key={tag}>
                  <SectionHeader
                    title={tag.charAt(0).toUpperCase() + tag.slice(1)}
                    count={eps.length}
                  />
                  <div className="card p-0 overflow-hidden">
                    <table className="table table-compact w-full">
                      <thead>
                        <tr>
                          <th className="w-20">Method</th>
                          <th>Path</th>
                          <th>Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {eps.map((ep, i) => (
                          <tr key={i}>
                            <td>
                              <span
                                className={methodBadgeClass(
                                  ep.method
                                )}
                              >
                                {ep.method}
                              </span>
                            </td>
                            <td>
                              <span className="font-mono text-[var(--text-primary)] text-xs">
                                {ep.path}
                              </span>
                            </td>
                            <td className="text-xs text-[var(--text-tertiary)]">
                              {ep.desc}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </Tabs.Content>

          {/* ============================================================
              TAB 4 — Live API Tester
              ============================================================ */}
          <Tabs.Content value="live">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Request panel */}
              <div className="space-y-4">
                <div className="card">
                  <SectionHeader title="Request" />

                  {/* Method + path */}
                  <div className="flex gap-2 mb-4">
                    <select
                      value={liveMethod}
                      onChange={(e) => setLiveMethod(e.target.value)}
                      className="input font-mono !w-24"
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                      <option value="PATCH">PATCH</option>
                      <option value="PUT">PUT</option>
                      <option value="DELETE">DELETE</option>
                    </select>
                    <select
                      value={liveEndpoint}
                      onChange={(e) => {
                        setLiveEndpoint(e.target.value);
                        setLiveResponse("");
                      }}
                      className="input font-mono flex-1"
                    >
                      <option value="/healthz">/healthz</option>
                      <option value="/api/v1/dashboard/overview">
                        /api/v1/dashboard/overview
                      </option>
                      <option value="/api/v1/memories?limit=5">
                        /api/v1/memories?limit=5
                      </option>
                      <option value="/api/v1/transactions?limit=5">
                        /api/v1/transactions?limit=5
                      </option>
                      <option value="/api/v1/agents">
                        /api/v1/agents
                      </option>
                      <option value="/api/v1/health/contradictions">
                        /api/v1/health/contradictions
                      </option>
                      <option value="/api/v1/dashboard/top-memories">
                        /api/v1/dashboard/top-memories
                      </option>
                      <option value="/api/v1/dashboard/cost-summary">
                        /api/v1/dashboard/cost-summary
                      </option>
                    </select>
                  </div>

                  {/* Body */}
                  <div className="mb-4">
                    <label className="caption block mb-1.5">
                      Request Body (optional, for POST/PUT/PATCH)
                    </label>
                    <textarea
                      value={liveBody}
                      onChange={(e) => setLiveBody(e.target.value)}
                      placeholder='{"key": "value"}'
                      className="input font-mono text-xs h-32 resize-none"
                    />
                  </div>

                  <button
                    onClick={sendLiveRequest}
                    disabled={liveLoading}
                    className="btn btn--primary w-full"
                  >
                    {liveLoading ? "Sending..." : "Send Request"}
                  </button>
                </div>
              </div>

              {/* Response panel */}
              <div className="card">
                <SectionHeader title="Response" />
                <div className="bg-[var(--bg-surface-2)] rounded-lg p-4 min-h-[300px] max-h-[500px] overflow-auto">
                  <pre className="text-xs whitespace-pre-wrap font-mono text-[var(--status-success)]">
                    {liveResponse ||
                      "Send a request to see the response"}
                  </pre>
                </div>
              </div>
            </div>
          </Tabs.Content>
        </Tabs.Root>
      </div>
    </PageTransition>
  );
}

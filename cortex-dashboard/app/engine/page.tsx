'use client';

import React from 'react';
import { Navigation } from '@/components/Navigation';

// ── Live EAS Calculator ─────────────────────────────────────────────
function cosineSim(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { dot += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i]; }
  const d = Math.sqrt(na) * Math.sqrt(nb);
  return d === 0 ? 0 : dot / d;
}
function computeEAS(M: number[][], q: number[], r: number[]) {
  const raw = M.map(m => Math.max(cosineSim(m, r), 0) * Math.max(cosineSim(m, q), 0));
  const total = raw.reduce((s, v) => s + v, 0);
  const scores = total > 0 ? raw.map(v => v / total) : raw.map(() => 1 / M.length);
  return { scores, raw, total };
}

// ── Gini / SNR calculators ──────────────────────────────────────────
function gini(scores: number[]): number {
  if (scores.length === 0) return 0;
  const n = scores.length;
  const mean = scores.reduce((a, b) => a + b, 0) / n;
  if (mean === 0) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) sum += Math.abs(scores[i] - scores[j]);
  return sum / (2 * n * n * mean);
}
function snrDb(scores: number[]): number {
  const signal = scores.filter(s => s > 0).reduce((a, s) => a + s * s, 0);
  const noise = scores.filter(s => s <= 0).reduce((a, s) => a + s * s, 0) + 1e-10;
  return 10 * Math.log10(signal / noise);
}

// ── Norm helper ─────────────────────────────────────────────────────
function normalize(v: number[]): number[] {
  const n = Math.sqrt(v.reduce((s, x) => s + x * x, 0));
  return n > 0 ? v.map(x => x / n) : v;
}

// ── Seeded random for reproducible demos ────────────────────────────
function seededRandom(seed: number) {
  let s = seed;
  return () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; };
}

type Tab = 'architecture' | 'eas' | 'api' | 'flow';

export default function EnginePage() {
  const [activeTab, setActiveTab] = React.useState<Tab>('architecture');
  const [memoryCount, setMemoryCount] = React.useState(5);
  const [seed, setSeed] = React.useState(42);
  const [apiStatus, setApiStatus] = React.useState<'unknown' | 'online' | 'offline'>('unknown');
  const [hoveredFile, setHoveredFile] = React.useState<string | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = React.useState<string | null>(null);

  // Check API status
  React.useEffect(() => {
    fetch('http://localhost:8000/healthz').then(r => r.ok ? setApiStatus('online') : setApiStatus('offline')).catch(() => setApiStatus('offline'));
  }, []);

  // Generate demo embeddings (3D for visualization, using seed)
  const rng = seededRandom(seed);
  const q3d = React.useMemo(() => normalize([rng() - 0.5, rng() - 0.5, rng() - 0.5]), [seed]);
  const r3d = React.useMemo(() => normalize([rng() - 0.5, rng() - 0.5, rng() - 0.5]), [seed]);
  const M3d = React.useMemo(() => Array.from({ length: memoryCount }, () =>
    normalize([rng() - 0.5, rng() - 0.5, rng() - 0.5])
  ), [seed, memoryCount]);

  const eas = React.useMemo(() => computeEAS(M3d, q3d, r3d), [M3d, q3d, r3d]);
  const giniVal = React.useMemo(() => gini(eas.scores), [eas.scores]);
  const snrVal = React.useMemo(() => snrDb(eas.scores), [eas.scores]);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'architecture', label: 'ARCHITECTURE' },
    { id: 'eas', label: 'EAS CALCULATOR' },
    { id: 'api', label: 'API ROUTES' },
    { id: 'flow', label: 'TWO-PHASE FLOW' },
  ];

  const fileDescriptions: Record<string, string> = {
    'pyproject.toml': '10 deps: fastapi, uvicorn, pydantic, sqlalchemy, asyncpg, numpy, sentence-transformers, httpx, otel, alembic',
    'config.py': 'pydantic-settings with CORTEX_ env prefix. DB URL, embedding model, token pricing, CORS origins.',
    'models.py': '16 Pydantic models mapping paper math. MemoryUnit=(M,φ,τ), Transaction=ξ=(q,S,C,r,t), AttributionScore=aᵢ',
    'database.py': 'AsyncPG engine + session factory. Pool size 5, expire_on_commit=False.',
    'tables.py': '9 SQLAlchemy tables: memories, transactions, attribution_scores, memory_profiles, contradictions, health_snapshots, calibration_pairs, agent_cost_configs',
    'eas.py': 'EAS computation — numpy vectorized. aᵢ = cosim(φ(mᵢ),φ(r))·cosim(φ(mᵢ),φ(q)) / Σⱼ[...]. O(kd), microsecond-scale.',
    '__init__.py (attribution)': 'Lazy-loaded all-MiniLM-L6-v2 via @lru_cache. embed(texts) → batch 384-dim vectors.',
    'calculator.py': 'Ported from calculator.ts: transaction_cost, memory_pnl, gini_coefficient, snr_db, token_waste_rate, contradiction_risk',
    'app.py': 'FastAPI factory with CORS, lifespan (model warmup + engine dispose), 5 routers under /api/v1',
    'memories.py': 'CRUD: POST/GET/GET/{id}/PATCH/DELETE. Auto-embeds content. Soft delete via deleted_at.',
    'transactions.py': 'Critical path: embed→EAS→store→Welford. Single-shot + two-phase protocol. Atomic UPSERT.',
    'attribution.py': 'Score queries: GET by transaction, GET by memory (with profile).',
    'dashboard.py': 'Aggregated overview: per-agent stats, Gini, SNR, waste rate. Matches frontend AgentSummary shape.',
    'health.py': 'Agent health snapshots + contradiction queries.',
    'wrapper.py': 'CortexMemory SDK: wraps Mem0 with OTel spans. Two-phase: search()→txn_id, report_response()→EAS.',
    '001_initial_schema.py': 'Creates 6 base tables with indexes. FLOAT8[] embeddings (pgvector Phase 2).',
    '002_calibration_and_cost_configs.py': 'Adds calibration_pairs, agent_cost_configs. Renames variance→m2. Adds transaction status.',
  };

  const endpoints = [
    { method: 'POST', path: '/api/v1/memories', desc: 'Create memory (auto-embeds content)', tag: 'memories' },
    { method: 'GET', path: '/api/v1/memories', desc: 'List memories (paginated, filterable by agent_id/tier)', tag: 'memories' },
    { method: 'GET', path: '/api/v1/memories/{id}', desc: 'Get memory with profile', tag: 'memories' },
    { method: 'PATCH', path: '/api/v1/memories/{id}', desc: 'Update tier/metadata', tag: 'memories' },
    { method: 'DELETE', path: '/api/v1/memories/{id}', desc: 'Soft delete (GDPR)', tag: 'memories' },
    { method: 'POST', path: '/api/v1/transactions', desc: 'Single-shot: embed → EAS → store → Welford → return scores', tag: 'transactions' },
    { method: 'POST', path: '/api/v1/transactions/initiate', desc: 'Phase 1: Create pending transaction at search time', tag: 'transactions' },
    { method: 'POST', path: '/api/v1/transactions/{id}/complete', desc: 'Phase 2: Complete with response, triggers EAS', tag: 'transactions' },
    { method: 'GET', path: '/api/v1/transactions', desc: 'List transactions (filterable by status)', tag: 'transactions' },
    { method: 'GET', path: '/api/v1/transactions/{id}', desc: 'Get transaction with attribution scores', tag: 'transactions' },
    { method: 'GET', path: '/api/v1/attribution/{txn_id}', desc: 'Scores for a transaction', tag: 'attribution' },
    { method: 'GET', path: '/api/v1/attribution/memory/{id}', desc: 'All scores + profile for a memory', tag: 'attribution' },
    { method: 'GET', path: '/api/v1/health/{agent_id}', desc: 'Recent health snapshots', tag: 'health' },
    { method: 'GET', path: '/api/v1/health/contradictions', desc: 'List contradictions', tag: 'health' },
    { method: 'GET', path: '/api/v1/dashboard/overview', desc: 'Aggregated view matching frontend AgentSummary', tag: 'dashboard' },
  ];

  const methodColors: Record<string, string> = {
    GET: '#00FF88', POST: '#00D9FF', PATCH: '#FFB800', DELETE: '#FF3A5E',
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white/70 font-mono">
      <Navigation />

      {/* Header */}
      <div className="border-b border-white/10 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-bold text-white tracking-tight">CORTEX ENGINE</h1>
            <p className="text-[12px] text-white/40 mt-1">Phase 1: SDK + EAS Foundation — Python Backend</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-[12px]">
              <div className={`w-2 h-2 rounded-full ${apiStatus === 'online' ? 'bg-[#00FF88]' : apiStatus === 'offline' ? 'bg-[#FF3A5E]' : 'bg-white/30'}`} />
              <span className={apiStatus === 'online' ? 'text-[#00FF88]' : 'text-white/40'}>
                API {apiStatus === 'online' ? 'ONLINE' : apiStatus === 'offline' ? 'OFFLINE' : 'CHECKING'}
              </span>
              <span className="text-white/20">localhost:8000</span>
            </div>
            <div className="text-[12px] text-white/30">38 tests passing</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2 text-[12px] font-bold tracking-wider transition-all ${
                activeTab === t.id
                  ? 'bg-white/10 text-[#00D9FF] border-b-2 border-[#00D9FF]'
                  : 'text-white/40 hover:text-white/60 hover:bg-white/5'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-6">

        {/* ── ARCHITECTURE TAB ─────────────────────────────────────── */}
        {activeTab === 'architecture' && (
          <div className="grid grid-cols-[1fr_350px] gap-6">
            {/* File tree */}
            <div className="bg-[#111] border border-white/10 rounded-lg p-5">
              <div className="text-[13px] font-bold text-white/80 mb-4">cortex-engine/</div>
              <div className="space-y-0.5 text-[12px]">
                {[
                  { depth: 0, name: 'pyproject.toml', type: 'file' as const },
                  { depth: 0, name: 'alembic.ini', type: 'file' as const },
                  { depth: 0, name: 'alembic/', type: 'dir' as const },
                  { depth: 1, name: 'env.py', type: 'file' as const },
                  { depth: 1, name: 'versions/', type: 'dir' as const },
                  { depth: 2, name: '001_initial_schema.py', type: 'file' as const },
                  { depth: 2, name: '002_calibration_and_cost_configs.py', type: 'file' as const },
                  { depth: 0, name: 'cortex/', type: 'dir' as const },
                  { depth: 1, name: 'config.py', type: 'file' as const },
                  { depth: 1, name: 'models.py', type: 'file' as const },
                  { depth: 1, name: 'database.py', type: 'file' as const },
                  { depth: 1, name: 'sdk/', type: 'dir' as const },
                  { depth: 2, name: 'wrapper.py', type: 'file' as const },
                  { depth: 1, name: 'attribution/', type: 'dir' as const },
                  { depth: 2, name: '__init__.py (attribution)', type: 'file' as const },
                  { depth: 2, name: 'eas.py', type: 'file' as const },
                  { depth: 1, name: 'metrics/', type: 'dir' as const },
                  { depth: 2, name: 'calculator.py', type: 'file' as const },
                  { depth: 1, name: 'api/', type: 'dir' as const },
                  { depth: 2, name: 'app.py', type: 'file' as const },
                  { depth: 2, name: 'memories.py', type: 'file' as const },
                  { depth: 2, name: 'transactions.py', type: 'file' as const },
                  { depth: 2, name: 'attribution.py', type: 'file' as const },
                  { depth: 2, name: 'health.py', type: 'file' as const },
                  { depth: 2, name: 'dashboard.py', type: 'file' as const },
                  { depth: 1, name: 'db/', type: 'dir' as const },
                  { depth: 2, name: 'tables.py', type: 'file' as const },
                  { depth: 0, name: 'tests/', type: 'dir' as const },
                  { depth: 1, name: 'test_eas.py', type: 'file' as const },
                  { depth: 1, name: 'test_models.py', type: 'file' as const },
                  { depth: 1, name: 'test_api.py', type: 'file' as const },
                  { depth: 1, name: 'test_two_phase.py', type: 'file' as const },
                ].map((item, i) => (
                  <div
                    key={i}
                    style={{ paddingLeft: `${item.depth * 20 + 8}px` }}
                    className={`py-1 px-2 rounded cursor-pointer transition-all ${
                      hoveredFile === item.name
                        ? 'bg-[#00D9FF]/10 text-[#00D9FF]'
                        : item.type === 'dir' ? 'text-white/50' : 'text-white/70 hover:bg-white/5'
                    }`}
                    onMouseEnter={() => item.type === 'file' ? setHoveredFile(item.name) : null}
                    onMouseLeave={() => setHoveredFile(null)}
                  >
                    <span className="text-white/30 mr-2">{item.type === 'dir' ? '📁' : '📄'}</span>
                    {item.name}
                  </div>
                ))}
              </div>
            </div>

            {/* Description panel */}
            <div className="space-y-4">
              <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                <div className="text-[11px] text-white/40 uppercase tracking-widest mb-2">File Details</div>
                {hoveredFile && fileDescriptions[hoveredFile] ? (
                  <div>
                    <div className="text-[13px] font-bold text-[#00D9FF] mb-2">{hoveredFile}</div>
                    <div className="text-[12px] text-white/60 leading-relaxed">{fileDescriptions[hoveredFile]}</div>
                  </div>
                ) : (
                  <div className="text-[12px] text-white/30 italic">Hover over a file to see details</div>
                )}
              </div>

              {/* Stats */}
              <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                <div className="text-[11px] text-white/40 uppercase tracking-widest mb-3">Project Stats</div>
                <div className="space-y-2 text-[12px]">
                  {[
                    ['Source Files', '20'],
                    ['Pydantic Models', '16'],
                    ['DB Tables', '9'],
                    ['API Endpoints', '15'],
                    ['Tests Passing', '38'],
                    ['Test Coverage', 'EAS + Models + Metrics + Shape'],
                  ].map(([label, value]) => (
                    <div key={label} className="flex justify-between">
                      <span className="text-white/50">{label}</span>
                      <span className="text-white font-bold">{value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* DB Schema */}
              <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                <div className="text-[11px] text-white/40 uppercase tracking-widest mb-3">Database Schema</div>
                <div className="space-y-1.5 text-[12px]">
                  {[
                    { name: 'memories', cols: 'id, content, embedding[], tokens, agent_id, tier, deleted_at' },
                    { name: 'transactions', cols: 'id, query, response, memory_ids[], status, agent_id' },
                    { name: 'attribution_scores', cols: 'id, memory_id, transaction_id, score, method' },
                    { name: 'memory_profiles', cols: 'memory_id, mean, m2, count, trend (Welford)' },
                    { name: 'calibration_pairs', cols: 'eas_score, exact_score (§3.4 two-speed)' },
                    { name: 'agent_cost_configs', cols: 'agent_id, input/output costs, provider' },
                    { name: 'contradictions', cols: 'memory_id_1, memory_id_2, type, confidence' },
                    { name: 'health_snapshots', cols: 'agent_id, rates, drift, quality' },
                  ].map(t => (
                    <div key={t.name}>
                      <span className="text-[#FFB800] font-bold">{t.name}</span>
                      <span className="text-white/30 ml-2">— {t.cols}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── EAS CALCULATOR TAB ───────────────────────────────────── */}
        {activeTab === 'eas' && (
          <div className="space-y-6">
            {/* Formula */}
            <div className="bg-[#111] border border-white/10 rounded-lg p-5">
              <div className="text-[11px] text-white/40 uppercase tracking-widest mb-3">EAS Formula (Section 3.3)</div>
              <div className="text-[16px] text-white font-bold mb-2" style={{ fontFamily: 'serif' }}>
                a<sub>i</sub><sup>fast</sup> = [ cos(φ(m<sub>i</sub>), φ(r)) · cos(φ(m<sub>i</sub>), φ(q)) ] / Σ<sub>j</sub>[ cos(φ(m<sub>j</sub>), φ(r)) · cos(φ(m<sub>j</sub>), φ(q)) ]
              </div>
              <div className="text-[12px] text-white/40">
                O(kd) complexity — zero LLM calls — microsecond-scale for k=10, d=384
              </div>
            </div>

            {/* Controls */}
            <div className="flex gap-4">
              <div className="bg-[#111] border border-white/10 rounded-lg p-4 flex items-center gap-4">
                <span className="text-[12px] text-white/50">Memories (k):</span>
                <input
                  type="range" min={2} max={20} value={memoryCount}
                  onChange={e => setMemoryCount(Number(e.target.value))}
                  className="w-32 accent-[#00D9FF]"
                />
                <span className="text-[14px] text-white font-bold w-6">{memoryCount}</span>
              </div>
              <div className="bg-[#111] border border-white/10 rounded-lg p-4 flex items-center gap-4">
                <span className="text-[12px] text-white/50">Seed:</span>
                <input
                  type="range" min={1} max={200} value={seed}
                  onChange={e => setSeed(Number(e.target.value))}
                  className="w-32 accent-[#FFB800]"
                />
                <span className="text-[14px] text-white font-bold w-6">{seed}</span>
              </div>
              <button
                onClick={() => setSeed(Math.floor(Math.random() * 200))}
                className="bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-[12px] text-white/60 hover:text-[#00D9FF] hover:border-[#00D9FF]/30 transition-all"
              >
                RANDOMIZE
              </button>
            </div>

            <div className="grid grid-cols-[1fr_300px] gap-6">
              {/* Score bars */}
              <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                <div className="text-[11px] text-white/40 uppercase tracking-widest mb-4">Attribution Scores (sum = 1.0)</div>
                <div className="space-y-2">
                  {eas.scores.map((score, i) => {
                    const barColor = score === Math.max(...eas.scores) ? '#00FF88' : score > 0.01 ? '#00D9FF' : '#FF3A5E';
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <div className="text-[12px] text-white/50 w-12 text-right">m<sub>{i}</sub></div>
                        <div className="flex-1 bg-white/5 rounded-sm h-6 relative overflow-hidden">
                          <div
                            className="h-full rounded-sm transition-all duration-500"
                            style={{ width: `${Math.max(score * 100, 0.5)}%`, backgroundColor: barColor, opacity: 0.8 }}
                          />
                          <div className="absolute inset-0 flex items-center px-2">
                            <span className="text-[11px] text-white font-bold tabular-nums">
                              {(score * 100).toFixed(2)}%
                            </span>
                          </div>
                        </div>
                        <div className="text-[10px] text-white/30 w-16 tabular-nums">
                          raw: {eas.raw[i].toFixed(4)}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 text-[11px] text-white/30">
                  Σ scores = {eas.scores.reduce((a, b) => a + b, 0).toFixed(6)} | Σ raw = {eas.total.toFixed(6)}
                </div>
              </div>

              {/* Metrics */}
              <div className="space-y-4">
                <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                  <div className="text-[11px] text-white/40 uppercase tracking-widest mb-3">Live Metrics</div>
                  <div className="space-y-3">
                    {[
                      { label: 'Gini Coefficient', value: giniVal.toFixed(4), desc: '0=equal, 1=concentrated', color: giniVal > 0.6 ? '#FF3A5E' : giniVal > 0.3 ? '#FFB800' : '#00FF88' },
                      { label: 'SNR (dB)', value: snrVal.toFixed(1), desc: 'Signal-to-noise ratio', color: snrVal > 20 ? '#00FF88' : snrVal > 10 ? '#FFB800' : '#FF3A5E' },
                      { label: 'Waste Rate', value: `${(eas.scores.filter(s => s < 0.01).length / eas.scores.length * 100).toFixed(0)}%`, desc: 'Memories with <1% attribution', color: '#FFB800' },
                      { label: 'Max Attribution', value: `${(Math.max(...eas.scores) * 100).toFixed(1)}%`, desc: 'Highest single memory', color: '#00D9FF' },
                    ].map(m => (
                      <div key={m.label}>
                        <div className="flex justify-between items-baseline">
                          <span className="text-[12px] text-white/50">{m.label}</span>
                          <span className="text-[16px] font-bold tabular-nums" style={{ color: m.color }}>{m.value}</span>
                        </div>
                        <div className="text-[10px] text-white/25">{m.desc}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                  <div className="text-[11px] text-white/40 uppercase tracking-widest mb-2">Vectors (3D demo)</div>
                  <div className="text-[10px] text-white/30 space-y-1">
                    <div><span className="text-[#00D9FF]">q</span> = [{q3d.map(v => v.toFixed(3)).join(', ')}]</div>
                    <div><span className="text-[#00FF88]">r</span> = [{r3d.map(v => v.toFixed(3)).join(', ')}]</div>
                    <div className="text-white/20 mt-1">Production uses d=384 (all-MiniLM-L6-v2)</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── API ROUTES TAB ───────────────────────────────────────── */}
        {activeTab === 'api' && (
          <div className="grid grid-cols-[1fr_400px] gap-6">
            <div className="bg-[#111] border border-white/10 rounded-lg p-5">
              <div className="text-[11px] text-white/40 uppercase tracking-widest mb-4">15 Endpoints — /api/v1</div>
              <div className="space-y-1">
                {endpoints.map((ep, i) => (
                  <div
                    key={i}
                    onClick={() => setSelectedEndpoint(selectedEndpoint === ep.path ? null : ep.path)}
                    className={`flex items-center gap-3 px-3 py-2 rounded cursor-pointer transition-all ${
                      selectedEndpoint === ep.path ? 'bg-white/10' : 'hover:bg-white/5'
                    }`}
                  >
                    <span
                      className="text-[11px] font-bold w-14 text-center py-0.5 rounded"
                      style={{ color: methodColors[ep.method], backgroundColor: `${methodColors[ep.method]}15` }}
                    >
                      {ep.method}
                    </span>
                    <span className="text-[12px] text-white/80 font-bold flex-1">{ep.path}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                      ep.tag === 'transactions' ? 'bg-[#00D9FF]/10 text-[#00D9FF]' :
                      ep.tag === 'memories' ? 'bg-[#00FF88]/10 text-[#00FF88]' :
                      ep.tag === 'attribution' ? 'bg-[#FFB800]/10 text-[#FFB800]' :
                      ep.tag === 'dashboard' ? 'bg-[#A855F7]/10 text-[#A855F7]' :
                      'bg-white/5 text-white/40'
                    }`}>
                      {ep.tag}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              {selectedEndpoint ? (
                <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                  <div className="text-[11px] text-white/40 uppercase tracking-widest mb-2">Endpoint Detail</div>
                  {(() => {
                    const ep = endpoints.find(e => e.path === selectedEndpoint)!;
                    return (
                      <div>
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ color: methodColors[ep.method], backgroundColor: `${methodColors[ep.method]}15` }}>{ep.method}</span>
                          <span className="text-[13px] text-white font-bold">{ep.path}</span>
                        </div>
                        <div className="text-[12px] text-white/60 mb-4">{ep.desc}</div>

                        {ep.path === '/api/v1/transactions' && ep.method === 'POST' && (
                          <div className="bg-black/50 rounded p-3 text-[11px]">
                            <div className="text-white/40 mb-2">Request Body:</div>
                            <pre className="text-[#00D9FF] whitespace-pre-wrap">{JSON.stringify({
                              query_text: "How fast is light?",
                              response_text: "Light travels at ~300,000 km/s",
                              retrieved_memory_ids: ["mem-001", "mem-002"],
                              agent_id: "physics-agent",
                              model: "gpt-4"
                            }, null, 2)}</pre>
                          </div>
                        )}
                        {ep.path === '/api/v1/transactions/initiate' && (
                          <div className="bg-black/50 rounded p-3 text-[11px]">
                            <div className="text-white/40 mb-2">Request Body (Phase 1):</div>
                            <pre className="text-[#00D9FF] whitespace-pre-wrap">{JSON.stringify({
                              query_text: "What is quantum entanglement?",
                              retrieved_memory_ids: ["mem-003"],
                              agent_id: "physics-agent"
                            }, null, 2)}</pre>
                            <div className="text-white/40 mt-3 mb-2">Response:</div>
                            <pre className="text-[#00FF88] whitespace-pre-wrap">{JSON.stringify({
                              transaction_id: "txn-abc-123",
                              status: "pending"
                            }, null, 2)}</pre>
                          </div>
                        )}
                        {ep.path === '/api/v1/dashboard/overview' && (
                          <div className="bg-black/50 rounded p-3 text-[11px]">
                            <div className="text-white/40 mb-2">Response Shape (matches frontend):</div>
                            <pre className="text-[#00FF88] whitespace-pre-wrap">{JSON.stringify({
                              agents: [{ agent_id: "legal-retrieval", total_memories: 24900, total_transactions: 1247, avg_attribution: 0.42, tier_distribution: { hot: 4200, warm: 8300, cold: 12400 }, token_usage: { input: 1247000, output: 843000 }, gini_coefficient: 0.35, snr_db: 18.5, waste_rate: 12.3, contradiction_count: 1 }],
                              total_memories: 100000, total_transactions: 5000, total_attributions: 15000, overall_gini: 0.4, overall_snr_db: 20.0, overall_waste_rate: 15.0
                            }, null, 2)}</pre>
                          </div>
                        )}
                        {ep.path === '/api/v1/memories' && ep.method === 'POST' && (
                          <div className="bg-black/50 rounded p-3 text-[11px]">
                            <div className="text-white/40 mb-2">Request Body:</div>
                            <pre className="text-[#00D9FF] whitespace-pre-wrap">{JSON.stringify({
                              content: "The speed of light is 299,792,458 m/s",
                              agent_id: "physics-agent",
                              tier: "hot",
                              criticality: 0.9
                            }, null, 2)}</pre>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              ) : (
                <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                  <div className="text-[12px] text-white/30 italic">Click an endpoint to see details</div>
                </div>
              )}

              {/* Tag legend */}
              <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                <div className="text-[11px] text-white/40 uppercase tracking-widest mb-3">Route Groups</div>
                <div className="space-y-2 text-[12px]">
                  {[
                    { tag: 'memories', color: '#00FF88', count: 5, desc: 'CRUD + soft delete' },
                    { tag: 'transactions', color: '#00D9FF', count: 5, desc: 'Critical path + two-phase' },
                    { tag: 'attribution', color: '#FFB800', count: 2, desc: 'Score queries' },
                    { tag: 'health', color: '#FF3A5E', count: 2, desc: 'Snapshots + contradictions' },
                    { tag: 'dashboard', color: '#A855F7', count: 1, desc: 'Aggregated overview' },
                  ].map(g => (
                    <div key={g.tag} className="flex items-center gap-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px]" style={{ backgroundColor: `${g.color}15`, color: g.color }}>{g.tag}</span>
                      <span className="text-white/40">{g.count} endpoints — {g.desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TWO-PHASE FLOW TAB ───────────────────────────────────── */}
        {activeTab === 'flow' && (
          <div className="space-y-6">
            {/* Comparison diagram */}
            <div className="grid grid-cols-2 gap-6">
              {/* Single-shot */}
              <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                <div className="text-[13px] font-bold text-[#00D9FF] mb-4">Single-Shot Flow</div>
                <div className="text-[11px] text-white/40 mb-4">POST /api/v1/transactions</div>
                <div className="space-y-0">
                  {[
                    { step: '1', label: 'Receive query + response + memory_ids', color: '#00D9FF' },
                    { step: '2', label: 'Batch embed(query, response) → 384-dim vectors', color: '#FFB800' },
                    { step: '3', label: 'Fetch memory embeddings from DB', color: '#00FF88' },
                    { step: '4', label: 'compute_eas(M, q, r) → scores', color: '#A855F7' },
                    { step: '5', label: 'Store transaction + attribution scores', color: '#00D9FF' },
                    { step: '6', label: 'Atomic Welford UPSERT on profiles', color: '#FFB800' },
                    { step: '7', label: 'Return TransactionWithScores + cost', color: '#00FF88' },
                  ].map((s, i) => (
                    <div key={i} className="flex items-start gap-3 py-2">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5" style={{ backgroundColor: `${s.color}20`, color: s.color, border: `1px solid ${s.color}40` }}>{s.step}</div>
                      <div className="text-[12px] text-white/60">{s.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Two-phase */}
              <div className="bg-[#111] border border-white/10 rounded-lg p-5">
                <div className="text-[13px] font-bold text-[#FFB800] mb-4">Two-Phase Flow</div>
                <div className="text-[11px] text-white/40 mb-4">search() → ... time passes ... → report_response()</div>
                <div className="space-y-0">
                  <div className="text-[10px] text-white/30 uppercase tracking-widest mb-2 px-9">Phase 1: At Search Time</div>
                  {[
                    { step: '1', label: 'SDK search() → Mem0 retrieves memories', color: '#FFB800' },
                    { step: '2', label: 'POST /initiate → embed(query), store pending txn', color: '#FFB800' },
                    { step: '3', label: 'Return transaction_id to caller', color: '#FFB800' },
                  ].map((s, i) => (
                    <div key={i} className="flex items-start gap-3 py-2">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5" style={{ backgroundColor: `${s.color}20`, color: s.color, border: `1px solid ${s.color}40` }}>{s.step}</div>
                      <div className="text-[12px] text-white/60">{s.label}</div>
                    </div>
                  ))}

                  <div className="mx-9 my-3 border-t border-dashed border-white/10 relative">
                    <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 bg-[#111] px-3 text-[10px] text-white/20">LLM processing gap</span>
                  </div>

                  <div className="text-[10px] text-white/30 uppercase tracking-widest mb-2 px-9">Phase 2: After LLM Response</div>
                  {[
                    { step: '4', label: 'SDK report_response(txn_id, response_text)', color: '#00D9FF' },
                    { step: '5', label: 'POST /{id}/complete → embed(response)', color: '#00D9FF' },
                    { step: '6', label: 'Fetch snapshotted memory set (ignores deletions)', color: '#A855F7' },
                    { step: '7', label: 'compute_eas → identical scores to single-shot', color: '#00FF88' },
                  ].map((s, i) => (
                    <div key={i} className="flex items-start gap-3 py-2">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5" style={{ backgroundColor: `${s.color}20`, color: s.color, border: `1px solid ${s.color}40` }}>{s.step}</div>
                      <div className="text-[12px] text-white/60">{s.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Snapshot explanation */}
            <div className="bg-[#111] border border-[#A855F7]/30 rounded-lg p-5">
              <div className="text-[13px] font-bold text-[#A855F7] mb-2">Snapshot Contract</div>
              <div className="text-[12px] text-white/50 space-y-2">
                <p>Memory IDs are <span className="text-white font-bold">snapshotted at initiate time</span> (stored in the transaction row). When completing:</p>
                <ul className="list-disc list-inside space-y-1 pl-2">
                  <li><code className="text-[#00FF88] text-[11px]">snapshot=True</code> — skips <code className="text-[#FFB800] text-[11px]">deleted_at</code> filter. Memories deleted between phases still get scored.</li>
                  <li><code className="text-[#00D9FF] text-[11px]">ORDER BY id</code> — deterministic row ordering so scores map to correct memories across separate queries.</li>
                  <li>Scores are <span className="text-white font-bold">byte-identical</span> to single-shot given same (M, q, r) — verified by 10 randomized test scenarios.</li>
                </ul>
              </div>
            </div>

            {/* Welford UPSERT */}
            <div className="bg-[#111] border border-white/10 rounded-lg p-5">
              <div className="text-[13px] font-bold text-[#FFB800] mb-2">Atomic Welford UPSERT (Race-Free)</div>
              <pre className="text-[11px] text-white/50 overflow-x-auto whitespace-pre">{`INSERT INTO memory_profiles (memory_id, mean_attribution, m2, retrieval_count, ...)
VALUES ($1, $2, 0, 1, ...)
ON CONFLICT (memory_id) DO UPDATE SET
  retrieval_count = memory_profiles.retrieval_count + 1,
  mean_attribution = memory_profiles.mean_attribution +
    ($2 - memory_profiles.mean_attribution) / (memory_profiles.retrieval_count + 1),
  m2 = memory_profiles.m2 +
    ($2 - memory_profiles.mean_attribution) *
    ($2 - (memory_profiles.mean_attribution +
      ($2 - memory_profiles.mean_attribution) / (memory_profiles.retrieval_count + 1)))`}</pre>
              <div className="text-[11px] text-white/30 mt-2">Single atomic statement — no SELECT...FOR UPDATE needed. Concurrent transactions produce correct running mean/variance.</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

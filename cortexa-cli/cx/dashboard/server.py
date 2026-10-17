"""FastAPI dashboard server for Cortexa trace explorer."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from cx.adapters.base import MemoryAdapter

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Cortexa Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global adapter reference — set by the dashboard command
_adapter: MemoryAdapter | None = None
_websocket_clients: list[WebSocket] = []


def set_adapter(adapter: MemoryAdapter) -> None:
    global _adapter
    _adapter = adapter


def _get_adapter() -> MemoryAdapter:
    if _adapter is None:
        from cx.adapters.demo import DemoAdapter
        return DemoAdapter()
    return _adapter


# ── API Routes ────────────────────────────────────────────────────────

@app.get("/api/health")
def api_health() -> dict:
    """Current health metrics."""
    from cx.core.auditor import run_audit
    adapter = _get_adapter()
    report = run_audit(adapter)
    return {
        "health_score": report.health_score,
        "total_memories": report.total_memories,
        "collections": report.collections,
        "ghost_token_pct": report.ghost_pct,
        "ghost_token_count": len(report.ghost_tokens),
        "contradiction_count": len(report.contradictions),
        "stale_count": report.stale_count,
        "mas_avg": report.mas_avg,
        "mas_distribution": {
            "high": report.mas_high_count,
            "mid": report.mas_mid_count,
            "low": report.mas_low_count,
        },
        "estimated_token_waste_per_day": report.estimated_token_waste_per_day,
        "estimated_cost_waste_per_day": report.estimated_cost_waste_per_day,
    }


@app.get("/api/memories")
def api_memories(collection: str | None = None, sort: str = "mas", order: str = "desc") -> dict:
    """List memories with MAS scores."""
    adapter = _get_adapter()
    memories = adapter.list_memories(collection)

    items = []
    for m in memories:
        items.append({
            "id": m.id,
            "content": m.content,
            "collection": m.collection,
            "mas_score": m.mas_score or 0.0,
            "access_count": m.access_count,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "last_accessed": m.last_accessed.isoformat() if m.last_accessed else None,
            "source": m.source,
            "ghost": m.metadata.get("ghost", False),
            "contradiction": m.metadata.get("contradiction", False),
        })

    reverse = order == "desc"
    if sort == "mas":
        items.sort(key=lambda x: x["mas_score"], reverse=reverse)
    elif sort == "access":
        items.sort(key=lambda x: x["access_count"], reverse=reverse)
    elif sort == "created":
        items.sort(key=lambda x: x["created_at"] or "", reverse=reverse)

    return {"memories": items, "total": len(items)}


@app.get("/api/memories/{memory_id}")
def api_memory_detail(memory_id: str) -> dict:
    """Full memory detail with history."""
    adapter = _get_adapter()
    mem = adapter.get_memory(memory_id)
    if not mem:
        return JSONResponse({"error": "Memory not found"}, status_code=404)

    return {
        "id": mem.id,
        "content": mem.content,
        "collection": mem.collection,
        "mas_score": mem.mas_score or 0.0,
        "mas_history": mem.mas_history,
        "access_count": mem.access_count,
        "created_at": mem.created_at.isoformat() if mem.created_at else None,
        "last_accessed": mem.last_accessed.isoformat() if mem.last_accessed else None,
        "source": mem.source,
        "source_updated_at": mem.source_updated_at.isoformat() if mem.source_updated_at else None,
        "ghost": mem.metadata.get("ghost", False),
        "contradiction": mem.metadata.get("contradiction", False),
        "metadata": {k: v for k, v in mem.metadata.items() if k not in ("ghost", "contradiction")},
    }


@app.get("/api/contradictions")
def api_contradictions() -> dict:
    """List active contradictions."""
    adapter = _get_adapter()
    if hasattr(adapter, "get_contradictions"):
        contradictions = adapter.get_contradictions()
    else:
        contradictions = []
    return {"contradictions": contradictions, "count": len(contradictions)}


@app.get("/api/collections")
def api_collections() -> dict:
    """List all collections with counts."""
    adapter = _get_adapter()
    collections = adapter.list_collections()
    memories = adapter.list_memories()

    counts = {}
    for m in memories:
        counts[m.collection] = counts.get(m.collection, 0) + 1

    return {
        "collections": [
            {"name": c, "count": counts.get(c, 0)}
            for c in collections
        ]
    }


@app.post("/api/memories/{memory_id}/archive")
def api_archive_memory(memory_id: str) -> dict:
    """Archive a memory."""
    adapter = _get_adapter()
    success = adapter.archive_memory(memory_id)
    return {"success": success, "memory_id": memory_id, "action": "archive"}


@app.post("/api/memories/{memory_id}/delete")
def api_delete_memory(memory_id: str) -> dict:
    """Delete a memory."""
    adapter = _get_adapter()
    success = adapter.delete_memory(memory_id)
    return {"success": success, "memory_id": memory_id, "action": "delete"}


# ── WebSocket for live updates ────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await websocket.accept()
    _websocket_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _websocket_clients.remove(websocket)


# ── Serve the SPA ─────────────────────────────────────────────────────

@app.get("/")
def serve_index() -> HTMLResponse:
    """Serve the single-page dashboard app."""
    return HTMLResponse(_get_dashboard_html())


def _get_dashboard_html() -> str:
    """Return the self-contained dashboard HTML."""
    return _DASHBOARD_HTML


# ── Self-contained dashboard HTML (no build step needed) ──────────────

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cortexa Dashboard</title>
<style>
  :root {
    --bg: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --cyan: #00d4aa;
    --amber: #ffb347;
    --green: #5af78e;
    --red: #ff5c57;
    --ghost: #6c6c8a;
    --blue: #57c7ff;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  .app { display: flex; min-height: 100vh; }

  /* Sidebar */
  .sidebar {
    width: 220px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    padding: 20px 0;
    flex-shrink: 0;
  }

  .sidebar-logo {
    padding: 0 20px 20px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 8px;
  }

  .sidebar-logo h1 {
    font-size: 18px;
    color: var(--cyan);
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .sidebar-logo span {
    font-size: 11px;
    color: var(--text-dim);
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 20px;
    color: var(--text-dim);
    cursor: pointer;
    transition: all 0.15s;
    font-size: 14px;
    border-left: 3px solid transparent;
  }

  .nav-item:hover { background: var(--bg-tertiary); color: var(--text); }
  .nav-item.active {
    color: var(--cyan);
    background: rgba(0, 212, 170, 0.08);
    border-left-color: var(--cyan);
  }

  /* Main content */
  .main {
    flex: 1;
    padding: 24px 32px;
    overflow-y: auto;
  }

  .page-header {
    margin-bottom: 24px;
  }

  .page-header h2 {
    font-size: 22px;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .page-header p {
    color: var(--text-dim);
    font-size: 13px;
  }

  /* Cards grid */
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    margin-bottom: 28px;
  }

  .card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px;
  }

  .card-label {
    font-size: 12px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }

  .card-value {
    font-size: 28px;
    font-weight: 700;
  }

  .card-sub {
    font-size: 12px;
    color: var(--text-dim);
    margin-top: 4px;
  }

  .score-high { color: var(--green); }
  .score-mid { color: var(--amber); }
  .score-low { color: var(--red); }

  /* Score bar */
  .score-bar {
    height: 6px;
    border-radius: 3px;
    background: var(--bg-tertiary);
    margin-top: 10px;
    overflow: hidden;
  }

  .score-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
  }

  /* Table */
  .data-table {
    width: 100%;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 24px;
  }

  .data-table table {
    width: 100%;
    border-collapse: collapse;
  }

  .data-table th {
    text-align: left;
    padding: 12px 16px;
    font-size: 12px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-tertiary);
    cursor: pointer;
  }

  .data-table th:hover { color: var(--cyan); }

  .data-table td {
    padding: 10px 16px;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
  }

  .data-table tr:last-child td { border-bottom: none; }
  .data-table tr:hover td { background: rgba(0, 212, 170, 0.04); }

  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
  }

  .badge-ghost { background: rgba(108, 108, 138, 0.2); color: var(--ghost); }
  .badge-contradiction { background: rgba(255, 92, 87, 0.15); color: var(--red); }
  .badge-healthy { background: rgba(90, 247, 142, 0.15); color: var(--green); }

  .mas-bar {
    display: inline-block;
    height: 4px;
    border-radius: 2px;
    vertical-align: middle;
    margin-left: 6px;
  }

  /* Contradiction panel */
  .contradiction-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-left: 3px solid var(--red);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .contradiction-card h4 {
    color: var(--red);
    font-size: 13px;
    margin-bottom: 8px;
  }

  .contradiction-pair {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 12px;
    align-items: center;
  }

  .contradiction-mem {
    background: var(--bg-tertiary);
    border-radius: 6px;
    padding: 10px;
    font-size: 13px;
  }

  .contradiction-vs {
    color: var(--red);
    font-weight: 700;
    font-size: 16px;
  }

  .mem-source {
    font-size: 11px;
    color: var(--text-dim);
    margin-top: 4px;
  }

  /* Loading */
  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-dim);
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--border);
    border-top-color: var(--cyan);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-right: 10px;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  /* Detail panel */
  .detail-panel {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 24px;
  }

  .detail-row {
    display: flex;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
  }

  .detail-row:last-child { border-bottom: none; }
  .detail-label { width: 140px; color: var(--text-dim); flex-shrink: 0; }
  .detail-value { flex: 1; }

  .btn {
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--bg-tertiary);
    color: var(--text);
    transition: all 0.15s;
  }

  .btn:hover { border-color: var(--cyan); color: var(--cyan); }
  .btn-danger:hover { border-color: var(--red); color: var(--red); }
  .btn-back { margin-bottom: 16px; }

  /* MAS distribution bar */
  .mas-dist {
    display: flex;
    height: 24px;
    border-radius: 6px;
    overflow: hidden;
    margin-top: 8px;
  }

  .mas-dist-seg {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 600;
    color: var(--bg);
    transition: width 0.5s ease;
  }
</style>
</head>
<body>

<div class="app" id="app">
  <nav class="sidebar">
    <div class="sidebar-logo">
      <h1>Cortexa</h1>
      <span>Memory Intelligence</span>
    </div>
    <div class="nav-item active" onclick="navigate('health')" id="nav-health">
      <span>&#9829;</span> Health
    </div>
    <div class="nav-item" onclick="navigate('memories')" id="nav-memories">
      <span>&#9733;</span> Memories
    </div>
    <div class="nav-item" onclick="navigate('contradictions')" id="nav-contradictions">
      <span>&#9888;</span> Contradictions
    </div>
  </nav>
  <main class="main" id="main-content">
    <div class="loading"><div class="spinner"></div> Loading...</div>
  </main>
</div>

<script>
const API = '';
let currentPage = 'health';
let healthData = null;
let memoriesData = null;
let contradictionsData = null;

async function fetchJSON(url) {
  const res = await fetch(API + url);
  return res.json();
}

function navigate(page, extra) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const nav = document.getElementById('nav-' + page);
  if (nav) nav.classList.add('active');
  currentPage = page;

  if (page === 'health') renderHealth();
  else if (page === 'memories') renderMemories();
  else if (page === 'contradictions') renderContradictions();
  else if (page === 'memory-detail') renderMemoryDetail(extra);
}

function scoreClass(score) {
  if (score >= 75) return 'score-high';
  if (score >= 25) return 'score-mid';
  return 'score-low';
}

function scoreColor(score) {
  if (score >= 0.7) return 'var(--green)';
  if (score >= 0.3) return 'var(--amber)';
  return 'var(--red)';
}

function masBarHTML(score) {
  const w = Math.max(2, score * 60);
  return '<span class="mas-bar" style="width:' + w + 'px;background:' + scoreColor(score) + '"></span>';
}

function badgeHTML(mem) {
  if (mem.ghost) return '<span class="badge badge-ghost">Ghost</span>';
  if (mem.contradiction) return '<span class="badge badge-contradiction">Contradiction</span>';
  return '<span class="badge badge-healthy">Healthy</span>';
}

async function renderHealth() {
  const el = document.getElementById('main-content');
  el.innerHTML = '<div class="loading"><div class="spinner"></div> Loading health data...</div>';

  healthData = await fetchJSON('/api/health');
  const h = healthData;
  const sc = scoreClass(h.health_score);
  const barColor = h.health_score >= 75 ? 'var(--green)' : h.health_score >= 25 ? 'var(--amber)' : 'var(--red)';
  const costYear = (h.estimated_cost_waste_per_day * 365).toFixed(0);

  const totalMAS = h.mas_distribution.high + h.mas_distribution.mid + h.mas_distribution.low;
  const highPct = totalMAS ? (h.mas_distribution.high / totalMAS * 100).toFixed(0) : 0;
  const midPct = totalMAS ? (h.mas_distribution.mid / totalMAS * 100).toFixed(0) : 0;
  const lowPct = totalMAS ? (h.mas_distribution.low / totalMAS * 100).toFixed(0) : 0;

  el.innerHTML = `
    <div class="page-header">
      <h2>Health Dashboard</h2>
      <p>Memory system health overview</p>
    </div>

    <div class="cards">
      <div class="card">
        <div class="card-label">Health Score</div>
        <div class="card-value ${sc}">${h.health_score.toFixed(0)}</div>
        <div class="score-bar">
          <div class="score-bar-fill" style="width:${h.health_score}%;background:${barColor}"></div>
        </div>
      </div>
      <div class="card">
        <div class="card-label">Total Memories</div>
        <div class="card-value">${h.total_memories}</div>
        <div class="card-sub">${h.collections.length} collections</div>
      </div>
      <div class="card">
        <div class="card-label">Ghost Tokens</div>
        <div class="card-value score-low">${h.ghost_token_pct.toFixed(0)}%</div>
        <div class="card-sub">${h.ghost_token_count} memories</div>
      </div>
      <div class="card">
        <div class="card-label">Contradictions</div>
        <div class="card-value ${h.contradiction_count > 0 ? 'score-low' : 'score-high'}">${h.contradiction_count}</div>
        <div class="card-sub">${h.contradiction_count > 0 ? 'needs attention' : 'none found'}</div>
      </div>
      <div class="card">
        <div class="card-label">Stale Memories</div>
        <div class="card-value score-mid">${h.stale_count}</div>
        <div class="card-sub">&gt;30 days since access</div>
      </div>
      <div class="card">
        <div class="card-label">Avg MAS</div>
        <div class="card-value">${h.mas_avg.toFixed(3)}</div>
        <div class="card-sub">Memory Attribution Score</div>
      </div>
      <div class="card">
        <div class="card-label">Token Waste</div>
        <div class="card-value score-mid">~${h.estimated_token_waste_per_day.toLocaleString()}</div>
        <div class="card-sub">tokens/day wasted</div>
      </div>
      <div class="card">
        <div class="card-label">Cost Waste</div>
        <div class="card-value score-mid">$${h.estimated_cost_waste_per_day}</div>
        <div class="card-sub">$${costYear}/year estimated</div>
      </div>
    </div>

    <div class="detail-panel">
      <h3 style="margin-bottom:12px;font-size:14px;">MAS Distribution</h3>
      <div class="mas-dist">
        <div class="mas-dist-seg" style="width:${highPct}%;background:var(--green)">
          ${highPct > 5 ? highPct + '%' : ''}
        </div>
        <div class="mas-dist-seg" style="width:${midPct}%;background:var(--amber)">
          ${midPct > 5 ? midPct + '%' : ''}
        </div>
        <div class="mas-dist-seg" style="width:${lowPct}%;background:var(--red)">
          ${lowPct > 5 ? lowPct + '%' : ''}
        </div>
      </div>
      <div style="display:flex;gap:20px;margin-top:10px;font-size:12px;color:var(--text-dim)">
        <span><span style="color:var(--green)">&#9632;</span> High (${h.mas_distribution.high})</span>
        <span><span style="color:var(--amber)">&#9632;</span> Mid (${h.mas_distribution.mid})</span>
        <span><span style="color:var(--red)">&#9632;</span> Low (${h.mas_distribution.low})</span>
      </div>
    </div>

    <div class="detail-panel">
      <h3 style="margin-bottom:12px;font-size:14px;">Collections</h3>
      ${h.collections.map(c => '<span class="badge badge-healthy" style="margin:2px 4px">' + c + '</span>').join('')}
    </div>
  `;
}

async function renderMemories() {
  const el = document.getElementById('main-content');
  el.innerHTML = '<div class="loading"><div class="spinner"></div> Loading memories...</div>';

  memoriesData = await fetchJSON('/api/memories');
  const mems = memoriesData.memories;

  el.innerHTML = `
    <div class="page-header">
      <h2>Memory Store</h2>
      <p>${mems.length} memories across all collections — sorted by MAS score</p>
    </div>
    <div class="data-table">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Content</th>
            <th>Collection</th>
            <th>MAS</th>
            <th>Access</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${mems.map(m => `
            <tr onclick="navigate('memory-detail','${m.id}')" style="cursor:pointer">
              <td style="color:var(--cyan);font-family:monospace;font-size:12px">${m.id}</td>
              <td>${m.content.length > 55 ? m.content.slice(0,55) + '...' : m.content}</td>
              <td style="color:var(--text-dim);font-size:12px">${m.collection}</td>
              <td>
                <span style="color:${scoreColor(m.mas_score)};font-weight:600">${m.mas_score.toFixed(2)}</span>
                ${masBarHTML(m.mas_score)}
              </td>
              <td style="text-align:center">${m.access_count}</td>
              <td>${badgeHTML(m)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

async function renderMemoryDetail(memId) {
  const el = document.getElementById('main-content');
  el.innerHTML = '<div class="loading"><div class="spinner"></div> Loading memory detail...</div>';

  const mem = await fetchJSON('/api/memories/' + memId);

  el.innerHTML = `
    <button class="btn btn-back" onclick="navigate('memories')">&#8592; Back to Memories</button>
    <div class="page-header">
      <h2 style="color:var(--cyan);font-family:monospace">${mem.id}</h2>
      <p>${badgeHTML(mem)}</p>
    </div>
    <div class="detail-panel">
      <div class="detail-row">
        <div class="detail-label">Content</div>
        <div class="detail-value">${mem.content}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Collection</div>
        <div class="detail-value">${mem.collection}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">MAS Score</div>
        <div class="detail-value">
          <span style="color:${scoreColor(mem.mas_score)};font-weight:700;font-size:18px">${mem.mas_score.toFixed(3)}</span>
          ${masBarHTML(mem.mas_score)}
        </div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Access Count</div>
        <div class="detail-value">${mem.access_count}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Source</div>
        <div class="detail-value">${mem.source || 'Unknown'}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Created</div>
        <div class="detail-value">${mem.created_at ? new Date(mem.created_at).toLocaleDateString() : 'Unknown'}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Last Accessed</div>
        <div class="detail-value">${mem.last_accessed ? new Date(mem.last_accessed).toLocaleDateString() : 'Never'}</div>
      </div>
      <div class="detail-row">
        <div class="detail-label">Source Updated</div>
        <div class="detail-value">${mem.source_updated_at ? new Date(mem.source_updated_at).toLocaleDateString() : 'N/A'}</div>
      </div>
      ${mem.mas_history && mem.mas_history.length > 0 ? `
      <div class="detail-row">
        <div class="detail-label">MAS History</div>
        <div class="detail-value">
          <svg width="200" height="40" viewBox="0 0 200 40">
            <polyline
              points="${mem.mas_history.map((v, i) => `${i * (200 / (mem.mas_history.length - 1))},${40 - v * 40}`).join(' ')}"
              fill="none" stroke="var(--cyan)" stroke-width="2"
            />
          </svg>
        </div>
      </div>` : ''}
    </div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-danger" onclick="archiveMemory('${mem.id}')">Archive</button>
      <button class="btn btn-danger" onclick="deleteMemory('${mem.id}')">Delete</button>
    </div>
  `;
}

async function archiveMemory(id) {
  if (!confirm('Archive memory ' + id + '?')) return;
  await fetch('/api/memories/' + id + '/archive', {method:'POST'});
  navigate('memories');
}

async function deleteMemory(id) {
  if (!confirm('Permanently delete memory ' + id + '?')) return;
  await fetch('/api/memories/' + id + '/delete', {method:'POST'});
  navigate('memories');
}

async function renderContradictions() {
  const el = document.getElementById('main-content');
  el.innerHTML = '<div class="loading"><div class="spinner"></div> Loading contradictions...</div>';

  contradictionsData = await fetchJSON('/api/contradictions');
  const items = contradictionsData.contradictions;

  el.innerHTML = `
    <div class="page-header">
      <h2>Contradictions</h2>
      <p>${items.length} contradiction${items.length !== 1 ? 's' : ''} found in the memory store</p>
    </div>
    ${items.length === 0 ? '<div class="detail-panel"><p style="color:var(--green)">No contradictions detected.</p></div>' :
      items.map((c, i) => `
        <div class="contradiction-card">
          <h4>Contradiction #${i + 1}</h4>
          <div class="contradiction-pair">
            <div class="contradiction-mem">
              <strong style="color:var(--cyan)">${c.memory_a.id}</strong>
              <p style="margin-top:4px">"${c.memory_a.content}"</p>
              <div class="mem-source">Source: ${c.memory_a.source || 'unknown'}</div>
              <div class="mem-source">MAS: ${(c.memory_a.mas || 0).toFixed(2)}</div>
            </div>
            <div class="contradiction-vs">vs</div>
            <div class="contradiction-mem">
              <strong style="color:var(--cyan)">${c.memory_b.id}</strong>
              <p style="margin-top:4px">"${c.memory_b.content}"</p>
              <div class="mem-source">Source: ${c.memory_b.source || 'unknown'}</div>
              <div class="mem-source">MAS: ${(c.memory_b.mas || 0).toFixed(2)}</div>
            </div>
          </div>
          <p style="margin-top:12px;font-size:13px;color:var(--text-dim)">${c.explanation}</p>
        </div>
      `).join('')}
  `;
}

// Initialize
navigate('health');
</script>

</body>
</html>"""

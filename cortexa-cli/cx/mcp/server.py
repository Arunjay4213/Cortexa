"""Cortexa MCP server — exposes memory intelligence tools via Model Context Protocol."""

from __future__ import annotations

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

from cx.adapters.base import MemoryAdapter

# ── Server init ───────────────────────────────────────────────────────

mcp = FastMCP("cortexa_mcp")

# Global adapter — set before running
_adapter: MemoryAdapter | None = None


def set_adapter(adapter: MemoryAdapter) -> None:
    global _adapter
    _adapter = adapter


def _get_adapter() -> MemoryAdapter:
    if _adapter is None:
        from cx.adapters.demo import DemoAdapter
        return DemoAdapter()
    return _adapter


# ── Input models ──────────────────────────────────────────────────────

class TraceInput(BaseModel):
    """Trace which memories attributed to a query/response."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., description="The user query to trace", min_length=1)
    response: str = Field("", description="The agent response to trace")


class SearchInput(BaseModel):
    """Search the memory store."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., description="Search query", min_length=1)
    collection: Optional[str] = Field(None, description="Filter by collection name")
    min_mas: float = Field(0.0, description="Minimum MAS score", ge=0.0, le=1.0)
    max_mas: float = Field(1.0, description="Maximum MAS score", ge=0.0, le=1.0)


class MemoryDetailInput(BaseModel):
    """Get full detail on a specific memory."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    memory_id: str = Field(..., description="The memory ID to inspect", min_length=1)


class ContradictionInput(BaseModel):
    """Find contradictions in the memory store."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    memory_id: Optional[str] = Field(None, description="Find contradictions for this specific memory")
    scope: str = Field("all", description="Search scope: 'all' or 'single'")


class SimulateInput(BaseModel):
    """Simulate a change to a memory."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    memory_id: str = Field(..., description="Memory ID to simulate changes for", min_length=1)
    action: str = Field(..., description="Action to simulate: 'delete' or 'update'")
    new_content: Optional[str] = Field(None, description="New content if action is 'update'")


class ApplyFixInput(BaseModel):
    """Apply a fix to the memory store."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    memory_id: str = Field(..., description="Memory ID to modify", min_length=1)
    action: str = Field(..., description="Action: 'delete', 'update', or 'archive'")
    new_content: Optional[str] = Field(None, description="New content if action is 'update'")


# ── Tools ─────────────────────────────────────────────────────────────

@mcp.tool(
    name="cortexa_trace_response",
    annotations={
        "title": "Trace Memory Attribution",
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
async def trace_response(params: TraceInput) -> str:
    """Trace which memories attributed to a specific response or query. Returns memories with MAS scores."""
    adapter = _get_adapter()
    memories = adapter.list_memories()
    matches = []
    for m in memories:
        if any(word.lower() in m.content.lower() for word in params.query.split() if len(word) > 3):
            matches.append({
                "memory_id": m.id,
                "content": m.content,
                "mas_score": m.mas_score or 0.0,
                "collection": m.collection,
                "source": m.source,
                "access_count": m.access_count,
            })
    matches.sort(key=lambda x: x["mas_score"], reverse=True)
    return json.dumps({"traces": matches[:10], "total_matches": len(matches)})


@mcp.tool(
    name="cortexa_search_memories",
    annotations={
        "title": "Search Memories",
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
async def search_memories(params: SearchInput) -> str:
    """Search the memory store by content, collection, or MAS range."""
    adapter = _get_adapter()
    memories = adapter.list_memories(params.collection)
    results = []
    for m in memories:
        mas = m.mas_score or 0.0
        if mas < params.min_mas or mas > params.max_mas:
            continue
        if params.query and not any(
            w.lower() in m.content.lower() for w in params.query.split() if len(w) > 2
        ):
            continue
        results.append({
            "memory_id": m.id,
            "content": m.content,
            "mas_score": mas,
            "collection": m.collection,
            "source": m.source,
            "ghost": m.metadata.get("ghost", False),
        })
    results.sort(key=lambda x: x["mas_score"], reverse=True)
    return json.dumps({"results": results[:20], "total": len(results)})


@mcp.tool(
    name="cortexa_get_memory_detail",
    annotations={
        "title": "Get Memory Detail",
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
async def get_memory_detail(params: MemoryDetailInput) -> str:
    """Get full detail on a specific memory including provenance, access history, and MAS history."""
    adapter = _get_adapter()
    mem = adapter.get_memory(params.memory_id)
    if not mem:
        return json.dumps({"error": f"Memory {params.memory_id} not found"})
    return json.dumps({
        "memory_id": mem.id,
        "content": mem.content,
        "collection": mem.collection,
        "created_at": str(mem.created_at) if mem.created_at else None,
        "last_accessed": str(mem.last_accessed) if mem.last_accessed else None,
        "access_count": mem.access_count,
        "source": mem.source,
        "source_updated_at": str(mem.source_updated_at) if mem.source_updated_at else None,
        "mas_score": mem.mas_score,
        "mas_history": mem.mas_history[-5:] if mem.mas_history else [],
        "ghost": mem.metadata.get("ghost", False),
        "contradiction": mem.metadata.get("contradiction", False),
    })


@mcp.tool(
    name="cortexa_find_contradictions",
    annotations={
        "title": "Find Contradictions",
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
async def find_contradictions(params: ContradictionInput) -> str:
    """Find memories that contradict each other or a specific memory."""
    adapter = _get_adapter()
    if hasattr(adapter, "get_contradictions"):
        contradictions = adapter.get_contradictions()
        if params.memory_id:
            contradictions = [
                c for c in contradictions
                if c["memory_a"]["id"] == params.memory_id
                or c["memory_b"]["id"] == params.memory_id
            ]
        return json.dumps({"contradictions": contradictions, "count": len(contradictions)})
    return json.dumps({"contradictions": [], "count": 0})


@mcp.tool(
    name="cortexa_simulate_change",
    annotations={
        "title": "Simulate Memory Change",
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
async def simulate_change(params: SimulateInput) -> str:
    """Simulate what would happen if a memory were changed or deleted (read-only prediction)."""
    adapter = _get_adapter()
    mem = adapter.get_memory(params.memory_id)
    if not mem:
        return json.dumps({"error": f"Memory {params.memory_id} not found"})

    mas = mem.mas_score or 0.0
    affected = int(mas * 25)

    if params.action == "delete":
        return json.dumps({
            "action": "delete",
            "memory_id": params.memory_id,
            "affected_responses": affected,
            "mas_impact": f"Removing memory with MAS {mas:.2f}",
            "risk": "high" if mas > 0.7 else "medium" if mas > 0.3 else "low",
            "recommendation": "Safe to delete" if mas < 0.1 else "Caution: this memory is actively used",
        })
    else:
        return json.dumps({
            "action": "update",
            "memory_id": params.memory_id,
            "new_content": params.new_content or "",
            "affected_responses": affected,
            "estimated_improvement": f"+{int(mas * 30)}% accuracy on related queries",
            "risk": "low",
        })


@mcp.tool(
    name="cortexa_apply_fix",
    annotations={
        "title": "Apply Memory Fix",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def apply_fix(params: ApplyFixInput) -> str:
    """Apply a change to the memory store: delete, update, or archive a memory."""
    adapter = _get_adapter()
    if params.action == "delete":
        ok = adapter.delete_memory(params.memory_id)
    elif params.action == "archive":
        ok = adapter.archive_memory(params.memory_id)
    elif params.action == "update":
        ok = adapter.update_memory(params.memory_id, params.new_content or "")
    else:
        return json.dumps({"error": f"Unknown action: {params.action}"})
    return json.dumps({"success": ok, "action": params.action, "memory_id": params.memory_id})


@mcp.tool(
    name="cortexa_get_health_summary",
    annotations={
        "title": "Memory Health Summary",
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
async def get_health_summary() -> str:
    """Get current memory health metrics: health score, ghost token %, contradiction count, staleness, MAS average."""
    from cx.core.auditor import run_audit
    adapter = _get_adapter()
    report = run_audit(adapter)
    return json.dumps({
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
    })

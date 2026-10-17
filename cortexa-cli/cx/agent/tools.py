"""Tool definitions and execution for the Cortexa agent."""

from __future__ import annotations

import json
from typing import Any

from cx.adapters.base import MemoryAdapter

# ── Tool definitions for Claude API ──────────────────────────────────

TOOLS = [
    {
        "name": "trace_response",
        "description": "Trace which memories attributed to a specific response or query. Returns memories with MAS scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user query to trace"},
                "response": {"type": "string", "description": "The agent response to trace"},
            },
        },
    },
    {
        "name": "search_memories",
        "description": "Search the memory store by content, collection, or MAS range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "collection": {"type": "string", "description": "Filter by collection name"},
                "min_mas": {"type": "number", "description": "Minimum MAS score"},
                "max_mas": {"type": "number", "description": "Maximum MAS score"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_memory_detail",
        "description": "Get full detail on a specific memory including provenance, access history, and MAS history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "The memory ID to inspect"},
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "find_contradictions",
        "description": "Find memories that contradict each other or a specific memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "Optional: find contradictions for this specific memory"},
                "scope": {"type": "string", "enum": ["all", "single"], "description": "Search scope"},
            },
        },
    },
    {
        "name": "simulate_change",
        "description": "Simulate what would happen if a memory were changed or deleted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "Memory ID to simulate changes for"},
                "action": {"type": "string", "enum": ["delete", "update"], "description": "Action to simulate"},
                "new_content": {"type": "string", "description": "New content if action is 'update'"},
            },
            "required": ["memory_id", "action"],
        },
    },
    {
        "name": "apply_fix",
        "description": "Apply a change to the memory store (delete, update, or archive a memory).",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "Memory ID to modify"},
                "action": {"type": "string", "enum": ["delete", "update", "archive"], "description": "Action to take"},
                "new_content": {"type": "string", "description": "New content if action is 'update'"},
            },
            "required": ["memory_id", "action"],
        },
    },
    {
        "name": "get_health_summary",
        "description": "Get current memory health metrics including health score, ghost token %, contradiction count.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def summarize_input(inp: dict) -> str:
    """Short summary of tool input for display."""
    if "query" in inp:
        q = inp["query"]
        return f'"{q[:40]}"' if len(q) > 40 else f'"{q}"'
    if "memory_id" in inp:
        return inp["memory_id"]
    if "scope" in inp:
        return inp["scope"]
    return ""


def summarize_result(name: str, result_json: str) -> str:
    """Short summary of tool result for display."""
    try:
        data = json.loads(result_json)
    except json.JSONDecodeError:
        return result_json[:60]

    if "error" in data:
        return f"error: {data['error']}"
    if "traces" in data:
        return f"found {data['total_matches']} traces"
    if "results" in data:
        return f"found {data['total']} memories"
    if "contradictions" in data:
        return f"found {data['count']} contradictions"
    if "health_score" in data:
        return f"health: {data['health_score']}/100"
    if "success" in data:
        return f"{data['action']}: {'done' if data['success'] else 'failed'}"
    if "affected_responses" in data:
        return f"~{data['affected_responses']} responses affected"
    if "memory_id" in data:
        return f"{data['memory_id']}: MAS {data.get('mas_score', '?')}"
    return str(data)[:60]


class ToolExecutor:
    """Executes tool calls against the memory adapter."""

    def __init__(self, adapter: MemoryAdapter) -> None:
        self.adapter = adapter

    def execute(self, name: str, input_data: dict) -> str:
        """Execute a tool call and return JSON result."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        return handler(input_data)

    def _tool_trace_response(self, inp: dict) -> str:
        query = inp.get("query", "")
        memories = self.adapter.list_memories()
        matches = []
        for m in memories:
            if any(w.lower() in m.content.lower() for w in query.split() if len(w) > 3):
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

    def _tool_search_memories(self, inp: dict) -> str:
        query = inp.get("query", "")
        collection = inp.get("collection")
        min_mas = inp.get("min_mas", 0.0)
        max_mas = inp.get("max_mas", 1.0)
        memories = self.adapter.list_memories(collection)
        results = []
        for m in memories:
            mas = m.mas_score or 0.0
            if mas < min_mas or mas > max_mas:
                continue
            if query and not any(
                w.lower() in m.content.lower() for w in query.split() if len(w) > 2
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

    def _tool_get_memory_detail(self, inp: dict) -> str:
        mid = inp.get("memory_id", "")
        mem = self.adapter.get_memory(mid)
        if not mem:
            return json.dumps({"error": f"Memory {mid} not found"})
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

    def _tool_find_contradictions(self, inp: dict) -> str:
        if hasattr(self.adapter, "get_contradictions"):
            contradictions = self.adapter.get_contradictions()
            mid = inp.get("memory_id")
            if mid:
                contradictions = [
                    c for c in contradictions
                    if c["memory_a"]["id"] == mid or c["memory_b"]["id"] == mid
                ]
            return json.dumps({"contradictions": contradictions, "count": len(contradictions)})
        return json.dumps({"contradictions": [], "count": 0})

    def _tool_simulate_change(self, inp: dict) -> str:
        mid = inp.get("memory_id", "")
        action = inp.get("action", "delete")
        mem = self.adapter.get_memory(mid)
        if not mem:
            return json.dumps({"error": f"Memory {mid} not found"})
        mas = mem.mas_score or 0.0
        affected = int(mas * 25)
        if action == "delete":
            return json.dumps({
                "action": "delete",
                "memory_id": mid,
                "affected_responses": affected,
                "mas_impact": f"Removing memory with MAS {mas:.2f}",
                "risk": "high" if mas > 0.7 else "medium" if mas > 0.3 else "low",
                "recommendation": "Safe to delete" if mas < 0.1 else "Caution: actively used",
            })
        return json.dumps({
            "action": "update",
            "memory_id": mid,
            "new_content": inp.get("new_content", ""),
            "affected_responses": affected,
            "estimated_improvement": f"+{int(mas * 30)}% accuracy on related queries",
            "risk": "low",
        })

    def _tool_apply_fix(self, inp: dict) -> str:
        mid = inp.get("memory_id", "")
        action = inp.get("action", "archive")
        if action == "delete":
            ok = self.adapter.delete_memory(mid)
        elif action == "archive":
            ok = self.adapter.archive_memory(mid)
        elif action == "update":
            ok = self.adapter.update_memory(mid, inp.get("new_content", ""))
        else:
            return json.dumps({"error": f"Unknown action: {action}"})
        return json.dumps({"success": ok, "action": action, "memory_id": mid})

    def _tool_get_health_summary(self, _: dict) -> str:
        from cx.core.auditor import run_audit

        report = run_audit(self.adapter)
        return json.dumps({
            "health_score": report.health_score,
            "total_memories": report.total_memories,
            "ghost_token_pct": report.ghost_pct,
            "contradiction_count": len(report.contradictions),
            "stale_count": report.stale_count,
            "mas_avg": report.mas_avg,
        })

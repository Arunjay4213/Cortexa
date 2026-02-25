"""Async HTTP client for CortexOS API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class AgentSummary:
    agent_id: str
    total_memories: int = 0
    total_transactions: int = 0
    avg_attribution: float = 0.0
    last_active: str = ""
    gini: float = 0.0
    snr_db: float = 0.0
    waste_rate: float = 0.0
    contradiction_count: int = 0
    avg_hallucination: float = 0.0


@dataclass
class MemorySummary:
    id: str
    content: str
    agent_id: str
    tier: str = "warm"
    retrieval_count: int = 0
    created_at: str = ""
    mean_attribution: float = 0.0
    total_attribution: float = 0.0


@dataclass
class TransactionSummary:
    id: str
    agent_id: str
    query: str
    status: str = "completed"
    created_at: str = ""
    hallucination_index: float | None = None


@dataclass
class ClaimDetail:
    claim: str
    claim_type: str
    support_type: str
    sources: list[dict] = field(default_factory=list)
    best_entailment: float = 0.0
    is_hallucination: bool = False
    hallucination_reason: str = ""


@dataclass
class CAMADetail:
    transaction_id: str
    agent_id: str
    query: str
    scores: dict[str, float] = field(default_factory=dict)
    claims: list[ClaimDetail] = field(default_factory=list)
    hallucination_index: float = 0.0
    dead_memories: list[str] = field(default_factory=list)
    num_claims: int = 0


@dataclass
class DeadMemory:
    memory_id: str
    agent_id: str
    content: str
    retrieval_count: int = 0
    mean_attribution: float = 0.0


@dataclass
class SystemStats:
    total_memories: int = 0
    total_agents: int = 0
    total_transactions: int = 0
    total_attributions: int = 0
    avg_hallucination_index: float = 0.0
    most_active_agent: str = ""


class CortexAPI:
    """Async HTTP client wrapping all CortexOS API endpoints."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._prefix = "/api/v1"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._async = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=60.0,
        )
        self._sync = httpx.Client(
            base_url=self.base_url, headers=headers, timeout=60.0,
        )

    # ── helpers ──────────────────────────────────────────────────

    async def _get(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        resp = await self._async.get(f"{self._prefix}{path}", params=clean)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: dict | None = None) -> Any:
        resp = await self._async.post(f"{self._prefix}{path}", json=json)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str) -> int:
        resp = await self._async.delete(f"{self._prefix}{path}")
        resp.raise_for_status()
        return resp.status_code

    def _get_sync(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        resp = self._sync.get(f"{self._prefix}{path}", params=clean)
        resp.raise_for_status()
        return resp.json()

    def _post_sync(self, path: str, json: dict | None = None) -> Any:
        resp = self._sync.post(f"{self._prefix}{path}", json=json)
        resp.raise_for_status()
        return resp.json()

    def _delete_sync(self, path: str) -> int:
        resp = self._sync.delete(f"{self._prefix}{path}")
        resp.raise_for_status()
        return resp.status_code

    # ── health ───────────────────────────────────────────────────

    async def healthz(self) -> bool:
        try:
            resp = await self._async.get("/healthz")
            return resp.status_code == 200
        except Exception:
            return False

    def healthz_sync(self) -> bool:
        try:
            resp = self._sync.get("/healthz")
            return resp.status_code == 200
        except Exception:
            return False

    # ── stats ────────────────────────────────────────────────────

    async def stats(self) -> SystemStats:
        data = await self._get("/dashboard/stats")
        return SystemStats(
            total_memories=data.get("total_memories", 0),
            total_agents=data.get("total_agents", 0),
            total_transactions=data.get("total_transactions", 0),
            total_attributions=data.get("total_attributions", 0),
            avg_hallucination_index=data.get("avg_hallucination_index", 0.0),
            most_active_agent=data.get("most_active_agent", ""),
        )

    def stats_sync(self) -> SystemStats:
        data = self._get_sync("/dashboard/stats")
        return SystemStats(
            total_memories=data.get("total_memories", 0),
            total_agents=data.get("total_agents", 0),
            total_transactions=data.get("total_transactions", 0),
            total_attributions=data.get("total_attributions", 0),
            avg_hallucination_index=data.get("avg_hallucination_index", 0.0),
            most_active_agent=data.get("most_active_agent", ""),
        )

    # ── agents ───────────────────────────────────────────────────

    async def agents(self) -> list[AgentSummary]:
        data = await self._get("/agents")
        return [
            AgentSummary(
                agent_id=a["agent_id"],
                total_memories=a.get("total_memories", 0),
                total_transactions=a.get("total_transactions", 0),
                avg_attribution=a.get("avg_attribution", 0.0),
                last_active=a.get("last_active", ""),
                gini=a.get("gini", 0.0),
                snr_db=a.get("snr_db", 0.0),
                waste_rate=a.get("waste_rate", 0.0),
                contradiction_count=a.get("contradiction_count", 0),
            )
            for a in data
        ]

    def agents_sync(self) -> list[AgentSummary]:
        data = self._get_sync("/agents")
        return [
            AgentSummary(
                agent_id=a["agent_id"],
                total_memories=a.get("total_memories", 0),
                total_transactions=a.get("total_transactions", 0),
                avg_attribution=a.get("avg_attribution", 0.0),
                last_active=a.get("last_active", ""),
            )
            for a in data
        ]

    # ── memories ─────────────────────────────────────────────────

    async def memories(
        self, agent_id: str | None = None, limit: int = 20, offset: int = 0,
        sort_by: str = "created_at", order: str = "desc",
    ) -> tuple[list[MemorySummary], int]:
        data = await self._get(
            "/memories", agent_id=agent_id, limit=limit, offset=offset,
            sort_by=sort_by, order=order,
        )
        items = [
            MemorySummary(
                id=m["id"], content=m.get("content", ""),
                agent_id=m.get("agent_id", ""),
                tier=m.get("tier", "warm"),
                retrieval_count=m.get("retrieval_count", 0),
                created_at=m.get("created_at", ""),
            )
            for m in data.get("items", [])
        ]
        return items, data.get("total", 0)

    def memories_sync(
        self, agent_id: str | None = None, limit: int = 20, offset: int = 0,
    ) -> tuple[list[MemorySummary], int]:
        data = self._get_sync(
            "/memories", agent_id=agent_id, limit=limit, offset=offset,
            sort_by="created_at", order="desc",
        )
        items = [
            MemorySummary(
                id=m["id"], content=m.get("content", ""),
                agent_id=m.get("agent_id", ""),
                tier=m.get("tier", "warm"),
                retrieval_count=m.get("retrieval_count", 0),
                created_at=m.get("created_at", ""),
            )
            for m in data.get("items", [])
        ]
        return items, data.get("total", 0)

    # ── search ───────────────────────────────────────────────────

    async def search(self, query: str, agent_id: str | None = None, top_k: int = 5):
        data = await self._get(
            "/memories/search", q=query, agent_id=agent_id, top_k=top_k,
        )
        return data  # list of {memory: {...}, similarity: float}

    def search_sync(self, query: str, agent_id: str | None = None, top_k: int = 5):
        return self._get_sync(
            "/memories/search", q=query, agent_id=agent_id, top_k=top_k,
        )

    # ── transactions ─────────────────────────────────────────────

    async def transactions(
        self, agent_id: str | None = None, limit: int = 20,
    ) -> list[TransactionSummary]:
        data = await self._get("/transactions", agent_id=agent_id, limit=limit)
        return [
            TransactionSummary(
                id=t["id"], agent_id=t.get("agent_id", ""),
                query=(t.get("query_text", "") or "")[:80],
                status=t.get("status", "completed"),
                created_at=t.get("created_at", ""),
            )
            for t in data.get("items", [])
        ]

    def transactions_sync(
        self, agent_id: str | None = None, limit: int = 20,
    ) -> list[TransactionSummary]:
        data = self._get_sync("/transactions", agent_id=agent_id, limit=limit)
        return [
            TransactionSummary(
                id=t["id"], agent_id=t.get("agent_id", ""),
                query=(t.get("query_text", "") or "")[:80],
                status=t.get("status", "completed"),
                created_at=t.get("created_at", ""),
            )
            for t in data.get("items", [])
        ]

    # ── transaction detail + CAMA ────────────────────────────────

    async def transaction_detail(self, txn_id: str) -> dict:
        return await self._get(f"/transactions/{txn_id}")

    async def trigger_cama(self, txn_id: str) -> dict:
        return await self._post(f"/attribution/{txn_id}/cama")

    def trigger_cama_sync(self, txn_id: str) -> dict:
        return self._post_sync(f"/attribution/{txn_id}/cama")

    # ── hallucinations ───────────────────────────────────────────

    async def hallucinations(self, agent_id: str | None = None, limit: int = 20):
        return await self._get(
            "/dashboard/hallucinations", agent_id=agent_id, limit=limit,
        )

    def hallucinations_sync(self, agent_id: str | None = None, limit: int = 20):
        return self._get_sync(
            "/dashboard/hallucinations", agent_id=agent_id, limit=limit,
        )

    # ── dead memories ────────────────────────────────────────────

    async def dead_memories(self) -> list[DeadMemory]:
        data = await self._get("/dashboard/dead-memories")
        return [
            DeadMemory(
                memory_id=d.get("memory_id", ""),
                agent_id=d.get("agent_id", ""),
                content=d.get("content", ""),
                retrieval_count=d.get("retrieval_count", 0),
                mean_attribution=d.get("mean_attribution", 0.0),
            )
            for d in data
        ]

    def dead_memories_sync(self) -> list[DeadMemory]:
        data = self._get_sync("/dashboard/dead-memories")
        return [
            DeadMemory(
                memory_id=d.get("memory_id", ""),
                agent_id=d.get("agent_id", ""),
                content=d.get("content", ""),
                retrieval_count=d.get("retrieval_count", 0),
                mean_attribution=d.get("mean_attribution", 0.0),
            )
            for d in data
        ]

    # ── overview (dashboard) ─────────────────────────────────────

    async def overview(self) -> dict:
        return await self._get("/dashboard/overview")

    def overview_sync(self) -> dict:
        return self._get_sync("/dashboard/overview")

    # ── delete ───────────────────────────────────────────────────

    async def delete_memory(self, memory_id: str) -> bool:
        status = await self._delete(f"/memories/{memory_id}")
        return status == 204

    def delete_memory_sync(self, memory_id: str) -> bool:
        status = self._delete_sync(f"/memories/{memory_id}")
        return status == 204

    # ── cleanup ──────────────────────────────────────────────────

    async def close(self):
        await self._async.aclose()

    def close_sync(self):
        self._sync.close()

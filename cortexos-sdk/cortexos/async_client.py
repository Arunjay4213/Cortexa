"""Asynchronous CortexOS client — same interface as Cortex but fully async."""

from __future__ import annotations

from typing import Any

from cortexos._http import AsyncHTTP
from cortexos.client import _memory_payload, _DEFAULT_BASE_URL, _API_PREFIX, _DEFAULT_TIMEOUT, _DEFAULT_RETRIES
from cortexos.types import Attribution, CAMAAttribution, Memory, Page, RecallAndAttributeResult, RecallResult


class AsyncCortex:
    """
    Asynchronous CortexOS SDK client.

    Usage::

        from cortexos import AsyncCortex

        async with AsyncCortex(api_key="sk-...", agent_id="my-agent") as cx:
            mem = await cx.remember("User prefers dark mode", importance=0.8)
            results = await cx.recall("UI preferences?", top_k=5)
    """

    def __init__(
        self,
        agent_id: str,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_RETRIES,
    ):
        """
        Args:
            agent_id:    The default agent namespace for all operations.
            api_key:     Bearer token sent as ``Authorization: Bearer <key>``.
            base_url:    Root URL of the CortexOS engine.
            timeout:     Per-request timeout in seconds.
            max_retries: Number of retry attempts on transient errors.
        """
        self.agent_id = agent_id
        self._http = AsyncHTTP(base_url, api_key, timeout, max_retries)
        self._prefix = _API_PREFIX

    # ── Context manager support ────────────────────────────────────────────

    async def __aenter__(self) -> "AsyncCortex":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying async HTTP connection pool."""
        await self._http.aclose()

    # ── Memory CRUD ────────────────────────────────────────────────────────

    async def remember(
        self,
        content: str,
        *,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        tier: str = "warm",
        ttl: int | None = None,
        agent_id: str | None = None,
    ) -> Memory:
        """Store a new memory. See :meth:`~cortexos.Cortex.remember` for full docs."""
        payload = _memory_payload(
            content=content,
            agent_id=agent_id or self.agent_id,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
            tier=tier,
            ttl=ttl,
        )
        resp = await self._http.post(f"{self._prefix}/memories", json=payload)
        return Memory._from_api(resp.json())

    async def get(self, memory_id: str) -> Memory:
        """Fetch a memory by ID. Raises :class:`~cortexos.errors.MemoryNotFoundError` if missing."""
        resp = await self._http.get(
            f"{self._prefix}/memories/{memory_id}",
            memory_id=memory_id,
        )
        return Memory._from_api(resp.json()["memory"])

    async def update(
        self,
        memory_id: str,
        *,
        importance: float | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        tier: str | None = None,
    ) -> Memory:
        """Update memory fields. See :meth:`~cortexos.Cortex.update` for full docs."""
        values: dict[str, Any] = {}
        if importance is not None:
            values["criticality"] = importance
        if tier is not None:
            values["tier"] = tier
        if tags is not None or metadata is not None:
            current = await self.get(memory_id)
            merged_meta = dict(current.metadata)
            if tags is not None:
                merged_meta["_tags"] = tags
            if metadata is not None:
                merged_meta.update(metadata)
            values["metadata"] = merged_meta
        resp = await self._http.patch(
            f"{self._prefix}/memories/{memory_id}",
            json=values,
            memory_id=memory_id,
        )
        return Memory._from_api(resp.json())

    async def forget(self, memory_id: str) -> None:
        """Soft-delete a memory. Raises :class:`~cortexos.errors.MemoryNotFoundError` if missing."""
        await self._http.delete(
            f"{self._prefix}/memories/{memory_id}",
            memory_id=memory_id,
        )

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tier: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        agent_id: str | None = None,
    ) -> Page:
        """List memories with pagination. See :meth:`~cortexos.Cortex.list` for full docs."""
        params: dict[str, Any] = {
            "agent_id": agent_id or self.agent_id,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "order": order,
        }
        if tier is not None:
            params["tier"] = tier
        resp = await self._http.get(f"{self._prefix}/memories", params=params)
        data = resp.json()
        return Page(
            items=[Memory._from_api(m) for m in data["items"]],
            total=data["total"],
            offset=data["offset"],
            limit=data["limit"],
        )

    # ── Recall ─────────────────────────────────────────────────────────────

    async def recall(
        self,
        query: str,
        *,
        top_k: int = 10,
        min_score: float = 0.0,
        tags: list[str] | None = None,
        agent_id: str | None = None,
    ) -> list[RecallResult]:
        """Semantic search. See :meth:`~cortexos.Cortex.recall` for full docs."""
        params: dict[str, Any] = {
            "q": query,
            "agent_id": agent_id or self.agent_id,
            "top_k": top_k,
        }
        resp = await self._http.get(f"{self._prefix}/memories/search", params=params)
        results = [
            RecallResult(memory=Memory._from_api(item["memory"]), score=item["similarity"])
            for item in resp.json()
            if item["similarity"] >= min_score
        ]
        if tags:
            tag_set = set(tags)
            results = [r for r in results if tag_set.intersection(r.memory.tags)]
        return results

    # ── Attribution ─────────────────────────────────────────────────────────

    async def attribute(
        self,
        query: str,
        response: str,
        memory_ids: list[str],
        *,
        agent_id: str | None = None,
    ) -> Attribution:
        """Run EAS attribution. See :meth:`~cortexos.Cortex.attribute` for full docs."""
        payload = {
            "query_text": query,
            "response_text": response,
            "retrieved_memory_ids": memory_ids,
            "agent_id": agent_id or self.agent_id,
        }
        resp = await self._http.post(f"{self._prefix}/transactions", json=payload)
        return Attribution._from_api(resp.json(), query=query, response=response)

    async def cama_attribute(
        self,
        transaction_id: str,
    ) -> CAMAAttribution:
        """Run CAMA attribution on an existing transaction.

        See :meth:`~cortexos.Cortex.cama_attribute` for full docs.
        """
        resp = await self._http.post(f"{self._prefix}/attribution/{transaction_id}/cama")
        return CAMAAttribution._from_api(resp.json(), transaction_id=transaction_id)

    async def check(
        self,
        query: str,
        response: str,
        memory_ids: list[str],
        *,
        agent_id: str | None = None,
    ) -> CAMAAttribution:
        """One-shot hallucination check. See :meth:`~cortexos.Cortex.check` for full docs."""
        attr = await self.attribute(query, response, memory_ids, agent_id=agent_id)
        return await self.cama_attribute(attr.transaction_id)

    async def forget_all(self, *, agent_id: str | None = None) -> int:
        """Delete all memories for the given agent. Returns count deleted."""
        count = 0
        while True:
            page = await self.list(agent_id=agent_id, limit=50, offset=0)
            if not page.items:
                break
            for mem in page.items:
                await self.forget(mem.id)
                count += 1
        return count

    async def recall_and_attribute(
        self,
        query: str,
        response: str,
        *,
        top_k: int = 10,
        min_score: float = 0.0,
        agent_id: str | None = None,
    ) -> RecallAndAttributeResult:
        """Recall then attribute. See :meth:`~cortexos.Cortex.recall_and_attribute` for full docs."""
        aid = agent_id or self.agent_id
        recall_results = await self.recall(query, top_k=top_k, min_score=min_score, agent_id=aid)
        memory_ids = [r.memory.id for r in recall_results]
        attribution = await self.attribute(query, response, memory_ids, agent_id=aid)
        return RecallAndAttributeResult(memories=recall_results, attribution=attribution)

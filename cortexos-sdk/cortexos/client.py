"""Synchronous CortexOS client."""

from __future__ import annotations

from typing import Any

from cortexos._http import SyncHTTP
from cortexos.types import Attribution, CAMAAttribution, Memory, Page, RecallAndAttributeResult, RecallResult

_DEFAULT_BASE_URL = "http://localhost:8000"
_API_PREFIX = "/api/v1"
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_RETRIES = 3


def _memory_payload(
    content: str,
    agent_id: str,
    importance: float,
    tags: list[str],
    metadata: dict[str, Any],
    tier: str,
    ttl: int | None,
) -> dict:
    """Build the JSON body for POST /memories."""
    meta = dict(metadata)
    if tags:
        meta["_tags"] = tags
    if ttl is not None:
        meta["_ttl_seconds"] = ttl
    return {
        "content": content,
        "agent_id": agent_id,
        "tier": tier,
        "criticality": importance,
        "metadata": meta,
    }


class Cortex:
    """
    Synchronous CortexOS SDK client.

    Usage::

        from cortexos import Cortex

        cx = Cortex(api_key="sk-...", agent_id="my-agent")
        mem = cx.remember("User prefers dark mode", importance=0.8)
        results = cx.recall("what are the user's UI preferences?", top_k=5)
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
                         Pass ``None`` if the server runs without auth.
            base_url:    Root URL of the CortexOS engine (no trailing slash).
            timeout:     Per-request timeout in seconds.
            max_retries: Number of retry attempts on transient errors.
        """
        self.agent_id = agent_id
        self._http = SyncHTTP(base_url, api_key, timeout, max_retries)
        self._prefix = _API_PREFIX

    # ── Context manager support ────────────────────────────────────────────

    def __enter__(self) -> "Cortex":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    # ── Memory CRUD ────────────────────────────────────────────────────────

    def remember(
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
        """
        Store a new memory.

        Args:
            content:    The text content to store.
            importance: Criticality score [0.0, 1.0].
            tags:       Optional list of string tags (stored in metadata._tags).
            metadata:   Arbitrary key-value metadata dict.
            tier:       Storage tier — ``"hot"``, ``"warm"``, or ``"cold"``.
            ttl:        Time-to-live in seconds (stored in metadata._ttl_seconds).
            agent_id:   Override the client-level agent_id for this call.

        Returns:
            The created :class:`~cortexos.types.Memory`.
        """
        payload = _memory_payload(
            content=content,
            agent_id=agent_id or self.agent_id,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
            tier=tier,
            ttl=ttl,
        )
        resp = self._http.post(f"{self._prefix}/memories", json=payload)
        return Memory._from_api(resp.json())

    def get(self, memory_id: str) -> Memory:
        """
        Fetch a single memory by ID.

        Raises:
            :class:`~cortexos.errors.MemoryNotFoundError`: if the ID doesn't exist.
        """
        resp = self._http.get(
            f"{self._prefix}/memories/{memory_id}",
            memory_id=memory_id,
        )
        return Memory._from_api(resp.json()["memory"])

    def update(
        self,
        memory_id: str,
        *,
        importance: float | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        tier: str | None = None,
    ) -> Memory:
        """
        Update an existing memory's fields.

        Only provided kwargs are sent; omitted fields are left unchanged.

        Raises:
            :class:`~cortexos.errors.MemoryNotFoundError`: if the ID doesn't exist.
        """
        values: dict[str, Any] = {}
        if importance is not None:
            values["criticality"] = importance
        if tier is not None:
            values["tier"] = tier
        if tags is not None or metadata is not None:
            # Fetch current metadata to merge tags cleanly
            current = self.get(memory_id)
            merged_meta = dict(current.metadata)
            if tags is not None:
                merged_meta["_tags"] = tags
            if metadata is not None:
                merged_meta.update(metadata)
            values["metadata"] = merged_meta
        resp = self._http.patch(
            f"{self._prefix}/memories/{memory_id}",
            json=values,
            memory_id=memory_id,
        )
        return Memory._from_api(resp.json())

    def forget(self, memory_id: str) -> None:
        """
        Soft-delete a memory.

        Raises:
            :class:`~cortexos.errors.MemoryNotFoundError`: if the ID doesn't exist.
        """
        self._http.delete(
            f"{self._prefix}/memories/{memory_id}",
            memory_id=memory_id,
        )

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tier: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        agent_id: str | None = None,
    ) -> Page:
        """
        List memories with pagination.

        Args:
            limit:    Max items per page (1–200).
            offset:   Pagination offset.
            tier:     Filter by tier (``"hot"``, ``"warm"``, ``"cold"``).
            sort_by:  Field to sort by (``"created_at"``, ``"criticality"``, etc.).
            order:    ``"asc"`` or ``"desc"``.
            agent_id: Override the client-level agent_id for this call.

        Returns:
            A :class:`~cortexos.types.Page` with ``.items``, ``.total``, ``.has_more``.
        """
        params: dict[str, Any] = {
            "agent_id": agent_id or self.agent_id,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "order": order,
        }
        if tier is not None:
            params["tier"] = tier
        resp = self._http.get(f"{self._prefix}/memories", params=params)
        data = resp.json()
        return Page(
            items=[Memory._from_api(m) for m in data["items"]],
            total=data["total"],
            offset=data["offset"],
            limit=data["limit"],
        )

    # ── Recall (semantic search) ───────────────────────────────────────────

    def recall(
        self,
        query: str,
        *,
        top_k: int = 10,
        min_score: float = 0.0,
        tags: list[str] | None = None,
        agent_id: str | None = None,
    ) -> list[RecallResult]:
        """
        Semantic search over stored memories.

        Args:
            query:     Natural-language query.
            top_k:     Maximum results to return.
            min_score: Minimum cosine similarity threshold (0.0 = return all).
            tags:      Optional tag filter (client-side post-filter).
            agent_id:  Override the client-level agent_id.

        Returns:
            List of :class:`~cortexos.types.RecallResult`, sorted by score descending.
        """
        params: dict[str, Any] = {
            "q": query,
            "agent_id": agent_id or self.agent_id,
            "top_k": top_k,
        }
        resp = self._http.get(f"{self._prefix}/memories/search", params=params)
        results = [
            RecallResult(memory=Memory._from_api(item["memory"]), score=item["similarity"])
            for item in resp.json()
            if item["similarity"] >= min_score
        ]
        if tags:
            tag_set = set(tags)
            results = [r for r in results if tag_set.intersection(r.memory.tags)]
        return results

    # ── Attribution (EAS) ──────────────────────────────────────────────────

    def attribute(
        self,
        query: str,
        response: str,
        memory_ids: list[str],
        *,
        agent_id: str | None = None,
    ) -> Attribution:
        """
        Run EAS attribution: score how much each memory contributed to the response.

        Args:
            query:      The original query sent to the LLM.
            response:   The LLM's response text.
            memory_ids: IDs of memories that were provided as context.
            agent_id:   Override the client-level agent_id.

        Returns:
            :class:`~cortexos.types.Attribution` with a ``scores`` dict.
        """
        payload = {
            "query_text": query,
            "response_text": response,
            "retrieved_memory_ids": memory_ids,
            "agent_id": agent_id or self.agent_id,
        }
        resp = self._http.post(f"{self._prefix}/transactions", json=payload)
        return Attribution._from_api(resp.json(), query=query, response=response)

    def cama_attribute(
        self,
        transaction_id: str,
    ) -> CAMAAttribution:
        """
        Run CAMA (Claim-Aware Memory Attribution) on an existing transaction.

        CAMA decomposes the response into claims, runs NLI entailment,
        computes Shapley values, and detects hallucinations.

        Args:
            transaction_id: ID of a completed transaction.

        Returns:
            :class:`~cortexos.types.CAMAAttribution` with claim-level analysis.
        """
        resp = self._http.post(f"{self._prefix}/attribution/{transaction_id}/cama")
        return CAMAAttribution._from_api(resp.json(), transaction_id=transaction_id)

    def check(
        self,
        query: str,
        response: str,
        memory_ids: list[str],
        *,
        agent_id: str | None = None,
    ) -> CAMAAttribution:
        """
        One-shot hallucination check: create a transaction then run CAMA.

        Combines :meth:`attribute` and :meth:`cama_attribute` in a single call.

        Args:
            query:      The original query.
            response:   The LLM response to check.
            memory_ids: IDs of memories used as context.
            agent_id:   Override the client-level agent_id.

        Returns:
            :class:`~cortexos.types.CAMAAttribution` with claim-level analysis.
        """
        attr = self.attribute(query, response, memory_ids, agent_id=agent_id)
        return self.cama_attribute(attr.transaction_id)

    def forget_all(self, *, agent_id: str | None = None) -> int:
        """
        Delete all memories for the given agent.

        Returns:
            Number of memories deleted.
        """
        count = 0
        while True:
            page = self.list(agent_id=agent_id, limit=50, offset=0)
            if not page.items:
                break
            for mem in page.items:
                self.forget(mem.id)
                count += 1
        return count

    def recall_and_attribute(
        self,
        query: str,
        response: str,
        *,
        top_k: int = 10,
        min_score: float = 0.0,
        agent_id: str | None = None,
    ) -> RecallAndAttributeResult:
        """
        Recall relevant memories for a query, then attribute the response to them.

        This is a convenience method that combines :meth:`recall` and :meth:`attribute`
        in a single call.

        Args:
            query:     The original query.
            response:  The LLM's response to attribute.
            top_k:     Max memories to recall.
            min_score: Minimum recall similarity threshold.
            agent_id:  Override the client-level agent_id.

        Returns:
            :class:`~cortexos.types.RecallAndAttributeResult`
        """
        aid = agent_id or self.agent_id
        recall_results = self.recall(query, top_k=top_k, min_score=min_score, agent_id=aid)
        memory_ids = [r.memory.id for r in recall_results]
        attribution = self.attribute(query, response, memory_ids, agent_id=aid)
        return RecallAndAttributeResult(memories=recall_results, attribution=attribution)

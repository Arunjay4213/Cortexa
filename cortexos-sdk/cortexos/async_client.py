"""Asynchronous CortexOS client for the v2 verification API."""

from __future__ import annotations

from typing import Any

from cortexos._http import AsyncHTTP
from cortexos.client import _DEFAULT_BASE_URL, _DEFAULT_TIMEOUT, _DEFAULT_RETRIES
from cortexos.models import CheckResult, GateResult, MemoryHealthResult, MemoryWriteResult, TraceResult


class AsyncCortex:
    """
    Asynchronous CortexOS SDK client.

    Usage::

        from cortexos import AsyncCortex

        async with AsyncCortex(api_key="cx-...") as cx:
            result = await cx.check(
                response="The return window is 30 days",
                sources=["Return policy: 30-day window for all items."],
            )
            print(result.hallucination_index)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        agent_id: str = "default",
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_RETRIES,
    ):
        self.agent_id = agent_id
        self._http = AsyncHTTP(base_url, api_key, timeout, max_retries)

    async def __aenter__(self) -> "AsyncCortex":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying async HTTP connection pool."""
        await self._http.aclose()

    async def check(
        self,
        response: str,
        sources: list[str],
        *,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> CheckResult:
        """
        Run full verification: decompose -> numerical -> fuzzy -> NLI.

        Args:
            response: The text to verify.
            sources:  Ground-truth source documents.
            agent_id: Override the client-level agent_id.
            config:   Optional overrides.

        Returns:
            CheckResult with per-claim verdicts and hallucination index.
        """
        payload: dict[str, Any] = {
            "response": response,
            "sources": sources,
            "agent_id": agent_id or self.agent_id,
        }
        if config:
            payload["config"] = config
        resp = await self._http.post("/v1/check", json=payload)
        return CheckResult._from_api(resp.json())

    async def gate(
        self,
        memory: str,
        sources: list[str],
        *,
        agent_id: str | None = None,
    ) -> GateResult:
        """
        Gate check: should this memory be stored?

        Args:
            memory:   The candidate memory text.
            sources:  Source documents to verify against.
            agent_id: Override the client-level agent_id.

        Returns:
            GateResult with grounded flag and flagged claims.
        """
        payload: dict[str, Any] = {
            "candidate_memory": memory,
            "sources": sources,
            "agent_id": agent_id or self.agent_id,
        }
        resp = await self._http.post("/v1/gate", json=payload)
        return GateResult._from_api(resp.json())

    async def memory_write(
        self,
        memory: str,
        *,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryWriteResult:
        """
        Write a memory with automatic duplicate detection.

        Args:
            memory:   The memory text to store.
            agent_id: Override the client-level agent_id.
            metadata: Optional key-value metadata to attach.

        Returns:
            MemoryWriteResult with status 'written' | 'duplicate' | 'merged'.
        """
        payload: dict[str, Any] = {
            "memory": memory,
            "agent_id": agent_id or self.agent_id,
        }
        if metadata:
            payload["metadata"] = metadata
        resp = await self._http.post("/v1/memory/write", json=payload)
        return MemoryWriteResult._from_api(resp.json())

    async def memory_health(self, agent_id: str | None = None) -> MemoryHealthResult:
        """
        Get memory health stats for an agent.

        Returns duplicate %, unique memory count, and token burn savings.

        Args:
            agent_id: Override the client-level agent_id.
        """
        aid = agent_id or self.agent_id
        resp = await self._http.get(f"/v1/memory/health/{aid}")
        return MemoryHealthResult._from_api(resp.json())

    async def trace(
        self,
        query: str,
        *,
        agent_id: str | None = None,
        top_k: int = 5,
    ) -> TraceResult:
        """
        Trace which memories are most relevant to a query.

        When an agent gives a wrong answer, run cx.trace(answer) to find
        which stored memory caused it.

        Args:
            query:    The text to trace (e.g. the wrong agent answer).
            agent_id: Override the client-level agent_id.
            top_k:    Maximum number of matching memories to return.
        """
        payload: dict[str, Any] = {
            "query": query,
            "agent_id": agent_id or self.agent_id,
            "top_k": top_k,
        }
        resp = await self._http.post("/v1/memory/trace", json=payload)
        return TraceResult._from_api(resp.json())

    async def memory_clear(self, agent_id: str | None = None) -> dict:
        """
        Clear all memories for an agent.

        Args:
            agent_id: Override the client-level agent_id.
        """
        aid = agent_id or self.agent_id
        resp = await self._http.delete(f"/v1/memory/{aid}")
        return resp.json()

    async def health(self) -> dict:
        """Check server health."""
        resp = await self._http.get("/healthz")
        return resp.json()

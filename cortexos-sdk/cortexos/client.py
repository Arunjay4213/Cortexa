"""Synchronous CortexOS client for the v2 verification API."""

from __future__ import annotations

import os
from typing import Any

from cortexos._http import SyncHTTP
from cortexos.models import CheckResult, GateResult, MemoryHealthResult, MemoryWriteResult, TraceResult

_DEFAULT_BASE_URL = os.environ.get("CORTEX_URL", "https://api.cortexa.ink")
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_RETRIES = 3


class Cortex:
    """
    Synchronous CortexOS SDK client.

    Usage::

        from cortexos import Cortex

        cx = Cortex(api_key="cx-...")
        result = cx.check(
            response="The return window is 30 days",
            sources=["Return policy: 30-day window for all items."],
        )
        print(result.hallucination_index)  # 0.0
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
        self._http = SyncHTTP(base_url, api_key, timeout, max_retries)

    def __enter__(self) -> "Cortex":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def check(
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
            config:   Optional overrides (e.g. attribution settings).

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
        resp = self._http.post("/v1/check", json=payload)
        return CheckResult._from_api(resp.json())

    def gate(
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
        resp = self._http.post("/v1/gate", json=payload)
        return GateResult._from_api(resp.json())

    def memory_write(
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
        resp = self._http.post("/v1/memory/write", json=payload)
        return MemoryWriteResult._from_api(resp.json())

    def memory_health(self, agent_id: str | None = None) -> MemoryHealthResult:
        """
        Get memory health stats for an agent.

        Returns duplicate %, unique memory count, and token burn savings.

        Args:
            agent_id: Override the client-level agent_id.

        Returns:
            MemoryHealthResult with duplicate_pct and token_burn_savings_pct.
        """
        aid = agent_id or self.agent_id
        resp = self._http.get(f"/v1/memory/health/{aid}")
        return MemoryHealthResult._from_api(resp.json())

    def trace(
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

        Returns:
            TraceResult with ranked memory matches and relevance scores.
        """
        payload: dict[str, Any] = {
            "query": query,
            "agent_id": agent_id or self.agent_id,
            "top_k": top_k,
        }
        resp = self._http.post("/v1/memory/trace", json=payload)
        return TraceResult._from_api(resp.json())

    def memory_clear(self, agent_id: str | None = None) -> dict:
        """
        Clear all memories for an agent.

        Args:
            agent_id: Override the client-level agent_id.

        Returns:
            Dict with 'cleared' count and 'agent_id'.
        """
        aid = agent_id or self.agent_id
        resp = self._http.delete(f"/v1/memory/{aid}")
        return resp.json()

    def health(self) -> dict:
        """
        Check server health.

        Returns:
            Server health status dict.
        """
        resp = self._http.get("/healthz")
        return resp.json()

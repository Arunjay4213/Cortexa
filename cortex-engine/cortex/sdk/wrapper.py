"""
CortexMemory — OTel-instrumented wrapper around any Mem0-compatible client.

Non-blocking: all backend calls are wrapped in try/except so the SDK never
crashes the host application.

Two-phase attribution protocol:
  1. search() → returns results + initiates a pending transaction (gets txn_id)
  2. report_response(txn_id, response) → completes the transaction, triggers EAS
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("cortex.sdk")


class Mem0Client(Protocol):
    """Minimal Mem0 interface we wrap."""

    def add(self, data: str, **kwargs: Any) -> Any: ...
    def search(self, query: str, **kwargs: Any) -> Any: ...
    def get(self, memory_id: str, **kwargs: Any) -> Any: ...


class CortexMemory:
    """Wraps a Mem0 client, adding OTel spans and optional backend reporting."""

    def __init__(
        self,
        client: Mem0Client,
        backend_url: str | None = None,
        agent_id: str = "default",
    ) -> None:
        self._client = client
        self._backend_url = backend_url
        self._agent_id = agent_id

    # ── Mem0 pass-throughs with OTel ──────────────────────────────────

    def add(self, data: str, **kwargs: Any) -> Any:
        with tracer.start_as_current_span("cortex.memory.add") as span:
            span.set_attribute("cortex.agent_id", self._agent_id)
            span.set_attribute("cortex.content_length", len(data))
            try:
                result = self._client.add(data, **kwargs)
                span.set_attribute("cortex.success", True)
                self._report_add(data, result)
                return result
            except Exception as exc:
                span.set_attribute("cortex.success", False)
                span.record_exception(exc)
                logger.warning("cortex.add failed: %s", exc)
                return self._client.add(data, **kwargs)

    def search(
        self, query: str, **kwargs: Any
    ) -> tuple[Any, str | None]:
        """Search memories and optionally initiate a pending transaction.

        Returns (results, transaction_id).  transaction_id is None when
        no backend is configured.  Pass it to ``report_response()``
        once the LLM response is available.
        """
        with tracer.start_as_current_span("cortex.memory.search") as span:
            span.set_attribute("cortex.agent_id", self._agent_id)
            span.set_attribute("cortex.query_length", len(query))
            try:
                results = self._client.search(query, **kwargs)
                k = len(results) if isinstance(results, list) else 0
                span.set_attribute("cortex.retrieved_count", k)
                span.set_attribute("cortex.success", True)

                # Initiate pending transaction if backend configured
                txn_id = self._initiate_transaction(query, results)
                if txn_id:
                    span.set_attribute("cortex.transaction_id", txn_id)

                return results, txn_id
            except Exception as exc:
                span.set_attribute("cortex.success", False)
                span.record_exception(exc)
                logger.warning("cortex.search failed: %s", exc)
                return self._client.search(query, **kwargs), None

    def get(self, memory_id: str, **kwargs: Any) -> Any:
        with tracer.start_as_current_span("cortex.memory.get") as span:
            span.set_attribute("cortex.agent_id", self._agent_id)
            span.set_attribute("cortex.memory_id", memory_id)
            try:
                result = self._client.get(memory_id, **kwargs)
                span.set_attribute("cortex.success", True)
                return result
            except Exception as exc:
                span.set_attribute("cortex.success", False)
                span.record_exception(exc)
                logger.warning("cortex.get failed: %s", exc)
                return self._client.get(memory_id, **kwargs)

    # ── Two-phase deferred attribution ────────────────────────────────

    def report_response(
        self,
        transaction_id: str,
        response: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> dict | None:
        """Phase 2: Complete a pending transaction with the LLM response.

        This triggers EAS computation on the backend. Call this once you
        have the response text — the backend already knows the query and
        retrieved memory IDs from the initiate call.
        """
        if not self._backend_url:
            return None
        with tracer.start_as_current_span("cortex.report_response") as span:
            span.set_attribute("cortex.agent_id", self._agent_id)
            span.set_attribute("cortex.transaction_id", transaction_id)
            try:
                import httpx

                resp = httpx.post(
                    f"{self._backend_url}/api/v1/transactions/{transaction_id}/complete",
                    json={
                        "response_text": response,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    timeout=5.0,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                span.record_exception(exc)
                logger.warning("cortex.report_response failed: %s", exc)
                return None

    def report_full(
        self,
        query: str,
        response: str,
        retrieved_memory_ids: list[str],
        model: str = "unknown",
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> dict | None:
        """Single-shot: report a complete transaction (query + response together).

        Use this when the response is available at the same time as the search,
        or when you don't need the two-phase protocol.
        """
        if not self._backend_url:
            return None
        with tracer.start_as_current_span("cortex.report_full") as span:
            span.set_attribute("cortex.agent_id", self._agent_id)
            span.set_attribute("cortex.memory_count", len(retrieved_memory_ids))
            try:
                import httpx

                resp = httpx.post(
                    f"{self._backend_url}/api/v1/transactions",
                    json={
                        "query_text": query,
                        "response_text": response,
                        "retrieved_memory_ids": retrieved_memory_ids,
                        "agent_id": self._agent_id,
                        "model": model,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    timeout=5.0,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                span.record_exception(exc)
                logger.warning("cortex.report_full failed: %s", exc)
                return None

    # ── Internal helpers ──────────────────────────────────────────────

    def _initiate_transaction(self, query: str, results: Any) -> str | None:
        """Phase 1: Best-effort POST to create a pending transaction."""
        if not self._backend_url:
            return None
        try:
            import httpx

            memory_ids = []
            if isinstance(results, list):
                for r in results:
                    if isinstance(r, dict) and "id" in r:
                        memory_ids.append(r["id"])

            resp = httpx.post(
                f"{self._backend_url}/api/v1/transactions/initiate",
                json={
                    "query_text": query,
                    "retrieved_memory_ids": memory_ids,
                    "agent_id": self._agent_id,
                },
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json().get("transaction_id")
        except Exception as exc:
            logger.debug("cortex._initiate_transaction failed: %s", exc)
            return None

    def _report_add(self, data: str, result: Any) -> None:
        """Best-effort POST to backend when a memory is added."""
        if not self._backend_url:
            return
        try:
            import httpx

            httpx.post(
                f"{self._backend_url}/api/v1/memories",
                json={
                    "content": data,
                    "agent_id": self._agent_id,
                },
                timeout=5.0,
            )
        except Exception as exc:
            logger.debug("cortex._report_add failed: %s", exc)

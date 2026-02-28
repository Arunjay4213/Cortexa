"""CortexOS verification client — async HTTP client for /v1/check, /v1/gate, /v1/shield."""

from __future__ import annotations

import asyncio
import logging
import os
import warnings
from typing import Any

import httpx

from cortexos.models import CheckResult, GateResult, ShieldResult

logger = logging.getLogger("cortexos.verification")

_DEFAULT_BASE_URL = os.environ.get("CORTEX_URL", "https://api.cortexa.ink")
_DEFAULT_TIMEOUT = 30.0


class VerificationClient:
    """
    Thin async HTTP client for the CortexOS verification API.
    Used internally by integration wrappers.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self._timeout,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def check(
        self,
        response: str,
        sources: list[str],
        config: dict[str, Any] | None = None,
    ) -> CheckResult:
        """
        Run full verification: decompose → numerical → fuzzy → NLI.

        Args:
            response: The text to verify.
            sources:  Ground-truth source documents.
            config:   Optional overrides (e.g. threshold).

        Returns:
            CheckResult with per-claim verdicts and hallucination index.
        """
        payload: dict[str, Any] = {"response": response, "sources": sources}
        if config:
            payload["config"] = config
        client = self._get_client()
        resp = await client.post("/v1/check", json=payload)
        resp.raise_for_status()
        return CheckResult._from_api(resp.json())

    async def gate(
        self,
        candidate_memory: str,
        sources: list[str],
    ) -> GateResult:
        """
        Gate check: should this memory be stored?

        Args:
            candidate_memory: The memory text about to be written.
            sources:          Source documents to verify against.

        Returns:
            GateResult with grounded flag and flagged claims.
        """
        payload = {"candidate_memory": candidate_memory, "sources": sources}
        client = self._get_client()
        resp = await client.post("/v1/gate", json=payload)
        resp.raise_for_status()
        return GateResult._from_api(resp.json())

    async def shield(
        self,
        candidate_memory: str,
        source_type: str = "unknown",
    ) -> ShieldResult:
        """
        Shield check: detect injection attacks or anomalies.

        Note: /v1/shield endpoint may not be implemented yet.
        Falls back to a safe default if unavailable.

        Args:
            candidate_memory: The memory text to scan.
            source_type:      Context for the memory origin.

        Returns:
            ShieldResult with safe flag and threat details.
        """
        payload = {"content": candidate_memory, "source_type": source_type}
        client = self._get_client()
        try:
            resp = await client.post("/v1/shield", json=payload)
            resp.raise_for_status()
            return ShieldResult._from_api(resp.json())
        except (httpx.HTTPStatusError, httpx.RequestError):
            # Shield endpoint not available — fail open
            return ShieldResult(safe=True, source_type=source_type)

    # ── Sync wrappers ────────────────────────────────────────────────────

    def _run_sync(self, coro: Any) -> Any:
        """Run an async coroutine synchronously."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context — warn the developer
            warnings.warn(
                "Sync CortexOS method called from async context. "
                "Use the async API (e.g. await cortex.check()) instead. "
                "Falling back to thread pool executor.",
                RuntimeWarning,
                stacklevel=3,
            )
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def check_sync(
        self,
        response: str,
        sources: list[str],
        config: dict[str, Any] | None = None,
    ) -> CheckResult:
        """Synchronous wrapper for check()."""
        return self._run_sync(self.check(response, sources, config))

    def gate_sync(
        self,
        candidate_memory: str,
        sources: list[str],
    ) -> GateResult:
        """Synchronous wrapper for gate()."""
        return self._run_sync(self.gate(candidate_memory, sources))

    def shield_sync(
        self,
        candidate_memory: str,
        source_type: str = "unknown",
    ) -> ShieldResult:
        """Synchronous wrapper for shield()."""
        return self._run_sync(self.shield(candidate_memory, source_type))


def _fail_open_warning(operation: str, error: Exception) -> None:
    """Log a warning when CortexOS is unreachable (fail-open policy)."""
    warnings.warn(
        f"CortexOS {operation} unavailable ({type(error).__name__}: {error}). "
        f"Allowing write to proceed (fail-open policy).",
        stacklevel=3,
    )
    logger.warning(
        "CortexOS %s failed: %s. Failing open.", operation, error
    )

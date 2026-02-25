"""
Core async test runner for CortexOS stress tests.

Usage:
    async with AsyncWorkerPool(workers=8, base_url=BASE_URL) as pool:
        results = await pool.run_tasks(task_list, collector)

Each task is a coroutine factory: async def task(client) -> OperationResult
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable, Coroutine
from typing import Any

import httpx

from stress_tests.config import BASE_URL, StressConfig
from stress_tests.metrics import ErrorType, MetricsCollector, OperationResult, classify_error

# Module-level cached key so individual stress test helpers that create their
# own AsyncWorkerPool instances pick up auth automatically.
_SESSION_API_KEY: str = ""


def _get_session_api_key() -> str:
    global _SESSION_API_KEY
    if _SESSION_API_KEY:
        return _SESSION_API_KEY
    # Try env var first (set by CI or conftest)
    key = os.environ.get("CORTEX_STRESS_API_KEY", "")
    if key:
        _SESSION_API_KEY = key
    return _SESSION_API_KEY


def set_session_api_key(key: str) -> None:
    """Called by conftest once a key is provisioned for the session."""
    global _SESSION_API_KEY
    _SESSION_API_KEY = key
    os.environ["CORTEX_STRESS_API_KEY"] = key


TaskFn = Callable[[httpx.AsyncClient], Coroutine[Any, Any, OperationResult]]


async def timed_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> OperationResult:
    """Execute an HTTP request and return a timed OperationResult."""
    t0 = time.perf_counter()
    try:
        resp = await client.request(method, url, **kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code < 400:
            return OperationResult(
                success=True,
                latency_ms=latency_ms,
                status_code=resp.status_code,
                data=resp.json() if resp.content else None,
            )
        else:
            err_type = classify_error(None, resp.status_code)
            return OperationResult(
                success=False,
                latency_ms=latency_ms,
                status_code=resp.status_code,
                error_type=err_type,
                error_msg=resp.text[:200],
            )
    except httpx.TimeoutException as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return OperationResult(
            success=False,
            latency_ms=latency_ms,
            error_type=ErrorType.TIMEOUT,
            error_msg=str(exc)[:200],
        )
    except httpx.ConnectError as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return OperationResult(
            success=False,
            latency_ms=latency_ms,
            error_type=ErrorType.CONNECTION_ERROR,
            error_msg=str(exc)[:200],
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return OperationResult(
            success=False,
            latency_ms=latency_ms,
            error_type=classify_error(exc),
            error_msg=str(exc)[:200],
        )


class AsyncWorkerPool:
    """Manages N concurrent async workers pulling from a shared task queue."""

    def __init__(
        self,
        workers: int,
        base_url: str = BASE_URL,
        timeout: float = StressConfig.HTTP_TIMEOUT,
        api_key: str | None = None,
    ) -> None:
        self.workers = workers
        self.base_url = base_url
        self.timeout = timeout
        self.api_key = api_key or _get_session_api_key()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncWorkerPool":
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                connect=StressConfig.HTTP_CONNECT_TIMEOUT,
                read=self.timeout,
                write=self.timeout,
                pool=self.timeout,
            ),
            limits=httpx.Limits(
                max_connections=256,
                max_keepalive_connections=128,
            ),
            headers=headers,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    async def run_tasks(
        self,
        tasks: list[TaskFn],
        collector: MetricsCollector,
        *,
        barrier: asyncio.Event | None = None,
    ) -> None:
        """Run all tasks with N concurrent workers, recording results into collector."""
        queue: asyncio.Queue[TaskFn] = asyncio.Queue()
        for t in tasks:
            await queue.put(t)

        if barrier:
            await barrier.wait()

        async def worker() -> None:
            assert self._client is not None
            while True:
                try:
                    task = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                result = await task(self._client)
                collector.record(result)
                queue.task_done()

        worker_tasks = [asyncio.create_task(worker()) for _ in range(self.workers)]
        await asyncio.gather(*worker_tasks)

    async def run_sustained(
        self,
        task_factory: Callable[[], TaskFn],
        collector: MetricsCollector,
        duration_s: float,
        rps_limit: float | None = None,
    ) -> None:
        """Run a sustained workload for *duration_s* seconds across N workers."""
        assert self._client is not None
        deadline = time.monotonic() + duration_s
        interval = (1.0 / rps_limit) if rps_limit else 0.0

        semaphore = asyncio.Semaphore(self.workers)

        async def run_one() -> None:
            async with semaphore:
                task = task_factory()
                result = await task(self._client)  # type: ignore[arg-type]
                collector.record(result)

        tasks_launched: list[asyncio.Task] = []
        while time.monotonic() < deadline:
            t = asyncio.create_task(run_one())
            tasks_launched.append(t)
            if interval > 0:
                await asyncio.sleep(interval)
            else:
                await asyncio.sleep(0)  # yield control

        await asyncio.gather(*tasks_launched, return_exceptions=True)


# ── Convenience helpers ──────────────────────────────────────────────────────

def make_memory_task(
    content: str,
    agent_id: str = "stress-test",
    tier: str = "warm",
    criticality: float = 0.5,
    metadata: dict | None = None,
) -> TaskFn:
    """Return a task that POSTs a single memory."""
    payload = {
        "content": content,
        "agent_id": agent_id,
        "tier": tier,
        "criticality": criticality,
        "metadata": metadata or {},
    }

    async def task(client: httpx.AsyncClient) -> OperationResult:
        return await timed_request(client, "POST", "/api/v1/memories", json=payload)

    return task


def make_search_task(query: str, agent_id: str | None = None, top_k: int = 10) -> TaskFn:
    """Return a task that GETs /memories/search."""
    params: dict[str, Any] = {"q": query, "top_k": top_k}
    if agent_id:
        params["agent_id"] = agent_id

    async def task(client: httpx.AsyncClient) -> OperationResult:
        return await timed_request(client, "GET", "/api/v1/memories/search", params=params)

    return task


def make_transaction_task(
    query: str,
    response: str,
    memory_ids: list[str],
    agent_id: str = "stress-test",
) -> TaskFn:
    """Return a task that POSTs a full transaction."""
    payload = {
        "query_text": query,
        "response_text": response,
        "retrieved_memory_ids": memory_ids,
        "agent_id": agent_id,
    }

    async def task(client: httpx.AsyncClient) -> OperationResult:
        return await timed_request(client, "POST", "/api/v1/transactions", json=payload)

    return task


def make_delete_task(memory_id: str) -> TaskFn:
    async def task(client: httpx.AsyncClient) -> OperationResult:
        return await timed_request(client, "DELETE", f"/api/v1/memories/{memory_id}")

    return task


def make_get_task(memory_id: str) -> TaskFn:
    async def task(client: httpx.AsyncClient) -> OperationResult:
        return await timed_request(client, "GET", f"/api/v1/memories/{memory_id}")

    return task

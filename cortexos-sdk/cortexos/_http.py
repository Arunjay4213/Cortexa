"""Internal HTTP layer — sync and async httpx clients with retry and auth."""

from __future__ import annotations

import time
from typing import Any

import httpx

from cortexos.errors import (
    AuthError,
    CortexError,
    MemoryNotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)

_DEFAULT_RETRIES = 3
_RETRY_STATUSES = {429, 502, 503, 504}
_BACKOFF_BASE = 0.5  # seconds


def _build_headers(api_key: str | None) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _raise_for_status(resp: httpx.Response, memory_id: str | None = None) -> None:
    if resp.status_code < 400:
        return
    body = resp.text

    if resp.status_code == 401 or resp.status_code == 403:
        raise AuthError("Invalid or missing API key", status_code=resp.status_code, response_body=body)

    if resp.status_code == 404:
        if memory_id:
            raise MemoryNotFoundError(memory_id)
        raise CortexError("Resource not found", status_code=404, response_body=body)

    if resp.status_code == 422:
        raise ValidationError(f"Validation error: {body[:300]}", status_code=422, response_body=body)

    if resp.status_code == 429:
        retry_after: float | None = None
        try:
            retry_after = float(resp.headers.get("Retry-After", ""))
        except (ValueError, TypeError):
            pass
        raise RateLimitError(retry_after=retry_after, status_code=429, response_body=body)

    if resp.status_code >= 500:
        raise ServerError(f"Server error {resp.status_code}: {body[:300]}", status_code=resp.status_code, response_body=body)

    raise CortexError(f"Unexpected HTTP {resp.status_code}: {body[:300]}", status_code=resp.status_code, response_body=body)


# ── Sync HTTP client ───────────────────────────────────────────────────────


class SyncHTTP:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout: float,
        max_retries: int,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            headers=_build_headers(api_key),
            timeout=timeout,
        )
        self._max_retries = max_retries

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SyncHTTP":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        memory_id: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = self._client.request(method, path, **kwargs)
                if resp.status_code in _RETRY_STATUSES and attempt < self._max_retries - 1:
                    time.sleep(_BACKOFF_BASE * (2 ** attempt))
                    continue
                _raise_for_status(resp, memory_id=memory_id)
                return resp
            except (AuthError, MemoryNotFoundError, ValidationError):
                raise  # Never retry these
            except (RateLimitError, ServerError, CortexError) as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    time.sleep(_BACKOFF_BASE * (2 ** attempt))
            except httpx.TimeoutException as exc:
                last_exc = CortexError(f"Request timed out: {exc}")
                if attempt < self._max_retries - 1:
                    time.sleep(_BACKOFF_BASE * (2 ** attempt))
            except httpx.RequestError as exc:
                last_exc = CortexError(f"Connection error: {exc}")
                if attempt < self._max_retries - 1:
                    time.sleep(_BACKOFF_BASE * (2 ** attempt))
        raise last_exc or CortexError("Request failed after retries")

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)


# ── Async HTTP client ──────────────────────────────────────────────────────


class AsyncHTTP:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout: float,
        max_retries: int,
    ):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=_build_headers(api_key),
            timeout=timeout,
        )
        self._max_retries = max_retries

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncHTTP":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        memory_id: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        import asyncio

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code in _RETRY_STATUSES and attempt < self._max_retries - 1:
                    await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                    continue
                _raise_for_status(resp, memory_id=memory_id)
                return resp
            except (AuthError, MemoryNotFoundError, ValidationError):
                raise
            except (RateLimitError, ServerError, CortexError) as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
            except httpx.TimeoutException as exc:
                last_exc = CortexError(f"Request timed out: {exc}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
            except httpx.RequestError as exc:
                last_exc = CortexError(f"Connection error: {exc}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
        raise last_exc or CortexError("Request failed after retries")

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

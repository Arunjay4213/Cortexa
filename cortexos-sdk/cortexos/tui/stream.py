"""SSE client that posts Textual messages to the app."""

from __future__ import annotations

import asyncio
import json
from typing import Callable

import httpx
from httpx_sse import aconnect_sse
from textual.message import Message


class SSEEvent(Message):
    """An SSE event received from the server."""

    def __init__(self, data: dict) -> None:
        super().__init__()
        self.data = data


class SSEConnected(Message):
    """SSE connection established."""


class SSEDisconnected(Message):
    """SSE connection lost."""


class SSEStream:
    """Manages the SSE connection and delivers events to the app."""

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._task: asyncio.Task | None = None
        self._on_event: Callable[[dict], None] | None = None
        self._on_connected: Callable[[], None] | None = None
        self._on_disconnected: Callable[[], None] | None = None

    def start(
        self,
        on_event: Callable[[dict], None],
        on_connected: Callable[[], None],
        on_disconnected: Callable[[], None],
    ) -> None:
        self._on_event = on_event
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with aconnect_sse(
                        client,
                        "GET",
                        f"{self.base_url}/v1/stream",
                        headers=headers,
                    ) as sse:
                        if self._on_connected:
                            self._on_connected()
                        async for event in sse.aiter_sse():
                            try:
                                data = json.loads(event.data)
                            except (json.JSONDecodeError, TypeError):
                                continue
                            if self._on_event:
                                self._on_event(data)
            except asyncio.CancelledError:
                break
            except Exception:
                if self._on_disconnected:
                    self._on_disconnected()
                await asyncio.sleep(3)

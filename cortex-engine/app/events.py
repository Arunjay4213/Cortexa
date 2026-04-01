"""In-process pub/sub event bus for SSE streaming."""

from __future__ import annotations

import asyncio
import json


class EventBus:
    """
    In-process pub/sub. One queue per connected SSE client.
    Initialized as singleton — imported by checker.py and stream.py.
    """

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._queues.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    async def publish(self, event: dict) -> None:
        """Publish to all subscribers. Drop oldest if queue full."""
        payload = json.dumps(event)
        async with self._lock:
            queues = list(self._queues)
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()  # drop oldest
                    q.put_nowait(payload)
                except Exception:
                    pass


# Singleton
event_bus = EventBus()

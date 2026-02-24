"""WebSocket real-time layer for dashboard updates.

Clients subscribe to channels ("dashboard" or "agent:{id}").
Every message includes a monotonically increasing sequence_id per channel
so frontends can detect gaps and trigger full revalidation.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections per channel."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self._sequence: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        async with self._lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = []
                self._sequence[channel] = 0
            self.active_connections[channel].append(websocket)

    async def disconnect(self, websocket: WebSocket, channel: str) -> None:
        async with self._lock:
            if channel in self.active_connections:
                try:
                    self.active_connections[channel].remove(websocket)
                except ValueError:
                    pass
                if not self.active_connections[channel]:
                    del self.active_connections[channel]

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        """Broadcast a message to all connections on a channel."""
        async with self._lock:
            if channel not in self.active_connections:
                return
            self._sequence[channel] = self._sequence.get(channel, 0) + 1
            seq = self._sequence[channel]

        payload = {
            "sequence_id": seq,
            **message,
        }
        data = json.dumps(payload, default=str)

        connections = self.active_connections.get(channel, [])
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self.active_connections[channel].remove(ws)
                    except (ValueError, KeyError):
                        pass

    @property
    def connection_count(self) -> int:
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager — used by other API modules to broadcast
manager = ConnectionManager()


@router.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    await manager.connect(websocket, channel)
    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            # Echo ping-pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket, channel)
    except Exception:
        await manager.disconnect(websocket, channel)

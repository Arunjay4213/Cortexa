"""Tests for WebSocket real-time layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from cortex.api.websocket import ConnectionManager


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect(ws, "dashboard")
        assert manager.connection_count == 1
        assert "dashboard" in manager.active_connections
        assert len(manager.active_connections["dashboard"]) == 1

        await manager.disconnect(ws, "dashboard")
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_channel(self):
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(ws1, "dashboard")
        await manager.connect(ws2, "dashboard")

        await manager.broadcast("dashboard", {"type": "test", "data": {"value": 1}})

        # Both should receive the message
        assert ws1.send_text.called
        assert ws2.send_text.called

    @pytest.mark.asyncio
    async def test_broadcast_different_channels(self):
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(ws1, "dashboard")
        await manager.connect(ws2, "agent:abc")

        await manager.broadcast("dashboard", {"type": "test", "data": {}})

        # Only ws1 should receive
        assert ws1.send_text.called
        assert not ws2.send_text.called

    @pytest.mark.asyncio
    async def test_sequence_id_monotonic(self):
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect(ws, "dashboard")

        await manager.broadcast("dashboard", {"type": "test1"})
        await manager.broadcast("dashboard", {"type": "test2"})
        await manager.broadcast("dashboard", {"type": "test3"})

        # Check that sequence IDs are monotonically increasing
        calls = ws.send_text.call_args_list
        import json
        seq_ids = [json.loads(call.args[0])["sequence_id"] for call in calls]
        assert seq_ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_channel(self):
        manager = ConnectionManager()
        # Should not raise
        await manager.broadcast("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_dead_connection_cleanup(self):
        manager = ConnectionManager()
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("Connection closed")

        await manager.connect(ws_alive, "dashboard")
        await manager.connect(ws_dead, "dashboard")
        assert manager.connection_count == 2

        await manager.broadcast("dashboard", {"type": "test"})

        # Dead connection should be cleaned up
        assert manager.connection_count == 1

    @pytest.mark.asyncio
    async def test_multiple_channels(self):
        manager = ConnectionManager()
        ws = AsyncMock()

        await manager.connect(ws, "dashboard")
        await manager.connect(ws, "agent:abc")

        assert manager.connection_count == 2

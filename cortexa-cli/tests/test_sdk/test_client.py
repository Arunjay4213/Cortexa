"""Tests for cortexa.sdk.client — Cortexa client."""

from unittest.mock import MagicMock, patch

import pytest

from cortexa.engine.exceptions import BackendError, ConfigError
from cortexa.engine.models import (
    AuditResult,
    GateResult,
    Memory,
    TraceResult,
)
from cortexa.sdk.backends.custom import InMemoryBackend
from cortexa.sdk.client import Cortexa, _create_backend
from cortexa.sdk.config import CortexaConfig


@pytest.fixture
def client():
    """Client with in-memory backend and mocked NLI."""
    cx = Cortexa(backend="memory", nli_backend="api")
    # Mock the NLI entailment backend to avoid API calls
    mock_backend = MagicMock()
    mock_backend.score_pairs.return_value = [(0.1, 0.8, 0.1)]
    cx.scorer.entailment._backend = mock_backend
    return cx


@pytest.fixture
def populated_client(client):
    """Client pre-loaded with memories."""
    import asyncio

    async def _populate():
        await client.add_memory("The premium plan costs $49.99 per month", source="pricing")
        await client.add_memory("Express shipping costs $9.99", source="shipping")
        await client.add_memory("Free shipping on orders over $50", source="promotions")
        await client.add_memory("Returns accepted within 30 days", source="returns")
        return client

    return asyncio.run(_populate())


class TestClientInit:
    def test_default_init(self):
        cx = Cortexa(backend="memory")
        assert isinstance(cx.backend, InMemoryBackend)

    def test_custom_backend_instance(self):
        backend = InMemoryBackend()
        cx = Cortexa(backend=backend)
        assert cx.backend is backend

    def test_config_overrides(self):
        cx = Cortexa(
            backend="memory",
            nli_backend="local",
            ghost_threshold=0.10,
            contradiction_threshold=0.8,
        )
        assert cx.config.nli.backend == "local"
        assert cx.config.thresholds.ghost_mas == 0.10
        assert cx.config.thresholds.contradiction == 0.8

    def test_explicit_config(self):
        config = CortexaConfig()
        config.nli.backend = "api"
        cx = Cortexa(backend="memory", config=config)
        assert cx.config is config

    def test_unknown_backend_raises(self):
        with pytest.raises(ConfigError, match="Unknown backend type"):
            Cortexa(backend="postgres")


class TestMemoryCRUD:
    @pytest.mark.asyncio
    async def test_add_memory(self, client):
        mem = await client.add_memory("Test content", source="test")
        assert isinstance(mem, Memory)
        assert mem.content == "Test content"
        assert mem.source == "test"

    @pytest.mark.asyncio
    async def test_add_and_get(self, client):
        mem = await client.add_memory("Test content")
        retrieved = await client.get_memory(mem.id)
        assert retrieved is not None
        assert retrieved.content == "Test content"

    @pytest.mark.asyncio
    async def test_search_memories(self, populated_client):
        results = await populated_client.search_memories("shipping")
        assert len(results) >= 1
        assert any("shipping" in m.content.lower() for m in results)

    @pytest.mark.asyncio
    async def test_list_memories(self, populated_client):
        results = await populated_client.list_memories()
        assert len(results) == 4

    @pytest.mark.asyncio
    async def test_delete_memory(self, client):
        mem = await client.add_memory("To delete")
        assert await client.delete_memory(mem.id) is True
        assert await client.get_memory(mem.id) is None

    @pytest.mark.asyncio
    async def test_update_memory(self, client):
        mem = await client.add_memory("Old content")
        updated = await client.update_memory(mem.id, content="New content")
        assert updated is not None
        assert updated.content == "New content"

    @pytest.mark.asyncio
    async def test_memory_count(self, populated_client):
        assert await populated_client.memory_count() == 4

    @pytest.mark.asyncio
    async def test_add_with_metadata(self, client):
        mem = await client.add_memory("Test", metadata={"key": "val"})
        assert mem.metadata == {"key": "val"}


class TestTrace:
    @pytest.mark.asyncio
    async def test_trace_with_explicit_memories(self, client):
        memories = [Memory(id="m1", content="Premium plan costs $49.99")]
        result = await client.trace(
            query="How much?",
            response="The price is $49.99",
            memories=memories,
        )
        assert isinstance(result, TraceResult)
        assert result.query == "How much?"
        assert result.response == "The price is $49.99"
        assert len(result.claims) >= 1
        assert 0.0 <= result.health_score <= 100.0

    @pytest.mark.asyncio
    async def test_trace_with_backend_search(self, populated_client):
        # Mock returns enough scores for the search results
        mock = populated_client.scorer.entailment._backend
        mock.score_pairs.return_value = [(0.1, 0.8, 0.1)] * 20

        result = await populated_client.trace(
            query="shipping",
            response="Express shipping costs $9.99",
        )
        assert isinstance(result, TraceResult)
        assert len(result.claims) >= 1

    @pytest.mark.asyncio
    async def test_trace_empty_response(self, client):
        result = await client.trace(
            query="test",
            response="",
            memories=[],
        )
        assert result.claims == []
        assert result.health_score == 100.0

    @pytest.mark.asyncio
    async def test_trace_rolling_window(self, client):
        memories = [Memory(id="m1", content="Test memory")]
        # Run multiple traces to fill the rolling window
        for i in range(3):
            await client.trace(
                query=f"query {i}",
                response=f"response {i}",
                memories=memories,
            )
        assert len(client._recent_traces) == 3


class TestAudit:
    @pytest.mark.asyncio
    async def test_audit_empty(self, client):
        result = await client.audit()
        assert isinstance(result, AuditResult)
        assert result.total_memories == 0
        assert result.health_score == 100.0

    @pytest.mark.asyncio
    async def test_audit_with_memories(self, populated_client):
        result = await populated_client.audit()
        assert result.total_memories == 4
        assert result.health_score >= 0.0

    @pytest.mark.asyncio
    async def test_audit_explicit_memories(self, client):
        memories = [Memory(id=f"m{i}", content=f"content {i}") for i in range(5)]
        result = await client.audit(memories=memories)
        assert result.total_memories == 5


class TestGate:
    @pytest.mark.asyncio
    async def test_gate_no_memories(self, client):
        result = await client.gate(query="test", memories=[])
        assert isinstance(result, GateResult)
        assert result.memories_scored == 0
        assert result.safe_to_generate is True

    @pytest.mark.asyncio
    async def test_gate_safe(self, client):
        memories = [
            Memory(
                id="m1",
                content="Plan costs $49.99",
                source="pricing",
                created_at=Memory.__fields__["created_at"].default_factory(),
            ),
        ]
        result = await client.gate(query="pricing", memories=memories)
        assert result.memories_scored == 1
        assert result.safe_to_generate is True
        assert result.risk_summary == "No risks detected"

    @pytest.mark.asyncio
    async def test_gate_with_stale(self, client):
        from datetime import datetime, timedelta

        old = datetime.utcnow() - timedelta(days=90)
        six_weeks_ago = datetime.utcnow() - timedelta(weeks=6)
        memories = [
            Memory(
                id="m1",
                content="Old policy",
                source="policy.md",
                created_at=old,
                source_updated_at=six_weeks_ago,
            ),
        ]
        result = await client.gate(query="policy", memories=memories)
        assert result.safe_to_generate is False
        assert len(result.stale) >= 1

    @pytest.mark.asyncio
    async def test_gate_with_backend_search(self, populated_client):
        result = await populated_client.gate(query="shipping")
        assert isinstance(result, GateResult)
        assert result.memories_scored >= 1


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_empty(self, client):
        score = await client.health()
        assert score == 100.0


class TestBackendFactory:
    def test_create_memory_backend(self):
        backend = _create_backend("memory", CortexaConfig())
        assert isinstance(backend, InMemoryBackend)

    def test_create_unknown_backend(self):
        with pytest.raises(ConfigError, match="Unknown backend type"):
            _create_backend("sqlite", CortexaConfig())

    def test_mem0_without_package(self):
        config = CortexaConfig()
        config.backend.mem0_api_key = "test-key"
        # This will either work (if mem0ai installed) or raise BackendError
        try:
            _create_backend("mem0", config)
        except BackendError:
            pass  # Expected if mem0ai not installed

    def test_chromadb_without_package(self):
        config = CortexaConfig()
        # This will either work (if chromadb installed) or raise BackendError
        try:
            _create_backend("chromadb", config)
        except BackendError:
            pass  # Expected if chromadb not installed

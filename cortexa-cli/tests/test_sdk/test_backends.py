"""Tests for memory backends — InMemoryBackend ABC compliance."""

import asyncio
from datetime import datetime, timedelta

import pytest

from cortexa.engine.models import Memory
from cortexa.sdk.backends.base import MemoryBackend
from cortexa.sdk.backends.custom import InMemoryBackend


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def sample_memory():
    return Memory(
        id="m1",
        content="The premium plan costs $49.99 per month",
        source="pricing_page",
        metadata={"category": "pricing"},
    )


@pytest.fixture
def sample_memories():
    now = datetime.utcnow()
    return [
        Memory(
            id=f"m{i}",
            content=f"Memory content {i}",
            source="test",
            created_at=now - timedelta(hours=i),
        )
        for i in range(10)
    ]


class TestInMemoryBackendABC:
    def test_is_memory_backend(self, backend):
        assert isinstance(backend, MemoryBackend)

    @pytest.mark.asyncio
    async def test_add_and_get(self, backend, sample_memory):
        mid = await backend.add(sample_memory)
        assert mid == "m1"

        retrieved = await backend.get("m1")
        assert retrieved is not None
        assert retrieved.content == sample_memory.content
        assert retrieved.source == "pricing_page"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, backend):
        result = await backend.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, backend, sample_memory):
        await backend.add(sample_memory)
        assert await backend.delete("m1") is True
        assert await backend.get("m1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend):
        assert await backend.delete("nonexistent") is False

    @pytest.mark.asyncio
    async def test_count(self, backend, sample_memories):
        assert await backend.count() == 0
        for m in sample_memories:
            await backend.add(m)
        assert await backend.count() == 10

    @pytest.mark.asyncio
    async def test_update_content(self, backend, sample_memory):
        await backend.add(sample_memory)
        updated = await backend.update("m1", content="New content")
        assert updated is not None
        assert updated.content == "New content"
        # Source should be unchanged
        assert updated.source == "pricing_page"

    @pytest.mark.asyncio
    async def test_update_metadata(self, backend, sample_memory):
        await backend.add(sample_memory)
        updated = await backend.update("m1", metadata={"new_key": "val"})
        assert updated is not None
        assert updated.metadata["new_key"] == "val"
        # Original metadata should be preserved
        assert updated.metadata["category"] == "pricing"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, backend):
        result = await backend.update("nonexistent", content="x")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self, backend, sample_memories):
        for m in sample_memories:
            await backend.add(m)
        deleted = await backend.clear()
        assert deleted == 10
        assert await backend.count() == 0


class TestInMemorySearch:
    @pytest.mark.asyncio
    async def test_search_finds_matching(self, backend):
        await backend.add(Memory(id="m1", content="Express shipping costs $9.99"))
        await backend.add(Memory(id="m2", content="Password reset links expire"))
        await backend.add(Memory(id="m3", content="Standard shipping takes 5-7 days"))

        results = await backend.search("shipping")
        assert len(results) == 2
        result_ids = {m.id for m in results}
        assert "m1" in result_ids
        assert "m3" in result_ids

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, backend):
        await backend.add(Memory(id="m1", content="Express SHIPPING available"))
        results = await backend.search("shipping")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_limit(self, backend):
        for i in range(20):
            await backend.add(Memory(id=f"m{i}", content=f"shipping option {i}"))
        results = await backend.search("shipping", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_no_match(self, backend):
        await backend.add(Memory(id="m1", content="Express shipping costs $9.99"))
        results = await backend.search("quantum physics")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_empty_store(self, backend):
        results = await backend.search("anything")
        assert results == []


class TestInMemoryListAll:
    @pytest.mark.asyncio
    async def test_list_all_order(self, backend, sample_memories):
        for m in sample_memories:
            await backend.add(m)
        results = await backend.list_all()
        # Should be newest first (m0 was created most recently)
        assert results[0].id == "m0"

    @pytest.mark.asyncio
    async def test_list_all_pagination(self, backend, sample_memories):
        for m in sample_memories:
            await backend.add(m)
        page1 = await backend.list_all(limit=3, offset=0)
        page2 = await backend.list_all(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        # No overlap
        ids1 = {m.id for m in page1}
        ids2 = {m.id for m in page2}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_list_all_empty(self, backend):
        results = await backend.list_all()
        assert results == []

    @pytest.mark.asyncio
    async def test_list_all_offset_beyond_end(self, backend, sample_memories):
        for m in sample_memories:
            await backend.add(m)
        results = await backend.list_all(limit=10, offset=100)
        assert results == []


class TestInMemoryBulk:
    @pytest.mark.asyncio
    async def test_add_bulk(self, backend, sample_memories):
        ids = await backend.add_bulk(sample_memories)
        assert len(ids) == 10
        assert await backend.count() == 10

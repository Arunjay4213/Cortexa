"""
Integration tests for the CortexOS SDK against a live cortex-engine server.

Run with:
    pytest tests/test_integration.py -v

Requires:
    CORTEX_BASE_URL env var (default: https://api.cortexa.ink)
    A running cortex-engine server with embedding backend healthy.

These tests are skipped automatically if the server is not reachable.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
import pytest_asyncio

from cortexos import AsyncCortex, Cortex
from cortexos.errors import MemoryNotFoundError

BASE_URL = os.environ.get("CORTEX_BASE_URL", "https://api.cortexa.ink")
ADMIN_SECRET = os.environ.get("CORTEX_ADMIN_SECRET", "cortex-admin-secret")
AGENT_PREFIX = "sdk-integ"


def _provision_api_key(agent_id: str | None = None) -> str:
    """Create a fresh API key via the admin endpoint. Returns plaintext key."""
    resp = httpx.post(
        f"{BASE_URL}/api-keys",
        json={
            "email": f"sdk-test-{uuid.uuid4().hex[:6]}@example.com",
            "name": "sdk-integration-test",
            "agent_id": agent_id,
            "rate_limit_rpm": 300,
        },
        headers={"Authorization": f"Bearer {ADMIN_SECRET}"},
        timeout=10,
    )
    assert resp.status_code == 201, f"Could not provision API key: {resp.text}"
    return resp.json()["key"]


# ── Server availability guard ──────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def server_up():
    try:
        resp = httpx.get(f"{BASE_URL}/healthz", timeout=5.0)
        if resp.status_code != 200:
            pytest.skip(f"CortexOS server returned {resp.status_code}")
    except httpx.ConnectError:
        pytest.skip(f"CortexOS server not reachable at {BASE_URL}")


@pytest.fixture(scope="session")
def session_api_key() -> str:
    """One high-rate-limit API key shared across the entire test session."""
    return _provision_api_key()


@pytest.fixture
def agent_id() -> str:
    return f"{AGENT_PREFIX}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cx(agent_id: str, session_api_key: str) -> Cortex:
    client = Cortex(agent_id=agent_id, base_url=BASE_URL, api_key=session_api_key)
    yield client
    try:
        page = client.list(limit=200)
        for mem in page.items:
            try:
                client.forget(mem.id)
            except Exception:
                pass
    except Exception:
        pass
    client.close()


@pytest_asyncio.fixture
async def async_cx(agent_id: str, session_api_key: str) -> AsyncCortex:
    client = AsyncCortex(agent_id=agent_id, base_url=BASE_URL, api_key=session_api_key)
    yield client
    try:
        page = await client.list(limit=200)
        for mem in page.items:
            try:
                await client.forget(mem.id)
            except Exception:
                pass
    except Exception:
        pass
    await client.aclose()


# ── Sync integration tests ─────────────────────────────────────────────────


def test_remember_and_get(cx: Cortex):
    mem = cx.remember(
        "User prefers to be contacted via email",
        importance=0.85,
        tags=["preferences", "communication"],
        metadata={"source": "integration_test"},
    )
    assert mem.id
    assert mem.content == "User prefers to be contacted via email"
    assert mem.importance == pytest.approx(0.85)
    assert "preferences" in mem.tags

    fetched = cx.get(mem.id)
    assert fetched.id == mem.id
    assert fetched.content == mem.content


def test_forget_then_not_found(cx: Cortex):
    mem = cx.remember("Temporary memory for deletion test")
    cx.forget(mem.id)
    with pytest.raises(MemoryNotFoundError):
        cx.get(mem.id)


def test_update_importance_and_tags(cx: Cortex):
    mem = cx.remember("Notification preferences", importance=0.5, tags=["preferences"])
    updated = cx.update(mem.id, importance=0.95, tags=["preferences", "confirmed"])

    assert updated.importance == pytest.approx(0.95)
    assert "confirmed" in updated.tags
    assert "preferences" in updated.tags


def test_list_pagination(cx: Cortex):
    # Insert 5 memories
    for i in range(5):
        cx.remember(f"Memory {i} for pagination test")

    page1 = cx.list(limit=3, offset=0)
    assert len(page1.items) == 3
    assert page1.total >= 5
    assert page1.has_more

    page2 = cx.list(limit=3, offset=3)
    assert len(page2.items) >= 2

    all_ids = {m.id for m in page1.items} | {m.id for m in page2.items}
    assert len(all_ids) >= 5  # No duplicates across pages


def test_recall_semantic_search(cx: Cortex):
    cx.remember("User's email address is alice@example.com", importance=0.9, tags=["contact"])
    cx.remember("User prefers dark mode in the UI", importance=0.7, tags=["ui"])
    cx.remember("User lives in San Francisco", importance=0.6, tags=["location"])

    results = cx.recall("how should I contact the user?", top_k=5)

    assert len(results) > 0
    # The email memory should rank first (most semantically similar)
    top_content = results[0].memory.content
    assert "email" in top_content.lower() or "contact" in top_content.lower()
    # Scores should be in descending order
    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score


def test_recall_min_score(cx: Cortex):
    cx.remember("Completely irrelevant content about purple elephants flying", importance=0.3)
    results_all = cx.recall("contact user preferences", top_k=10, min_score=0.0)
    results_filtered = cx.recall("contact user preferences", top_k=10, min_score=0.5)

    assert len(results_filtered) <= len(results_all)
    for r in results_filtered:
        assert r.score >= 0.5


def test_attribute_eas_scores(cx: Cortex):
    mem1 = cx.remember("User prefers email communication for all notifications")
    mem2 = cx.remember("Server configuration settings for production deployment")

    attr = cx.attribute(
        query="How should I contact the user?",
        response="Based on the stored context, you should contact the user via email.",
        memory_ids=[mem1.id, mem2.id],
    )

    assert attr.transaction_id
    assert mem1.id in attr.scores
    assert mem2.id in attr.scores

    # EAS scores should sum to approximately 1.0
    total = sum(attr.scores.values())
    assert total == pytest.approx(1.0, abs=0.05)

    # The email memory should score higher than the server config memory
    assert attr.scores[mem1.id] > attr.scores[mem2.id]


def test_recall_and_attribute_combined(cx: Cortex):
    cx.remember("User's preferred contact is email", importance=0.9, tags=["contact"])
    cx.remember("User works at Acme Corp", importance=0.7, tags=["work"])

    result = cx.recall_and_attribute(
        query="How do I reach out to the user?",
        response="Based on their preferences, reach out via email.",
        top_k=5,
    )

    assert len(result.memories) > 0
    assert result.attribution.transaction_id
    assert len(result.attribution.scores) == len(result.memories)

    # All recalled memory IDs should appear in attribution scores
    for recall_result in result.memories:
        assert recall_result.memory.id in result.attribution.scores


def test_attribute_empty_memory_ids(cx: Cortex):
    """Attribution with no memory IDs should succeed (no scores returned)."""
    attr = cx.attribute(
        query="What is the capital of France?",
        response="Paris is the capital of France.",
        memory_ids=[],
    )
    assert attr.transaction_id
    assert attr.scores == {}


def test_list_tier_filter(cx: Cortex):
    cx.remember("Hot tier memory", tier="hot", importance=1.0)
    cx.remember("Cold tier memory", tier="cold", importance=0.1)

    hot_page = cx.list(tier="hot")
    for mem in hot_page.items:
        assert mem.tier == "hot"


def test_metadata_round_trip(cx: Cortex):
    rich_meta = {
        "source": "integration_test",
        "version": 2,
        "nested": {"key": "value"},
    }
    mem = cx.remember("Memory with rich metadata", metadata=rich_meta)
    fetched = cx.get(mem.id)

    assert fetched.metadata["source"] == "integration_test"
    assert fetched.metadata["version"] == 2
    assert fetched.metadata["nested"]["key"] == "value"


# ── Async integration tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_remember_and_recall(async_cx: AsyncCortex):
    await async_cx.remember(
        "Async: user prefers push notifications on mobile",
        importance=0.8,
        tags=["notifications", "mobile"],
    )

    results = await async_cx.recall("mobile notification preferences", top_k=5)
    assert len(results) > 0
    assert results[0].score > 0.0


@pytest.mark.asyncio
async def test_async_attribute(async_cx: AsyncCortex):
    mem = await async_cx.remember("User prefers morning meetings only")

    attr = await async_cx.attribute(
        query="When should I schedule the meeting?",
        response="Schedule it in the morning based on user preferences.",
        memory_ids=[mem.id],
    )

    assert attr.transaction_id
    assert mem.id in attr.scores


@pytest.mark.asyncio
async def test_async_forget(async_cx: AsyncCortex):
    mem = await async_cx.remember("Temporary async memory")
    await async_cx.forget(mem.id)

    with pytest.raises(MemoryNotFoundError):
        await async_cx.get(mem.id)


@pytest.mark.asyncio
async def test_async_recall_and_attribute(async_cx: AsyncCortex):
    await async_cx.remember("User speaks Spanish fluently")
    await async_cx.remember("User prefers metric units")

    result = await async_cx.recall_and_attribute(
        query="What language does the user prefer?",
        response="The user prefers Spanish.",
        top_k=5,
    )

    assert len(result.memories) > 0
    assert result.attribution.transaction_id

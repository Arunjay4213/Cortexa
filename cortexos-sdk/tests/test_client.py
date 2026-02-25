"""
Unit tests for cortexos.Cortex (sync) and cortexos.AsyncCortex.
Uses respx to mock the httpx transport — no real server required.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from cortexos import AsyncCortex, Cortex
from cortexos.errors import AuthError, CortexError, MemoryNotFoundError, RateLimitError, ServerError

# ── Shared fixtures ────────────────────────────────────────────────────────

BASE_URL = "http://test-cortex"
AGENT_ID = "test-agent"
NOW = datetime.now(timezone.utc).isoformat()

_MEMORY_DICT = {
    "id": "mem-001",
    "content": "User prefers email over Slack",
    "agent_id": AGENT_ID,
    "tier": "warm",
    "criticality": 0.85,
    "metadata": {"_tags": ["preferences", "communication"]},
    "retrieval_count": 0,
    "created_at": NOW,
    "last_accessed": None,
    "deleted_at": None,
    "tokens": 6,
    "embedding": [],
}

_MEMORY_RESPONSE = {"memory": _MEMORY_DICT, "profile": None}

_TXN_RESPONSE = {
    "transaction": {
        "id": "txn-001",
        "query_text": "how to contact user?",
        "response_text": "Contact via email.",
        "agent_id": AGENT_ID,
        "created_at": NOW,
    },
    "scores": [
        {"memory_id": "mem-001", "score": 0.82},
        {"memory_id": "mem-002", "score": 0.18},
    ],
    "cost": {},
}


# ── Sync client tests ──────────────────────────────────────────────────────


@respx.mock
def test_remember_creates_memory():
    respx.post(f"{BASE_URL}/api/v1/memories").mock(
        return_value=httpx.Response(201, json=_MEMORY_DICT)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    mem = cx.remember("User prefers email over Slack", importance=0.85, tags=["preferences", "communication"])

    assert mem.id == "mem-001"
    assert mem.content == "User prefers email over Slack"
    assert mem.importance == 0.85
    assert "preferences" in mem.tags
    assert "communication" in mem.tags


@respx.mock
def test_remember_sends_correct_payload():
    route = respx.post(f"{BASE_URL}/api/v1/memories").mock(
        return_value=httpx.Response(201, json=_MEMORY_DICT)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    cx.remember("hello", importance=0.9, tags=["t1"], metadata={"source": "test"}, tier="hot")

    sent = json.loads(route.calls[0].request.content)
    assert sent["criticality"] == 0.9
    assert sent["tier"] == "hot"
    assert sent["metadata"]["_tags"] == ["t1"]
    assert sent["metadata"]["source"] == "test"
    assert sent["agent_id"] == AGENT_ID


@respx.mock
def test_get_memory():
    respx.get(f"{BASE_URL}/api/v1/memories/mem-001").mock(
        return_value=httpx.Response(200, json=_MEMORY_RESPONSE)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    mem = cx.get("mem-001")

    assert mem.id == "mem-001"
    assert mem.tier == "warm"


@respx.mock
def test_get_memory_not_found():
    respx.get(f"{BASE_URL}/api/v1/memories/bad-id").mock(
        return_value=httpx.Response(404, json={"detail": "Memory not found"})
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    with pytest.raises(MemoryNotFoundError) as exc_info:
        cx.get("bad-id")
    assert exc_info.value.memory_id == "bad-id"


@respx.mock
def test_forget_memory():
    respx.delete(f"{BASE_URL}/api/v1/memories/mem-001").mock(
        return_value=httpx.Response(204)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    cx.forget("mem-001")  # Should not raise


@respx.mock
def test_forget_not_found():
    respx.delete(f"{BASE_URL}/api/v1/memories/bad-id").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    with pytest.raises(MemoryNotFoundError):
        cx.forget("bad-id")


@respx.mock
def test_update_importance_only():
    # GET for metadata merge
    respx.get(f"{BASE_URL}/api/v1/memories/mem-001").mock(
        return_value=httpx.Response(200, json=_MEMORY_RESPONSE)
    )
    updated = {**_MEMORY_DICT, "criticality": 0.95}
    respx.patch(f"{BASE_URL}/api/v1/memories/mem-001").mock(
        return_value=httpx.Response(200, json=updated)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    mem = cx.update("mem-001", importance=0.95)
    assert mem.importance == 0.95


@respx.mock
def test_list_memories():
    page_data = {
        "items": [_MEMORY_DICT],
        "total": 1,
        "offset": 0,
        "limit": 50,
    }
    respx.get(f"{BASE_URL}/api/v1/memories").mock(
        return_value=httpx.Response(200, json=page_data)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    page = cx.list(limit=50)

    assert page.total == 1
    assert len(page.items) == 1
    assert not page.has_more


@respx.mock
def test_recall_semantic_search():
    search_results = [
        {"memory": _MEMORY_DICT, "similarity": 0.91},
        {"memory": {**_MEMORY_DICT, "id": "mem-002", "content": "Other memory"}, "similarity": 0.42},
    ]
    respx.get(f"{BASE_URL}/api/v1/memories/search").mock(
        return_value=httpx.Response(200, json=search_results)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    results = cx.recall("how to contact user?", top_k=5)

    assert len(results) == 2
    assert results[0].score == 0.91
    assert results[0].memory.id == "mem-001"


@respx.mock
def test_recall_min_score_filter():
    search_results = [
        {"memory": _MEMORY_DICT, "similarity": 0.91},
        {"memory": {**_MEMORY_DICT, "id": "mem-002"}, "similarity": 0.2},
    ]
    respx.get(f"{BASE_URL}/api/v1/memories/search").mock(
        return_value=httpx.Response(200, json=search_results)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    results = cx.recall("query", min_score=0.5)

    assert len(results) == 1
    assert results[0].score == 0.91


@respx.mock
def test_recall_tag_filter():
    mem_with_tag = {**_MEMORY_DICT, "metadata": {"_tags": ["preferences"]}}
    mem_without_tag = {**_MEMORY_DICT, "id": "mem-002", "metadata": {}}
    search_results = [
        {"memory": mem_with_tag, "similarity": 0.9},
        {"memory": mem_without_tag, "similarity": 0.8},
    ]
    respx.get(f"{BASE_URL}/api/v1/memories/search").mock(
        return_value=httpx.Response(200, json=search_results)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    results = cx.recall("query", tags=["preferences"])

    assert len(results) == 1
    assert "preferences" in results[0].memory.tags


@respx.mock
def test_attribute():
    respx.post(f"{BASE_URL}/api/v1/transactions").mock(
        return_value=httpx.Response(201, json=_TXN_RESPONSE)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    attr = cx.attribute(
        query="how to contact user?",
        response="Contact via email.",
        memory_ids=["mem-001", "mem-002"],
    )

    assert attr.transaction_id == "txn-001"
    assert attr.scores["mem-001"] == pytest.approx(0.82)
    assert attr.scores["mem-002"] == pytest.approx(0.18)


@respx.mock
def test_recall_and_attribute():
    search_results = [
        {"memory": _MEMORY_DICT, "similarity": 0.91},
        {"memory": {**_MEMORY_DICT, "id": "mem-002", "content": "Other"}, "similarity": 0.6},
    ]
    respx.get(f"{BASE_URL}/api/v1/memories/search").mock(
        return_value=httpx.Response(200, json=search_results)
    )
    respx.post(f"{BASE_URL}/api/v1/transactions").mock(
        return_value=httpx.Response(201, json=_TXN_RESPONSE)
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    result = cx.recall_and_attribute(
        query="how to contact user?",
        response="Contact via email.",
        top_k=5,
    )

    assert len(result.memories) == 2
    assert result.attribution.transaction_id == "txn-001"
    assert result.attribution.scores["mem-001"] == pytest.approx(0.82)


# ── Error handling ─────────────────────────────────────────────────────────


@respx.mock
def test_auth_error_401():
    respx.post(f"{BASE_URL}/api/v1/memories").mock(
        return_value=httpx.Response(401, json={"detail": "Unauthorized"})
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    with pytest.raises(AuthError):
        cx.remember("test")


@respx.mock
def test_rate_limit_error():
    respx.post(f"{BASE_URL}/api/v1/memories").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "2.0"}, json={"detail": "slow down"})
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    with pytest.raises(RateLimitError) as exc_info:
        cx.remember("test")
    assert exc_info.value.retry_after == pytest.approx(2.0)


@respx.mock
def test_server_error_500():
    respx.post(f"{BASE_URL}/api/v1/memories").mock(
        return_value=httpx.Response(500, json={"detail": "Internal error"})
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1)
    with pytest.raises(ServerError):
        cx.remember("test")


# ── Retry logic ────────────────────────────────────────────────────────────


@respx.mock
def test_retry_on_503_then_success():
    respx.post(f"{BASE_URL}/api/v1/memories").mock(
        side_effect=[
            httpx.Response(503, json={"detail": "temporarily unavailable"}),
            httpx.Response(201, json=_MEMORY_DICT),
        ]
    )
    cx = Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=2)
    mem = cx.remember("test")
    assert mem.id == "mem-001"


# ── Async client tests ─────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_async_remember():
    respx.post(f"{BASE_URL}/api/v1/memories").mock(
        return_value=httpx.Response(201, json=_MEMORY_DICT)
    )
    async with AsyncCortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1) as cx:
        mem = await cx.remember("User prefers email", importance=0.85, tags=["preferences"])

    assert mem.id == "mem-001"
    assert "preferences" in mem.tags


@respx.mock
@pytest.mark.asyncio
async def test_async_get_not_found():
    respx.get(f"{BASE_URL}/api/v1/memories/bad-id").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    async with AsyncCortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1) as cx:
        with pytest.raises(MemoryNotFoundError):
            await cx.get("bad-id")


@respx.mock
@pytest.mark.asyncio
async def test_async_recall():
    search_results = [{"memory": _MEMORY_DICT, "similarity": 0.88}]
    respx.get(f"{BASE_URL}/api/v1/memories/search").mock(
        return_value=httpx.Response(200, json=search_results)
    )
    async with AsyncCortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1) as cx:
        results = await cx.recall("contact the user")

    assert len(results) == 1
    assert results[0].score == pytest.approx(0.88)


@respx.mock
@pytest.mark.asyncio
async def test_async_attribute():
    respx.post(f"{BASE_URL}/api/v1/transactions").mock(
        return_value=httpx.Response(201, json=_TXN_RESPONSE)
    )
    async with AsyncCortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1) as cx:
        attr = await cx.attribute(
            query="how to contact user?",
            response="Via email.",
            memory_ids=["mem-001", "mem-002"],
        )

    assert attr.transaction_id == "txn-001"
    assert "mem-001" in attr.scores


@respx.mock
@pytest.mark.asyncio
async def test_async_forget():
    respx.delete(f"{BASE_URL}/api/v1/memories/mem-001").mock(
        return_value=httpx.Response(204)
    )
    async with AsyncCortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1) as cx:
        await cx.forget("mem-001")  # Should not raise


# ── Context manager (sync) ────────────────────────────────────────────────


@respx.mock
def test_context_manager_closes_cleanly():
    respx.post(f"{BASE_URL}/api/v1/memories").mock(
        return_value=httpx.Response(201, json=_MEMORY_DICT)
    )
    with Cortex(agent_id=AGENT_ID, base_url=BASE_URL, max_retries=1) as cx:
        mem = cx.remember("test")
    assert mem.id == "mem-001"
    # After exit, calling close again is idempotent
    cx.close()


# ── Types ─────────────────────────────────────────────────────────────────


def test_memory_from_api_extracts_tags():
    from cortexos.types import Memory
    data = {
        "id": "m1",
        "content": "hello",
        "agent_id": "a1",
        "tier": "hot",
        "criticality": 1.0,
        "metadata": {"_tags": ["a", "b"], "source": "test"},
        "retrieval_count": 3,
        "created_at": NOW,
        "last_accessed": None,
    }
    mem = Memory._from_api(data)
    assert mem.tags == ["a", "b"]
    assert mem.metadata == {"source": "test"}  # _tags removed from metadata
    assert mem.importance == 1.0


def test_page_has_more():
    from cortexos.types import Memory, Page
    mem = Memory._from_api({**_MEMORY_DICT})
    page = Page(items=[mem], total=10, offset=0, limit=1)
    assert page.has_more is True

    full_page = Page(items=[mem], total=1, offset=0, limit=50)
    assert full_page.has_more is False


def test_attribution_from_api():
    from cortexos.types import Attribution
    attr = Attribution._from_api(_TXN_RESPONSE, query="q", response="r")
    assert attr.transaction_id == "txn-001"
    assert attr.scores == {"mem-001": 0.82, "mem-002": 0.18}
    assert attr.query == "q"

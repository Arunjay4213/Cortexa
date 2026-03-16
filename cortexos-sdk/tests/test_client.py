"""
Unit tests for cortexos.Cortex (sync) and cortexos.AsyncCortex.
Uses respx to mock the httpx transport — no real server required.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from cortexos import AsyncCortex, Cortex
from cortexos.errors import AuthError, CortexError, RateLimitError, ServerError

# ── Shared fixtures ────────────────────────────────────────────────────────

BASE_URL = "http://test-cortex"

_CHECK_RESPONSE = {
    "hallucination_index": 0.0,
    "total_claims": 1,
    "grounded_count": 1,
    "hallucinated_count": 0,
    "opinion_count": 0,
    "claims": [
        {
            "text": "The return window is 30 days",
            "grounded": True,
            "verdict": "GROUNDED",
            "reason": "",
            "source_quote": "30-day return policy for all items",
            "confidence": 0.95,
        }
    ],
    "latency_ms": 123.4,
}

_HALLUCINATION_RESPONSE = {
    "hallucination_index": 1.0,
    "total_claims": 1,
    "grounded_count": 0,
    "hallucinated_count": 1,
    "opinion_count": 0,
    "claims": [
        {
            "text": "The return window is 60 days",
            "grounded": False,
            "verdict": "NUM_MISMATCH",
            "reason": "NUM_MISMATCH: claim has 60 but source has 30",
            "confidence": 0.0,
        }
    ],
    "latency_ms": 100.0,
}

_GATE_GROUNDED = {
    "grounded": True,
    "hallucination_index": 0.0,
    "flagged_claims": [],
    "suggested_corrections": None,
}

_GATE_BLOCKED = {
    "grounded": False,
    "hallucination_index": 1.0,
    "flagged_claims": [
        {
            "text": "Revenue grew 500%",
            "verdict": "UNSUPPORTED",
            "reason": "No source sentence entails this claim",
        }
    ],
    "suggested_corrections": None,
}

_HEALTHZ = {"status": "ok"}


# ── Sync client: check ────────────────────────────────────────────────────


@respx.mock
def test_check_grounded():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(200, json=_CHECK_RESPONSE)
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    result = cx.check(
        response="The return window is 30 days",
        sources=["30-day return policy for all items"],
    )
    assert result.hallucination_index == 0.0
    assert result.grounded_count == 1
    assert result.passed is True
    assert len(result.claims) == 1
    assert result.claims[0].verdict == "GROUNDED"
    cx.close()


@respx.mock
def test_check_hallucination():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(200, json=_HALLUCINATION_RESPONSE)
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    result = cx.check(
        response="The return window is 60 days",
        sources=["30-day return policy for all items"],
    )
    assert result.hallucination_index == 1.0
    assert result.hallucinated_count == 1
    assert result.passed is False
    assert result.claims[0].verdict == "NUM_MISMATCH"
    cx.close()


@respx.mock
def test_check_sends_correct_payload():
    route = respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(200, json=_CHECK_RESPONSE)
    )
    cx = Cortex(base_url=BASE_URL, agent_id="my-agent", max_retries=1)
    cx.check(response="test", sources=["source1", "source2"])

    sent = json.loads(route.calls[0].request.content)
    assert sent["response"] == "test"
    assert sent["sources"] == ["source1", "source2"]
    assert sent["agent_id"] == "my-agent"
    cx.close()


@respx.mock
def test_check_with_config():
    route = respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(200, json=_CHECK_RESPONSE)
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    cx.check(
        response="test",
        sources=["source"],
        config={"attribution": True},
    )
    sent = json.loads(route.calls[0].request.content)
    assert sent["config"]["attribution"] is True
    cx.close()


# ── Sync client: gate ─────────────────────────────────────────────────────


@respx.mock
def test_gate_grounded():
    respx.post(f"{BASE_URL}/v1/gate").mock(
        return_value=httpx.Response(200, json=_GATE_GROUNDED)
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    result = cx.gate(
        memory="The return window is 30 days",
        sources=["30-day return policy"],
    )
    assert result.grounded is True
    assert result.hallucination_index == 0.0
    assert result.flagged_claims == []
    cx.close()


@respx.mock
def test_gate_blocked():
    respx.post(f"{BASE_URL}/v1/gate").mock(
        return_value=httpx.Response(200, json=_GATE_BLOCKED)
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    result = cx.gate(
        memory="Revenue grew 500%",
        sources=["Revenue grew 10% last quarter"],
    )
    assert result.grounded is False
    assert result.hallucination_index == 1.0
    assert len(result.flagged_claims) == 1
    cx.close()


@respx.mock
def test_gate_sends_correct_payload():
    route = respx.post(f"{BASE_URL}/v1/gate").mock(
        return_value=httpx.Response(200, json=_GATE_GROUNDED)
    )
    cx = Cortex(base_url=BASE_URL, agent_id="bot-1", max_retries=1)
    cx.gate(memory="some memory", sources=["source"])

    sent = json.loads(route.calls[0].request.content)
    assert sent["candidate_memory"] == "some memory"
    assert sent["sources"] == ["source"]
    assert sent["agent_id"] == "bot-1"
    cx.close()


# ── Sync client: health ───────────────────────────────────────────────────


@respx.mock
def test_health():
    respx.get(f"{BASE_URL}/healthz").mock(
        return_value=httpx.Response(200, json=_HEALTHZ)
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    result = cx.health()
    assert result["status"] == "ok"
    cx.close()


# ── Context manager ───────────────────────────────────────────────────────


@respx.mock
def test_context_manager():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(200, json=_CHECK_RESPONSE)
    )
    with Cortex(base_url=BASE_URL, max_retries=1) as cx:
        result = cx.check(response="test", sources=["source"])
    assert result.hallucination_index == 0.0
    cx.close()  # idempotent


# ── Error handling ────────────────────────────────────────────────────────


@respx.mock
def test_auth_error_401():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(401, json={"detail": "Unauthorized"})
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    with pytest.raises(AuthError):
        cx.check(response="test", sources=["source"])
    cx.close()


@respx.mock
def test_rate_limit_error():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "2.0"}, json={"detail": "slow down"})
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    with pytest.raises(RateLimitError) as exc_info:
        cx.check(response="test", sources=["source"])
    assert exc_info.value.retry_after == pytest.approx(2.0)
    cx.close()


@respx.mock
def test_server_error_500():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(500, json={"detail": "Internal error"})
    )
    cx = Cortex(base_url=BASE_URL, max_retries=1)
    with pytest.raises(ServerError):
        cx.check(response="test", sources=["source"])
    cx.close()


# ── Retry logic ───────────────────────────────────────────────────────────


@respx.mock
def test_retry_on_503_then_success():
    respx.post(f"{BASE_URL}/v1/check").mock(
        side_effect=[
            httpx.Response(503, json={"detail": "temporarily unavailable"}),
            httpx.Response(200, json=_CHECK_RESPONSE),
        ]
    )
    cx = Cortex(base_url=BASE_URL, max_retries=2)
    result = cx.check(response="test", sources=["source"])
    assert result.hallucination_index == 0.0
    cx.close()


# ── Async client tests ────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_async_check():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(200, json=_CHECK_RESPONSE)
    )
    async with AsyncCortex(base_url=BASE_URL, max_retries=1) as cx:
        result = await cx.check(
            response="The return window is 30 days",
            sources=["30-day return policy"],
        )
    assert result.hallucination_index == 0.0
    assert result.grounded_count == 1


@respx.mock
@pytest.mark.asyncio
async def test_async_gate():
    respx.post(f"{BASE_URL}/v1/gate").mock(
        return_value=httpx.Response(200, json=_GATE_GROUNDED)
    )
    async with AsyncCortex(base_url=BASE_URL, max_retries=1) as cx:
        result = await cx.gate(
            memory="The return window is 30 days",
            sources=["30-day return policy"],
        )
    assert result.grounded is True


@respx.mock
@pytest.mark.asyncio
async def test_async_health():
    respx.get(f"{BASE_URL}/healthz").mock(
        return_value=httpx.Response(200, json=_HEALTHZ)
    )
    async with AsyncCortex(base_url=BASE_URL, max_retries=1) as cx:
        result = await cx.health()
    assert result["status"] == "ok"


@respx.mock
@pytest.mark.asyncio
async def test_async_auth_error():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(401, json={"detail": "Unauthorized"})
    )
    async with AsyncCortex(base_url=BASE_URL, max_retries=1) as cx:
        with pytest.raises(AuthError):
            await cx.check(response="test", sources=["source"])


# ── CheckResult properties ────────────────────────────────────────────────


def test_check_result_passed_at():
    from cortexos.models import CheckResult

    result = CheckResult._from_api({
        "hallucination_index": 0.25,
        "total_claims": 4,
        "grounded_count": 3,
        "hallucinated_count": 1,
        "opinion_count": 0,
        "claims": [],
        "latency_ms": 100.0,
    })
    assert result.passed is True  # < 0.3
    assert result.passed_at(0.2) is False  # 0.25 >= 0.2
    assert result.passed_at(0.3) is True   # 0.25 < 0.3


# ── Top-level API ─────────────────────────────────────────────────────────


@respx.mock
def test_top_level_check():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(200, json=_CHECK_RESPONSE)
    )
    import cortexos

    result = cortexos.check(
        response="The return window is 30 days",
        sources=["30-day return policy"],
        base_url=BASE_URL,
    )
    assert result.hallucination_index == 0.0


@respx.mock
def test_top_level_gate():
    respx.post(f"{BASE_URL}/v1/gate").mock(
        return_value=httpx.Response(200, json=_GATE_GROUNDED)
    )
    import cortexos

    result = cortexos.gate(
        memory="30-day return window",
        sources=["30-day return policy"],
        base_url=BASE_URL,
    )
    assert result.grounded is True


@respx.mock
def test_top_level_configure():
    respx.post(f"{BASE_URL}/v1/check").mock(
        return_value=httpx.Response(200, json=_CHECK_RESPONSE)
    )
    import cortexos

    cortexos.configure(api_key="test-key", base_url=BASE_URL)
    result = cortexos.check(
        response="The return window is 30 days",
        sources=["30-day return policy"],
    )
    assert result.hallucination_index == 0.0
    # Reset config
    cortexos._config.clear()

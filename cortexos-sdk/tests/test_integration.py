"""
Integration tests for the CortexOS SDK against a live cortex-engine server.

Run with:
    pytest tests/test_integration.py -v

Requires:
    CORTEX_BASE_URL env var (default: https://api.cortexa.ink)
    CORTEX_API_KEY env var
    A running cortex-engine server.

These tests are skipped automatically if the server is not reachable.
"""

from __future__ import annotations

import os

import httpx
import pytest

from cortexos import Cortex

BASE_URL = os.environ.get("CORTEX_BASE_URL", "https://api.cortexa.ink")
API_KEY = os.environ.get("CORTEX_API_KEY", "")


@pytest.fixture(scope="session", autouse=True)
def server_up():
    if not API_KEY:
        pytest.skip("CORTEX_API_KEY not set — skipping integration tests")
    try:
        resp = httpx.get(f"{BASE_URL}/healthz", timeout=5.0)
        if resp.status_code != 200:
            pytest.skip(f"CortexOS server returned {resp.status_code}")
    except httpx.ConnectError:
        pytest.skip(f"CortexOS server not reachable at {BASE_URL}")


@pytest.fixture
def cx() -> Cortex:
    client = Cortex(api_key=API_KEY, base_url=BASE_URL)
    yield client
    client.close()


def test_health(cx: Cortex):
    result = cx.health()
    assert result["status"] == "ok"


def test_check_grounded(cx: Cortex):
    result = cx.check(
        response="The return policy is 30 days.",
        sources=["Return policy: 30-day window for all items."],
    )
    assert result.hallucination_index < 0.5
    assert result.total_claims >= 1
    assert result.grounded_count >= 1


def test_check_hallucination(cx: Cortex):
    result = cx.check(
        response="The return window is 60 days.",
        sources=["30-day return policy for all items."],
    )
    assert result.hallucination_index > 0.0
    assert result.hallucinated_count >= 1


def test_gate_grounded(cx: Cortex):
    result = cx.gate(
        memory="The return policy is 30 days.",
        sources=["Return policy: 30-day window for all items."],
    )
    assert result.grounded is True
    assert result.hallucination_index < 0.5


def test_gate_blocked(cx: Cortex):
    result = cx.gate(
        memory="The return window is 90 days and costs $500.",
        sources=["30-day return policy, free of charge."],
    )
    assert result.grounded is False
    assert len(result.flagged_claims) >= 1

"""
Shared pytest fixtures for the CortexOS stress test suite.

Fixtures:
  base_url           — the server URL (parameterisable via CORTEX_BASE_URL env var)
  http_client        — a synchronous httpx client (for setup/teardown helpers)
  async_client       — an async httpx client for use in async tests
  server_up          — asserts the server is reachable before any test runs
  embedding_available — True if /memories POST works (embedding backend healthy)
  unique_agent_id    — returns a per-test unique agent ID string
  cleanup_agent      — deletes all memories for an agent after the test
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
import pytest_asyncio

from stress_tests.config import BASE_URL

_ADMIN_SECRET = os.environ.get("CORTEX_ADMIN_SECRET", "cortex-admin-secret")


# ── Server base URL ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("CORTEX_BASE_URL", BASE_URL)


# ── Session-level API key (one key shared across all stress tests) ─────────


@pytest.fixture(scope="session")
def stress_api_key(base_url: str) -> str:
    """Provision a single high-rate-limit API key for the whole stress test session."""
    try:
        resp = httpx.post(
            f"{base_url}/api-keys",
            json={
                "email": f"stress-{uuid.uuid4().hex[:8]}@stress.local",
                "name": "stress-test-session",
                "rate_limit_rpm": 9999,
            },
            headers={"Authorization": f"Bearer {_ADMIN_SECRET}"},
            timeout=10,
        )
        if resp.status_code == 201:
            return resp.json()["key"]
    except Exception:
        pass
    return ""  # Server may not have auth yet; fall through gracefully


# ── Synchronous client (for setup helpers) ─────────────────────────────────


@pytest.fixture(scope="session")
def http_client(base_url: str, stress_api_key: str) -> httpx.Client:
    headers = {}
    if stress_api_key:
        headers["Authorization"] = f"Bearer {stress_api_key}"
    with httpx.Client(base_url=base_url, timeout=30.0, headers=headers) as client:
        yield client


# ── Server reachability guard ─────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def server_up(http_client: httpx.Client, stress_api_key: str) -> None:
    from stress_tests.harness import set_session_api_key
    if stress_api_key:
        set_session_api_key(stress_api_key)
    try:
        resp = http_client.get("/healthz")
        assert resp.status_code == 200, f"Server not healthy: {resp.status_code}"
    except httpx.ConnectError as exc:
        pytest.skip(f"CortexOS server not reachable at {BASE_URL}: {exc}")


# ── Embedding backend availability ────────────────────────────────────────


@pytest.fixture(scope="session")
def embedding_available(http_client: httpx.Client) -> bool:
    """Return True if POST /memories works (embedding backend loaded)."""
    try:
        resp = http_client.post(
            "/api/v1/memories",
            json={"content": "embedding probe", "agent_id": "probe-agent", "tier": "warm", "criticality": 0.5, "metadata": {}},
        )
        if resp.status_code == 201:
            # Clean up probe memory
            try:
                http_client.delete(f"/api/v1/memories/{resp.json()['id']}")
            except Exception:
                pass
            return True
        return False
    except Exception:
        return False


@pytest.fixture(autouse=True)
def skip_if_embedding_unavailable(request, embedding_available: bool) -> None:
    """Auto-skip tests marked with @pytest.mark.requires_embedding when backend is down."""
    if request.node.get_closest_marker("requires_embedding"):
        if not embedding_available:
            pytest.skip("Embedding backend unavailable (transformers conflict) — skipping")


# ── Async client ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def async_client(base_url: str, stress_api_key: str) -> httpx.AsyncClient:
    headers = {}
    if stress_api_key:
        headers["Authorization"] = f"Bearer {stress_api_key}"
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=30.0),
        limits=httpx.Limits(max_connections=256, max_keepalive_connections=128),
        headers=headers,
    ) as client:
        yield client


# ── Per-test unique agent ID ──────────────────────────────────────────────


@pytest.fixture
def unique_agent_id() -> str:
    return f"stress-{uuid.uuid4().hex[:10]}"


# ── Cleanup helper: delete all memories for an agent ─────────────────────


@pytest.fixture
def cleanup_agent(http_client: httpx.Client):
    """Yields an (agent_id, cleanup) tuple.

    After the test, deletes up to 1000 memories for that agent.
    """
    agents_to_clean: list[str] = []

    def register(agent_id: str) -> str:
        agents_to_clean.append(agent_id)
        return agent_id

    yield register

    for agent_id in agents_to_clean:
        try:
            resp = http_client.get(
                "/api/v1/memories",
                params={"agent_id": agent_id, "limit": 200, "offset": 0},
            )
            if resp.status_code != 200:
                continue
            items = resp.json().get("items", [])
            for mem in items:
                http_client.delete(f"/api/v1/memories/{mem['id']}")
        except Exception:
            pass  # Best-effort cleanup


# ── Bulk memory insertion helper ──────────────────────────────────────────


def insert_memories_sync(
    client: httpx.Client,
    memories: list[dict],
    *,
    stop_on_error: bool = False,
) -> list[str]:
    """Insert memories sequentially and return list of created IDs."""
    ids: list[str] = []
    for mem in memories:
        resp = client.post("/api/v1/memories", json=mem)
        if resp.status_code == 201:
            ids.append(resp.json()["id"])
        elif stop_on_error:
            raise RuntimeError(f"Insert failed: {resp.status_code} {resp.text}")
    return ids

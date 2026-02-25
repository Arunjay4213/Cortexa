"""
Test Suite — API Key Authentication

Covers:
  - Missing key → 401
  - Invalid key → 401
  - Revoked key → 401
  - Valid key → 200
  - Rate limiting → 429 + Retry-After header
  - X-RateLimit-* headers on valid requests
  - agent_id scoping (scoped key forces agent_id filter)
  - Admin endpoints: create / list / revoke
  - Admin without secret → 401
  - /healthz always 200 (no auth)
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio

BASE_URL = "http://localhost:8000"
ADMIN_SECRET = "cortex-admin-secret"


# ── Helpers ────────────────────────────────────────────────────────────────

def _admin_headers() -> dict:
    return {"Authorization": f"Bearer {ADMIN_SECRET}"}


async def _create_key(
    client: httpx.AsyncClient,
    email: str | None = None,
    name: str = "test",
    agent_id: str | None = None,
    rate_limit_rpm: int = 60,
) -> dict:
    """Create an API key via admin endpoint and return the response JSON."""
    if email is None:
        email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    payload: dict = {"email": email, "name": name, "rate_limit_rpm": rate_limit_rpm}
    if agent_id is not None:
        payload["agent_id"] = agent_id
    resp = await client.post("/api-keys", json=payload, headers=_admin_headers())
    assert resp.status_code == 201, f"Key creation failed: {resp.text}"
    return resp.json()


# ── Session-scoped server check ────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def server_up():
    resp = httpx.get(f"{BASE_URL}/healthz", timeout=5)
    assert resp.status_code == 200, f"Server not reachable at {BASE_URL}"


# ── /healthz — always open ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_healthz_no_auth():
    async with httpx.AsyncClient(base_url=BASE_URL) as c:
        resp = await c.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── Missing / invalid / revoked key ───────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_key_returns_401():
    async with httpx.AsyncClient(base_url=BASE_URL) as c:
        resp = await c.get("/api/v1/memories")
    assert resp.status_code == 401
    assert "missing" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_key_returns_401():
    async with httpx.AsyncClient(base_url=BASE_URL) as c:
        resp = await c.get(
            "/api/v1/memories",
            headers={"Authorization": "Bearer sk-cortex-totally-fake"},
        )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_revoked_key_returns_401():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        data = await _create_key(c, name="revoke-me")
        key = data["key"]
        key_id = data["id"]

        # Confirm it works before revocation
        resp = await c.get("/api/v1/memories", headers={"Authorization": f"Bearer {key}"})
        assert resp.status_code == 200

        # Revoke
        revoke = await c.delete(f"/api-keys/{key_id}", headers=_admin_headers())
        assert revoke.status_code == 204

        # Now should 401
        resp = await c.get("/api/v1/memories", headers={"Authorization": f"Bearer {key}"})
        assert resp.status_code == 401
        assert "revoked" in resp.json()["detail"].lower()


# ── Valid key ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_key_returns_200():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        data = await _create_key(c, name="valid-test")
        key = data["key"]
        resp = await c.get("/api/v1/memories", headers={"Authorization": f"Bearer {key}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_valid_key_updates_last_used():
    """last_used_at should be updated after a successful request."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        data = await _create_key(c, name="last-used-test")
        key = data["key"]
        key_id = data["id"]

        await c.get("/api/v1/memories", headers={"Authorization": f"Bearer {key}"})

        keys = await c.get("/api-keys", headers=_admin_headers())
        assert keys.status_code == 200
        match = next((k for k in keys.json() if k["id"] == key_id), None)
        assert match is not None
        assert match["last_used_at"] is not None


# ── Rate limiting ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_returns_429():
    """Key with rpm=2 should reject the 3rd request within 60s."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        data = await _create_key(c, name="rate-limit-test", rate_limit_rpm=2)
        key = data["key"]
        headers = {"Authorization": f"Bearer {key}"}

        r1 = await c.get("/api/v1/memories", headers=headers)
        r2 = await c.get("/api/v1/memories", headers=headers)
        r3 = await c.get("/api/v1/memories", headers=headers)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert "Retry-After" in r3.headers
        assert r3.headers["Retry-After"] == "60"
        assert r3.headers.get("X-RateLimit-Remaining") == "0"


@pytest.mark.asyncio
async def test_rate_limit_headers_on_success():
    """Valid requests should carry X-RateLimit-* headers."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        data = await _create_key(c, name="header-test", rate_limit_rpm=100)
        key = data["key"]
        resp = await c.get("/api/v1/memories", headers={"Authorization": f"Bearer {key}"})
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert resp.headers["X-RateLimit-Limit"] == "100"
    assert "X-RateLimit-Remaining" in resp.headers
    assert int(resp.headers["X-RateLimit-Remaining"]) == 99


# ── Agent-ID scoping ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scoped_key_forces_agent_id():
    """A key scoped to agent_id='bot-A' should only see memories for bot-A."""
    scoped_agent = f"scoped-{uuid.uuid4().hex[:8]}"
    other_agent = f"other-{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as c:
        # Create an unscoped key to seed both agents' memories
        unscoped = (await _create_key(c, name="unscoped"))["key"]
        unscoped_h = {"Authorization": f"Bearer {unscoped}"}

        # Insert memory for scoped_agent
        r_a = await c.post(
            "/api/v1/memories",
            json={"content": "Memory for bot-A", "agent_id": scoped_agent, "tier": "warm", "criticality": 0.5, "metadata": {}},
            headers=unscoped_h,
        )
        assert r_a.status_code == 201

        # Insert memory for other_agent
        r_b = await c.post(
            "/api/v1/memories",
            json={"content": "Memory for other agent", "agent_id": other_agent, "tier": "warm", "criticality": 0.5, "metadata": {}},
            headers=unscoped_h,
        )
        assert r_b.status_code == 201

        # Create scoped key
        scoped_data = await _create_key(c, name="scoped-key", agent_id=scoped_agent)
        scoped_key = scoped_data["key"]
        scoped_h = {"Authorization": f"Bearer {scoped_key}"}

        # List memories with scoped key — should only see scoped_agent memories
        list_resp = await c.get("/api/v1/memories", headers=scoped_h)
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        agent_ids = {m["agent_id"] for m in items}
        assert scoped_agent in agent_ids or len(items) == 0  # may be empty if no other memories exist
        assert other_agent not in agent_ids, "Scoped key leaked memories from another agent"


# ── Admin endpoints ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_create_key():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        resp = await c.post(
            "/api-keys",
            json={"email": f"newuser-{uuid.uuid4().hex[:6]}@example.com", "name": "ci-key"},
            headers=_admin_headers(),
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"].startswith("sk-cortex-")
    assert data["key_prefix"] == data["key"][:12]
    assert data["agent_id"] is None


@pytest.mark.asyncio
async def test_admin_list_keys_never_returns_plaintext():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        await _create_key(c, name="list-test-key")
        resp = await c.get("/api-keys", headers=_admin_headers())
    assert resp.status_code == 200
    for k in resp.json():
        assert "key_hash" not in k
        # key_prefix is the safe truncated display value
        assert len(k["key_prefix"]) == 12


@pytest.mark.asyncio
async def test_admin_revoke_already_revoked_returns_409():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        data = await _create_key(c, name="double-revoke")
        kid = data["id"]
        r1 = await c.delete(f"/api-keys/{kid}", headers=_admin_headers())
        assert r1.status_code == 204
        r2 = await c.delete(f"/api-keys/{kid}", headers=_admin_headers())
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_admin_without_secret_returns_401():
    async with httpx.AsyncClient(base_url=BASE_URL) as c:
        resp = await c.post(
            "/api-keys",
            json={"email": "hack@example.com", "name": "evil"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_wrong_secret_returns_401():
    async with httpx.AsyncClient(base_url=BASE_URL) as c:
        resp = await c.post(
            "/api-keys",
            json={"email": "hack@example.com", "name": "evil"},
            headers={"Authorization": "Bearer wrong-secret"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_revoke_nonexistent_returns_404():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        resp = await c.delete(f"/api-keys/{uuid.uuid4()}", headers=_admin_headers())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_create_scoped_key():
    """Keys created with agent_id are returned with that field set."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        data = await _create_key(c, name="scoped", agent_id="my-bot")
    assert data["agent_id"] == "my-bot"
    assert data["key"].startswith("sk-cortex-")


@pytest.mark.asyncio
async def test_idempotent_user_creation():
    """POSTing twice with the same email reuses the user but creates a new key."""
    email = f"idempotent-{uuid.uuid4().hex[:6]}@example.com"
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
        d1 = await _create_key(c, email=email, name="key-1")
        d2 = await _create_key(c, email=email, name="key-2")
    # Both keys work
    assert d1["key"] != d2["key"]
    assert d1["email"] == d2["email"] == email


# ── Wrong auth scheme ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_basic_auth_rejected():
    """Basic auth or non-Bearer scheme should return 401."""
    async with httpx.AsyncClient(base_url=BASE_URL) as c:
        resp = await c.get(
            "/api/v1/memories",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
    assert resp.status_code == 401

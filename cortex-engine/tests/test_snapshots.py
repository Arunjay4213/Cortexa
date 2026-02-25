"""Tests for Phase 4 memory versioning: snapshots, diff, restore, branches.

These tests run against a live cortex-engine server (same pattern as test_auth.py).
Using ASGITransport is incompatible with BaseHTTPMiddleware + asyncpg connection
pooling, so we test over HTTP like all other integration tests.
"""

import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"
ADMIN_SECRET = "cortex-admin-secret"


# ── Server guard ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def server_up():
    resp = httpx.get(f"{BASE_URL}/healthz", timeout=5)
    assert resp.status_code == 200, f"Server not reachable at {BASE_URL}"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _admin_headers() -> dict:
    return {"Authorization": f"Bearer {ADMIN_SECRET}"}


async def _create_key(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "/api-keys",
        json={
            "email": f"snap-test-{uuid.uuid4().hex[:6]}@example.com",
            "name": "snapshot-test",
            "rate_limit_rpm": 300,
        },
        headers=_admin_headers(),
    )
    assert resp.status_code == 201
    return resp.json()["key"]


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as c:
        key = await _create_key(c)
        c.headers.update({"Authorization": f"Bearer {key}"})
        yield c


@pytest.fixture
async def agent_with_memories(client: httpx.AsyncClient):
    """Isolated agent with exactly 3 memories; cleans up after the test."""
    agent_id = f"test-snapshot-agent-{uuid.uuid4().hex[:8]}"
    mem_ids = []
    for i in range(3):
        resp = await client.post("/api/v1/memories", json={
            "content": f"Memory content {i}",
            "agent_id": agent_id,
            "tier": "warm",
            "criticality": 0.5,
            "metadata": {},
        })
        assert resp.status_code == 201, f"Setup failed: {resp.text}"
        mem_ids.append(resp.json()["id"])

    yield agent_id, mem_ids

    for mid in mem_ids:
        try:
            await client.delete(f"/api/v1/memories/{mid}")
        except Exception:
            pass


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_snapshot(client: httpx.AsyncClient, agent_with_memories):
    """Snapshot creation captures current memory state."""
    agent_id, mem_ids = agent_with_memories

    resp = await client.post(f"/api/v1/snapshots/{agent_id}", json={
        "name": "v1-baseline",
        "description": "Initial state",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "v1-baseline"
    assert data["agent_id"] == agent_id
    assert data["memory_count"] == len(mem_ids)


@pytest.mark.asyncio
async def test_list_snapshots(client: httpx.AsyncClient, agent_with_memories):
    """List snapshots returns created snapshots."""
    agent_id, _ = agent_with_memories

    await client.post(f"/api/v1/snapshots/{agent_id}", json={"name": "snap-1"})
    await client.post(f"/api/v1/snapshots/{agent_id}", json={"name": "snap-2"})

    resp = await client.get(f"/api/v1/snapshots/{agent_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_diff_snapshots(client: httpx.AsyncClient, agent_with_memories):
    """Diff between two snapshots identifies added memories."""
    agent_id, mem_ids = agent_with_memories

    resp1 = await client.post(f"/api/v1/snapshots/{agent_id}", json={"name": "before"})
    assert resp1.status_code == 201
    snap1_id = resp1.json()["id"]

    # Add a new memory after snapshot
    resp = await client.post("/api/v1/memories", json={
        "content": "New memory added after snapshot",
        "agent_id": agent_id,
        "tier": "hot",
        "criticality": 0.5,
        "metadata": {},
    })
    assert resp.status_code == 201

    resp2 = await client.post(f"/api/v1/snapshots/{agent_id}", json={"name": "after"})
    assert resp2.status_code == 201
    snap2_id = resp2.json()["id"]

    resp = await client.get(f"/api/v1/snapshots/{agent_id}/{snap1_id}/diff/{snap2_id}")
    assert resp.status_code == 200
    diff = resp.json()
    assert diff["snapshot_a_id"] == snap1_id
    assert diff["snapshot_b_id"] == snap2_id
    assert len(diff["added"]) >= 1


@pytest.mark.asyncio
async def test_restore_snapshot(client: httpx.AsyncClient, agent_with_memories):
    """Restore replaces current memories with snapshot state."""
    agent_id, mem_ids = agent_with_memories

    resp = await client.post(f"/api/v1/snapshots/{agent_id}", json={"name": "restore-test"})
    assert resp.status_code == 201
    snap_id = resp.json()["id"]
    original_count = resp.json()["memory_count"]

    if mem_ids:
        await client.delete(f"/api/v1/memories/{mem_ids[0]}")

    resp = await client.post(f"/api/v1/snapshots/{agent_id}/{snap_id}/restore")
    assert resp.status_code == 200
    assert resp.json()["memory_count"] == original_count


@pytest.mark.asyncio
async def test_create_branch(client: httpx.AsyncClient, agent_with_memories):
    """Branch creation from snapshot."""
    agent_id, _ = agent_with_memories

    resp = await client.post(f"/api/v1/snapshots/{agent_id}", json={"name": "branch-base"})
    assert resp.status_code == 201
    snap_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/branches/{agent_id}", json={
        "name": "experiment-1",
        "snapshot_id": snap_id,
        "description": "Testing new configuration",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "experiment-1"
    assert data["parent_snapshot_id"] == snap_id
    assert data["agent_id"] == agent_id


@pytest.mark.asyncio
async def test_list_branches(client: httpx.AsyncClient, agent_with_memories):
    """List branches returns created branches."""
    agent_id, _ = agent_with_memories

    resp = await client.post(f"/api/v1/snapshots/{agent_id}", json={"name": "base"})
    assert resp.status_code == 201
    snap_id = resp.json()["id"]

    await client.post(f"/api/v1/branches/{agent_id}", json={
        "name": "branch-a",
        "snapshot_id": snap_id,
    })

    resp = await client.get(f"/api/v1/branches/{agent_id}")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

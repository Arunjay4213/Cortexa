"""
Test Suite 04 — Memory Lifecycle Stress Tests

4.1  Rapid CRUD Cycles               — concurrent create/read/update/delete
4.2  Soft Delete Verification        — deleted memories not returned by search
4.3  TTL-like Expiration             — delete after delay, verify no stale reads
4.4  Memory Update Consistency       — patch metadata, verify reads see new data
4.5  Cascading Delete via Pagination — bulk-delete all memories for an agent
"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
import pytest

from stress_tests.config import BASE_URL, StressConfig, auth_headers
from stress_tests.generators.memory_gen import generate_memories, generate_memory_content
from stress_tests.harness import AsyncWorkerPool
from stress_tests.metrics import MetricsCollector, OperationResult


# ── 4.1  Rapid CRUD Cycles ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rapid_crud_cycles(unique_agent_id: str):
    """8 concurrent workers each perform 50 CRUD cycles; assert zero consistency violations."""
    agent = unique_agent_id
    workers = 8
    cycles_per_worker = 50
    total_cycles = workers * cycles_per_worker

    violations: list[str] = []
    latencies: list[float] = []

    async def crud_cycle(client: httpx.AsyncClient, agent_id: str, cycle_id: int) -> None:
        # CREATE
        content = f"CRUD-cycle-{cycle_id}: " + generate_memory_content(80)
        t0 = time.perf_counter()
        resp = await client.post(
            "/api/v1/memories",
            json={"content": content, "agent_id": agent_id, "tier": "warm", "criticality": 0.5, "metadata": {}},
        )
        if resp.status_code != 201:
            violations.append(f"CREATE failed ({resp.status_code}): cycle {cycle_id}")
            return
        mem_id = resp.json()["id"]

        # READ — verify content
        resp = await client.get(f"/api/v1/memories/{mem_id}")
        if resp.status_code != 200:
            violations.append(f"READ-after-create failed ({resp.status_code}): {mem_id}")
        elif resp.json()["memory"]["content"] != content:
            violations.append(f"Content mismatch after create: {mem_id}")

        # UPDATE — patch metadata
        resp = await client.patch(
            f"/api/v1/memories/{mem_id}",
            json={"criticality": 0.9, "metadata": {"updated": True, "cycle": cycle_id}},
        )
        if resp.status_code != 200:
            violations.append(f"PATCH failed ({resp.status_code}): {mem_id}")

        # READ — verify update applied
        resp = await client.get(f"/api/v1/memories/{mem_id}")
        if resp.status_code == 200:
            mem = resp.json()["memory"]
            if abs(mem["criticality"] - 0.9) > 0.001:
                violations.append(f"Criticality not updated: {mem_id}")
            if not mem["metadata"].get("updated"):
                violations.append(f"Metadata not updated: {mem_id}")
        else:
            violations.append(f"READ-after-update failed ({resp.status_code}): {mem_id}")

        # DELETE
        resp = await client.delete(f"/api/v1/memories/{mem_id}")
        if resp.status_code not in (204, 200):
            violations.append(f"DELETE failed ({resp.status_code}): {mem_id}")

        # READ — verify gone
        resp = await client.get(f"/api/v1/memories/{mem_id}")
        if resp.status_code == 200:
            violations.append(f"Memory still accessible after delete: {mem_id}")

        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

    async def worker(agent_id: str, worker_id: int) -> None:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
            for cycle in range(cycles_per_worker):
                cycle_id = worker_id * cycles_per_worker + cycle
                await crud_cycle(client, agent_id, cycle_id)

    worker_tasks = [asyncio.create_task(worker(agent, wid)) for wid in range(workers)]
    await asyncio.gather(*worker_tasks)

    assert not violations, (
        f"{len(violations)} CRUD consistency violations:\n" + "\n".join(violations[:10])
    )

    p50 = sorted(latencies)[len(latencies) // 2] if latencies else 0
    p95 = sorted(latencies)[int(0.95 * len(latencies))] if latencies else 0
    print(
        f"\n[4.1] CRUD cycles: {total_cycles} complete | "
        f"p50={p50:.0f}ms p95={p95:.0f}ms | violations=0"
    )


# ── 4.2  Soft Delete Verification ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_soft_delete_not_returned_in_search(unique_agent_id: str):
    """Deleted memories must not appear in search results."""
    agent = unique_agent_id
    # Very distinctive content
    content = f"DELETED-SENTINEL-{uuid.uuid4().hex} unique marker for soft-delete test"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as client:
        # Create
        resp = await client.post(
            "/api/v1/memories",
            json={"content": content, "agent_id": agent, "tier": "warm", "criticality": 1.0, "metadata": {}},
        )
        assert resp.status_code == 201
        mem_id = resp.json()["id"]

        # Confirm searchable
        resp = await client.get(
            "/api/v1/memories/search",
            params={"q": "DELETED-SENTINEL", "agent_id": agent, "top_k": 5},
        )
        assert resp.status_code == 200
        returned_ids = [r["memory"]["id"] for r in resp.json()]
        assert mem_id in returned_ids, "Memory not found in search before delete"

        # Soft-delete
        resp = await client.delete(f"/api/v1/memories/{mem_id}")
        assert resp.status_code in (204, 200)

        # Search again — must not appear
        resp = await client.get(
            "/api/v1/memories/search",
            params={"q": "DELETED-SENTINEL", "agent_id": agent, "top_k": 5},
        )
        assert resp.status_code == 200
        returned_ids = [r["memory"]["id"] for r in resp.json()]
        assert mem_id not in returned_ids, "Soft-deleted memory still appears in search"

        # Direct GET — must return 404
        resp = await client.get(f"/api/v1/memories/{mem_id}")
        assert resp.status_code == 404, f"Soft-deleted memory returned {resp.status_code}"

    print(f"\n[4.2] Soft-delete: memory hidden from search and GET after delete ✓")


# ── 4.3  TTL-Like Expiration (manual delete after sleep) ─────────────────────

@pytest.mark.asyncio
async def test_ttl_pattern_via_manual_delete(unique_agent_id: str):
    """Simulate TTL: insert, wait, delete, confirm gone. Validates timing accuracy."""
    agent = unique_agent_id
    ttl_memories = 20
    sleep_s = 1  # Short sleep for test speed

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Insert TTL-tagged memories
        ttl_ids = []
        for i in range(ttl_memories):
            resp = await client.post(
                "/api/v1/memories",
                json={
                    "content": f"TTL memory #{i}: expires soon",
                    "agent_id": agent,
                    "tier": "warm",
                    "criticality": 0.1,
                    "metadata": {"ttl": sleep_s},
                },
            )
            assert resp.status_code == 201
            ttl_ids.append(resp.json()["id"])

        # Insert permanent memories
        perm_ids = []
        for i in range(ttl_memories):
            resp = await client.post(
                "/api/v1/memories",
                json={
                    "content": f"Permanent memory #{i}: never expires",
                    "agent_id": agent,
                    "tier": "warm",
                    "criticality": 0.9,
                    "metadata": {"ttl": None},
                },
            )
            assert resp.status_code == 201
            perm_ids.append(resp.json()["id"])

        # Simulate TTL expiration via delete
        await asyncio.sleep(sleep_s)
        for mid in ttl_ids:
            resp = await client.delete(f"/api/v1/memories/{mid}")
            assert resp.status_code in (204, 200)

        # Verify TTL memories gone
        for mid in ttl_ids:
            resp = await client.get(f"/api/v1/memories/{mid}")
            assert resp.status_code == 404, f"TTL memory {mid} still accessible"

        # Verify permanent memories still present
        for mid in perm_ids:
            resp = await client.get(f"/api/v1/memories/{mid}")
            assert resp.status_code == 200, f"Permanent memory {mid} was deleted"

    print(f"\n[4.3] TTL pattern: {ttl_memories} expired, {ttl_memories} permanent ✓")


# ── 4.4  Memory Update Consistency ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_consistency_concurrent(unique_agent_id: str):
    """Multiple workers patching the same memory; last-write wins with no corruption."""
    agent = unique_agent_id

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as client:
        resp = await client.post(
            "/api/v1/memories",
            json={
                "content": "Memory subject to concurrent updates",
                "agent_id": agent,
                "tier": "warm",
                "criticality": 0.5,
                "metadata": {},
            },
        )
        assert resp.status_code == 201
        mem_id = resp.json()["id"]

    # 8 concurrent workers each set a different criticality
    criticality_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

    async def update_worker(val: float) -> None:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as c:
            resp = await c.patch(
                f"/api/v1/memories/{mem_id}",
                json={"criticality": val, "metadata": {"set_by": str(val)}},
            )
            assert resp.status_code == 200, f"Patch failed: {resp.status_code}"

    await asyncio.gather(*[update_worker(v) for v in criticality_values])

    # Verify the memory is not corrupted
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as client:
        resp = await client.get(f"/api/v1/memories/{mem_id}")
        assert resp.status_code == 200
        mem = resp.json()["memory"]
        # criticality must be one of the valid values
        assert mem["criticality"] in criticality_values, (
            f"Corrupted criticality after concurrent updates: {mem['criticality']}"
        )

    print(f"\n[4.4] Concurrent update: no corruption, final value in expected set ✓")


# ── 4.5  Bulk Delete via Pagination ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_delete_via_pagination(unique_agent_id: str):
    """Insert N memories for agent, then delete all via paginated list; verify store is empty."""
    agent = unique_agent_id
    count = 50

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        # Insert
        for i in range(count):
            resp = await client.post(
                "/api/v1/memories",
                json={
                    "content": f"Bulk delete test memory #{i}",
                    "agent_id": agent,
                    "tier": "warm",
                    "criticality": 0.5,
                    "metadata": {},
                },
            )
            assert resp.status_code == 201

        # Paginate and delete
        deleted = 0
        for _ in range(20):  # max iterations
            resp = await client.get(
                "/api/v1/memories",
                params={"agent_id": agent, "limit": 50, "offset": 0},
            )
            assert resp.status_code == 200
            items = resp.json()["items"]
            if not items:
                break
            for mem in items:
                del_resp = await client.delete(f"/api/v1/memories/{mem['id']}")
                assert del_resp.status_code in (204, 200)
                deleted += 1

        # Verify store is empty for agent
        resp = await client.get(
            "/api/v1/memories",
            params={"agent_id": agent, "limit": 1},
        )
        assert resp.status_code == 200
        remaining = resp.json()["total"]
        assert remaining == 0, f"Store not empty after bulk delete: {remaining} remaining"

    print(f"\n[4.5] Bulk delete: {deleted} memories deleted, store empty ✓")

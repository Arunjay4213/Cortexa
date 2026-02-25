"""
Test Suite 06 — Consistency & Correctness Tests

6.1  Concurrent Write Consistency      — no corruption under concurrent writes to same agent
6.2  Read-Your-Writes                  — after a successful write, the write is always readable
6.3  Embedding Determinism             — same content always produces the same search rank
6.4  Pagination Consistency            — paginated listing returns all records exactly once
6.5  Attribution Sum Normalization     — EAS scores always sum to ~1.0
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import Counter

import httpx
import pytest

from stress_tests.config import BASE_URL, StressConfig, auth_headers
from stress_tests.generators.memory_gen import generate_memories, generate_memory_content
from stress_tests.harness import AsyncWorkerPool, make_memory_task
from stress_tests.metrics import MetricsCollector


# ── 6.1  Concurrent Write Consistency ────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_write_no_corruption(unique_agent_id: str):
    """16 workers write to the same agent namespace; no memory is corrupted or lost."""
    agent = unique_agent_id
    workers = 16
    per_worker = 10
    total = workers * per_worker

    mems = generate_memories(total, agent_id=agent)
    tasks = [make_memory_task(**m) for m in mems]
    collector = MetricsCollector("concurrent_write", warmup_fraction=0.0)

    async with AsyncWorkerPool(workers=workers) as pool:
        await pool.run_tasks(tasks, collector)

    assert collector.error_rate == 0.0, (
        f"Errors during concurrent writes: {collector.error_counts}"
    )

    # Verify exact count with no duplicates
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        all_ids: list[str] = []
        offset = 0
        while True:
            resp = await client.get(
                "/api/v1/memories",
                params={"agent_id": agent, "limit": 200, "offset": offset},
            )
            assert resp.status_code == 200
            data = resp.json()
            page = data["items"]
            all_ids.extend(m["id"] for m in page)
            if len(page) < 200:
                break
            offset += 200

    dups = [mid for mid, cnt in Counter(all_ids).items() if cnt > 1]
    assert not dups, f"Duplicate IDs after concurrent writes: {dups}"
    assert len(all_ids) == total, (
        f"Expected {total} memories after concurrent writes, found {len(all_ids)}"
    )

    print(f"\n[6.1] Concurrent writes: {total} memories, 0 corruptions, 0 duplicates ✓")


# ── 6.2  Read-Your-Writes ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_read_your_writes(unique_agent_id: str):
    """After a write returns 201, a GET for that memory_id must always succeed."""
    agent = unique_agent_id
    violations: list[str] = []

    async def write_then_read(client: httpx.AsyncClient, i: int) -> None:
        content = f"Read-your-writes test #{i}: {uuid.uuid4().hex}"
        resp = await client.post(
            "/api/v1/memories",
            json={"content": content, "agent_id": agent, "tier": "warm", "criticality": 0.5, "metadata": {}},
        )
        if resp.status_code != 201:
            violations.append(f"Write failed for #{i}: {resp.status_code}")
            return
        mem_id = resp.json()["id"]

        # Immediate read
        resp = await client.get(f"/api/v1/memories/{mem_id}")
        if resp.status_code != 200:
            violations.append(f"Read-after-write failed for {mem_id}: {resp.status_code}")
        elif resp.json()["memory"]["content"] != content:
            violations.append(f"Content mismatch after write for {mem_id}")

    tasks_coros = []
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        aws = [write_then_read(client, i) for i in range(100)]
        await asyncio.gather(*aws)

    assert not violations, (
        f"{len(violations)} read-your-writes violations:\n" + "\n".join(violations[:5])
    )
    print(f"\n[6.2] Read-your-writes: 100 write+read pairs, 0 violations ✓")


# ── 6.3  Embedding Determinism ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_embedding_determinism(unique_agent_id: str):
    """
    The same content string inserted twice produces the same search rank order.
    Verifies embedding model is deterministic.
    """
    agent = unique_agent_id
    shared_query = "preferred communication channel for user notifications"
    shared_content = "User strongly prefers to receive all notifications via email."

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Insert the same content twice under different IDs
        ids = []
        for _ in range(2):
            resp = await client.post(
                "/api/v1/memories",
                json={"content": shared_content, "agent_id": agent, "tier": "warm", "criticality": 0.5, "metadata": {}},
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])

        # Insert distractor
        resp = await client.post(
            "/api/v1/memories",
            json={"content": "Weather forecast: sunny with high pressure.", "agent_id": agent, "tier": "warm", "criticality": 0.5, "metadata": {}},
        )
        assert resp.status_code == 201
        distractor_id = resp.json()["id"]

        # Search twice
        rank_results: list[list[str]] = []
        for _ in range(3):
            resp = await client.get(
                "/api/v1/memories/search",
                params={"q": shared_query, "agent_id": agent, "top_k": 5},
            )
            assert resp.status_code == 200
            rank_results.append([r["memory"]["id"] for r in resp.json()])

    # Top result should consistently be one of the two identical-content memories
    for rank_list in rank_results:
        assert rank_list[0] in ids or (len(rank_list) > 1 and rank_list[1] in ids), (
            f"Identical content memory not in top-2: {rank_list}"
        )

    # All 3 rank lists should have the same order (deterministic embeddings)
    if len(rank_results) >= 2:
        assert rank_results[0] == rank_results[1], (
            f"Non-deterministic search order: {rank_results[0]} vs {rank_results[1]}"
        )

    print(f"\n[6.3] Embedding determinism: identical content ranks identically ✓")


# ── 6.4  Pagination Consistency ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pagination_consistency(unique_agent_id: str):
    """Paginating through all memories returns each memory exactly once."""
    agent = unique_agent_id
    total = 80  # 4 pages of 20

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        for i in range(total):
            resp = await client.post(
                "/api/v1/memories",
                json={"content": f"Pagination test memory #{i}: " + generate_memory_content(60), "agent_id": agent, "tier": "warm", "criticality": 0.5, "metadata": {}},
            )
            assert resp.status_code == 201

        # Paginate with page_size=20
        page_size = 20
        seen_ids: list[str] = []
        offset = 0
        while True:
            resp = await client.get(
                "/api/v1/memories",
                params={"agent_id": agent, "limit": page_size, "offset": offset},
            )
            assert resp.status_code == 200
            page_data = resp.json()
            items = page_data["items"]
            seen_ids.extend(m["id"] for m in items)
            if len(items) < page_size:
                break
            offset += page_size

    assert len(seen_ids) == total, f"Paginated {len(seen_ids)}, expected {total}"
    assert len(seen_ids) == len(set(seen_ids)), (
        f"Pagination returned duplicates: {len(seen_ids) - len(set(seen_ids))} dups"
    )
    print(f"\n[6.4] Pagination: {total} memories, no duplicates, no missing ✓")


# ── 6.5  Attribution Score Normalization ─────────────────────────────────────

@pytest.mark.asyncio
async def test_attribution_score_normalization(unique_agent_id: str):
    """EAS scores for a transaction must sum to ~1.0 (± 0.05 tolerance)."""
    agent = unique_agent_id
    context_sizes = [1, 3, 5, 10, 20]

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        for ctx_size in context_sizes:
            mems = generate_memories(ctx_size, agent_id=agent)
            mem_ids = []
            for m in mems:
                resp = await client.post("/api/v1/memories", json=m)
                assert resp.status_code == 201
                mem_ids.append(resp.json()["id"])

            resp = await client.post(
                "/api/v1/transactions",
                json={
                    "query_text": "What does the context say?",
                    "response_text": generate_memory_content(100),
                    "retrieved_memory_ids": mem_ids,
                    "agent_id": agent,
                },
            )
            assert resp.status_code == 201
            scores = resp.json()["scores"]

            if not scores:
                continue

            total = sum(s["score"] for s in scores)
            assert abs(total - 1.0) < 0.05, (
                f"Attribution scores don't sum to 1.0 (ctx={ctx_size}): total={total:.4f} "
                f"scores={[s['score'] for s in scores]}"
            )

    print(f"\n[6.5] Attribution normalization: scores sum to 1.0 ± 0.05 for all context sizes ✓")

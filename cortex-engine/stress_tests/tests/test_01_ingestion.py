"""
Test Suite 01 — Memory Ingestion Stress Tests

1.1  Sequential Bulk Ingestion        — per-insert latency scaling
1.2  Concurrent Bulk Ingestion        — aggregate throughput + duplicate ID check
1.3  Large Memory Payloads            — latency vs payload size + content integrity
1.4  Metadata-Heavy Ingestion         — rich metadata round-trip + invalid float rejection
1.5  Duplicate & Near-Duplicate       — deduplication behaviour under load
"""

from __future__ import annotations

import asyncio
import time
import uuid
from statistics import mean, stdev

import httpx
import pytest

from stress_tests.config import BASE_URL, StressConfig, auth_headers
from stress_tests.generators.memory_gen import generate_memories, generate_memory_content
from stress_tests.harness import AsyncWorkerPool, make_memory_task
from stress_tests.metrics import MetricsCollector


# ── 1.1  Sequential Bulk Ingestion ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_sequential_bulk_ingestion(async_client: httpx.AsyncClient, unique_agent_id: str):
    """Insert memories one-by-one; assert p95 doesn't degrade 2× between first and last 10%."""
    count = StressConfig.MEDIUM_SCALE  # 500 default
    memories = generate_memories(count, agent_id=unique_agent_id)

    latencies: list[float] = []

    for mem in memories:
        t0 = time.perf_counter()
        resp = await async_client.post("/api/v1/memories", json=mem)
        latency_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 201, f"Insert failed: {resp.status_code} {resp.text[:200]}"
        latencies.append(latency_ms)

    # First 10% and last 10%
    slice_size = max(1, count // 10)
    first_p95 = sorted(latencies[:slice_size])[int(0.95 * slice_size)]
    last_p95 = sorted(latencies[-slice_size:])[int(0.95 * slice_size)]

    ratio = last_p95 / first_p95 if first_p95 > 0 else 1.0
    assert ratio < 2.0, (
        f"Latency degraded {ratio:.2f}× between first and last 10% of inserts "
        f"(first p95={first_p95:.1f}ms, last p95={last_p95:.1f}ms)"
    )

    # No single insert > timeout
    max_latency = max(latencies)
    assert max_latency < StressConfig.SINGLE_OP_TIMEOUT_S * 1000, (
        f"Single insert took {max_latency:.0f}ms (>{StressConfig.SINGLE_OP_TIMEOUT_S}s)"
    )

    overall_p95 = sorted(latencies)[int(0.95 * len(latencies))]
    print(
        f"\n[1.1] Sequential bulk ({count} memories): "
        f"p50={sorted(latencies)[len(latencies)//2]:.1f}ms "
        f"p95={overall_p95:.1f}ms "
        f"degradation_ratio={ratio:.2f}x"
    )


# ── 1.2  Concurrent Bulk Ingestion ───────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("workers", [4, 8, 16])
async def test_concurrent_bulk_ingestion(workers: int, unique_agent_id: str):
    """N workers concurrently inserting memories — check throughput, no duplicate IDs, no drops."""
    count = StressConfig.MEDIUM_SCALE
    agent = f"{unique_agent_id}-w{workers}"
    memories = generate_memories(count, agent_id=agent)

    tasks = [make_memory_task(**mem) for mem in memories]
    # warmup_fraction=0 — we need all ops counted for the insert-count assertion
    collector = MetricsCollector(f"concurrent_ingestion_w{workers}", warmup_fraction=0.0)

    barrier = asyncio.Event()
    barrier.set()  # All workers start immediately

    async with AsyncWorkerPool(workers=workers) as pool:
        await pool.run_tasks(tasks, collector, barrier=barrier)

    report = collector.report()
    assert report["error_rate"] == 0.0, (
        f"Errors during concurrent ingestion: {report['error_counts']}"
    )
    assert report["success_ops"] == count, (
        f"Only {report['success_ops']}/{count} memories inserted"
    )

    # Verify no duplicate IDs by listing all memories
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Paginate through all memories for this agent
        all_ids: list[str] = []
        offset = 0
        limit = 200
        while True:
            resp = await client.get(
                "/api/v1/memories",
                params={"agent_id": agent, "limit": limit, "offset": offset},
            )
            assert resp.status_code == 200
            data = resp.json()
            items = data["items"]
            all_ids.extend(m["id"] for m in items)
            if len(items) < limit:
                break
            offset += limit

    assert len(all_ids) == len(set(all_ids)), "Duplicate memory IDs detected under concurrent insertion"
    assert len(all_ids) == count, f"Expected {count} memories, found {len(all_ids)}"

    print(
        f"\n[1.2] Concurrent ingestion (workers={workers}, count={count}): "
        f"throughput={report['throughput_overall_rps']:.1f} ops/s "
        f"p95={report['latency']['p95_ms']}ms"
    )


# ── 1.3  Large Memory Payloads ──────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("text_length", StressConfig.MEMORY_TEXT_LENGTHS)
async def test_large_payload_ingestion_and_integrity(text_length: int, unique_agent_id: str):
    """Insert memories of given size, then verify content integrity on readback."""
    count = 20  # enough for a latency curve, not too slow
    agent = f"{unique_agent_id}-len{text_length}"
    memories = generate_memories(count, agent_id=agent, target_length=text_length)

    latencies: list[float] = []
    created_ids: list[str] = []

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=StressConfig.HTTP_TIMEOUT, headers=auth_headers()) as client:
        for mem in memories:
            t0 = time.perf_counter()
            resp = await client.post("/api/v1/memories", json=mem)
            latency_ms = (time.perf_counter() - t0) * 1000
            assert resp.status_code == 201, f"text_length={text_length}: {resp.text[:200]}"
            latencies.append(latency_ms)
            created_ids.append(resp.json()["id"])

        # Verify content integrity
        corruption_count = 0
        for mem_id, original in zip(created_ids, memories):
            resp = await client.get(f"/api/v1/memories/{mem_id}")
            assert resp.status_code == 200
            stored_content = resp.json()["memory"]["content"]
            if stored_content != original["content"]:
                corruption_count += 1

    assert corruption_count == 0, (
        f"Content corruption detected: {corruption_count}/{count} memories corrupted at length={text_length}"
    )

    p50 = sorted(latencies)[len(latencies) // 2]
    p95 = sorted(latencies)[int(0.95 * len(latencies))]
    print(f"\n[1.3] Payload size={text_length}chars: p50={p50:.1f}ms p95={p95:.1f}ms")


# ── 1.4  Metadata-Heavy Ingestion ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_metadata_heavy_ingestion(unique_agent_id: str):
    """Insert memories with rich metadata and verify round-trip correctness."""
    agent = unique_agent_id
    memories_with_rich_meta = [
        {
            "content": f"Memory with rich metadata #{i}: " + generate_memory_content(100),
            "agent_id": agent,
            "tier": "warm",
            "criticality": 0.5,
            "metadata": {
                "context_tags": [f"tag-{j}" for j in range(20)],
                "source": "stress-test",
                "nested": {"level1": {"level2": {"level3": f"deep-value-{i}"}}},
                "numeric_array": list(range(10)),
                "string_val": "hello world",
                "bool_val": True,
            },
        }
        for i in range(50)
    ]

    created_ids: list[str] = []
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        for mem in memories_with_rich_meta:
            resp = await client.post("/api/v1/memories", json=mem)
            assert resp.status_code == 201, f"Rich meta insert failed: {resp.text[:300]}"
            created_ids.append(resp.json()["id"])

        # Verify metadata round-trips
        corruption_count = 0
        for mem_id, original in zip(created_ids, memories_with_rich_meta):
            resp = await client.get(f"/api/v1/memories/{mem_id}")
            assert resp.status_code == 200
            stored = resp.json()["memory"]["metadata"]
            orig_meta = original["metadata"]
            if stored.get("nested") != orig_meta["nested"]:
                corruption_count += 1
            if stored.get("context_tags") != orig_meta["context_tags"]:
                corruption_count += 1

    assert corruption_count == 0, f"Metadata corruption in {corruption_count} memories"
    print(f"\n[1.4] Rich metadata: {len(created_ids)} memories, 0 corruptions")


@pytest.mark.asyncio
async def test_invalid_float_rejection(unique_agent_id: str):
    """Memories with criticality out of expected range should be rejected or handled."""
    agent = unique_agent_id

    # Negative criticality — should be rejected (422) or accepted and clamped
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as client:
        resp = await client.post(
            "/api/v1/memories",
            json={
                "content": "Test memory with negative criticality",
                "agent_id": agent,
                "tier": "warm",
                "criticality": -1.0,  # invalid
                "metadata": {},
            },
        )
        # Should be rejected (422) OR stored without crashing (not a 500)
        assert resp.status_code != 500, f"Server crashed on invalid criticality: {resp.text}"
        print(f"\n[1.4] Negative criticality → HTTP {resp.status_code} (expected 422 or 201)")


# ── 1.5  Duplicate & Near-Duplicate Ingestion ────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_ingestion(unique_agent_id: str):
    """Insert exact duplicates and verify the system handles them (no crash, no corruption)."""
    agent = unique_agent_id
    unique_content = f"Unique memory content for duplicate test {uuid.uuid4().hex}"

    inserted_ids: list[str] = []
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Insert same content 5 times
        for _ in range(5):
            resp = await client.post(
                "/api/v1/memories",
                json={
                    "content": unique_content,
                    "agent_id": agent,
                    "tier": "warm",
                    "criticality": 0.5,
                    "metadata": {},
                },
            )
            # System may accept duplicates (201) or reject (409/422) — neither is wrong
            assert resp.status_code in (201, 409, 422), (
                f"Unexpected status on duplicate insert: {resp.status_code}"
            )
            if resp.status_code == 201:
                inserted_ids.append(resp.json()["id"])

        # Verify no memory corruption: each returned ID should fetch correctly
        for mem_id in inserted_ids:
            resp = await client.get(f"/api/v1/memories/{mem_id}")
            assert resp.status_code == 200
            assert resp.json()["memory"]["content"] == unique_content

    print(
        f"\n[1.5] Duplicate test: {len(inserted_ids)} accepted out of 5 attempts "
        f"({'deduplication active' if len(inserted_ids) < 5 else 'all accepted'})"
    )


@pytest.mark.asyncio
async def test_concurrent_ingestion_throughput(unique_agent_id: str):
    """Measure peak ingestion throughput with max workers."""
    workers = 16
    count = StressConfig.MEDIUM_SCALE
    agent = f"{unique_agent_id}-throughput"
    memories = generate_memories(count, agent_id=agent)

    tasks = [make_memory_task(**mem) for mem in memories]
    collector = MetricsCollector("peak_ingestion", warmup_fraction=0.1)

    t0 = time.monotonic()
    async with AsyncWorkerPool(workers=workers) as pool:
        await pool.run_tasks(tasks, collector)
    elapsed = time.monotonic() - t0

    report = collector.report()
    throughput = report["success_ops"] / elapsed

    print(
        f"\n[1.5] Peak ingestion throughput: "
        f"{throughput:.1f} ops/s | workers={workers} | "
        f"count={count} | elapsed={elapsed:.1f}s | "
        f"p95={report['latency']['p95_ms']}ms"
    )

    # Baseline assertion: at least 1 op/sec (system is barely running)
    assert throughput > 1.0, f"Throughput too low: {throughput:.2f} ops/s"
    assert report["error_rate"] < StressConfig.MAX_ERROR_RATE, (
        f"Error rate {report['error_rate']:.1%} exceeds threshold"
    )

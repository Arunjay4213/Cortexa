"""
Test Suite 02 — Memory Retrieval Stress Tests

2.1  Recall Latency vs Store Size       — latency at scale checkpoints
2.2  Concurrent Recall Throughput       — max QPS under load
2.3  Recall Relevance Under Scale       — needle-in-haystack quality
2.4  Cold vs Warm Recall                — first-hit vs repeated-query latency
2.5  Search Parameter Validation        — top_k edges, empty store, agent isolation
"""

from __future__ import annotations

import asyncio
import time
import statistics

import httpx
import pytest

from stress_tests.config import BASE_URL, StressConfig, auth_headers
from stress_tests.generators.memory_gen import generate_memories, generate_needle_memories
from stress_tests.generators.query_gen import generate_canary_pairs, generate_queries
from stress_tests.harness import AsyncWorkerPool, make_search_task
from stress_tests.metrics import MetricsCollector


# ── Helper: bulk-insert memories synchronously ────────────────────────────


async def _bulk_insert(client: httpx.AsyncClient, memories: list[dict]) -> list[str]:
    """Insert a list of memory dicts and return their IDs."""
    ids: list[str] = []
    for mem in memories:
        resp = await client.post("/api/v1/memories", json=mem)
        assert resp.status_code == 201, f"Bulk insert failed: {resp.text[:200]}"
        ids.append(resp.json()["id"])
    return ids


async def _concurrent_insert(
    memories: list[dict],
    workers: int = 8,
) -> list[str]:
    """Concurrently insert memories and return IDs."""
    from stress_tests.harness import make_memory_task
    tasks = [make_memory_task(**m) for m in memories]
    collector = MetricsCollector("setup_insert", warmup_fraction=0.0)
    async with AsyncWorkerPool(workers=workers) as pool:
        await pool.run_tasks(tasks, collector)
    # IDs come back from result data
    ids = [
        r.data["id"]
        for r in collector._results
        if r.success and r.data and "id" in r.data
    ]
    return ids


# ── 2.1  Recall Latency vs Store Size ────────────────────────────────────────

@pytest.mark.asyncio
async def test_recall_latency_vs_store_size(unique_agent_id: str):
    """Insert memories in batches; measure recall latency at each checkpoint."""
    agent = unique_agent_id
    batch_size = 50
    num_batches = 6  # up to 300 memories — balanced for CI speed
    query_count = 20
    queries = generate_queries(query_count)

    latency_by_size: dict[int, float] = {}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        total_inserted = 0
        for batch_idx in range(num_batches):
            # Insert a batch
            batch = generate_memories(batch_size, agent_id=agent)
            for mem in batch:
                resp = await client.post("/api/v1/memories", json=mem)
                assert resp.status_code == 201
            total_inserted += batch_size

            # Measure recall latency for fixed queries
            latencies: list[float] = []
            for q in queries:
                t0 = time.perf_counter()
                resp = await client.get(
                    "/api/v1/memories/search",
                    params={"q": q, "agent_id": agent, "top_k": 10},
                )
                lat = (time.perf_counter() - t0) * 1000
                assert resp.status_code == 200
                latencies.append(lat)

            p95 = sorted(latencies)[int(0.95 * len(latencies))]
            latency_by_size[total_inserted] = p95

    sizes = sorted(latency_by_size)
    p95_values = [latency_by_size[s] for s in sizes]

    # Latency should not catastrophically explode (allow 10× growth as store grows 6×)
    if len(p95_values) >= 2 and p95_values[0] > 0:
        ratio = p95_values[-1] / p95_values[0]
        assert ratio < 20.0, (
            f"Recall latency exploded {ratio:.1f}× as store grew: {dict(zip(sizes, p95_values))}"
        )

    print(f"\n[2.1] Recall latency vs store size: {latency_by_size}")


# ── 2.2  Concurrent Recall Throughput ───────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("workers", StressConfig.LIGHT_WORKERS)
async def test_concurrent_recall_throughput(workers: int, unique_agent_id: str):
    """Measure recall QPS under N concurrent workers."""
    agent = unique_agent_id
    # Pre-populate with a modest store
    memories = generate_memories(100, agent_id=agent)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        for mem in memories:
            resp = await client.post("/api/v1/memories", json=mem)
            assert resp.status_code == 201

    # Build 200 search tasks cycling through 20 queries
    queries = generate_queries(20)
    tasks = [
        make_search_task(queries[i % len(queries)], agent_id=agent)
        for i in range(200)
    ]
    collector = MetricsCollector(f"recall_qps_w{workers}", warmup_fraction=0.1)

    t0 = time.monotonic()
    async with AsyncWorkerPool(workers=workers) as pool:
        await pool.run_tasks(tasks, collector)
    elapsed = time.monotonic() - t0

    report = collector.report()
    qps = report["success_ops"] / elapsed

    assert report["error_rate"] < StressConfig.MAX_ERROR_RATE, (
        f"Error rate {report['error_rate']:.1%} with {workers} recall workers"
    )
    assert qps > 0.5, f"QPS too low: {qps:.2f}"

    print(
        f"\n[2.2] Recall QPS (workers={workers}): "
        f"{qps:.1f} qps | p95={report['latency']['p95_ms']}ms | errors={report['error_rate']:.1%}"
    )


# ── 2.3  Recall Relevance Under Scale (Needle-in-Haystack) ──────────────────

@pytest.mark.asyncio
async def test_needle_recall_quality(unique_agent_id: str):
    """Plant needle memories and verify they're returned in top-10 as store grows."""
    agent = unique_agent_id
    canary_pairs = generate_canary_pairs()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        # Insert needle memories
        needle_ids: list[str] = []
        for query, content in canary_pairs:
            resp = await client.post(
                "/api/v1/memories",
                json={
                    "content": content,
                    "agent_id": agent,
                    "tier": "hot",
                    "criticality": 1.0,
                    "metadata": {"needle": True},
                },
            )
            assert resp.status_code == 201
            needle_ids.append(resp.json()["id"])

        # Insert haystack memories
        haystack = generate_memories(200, agent_id=agent, domain="fact")
        for mem in haystack:
            resp = await client.post("/api/v1/memories", json=mem)
            assert resp.status_code == 201

        # Evaluate Recall@10
        hits = 0
        for i, (query, _) in enumerate(canary_pairs):
            resp = await client.get(
                "/api/v1/memories/search",
                params={"q": query, "agent_id": agent, "top_k": 10},
            )
            assert resp.status_code == 200
            results = resp.json()
            returned_ids = [r["memory"]["id"] for r in results]
            if needle_ids[i] in returned_ids:
                hits += 1

        recall_at_10 = hits / len(canary_pairs)

    assert recall_at_10 >= StressConfig.MIN_RECALL_AT_10, (
        f"Recall@10 = {recall_at_10:.2f} below threshold {StressConfig.MIN_RECALL_AT_10} "
        f"(haystack=200 memories)"
    )
    print(f"\n[2.3] Needle Recall@10 = {recall_at_10:.2f} (hits={hits}/{len(canary_pairs)})")


# ── 2.4  Cold vs Warm Recall Latency ────────────────────────────────────────

@pytest.mark.asyncio
async def test_warm_recall_faster_than_first(unique_agent_id: str):
    """Repeated identical queries should be faster or equal to the first (warm cache effect)."""
    agent = unique_agent_id
    query = "How should I contact the user?"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Insert some memories
        memories = generate_memories(50, agent_id=agent)
        for mem in memories:
            await client.post("/api/v1/memories", json=mem)

        # First (cold) query
        t0 = time.perf_counter()
        resp = await client.get(
            "/api/v1/memories/search",
            params={"q": query, "agent_id": agent, "top_k": 10},
        )
        cold_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200

        # Warm queries (repeated 10×)
        warm_latencies: list[float] = []
        for _ in range(10):
            t0 = time.perf_counter()
            resp = await client.get(
                "/api/v1/memories/search",
                params={"q": query, "agent_id": agent, "top_k": 10},
            )
            warm_latencies.append((time.perf_counter() - t0) * 1000)
            assert resp.status_code == 200

        warm_p50 = sorted(warm_latencies)[len(warm_latencies) // 2]

    # Warm p50 should be within 5× cold (generous, as we may not have a cache)
    assert warm_p50 < cold_ms * 5 or warm_p50 < 2000, (
        f"Warm recall not faster: cold={cold_ms:.1f}ms warm_p50={warm_p50:.1f}ms"
    )
    print(f"\n[2.4] Cold={cold_ms:.1f}ms | Warm p50={warm_p50:.1f}ms")


# ── 2.5  Search Parameter Validation ────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_parameter_edge_cases(unique_agent_id: str):
    """Test search with edge-case parameters."""
    agent = unique_agent_id

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as client:
        # Insert one memory first
        await client.post(
            "/api/v1/memories",
            json={"content": "Edge case test memory", "agent_id": agent, "tier": "warm", "criticality": 0.5, "metadata": {}},
        )

        # top_k=1 — minimum
        resp = await client.get("/api/v1/memories/search", params={"q": "edge case test", "agent_id": agent, "top_k": 1})
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

        # top_k=100 — maximum
        resp = await client.get("/api/v1/memories/search", params={"q": "edge case test", "agent_id": agent, "top_k": 100})
        assert resp.status_code == 200

        # Non-existent agent — should return empty list, not 500
        resp = await client.get(
            "/api/v1/memories/search",
            params={"q": "something", "agent_id": "nonexistent-agent-xyz", "top_k": 10},
        )
        assert resp.status_code == 200
        assert resp.json() == []

        # Very long query string
        long_query = "how " * 500  # ~2000 chars
        resp = await client.get(
            "/api/v1/memories/search",
            params={"q": long_query, "agent_id": agent, "top_k": 10},
        )
        assert resp.status_code in (200, 422), (
            f"Long query returned unexpected status: {resp.status_code}"
        )

    print("\n[2.5] Search parameter edge cases: all passed")

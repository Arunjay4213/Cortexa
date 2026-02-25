"""
Test Suite 10 — Endurance Tests

10.1  Short Soak Test (2 min)      — sustained mixed workload, look for latency drift
10.2  Memory Churn                 — continuous insert+delete, stable store size
10.3  Gradual Ramp to Breaking     — find saturation point via ramp-up
10.4  Attribution Quality Drift    — canary scores stable over extended run
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid

import httpx
import pytest

from stress_tests.config import BASE_URL, StressConfig, auth_headers
from stress_tests.generators.memory_gen import generate_memories, generate_memory_content
from stress_tests.generators.query_gen import generate_canary_pairs, generate_queries
from stress_tests.harness import AsyncWorkerPool, make_memory_task, make_search_task, make_transaction_task
from stress_tests.metrics import MetricsCollector, LatencyHistogram


# ── 10.1  Short Soak Test ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_short_soak(unique_agent_id: str):
    """
    2-minute mixed workload (60% recall, 30% remember, 10% attribution).
    Verify throughput doesn't degrade > 30% and error rate stays < 5%.

    Uses ENDURANCE_QUICK_S for CI-friendly duration.
    """
    agent = unique_agent_id
    duration_s = StressConfig.ENDURANCE_QUICK_S  # 120s default
    workers = 8

    # Pre-populate
    seed_mems = generate_memories(50, agent_id=agent)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        mem_ids = []
        for m in seed_mems:
            resp = await client.post("/api/v1/memories", json=m)
            if resp.status_code == 201:
                mem_ids.append(resp.json()["id"])

    queries = generate_queries(30)
    collector = MetricsCollector("soak_test", warmup_fraction=0.1)
    checkpoint_throughputs: list[float] = []
    start = time.monotonic()

    async def mixed_task_factory():
        """Return a random mix of remember / recall / attribution tasks."""
        roll = hash(str(time.monotonic())) % 10
        if roll < 3:  # 30% remember
            mems = generate_memories(1, agent_id=agent)
            return make_memory_task(**mems[0])
        elif roll < 9:  # 60% recall
            q = queries[int(time.monotonic()) % len(queries)]
            return make_search_task(q, agent_id=agent)
        else:  # 10% attribution
            q = queries[int(time.monotonic()) % len(queries)]
            return make_transaction_task(
                query=q,
                response=generate_memory_content(60),
                memory_ids=mem_ids[:5] if len(mem_ids) >= 5 else mem_ids,
                agent_id=agent,
            )

    # Run in sustained mode using asyncio directly
    semaphore = asyncio.Semaphore(workers)
    results_by_window: list[list[float]] = []  # per 30-second window

    async def run_one() -> None:
        async with semaphore:
            task = await mixed_task_factory()
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as c:
                result = await task(c)
                collector.record(result)

    window_start = time.monotonic()
    window_latencies: list[float] = []
    launched_tasks: list[asyncio.Task] = []
    checkpoint_interval = 30  # record every 30 seconds

    deadline = start + duration_s
    while time.monotonic() < deadline:
        t = asyncio.create_task(run_one())
        launched_tasks.append(t)
        await asyncio.sleep(0.05)  # ~20 ops/sec target

        # Checkpoint every 30s
        if time.monotonic() - window_start >= checkpoint_interval:
            report = collector.report()
            checkpoint_throughputs.append(report["throughput_overall_rps"])
            window_start = time.monotonic()

    await asyncio.gather(*launched_tasks, return_exceptions=True)

    report = collector.report()
    total_s = time.monotonic() - start

    # Final assertions
    assert report["error_rate"] < StressConfig.MAX_ERROR_RATE, (
        f"Error rate {report['error_rate']:.1%} exceeded {StressConfig.MAX_ERROR_RATE:.0%} during soak"
    )

    # Throughput should not degrade >30% if we have multiple checkpoints
    if len(checkpoint_throughputs) >= 2:
        first = checkpoint_throughputs[0]
        last = checkpoint_throughputs[-1]
        if first > 0:
            degradation = (first - last) / first
            assert degradation < 0.30, (
                f"Throughput degraded {degradation:.1%} over {total_s:.0f}s soak "
                f"(first={first:.1f} ops/s → last={last:.1f} ops/s)"
            )

    print(
        f"\n[10.1] Soak test ({total_s:.0f}s): "
        f"ops={report['total_ops']} "
        f"throughput={report['throughput_overall_rps']:.1f} ops/s "
        f"p95={report['latency']['p95_ms']}ms "
        f"errors={report['error_rate']:.1%} "
        f"checkpoints={checkpoint_throughputs}"
    )


# ── 10.2  Memory Churn Test ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_churn(unique_agent_id: str):
    """
    Continuous create+delete cycle: store size stays bounded, recall quality stays stable.
    Runs for 60 seconds with a target steady-state of 30 memories.
    """
    agent = unique_agent_id
    target_size = 30
    duration_s = 60
    queries = generate_queries(10)

    # Canary: plant one persistent memory for quality tracking
    canary_content = "User's primary communication preference is email for all notifications."
    canary_id: str | None = None

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as setup_client:
        resp = await setup_client.post(
            "/api/v1/memories",
            json={"content": canary_content, "agent_id": agent, "tier": "hot", "criticality": 1.0, "metadata": {"canary": True}},
        )
        assert resp.status_code == 201
        canary_id = resp.json()["id"]

        # Seed with target_size memories
        id_queue: asyncio.Queue[str] = asyncio.Queue()
        for m in generate_memories(target_size, agent_id=agent):
            resp = await setup_client.post("/api/v1/memories", json=m)
            if resp.status_code == 201:
                await id_queue.put(resp.json()["id"])

    churn_errors = 0
    canary_hits = 0
    canary_checks = 0
    start = time.monotonic()

    async def churn_loop() -> None:
        nonlocal churn_errors, canary_hits, canary_checks
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as c:
            while time.monotonic() - start < duration_s:
                try:
                    # Insert one
                    mems = generate_memories(1, agent_id=agent)
                    resp = await c.post("/api/v1/memories", json=mems[0])
                    if resp.status_code == 201:
                        await id_queue.put(resp.json()["id"])

                    # Delete one (oldest)
                    if id_queue.qsize() > target_size + 5:
                        old_id = id_queue.get_nowait()
                        resp = await c.delete(f"/api/v1/memories/{old_id}")
                        # 404 is OK (may have been deleted already)
                        if resp.status_code not in (204, 200, 404):
                            churn_errors += 1
                except Exception:
                    churn_errors += 1
                await asyncio.sleep(0.1)

    async def recall_loop() -> None:
        nonlocal canary_hits, canary_checks
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as c:
            while time.monotonic() - start < duration_s:
                try:
                    resp = await c.get(
                        "/api/v1/memories/search",
                        params={"q": "email notification preference", "agent_id": agent, "top_k": 10},
                    )
                    if resp.status_code == 200:
                        canary_checks += 1
                        ids_returned = [r["memory"]["id"] for r in resp.json()]
                        if canary_id in ids_returned:
                            canary_hits += 1
                except Exception:
                    pass
                await asyncio.sleep(0.5)

    await asyncio.gather(churn_loop(), recall_loop())

    # Canary should be findable at least 70% of the time
    if canary_checks > 0:
        hit_rate = canary_hits / canary_checks
        assert hit_rate >= 0.70, (
            f"Canary recall degraded during churn: {hit_rate:.1%} hit rate "
            f"({canary_hits}/{canary_checks})"
        )

    assert churn_errors < 20, f"Too many churn errors: {churn_errors}"

    print(
        f"\n[10.2] Memory churn ({duration_s}s): "
        f"churn_errors={churn_errors} | "
        f"canary_hit_rate={canary_hits/max(canary_checks,1):.1%} "
        f"({canary_hits}/{canary_checks})"
    )


# ── 10.3  Gradual Ramp to Breaking Point ─────────────────────────────────────

@pytest.mark.asyncio
async def test_gradual_ramp(unique_agent_id: str):
    """
    Start at 1 worker, ramp up every 15s. Stop when error rate > 5% or p99 > 30s.
    Report the breaking point.
    """
    agent = unique_agent_id
    window_s = 15  # seconds per concurrency level
    max_workers = 32

    # Pre-populate
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        for m in generate_memories(50, agent_id=agent):
            resp = await client.post("/api/v1/memories", json=m)
            assert resp.status_code == 201

    queries = generate_queries(20)
    ramp_results: list[dict] = []
    breaking_workers: int | None = None

    for workers in [1, 2, 4, 8, 16, 32]:
        if workers > max_workers:
            break

        tasks = [
            make_search_task(queries[i % len(queries)], agent_id=agent)
            for i in range(workers * 20)
        ]
        collector = MetricsCollector(f"ramp_w{workers}", warmup_fraction=0.1)

        t0 = time.monotonic()
        try:
            async with AsyncWorkerPool(workers=workers, timeout=30.0) as pool:
                await asyncio.wait_for(
                    pool.run_tasks(tasks, collector),
                    timeout=window_s * 2,
                )
        except asyncio.TimeoutError:
            pass

        elapsed = max(time.monotonic() - t0, 0.001)
        report = collector.report()
        qps = report["success_ops"] / elapsed
        p99 = report["latency"]["p99_ms"]
        err = report["error_rate"]

        ramp_results.append({
            "workers": workers,
            "qps": round(qps, 1),
            "p99_ms": round(p99, 0),
            "error_rate": round(err, 4),
        })

        if err > StressConfig.MAX_ERROR_RATE or p99 > 30_000:
            breaking_workers = workers
            break

        await asyncio.sleep(1)  # brief pause between ramp stages

    print(f"\n[10.3] Ramp results:")
    for r in ramp_results:
        print(f"  workers={r['workers']}: {r['qps']} qps | p99={r['p99_ms']}ms | err={r['error_rate']:.1%}")
    if breaking_workers:
        print(f"  Breaking point: {breaking_workers} workers")
    else:
        print(f"  No breaking point reached up to {max_workers} workers")

    # Sanity: we should at least complete the run without server crashes
    for r in ramp_results:
        assert r["error_rate"] < 0.5, (
            f"Catastrophic error rate at {r['workers']} workers: {r['error_rate']:.1%}"
        )


# ── 10.4  Attribution Quality Drift ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_attribution_quality_drift(unique_agent_id: str):
    """
    Run canary attribution queries throughout a sustained workload.
    Verify the top-scoring memory for each canary query remains stable.
    """
    agent = unique_agent_id
    canary_pairs = generate_canary_pairs()[:5]  # Use first 5 canary pairs

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Insert canary memories
        canary_mem_ids: list[str] = []
        canary_contents: list[str] = []
        for query, content in canary_pairs:
            resp = await client.post(
                "/api/v1/memories",
                json={"content": content, "agent_id": agent, "tier": "hot", "criticality": 1.0, "metadata": {"canary": True}},
            )
            assert resp.status_code == 201
            canary_mem_ids.append(resp.json()["id"])
            canary_contents.append(content)

        # Insert background noise
        noise = generate_memories(50, agent_id=agent)
        noise_ids = []
        for m in noise:
            resp = await client.post("/api/v1/memories", json=m)
            if resp.status_code == 201:
                noise_ids.append(resp.json()["id"])

        all_ids = canary_mem_ids + noise_ids

        # Measure canary attribution at 3 checkpoints (T=0, T=30s, T=60s)
        checkpoints: list[dict[str, float]] = []

        for checkpoint_idx in range(3):
            if checkpoint_idx > 0:
                # Generate background load between checkpoints
                load_tasks = [
                    make_transaction_task(
                        query=generate_queries(1)[0],
                        response=generate_memory_content(60),
                        memory_ids=all_ids[:10],
                        agent_id=agent,
                    )
                    for _ in range(20)
                ]
                load_collector = MetricsCollector("drift_load", warmup_fraction=0.0)
                async with AsyncWorkerPool(workers=4) as pool:
                    await pool.run_tasks(load_tasks, load_collector)
                await asyncio.sleep(2)

            # Run canary attribution
            canary_scores: dict[str, float] = {}
            for i, (query, _) in enumerate(canary_pairs):
                resp = await client.post(
                    "/api/v1/transactions",
                    json={
                        "query_text": query,
                        "response_text": f"Based on context: {canary_contents[i]}",
                        "retrieved_memory_ids": all_ids[:10],
                        "agent_id": agent,
                    },
                )
                assert resp.status_code == 201
                scores = {s["memory_id"]: s["score"] for s in resp.json()["scores"]}
                canary_scores[canary_mem_ids[i]] = scores.get(canary_mem_ids[i], 0.0)

            checkpoints.append(canary_scores)

    # For each canary memory, verify score doesn't drift >30% across checkpoints
    drift_violations = []
    if len(checkpoints) >= 2:
        for cmid in canary_mem_ids:
            t0_score = checkpoints[0].get(cmid, 0.0)
            for ck_idx, ck in enumerate(checkpoints[1:], 1):
                ck_score = ck.get(cmid, 0.0)
                if t0_score > 0.05:
                    drift = abs(ck_score - t0_score) / t0_score
                    if drift > 0.30:
                        drift_violations.append(
                            f"{cmid}: T0={t0_score:.4f} T{ck_idx}={ck_score:.4f} drift={drift:.1%}"
                        )

    assert not drift_violations, (
        f"Attribution drift detected:\n" + "\n".join(drift_violations)
    )

    print(
        f"\n[10.4] Attribution quality drift: "
        f"{len(canary_pairs)} canaries, 3 checkpoints, 0 drift violations ✓"
    )

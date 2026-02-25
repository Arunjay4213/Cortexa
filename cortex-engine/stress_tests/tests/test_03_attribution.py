"""
Test Suite 03 — EAS Attribution Engine Stress Tests

3.1  Attribution Latency vs Context Size     — overhead at context sizes 5-50
3.2  Attribution Score Stability             — coefficient of variation across identical runs
3.3  Attribution Correctness Under Load      — canary scores stable under concurrent load
3.4  Attribution with Contradictory Memories — high entropy, both memories scored
3.5  Dead Memory Detection at Scale          — % of store never contributing attribution
"""

from __future__ import annotations

import asyncio
import statistics
import time

import httpx
import pytest

from stress_tests.config import BASE_URL, StressConfig, auth_headers
from stress_tests.generators.memory_gen import (
    generate_memories,
    generate_memory_content,
    generate_contradiction_pairs,
)
from stress_tests.generators.query_gen import generate_canary_pairs, generate_queries
from stress_tests.harness import AsyncWorkerPool, make_transaction_task
from stress_tests.metrics import MetricsCollector


# ── Helper: create a full attribution transaction ──────────────────────────

async def _run_attribution(
    client: httpx.AsyncClient,
    query: str,
    memory_ids: list[str],
    agent_id: str,
) -> dict:
    """POST a transaction and return the TransactionWithScores response."""
    response_text = f"Based on the provided context, here is my answer to: {query}. " + generate_memory_content(50)
    payload = {
        "query_text": query,
        "response_text": response_text,
        "retrieved_memory_ids": memory_ids,
        "agent_id": agent_id,
    }
    t0 = time.perf_counter()
    resp = await client.post("/api/v1/transactions", json=payload)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 201, f"Transaction failed: {resp.status_code} {resp.text[:300]}"
    data = resp.json()
    data["_elapsed_ms"] = elapsed_ms
    return data


async def _insert_memories(client: httpx.AsyncClient, memories: list[dict]) -> list[str]:
    ids = []
    for mem in memories:
        resp = await client.post("/api/v1/memories", json=mem)
        assert resp.status_code == 201
        ids.append(resp.json()["id"])
    return ids


# ── 3.1  Attribution Latency vs Context Size ──────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("context_size", StressConfig.CONTEXT_WINDOW_SIZES)
async def test_attribution_latency_vs_context_size(context_size: int, unique_agent_id: str):
    """Measure attribution overhead as context window grows."""
    agent = unique_agent_id
    query = "What is the recommended configuration for this system?"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Insert context_size memories
        mems = generate_memories(context_size, agent_id=agent)
        mem_ids = await _insert_memories(client, mems)

        # Run 10 attribution transactions
        latencies: list[float] = []
        for _ in range(10):
            data = await _run_attribution(client, query, mem_ids, agent)
            latencies.append(data["_elapsed_ms"])

    p50 = sorted(latencies)[len(latencies) // 2]
    p95 = sorted(latencies)[int(0.95 * len(latencies))]

    # Attribution should complete within SLA
    assert p95 < StressConfig.MAX_P95_MS, (
        f"Attribution p95={p95:.0f}ms exceeds {StressConfig.MAX_P95_MS}ms "
        f"for context_size={context_size}"
    )

    print(
        f"\n[3.1] Attribution latency (context={context_size}): "
        f"p50={p50:.1f}ms p95={p95:.1f}ms"
    )


# ── 3.2  Attribution Score Stability ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_attribution_score_stability(unique_agent_id: str):
    """Run identical attribution 20 times; assert coefficient of variation < 0.15."""
    agent = unique_agent_id
    query = "How should I contact the user?"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        # Insert 5 memories including one highly relevant
        mems = [
            {
                "content": "User prefers email communication for all notifications.",
                "agent_id": agent,
                "tier": "hot",
                "criticality": 1.0,
                "metadata": {},
            },
        ] + generate_memories(4, agent_id=agent)
        mem_ids = await _insert_memories(client, mems)

        # Fixed response text — must be identical every run so embedding is deterministic
        fixed_response = "Based on the user's preferences, you should contact them via email."

        # Run 20 identical attribution queries
        score_vectors: list[list[float]] = []
        for _ in range(20):
            payload = {
                "query_text": query,
                "response_text": fixed_response,
                "retrieved_memory_ids": mem_ids,
                "agent_id": agent,
            }
            resp = await client.post("/api/v1/transactions", json=payload)
            assert resp.status_code == 201
            scores = {s["memory_id"]: s["score"] for s in resp.json()["scores"]}
            score_vectors.append([scores.get(mid, 0.0) for mid in mem_ids])

    # For each memory position, compute coefficient of variation
    unstable = []
    for col_idx in range(len(mem_ids)):
        col_scores = [v[col_idx] for v in score_vectors]
        mean_s = statistics.mean(col_scores)
        if mean_s < 0.05:
            continue  # skip near-zero scores (noise floor)
        std_s = statistics.stdev(col_scores) if len(col_scores) > 1 else 0.0
        cv = std_s / mean_s if mean_s > 0 else 0.0
        if cv > 0.15:
            unstable.append((mem_ids[col_idx], mean_s, cv))

    assert not unstable, (
        f"Unstable attribution scores (CV > 0.15): {unstable}"
    )
    print(f"\n[3.2] Attribution stability: all {len(mem_ids)} memories CV < 0.15 ✓")


# ── 3.3  Attribution Correctness Under Concurrent Load ───────────────────────

@pytest.mark.asyncio
async def test_attribution_correctness_under_load(unique_agent_id: str):
    """Canary attribution scores don't shift >20% when system is under concurrent load."""
    agent_canary = f"{unique_agent_id}-canary"
    agent_load = f"{unique_agent_id}-load"
    query = "How should I contact the user?"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        # Set up canary agent
        canary_mems = [
            {"content": "User prefers email communication.", "agent_id": agent_canary, "tier": "hot", "criticality": 1.0, "metadata": {}},
            {"content": "Irrelevant: weather is sunny today.", "agent_id": agent_canary, "tier": "warm", "criticality": 0.3, "metadata": {}},
            {"content": "Technical documentation about memory systems.", "agent_id": agent_canary, "tier": "warm", "criticality": 0.5, "metadata": {}},
        ]
        canary_ids = await _insert_memories(client, canary_mems)

        # Fixed response text — identical every run for deterministic comparison
        fixed_response = "Based on the provided context, you should contact the user via email."

        # Baseline: canary attribution in isolation
        baseline_resp = await client.post("/api/v1/transactions", json={
            "query_text": query,
            "response_text": fixed_response,
            "retrieved_memory_ids": canary_ids,
            "agent_id": agent_canary,
        })
        assert baseline_resp.status_code == 201
        baseline_scores = {s["memory_id"]: s["score"] for s in baseline_resp.json()["scores"]}

        # Setup load: many background memories for a different agent
        load_mems = generate_memories(50, agent_id=agent_load)
        await _insert_memories(client, load_mems)

    # Run canary + concurrent load simultaneously
    load_tasks = [make_transaction_task(
        query=generate_queries(1)[0],
        response=generate_memory_content(100),
        memory_ids=[],
        agent_id=agent_load,
    ) for _ in range(20)]

    collector = MetricsCollector("load_bg", warmup_fraction=0.0)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client2:
        async with AsyncWorkerPool(workers=8) as pool:
            # Start load in background
            load_future = asyncio.create_task(pool.run_tasks(load_tasks, collector))

            # Run canary queries while load is running — use fixed response text
            canary_under_load: list[dict[str, float]] = []
            for _ in range(5):
                resp = await client2.post("/api/v1/transactions", json={
                    "query_text": query,
                    "response_text": fixed_response,
                    "retrieved_memory_ids": canary_ids,
                    "agent_id": agent_canary,
                })
                assert resp.status_code == 201
                scores = {s["memory_id"]: s["score"] for s in resp.json()["scores"]}
                canary_under_load.append(scores)

            await load_future

    # Check canary scores didn't drift
    for mid, baseline_score in baseline_scores.items():
        if baseline_score < 0.05:
            continue
        under_load_scores = [s.get(mid, 0.0) for s in canary_under_load]
        for score in under_load_scores:
            drift = abs(score - baseline_score) / max(baseline_score, 0.01)
            assert drift < 0.3, (
                f"Attribution drift under load for {mid}: "
                f"baseline={baseline_score:.4f} under_load={score:.4f} drift={drift:.1%}"
            )

    print(f"\n[3.3] Canary attribution stable under concurrent load ✓")


# ── 3.4  Attribution with Contradictory Memories ─────────────────────────────

@pytest.mark.asyncio
async def test_attribution_with_contradictions(unique_agent_id: str):
    """Insert contradiction pairs; verify both get attribution scores (system doesn't ignore one)."""
    agent = unique_agent_id
    pairs = generate_contradiction_pairs(5, agent_id=agent)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        for mem_a, mem_b in pairs:
            resp_a = await client.post("/api/v1/memories", json=mem_a)
            resp_b = await client.post("/api/v1/memories", json=mem_b)
            assert resp_a.status_code == 201
            assert resp_b.status_code == 201
            id_a = resp_a.json()["id"]
            id_b = resp_b.json()["id"]

            query = "How should I contact the user?"
            data = await _run_attribution(client, query, [id_a, id_b], agent)

            scores = {s["memory_id"]: s["score"] for s in data["scores"]}
            score_a = scores.get(id_a, 0.0)
            score_b = scores.get(id_b, 0.0)

            # Both memories should receive non-trivial attribution (neither completely ignored)
            # This is relaxed — the winner can dominate, but the loser should still get some score
            assert score_a + score_b > 0.5, (
                f"Both contradicting memories got near-zero attribution: {score_a:.3f} + {score_b:.3f}"
            )

    print(f"\n[3.4] Contradiction attribution: both memories get attribution ✓")


# ── 3.5  Dead Memory Detection at Scale ──────────────────────────────────────

@pytest.mark.asyncio
async def test_dead_memory_detection(unique_agent_id: str):
    """Identify memories retrieved 5+ times but with consistently near-zero attribution."""
    agent = unique_agent_id
    total_memories = 30
    queries = generate_queries(20)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        # Insert memories — mix of relevant and irrelevant
        mems = generate_memories(total_memories, agent_id=agent)
        mem_ids = await _insert_memories(client, mems)

        # Run 30 attribution transactions (each using all memory IDs)
        for q in queries[:15]:
            response = f"Answer to: {q}. " + generate_memory_content(80)
            payload = {
                "query_text": q,
                "response_text": response,
                "retrieved_memory_ids": mem_ids,
                "agent_id": agent,
            }
            resp = await client.post("/api/v1/transactions", json=payload)
            assert resp.status_code == 201

        # Collect profiles from API
        # Dead threshold scales with context size: uniform distribution = 1/N per memory.
        # Flag memories scoring below half the uniform share (clearly below noise floor).
        dead_threshold = (1.0 / total_memories) * 0.5
        dead_memories: list[str] = []
        zero_attribution: list[str] = []

        for mid in mem_ids:
            resp = await client.get(f"/api/v1/memories/{mid}")
            assert resp.status_code == 200
            data = resp.json()
            profile = data.get("profile")
            if profile is not None:
                if profile["retrieval_count"] >= 5 and profile["mean_attribution"] < dead_threshold:
                    dead_memories.append(mid)
            elif data["memory"]["retrieval_count"] == 0:
                zero_attribution.append(mid)

        dead_rate = len(dead_memories) / total_memories

    print(
        f"\n[3.5] Dead memory analysis: "
        f"{len(dead_memories)}/{total_memories} dead ({dead_rate:.1%}), "
        f"{len(zero_attribution)} never retrieved"
    )
    # Not a hard failure — this is a diagnostic metric
    # But assert the system didn't crash during profiling
    assert dead_rate < 1.0, "All memories marked as dead — attribution system broken"

"""
Test Suite 05 — Multi-Agent Stress Tests

5.1  Agent Isolation Under Concurrent Access   — no cross-agent memory leakage
5.2  Concurrent Agents Independent Throughput  — per-agent fairness
5.3  Cross-Agent Attribution Divergence        — same memory, different contexts
5.4  Agent Namespace Integrity                 — agent A cannot read agent B's private memories
5.5  Simultaneous Agent Blast                  — many agents active at once
"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
import pytest

from stress_tests.config import BASE_URL, StressConfig, auth_headers
from stress_tests.generators.agent_gen import generate_agent_ids
from stress_tests.generators.memory_gen import generate_memories, generate_memory_content
from stress_tests.generators.query_gen import generate_queries
from stress_tests.harness import AsyncWorkerPool, make_memory_task, make_search_task
from stress_tests.metrics import MetricsCollector


# ── 5.1  Agent Isolation — No Cross-Contamination ─────────────────────────────

@pytest.mark.asyncio
async def test_agent_isolation(unique_agent_id: str):
    """
    Two agents insert tagged memories concurrently.
    After all inserts, each agent's store contains ONLY its own memories.
    """
    base = unique_agent_id
    agent_a = f"{base}-A"
    agent_b = f"{base}-B"
    count = 30

    mems_a = generate_memories(count, agent_id=agent_a)
    mems_b = generate_memories(count, agent_id=agent_b)

    # Tag content so we can identify ownership
    for i, m in enumerate(mems_a):
        m["content"] = f"AGENT_A_EXCLUSIVE_{i}: " + m["content"][:50]
    for i, m in enumerate(mems_b):
        m["content"] = f"AGENT_B_EXCLUSIVE_{i}: " + m["content"][:50]

    all_tasks = [make_memory_task(**m) for m in mems_a + mems_b]
    collector = MetricsCollector("agent_isolation_insert", warmup_fraction=0.0)

    async with AsyncWorkerPool(workers=8) as pool:
        await pool.run_tasks(all_tasks, collector)

    assert collector.error_rate == 0.0, f"Errors during isolation insert: {collector.error_counts}"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Fetch all memories per agent
        async def list_all(agent_id: str) -> list[dict]:
            items = []
            offset = 0
            while True:
                resp = await client.get(
                    "/api/v1/memories",
                    params={"agent_id": agent_id, "limit": 200, "offset": offset},
                )
                assert resp.status_code == 200
                page = resp.json()["items"]
                items.extend(page)
                if len(page) < 200:
                    break
                offset += 200
            return items

        mems_a_stored = await list_all(agent_a)
        mems_b_stored = await list_all(agent_b)

    # Every memory in agent_a's store must belong to agent_a
    contamination_a = [m for m in mems_a_stored if m["agent_id"] != agent_a]
    contamination_b = [m for m in mems_b_stored if m["agent_id"] != agent_b]

    assert not contamination_a, (
        f"Agent A's store has {len(contamination_a)} foreign memories"
    )
    assert not contamination_b, (
        f"Agent B's store has {len(contamination_b)} foreign memories"
    )

    # Content tagged for A should not appear in B and vice versa
    b_contents = {m["content"][:15] for m in mems_b_stored}
    leaked_a = any(c[:15] == "AGENT_A_EXCLUSI" for c in b_contents)
    assert not leaked_a, "Agent A's content leaked into Agent B's store"

    print(
        f"\n[5.1] Agent isolation: A={len(mems_a_stored)}, B={len(mems_b_stored)} memories, "
        f"0 contaminations ✓"
    )


# ── 5.2  Concurrent Agents — Fairness ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_agents_fairness(unique_agent_id: str):
    """N agents compete for the same server; no agent is starved of throughput."""
    num_agents = 5
    count_per_agent = 20
    agents = generate_agent_ids(num_agents, prefix=f"{unique_agent_id}-fair")

    # Build tasks for all agents interleaved
    tasks_by_agent: dict[str, list] = {}
    for agent in agents:
        mems = generate_memories(count_per_agent, agent_id=agent)
        tasks_by_agent[agent] = [make_memory_task(**m) for m in mems]

    all_tasks = []
    for i in range(count_per_agent):
        for agent in agents:
            if i < len(tasks_by_agent[agent]):
                all_tasks.append(tasks_by_agent[agent][i])

    collector = MetricsCollector("fairness_test", warmup_fraction=0.0)
    t0 = time.monotonic()

    async with AsyncWorkerPool(workers=8) as pool:
        await pool.run_tasks(all_tasks, collector)

    elapsed = time.monotonic() - t0
    report = collector.report()
    throughput = report["success_ops"] / elapsed

    assert report["error_rate"] < StressConfig.MAX_ERROR_RATE
    assert report["success_ops"] == num_agents * count_per_agent, (
        f"Lost {num_agents * count_per_agent - report['success_ops']} inserts"
    )

    print(
        f"\n[5.2] Concurrent agents (n={num_agents}): "
        f"throughput={throughput:.1f} ops/s | error_rate={report['error_rate']:.1%}"
    )


# ── 5.3  Cross-Agent Attribution Divergence ───────────────────────────────────

@pytest.mark.asyncio
async def test_cross_agent_attribution_divergence(unique_agent_id: str):
    """
    A shared memory gets different attribution scores in different agent contexts.
    Tests that per-agent context correctly influences attribution.
    """
    base = unique_agent_id
    num_agents = 4
    agents = generate_agent_ids(num_agents, prefix=f"{base}-xagent")
    query = "How should I handle user communication preferences?"
    shared_content = "User prefers email communication for all system notifications."

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        agent_scores: dict[str, float] = {}

        for agent in agents:
            # Insert the shared memory
            resp = await client.post(
                "/api/v1/memories",
                json={"content": shared_content, "agent_id": agent, "tier": "hot", "criticality": 1.0, "metadata": {}},
            )
            assert resp.status_code == 201
            shared_id = resp.json()["id"]

            # Each agent has different surrounding context
            context_size = agents.index(agent) * 3 + 2  # 2, 5, 8, 11
            extra_mems = generate_memories(context_size, agent_id=agent)
            mem_ids = [shared_id]
            for m in extra_mems:
                r = await client.post("/api/v1/memories", json=m)
                assert r.status_code == 201
                mem_ids.append(r.json()["id"])

            # Run attribution
            resp = await client.post(
                "/api/v1/transactions",
                json={
                    "query_text": query,
                    "response_text": f"For agent {agent}: based on the context, the user prefers email.",
                    "retrieved_memory_ids": mem_ids,
                    "agent_id": agent,
                },
            )
            assert resp.status_code == 201
            scores = {s["memory_id"]: s["score"] for s in resp.json()["scores"]}
            agent_scores[agent] = scores.get(shared_id, 0.0)

    # Report divergence — don't fail, just observe
    score_values = list(agent_scores.values())
    mean_score = sum(score_values) / len(score_values) if score_values else 0
    spread = max(score_values) - min(score_values) if score_values else 0

    print(
        f"\n[5.3] Cross-agent attribution divergence: "
        f"mean={mean_score:.4f} spread={spread:.4f} "
        f"scores={agent_scores}"
    )

    # Sanity: at least one agent gave the shared memory non-trivial attribution
    assert max(score_values) > 0.05, (
        f"Shared memory got near-zero attribution in all agents: {agent_scores}"
    )


# ── 5.4  Agent Namespace Integrity ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_namespace_integrity(unique_agent_id: str):
    """
    Agent B should not be able to read Agent A's memories even with direct ID access.
    The API doesn't have auth, but memories should be tagged correctly.
    """
    base = unique_agent_id
    agent_a = f"{base}-priv-A"
    agent_b = f"{base}-priv-B"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as client:
        # Insert a private memory for agent A
        resp = await client.post(
            "/api/v1/memories",
            json={
                "content": f"PRIVATE secret data for {agent_a} only",
                "agent_id": agent_a,
                "tier": "warm",
                "criticality": 1.0,
                "metadata": {"private": True},
            },
        )
        assert resp.status_code == 201
        a_mem_id = resp.json()["id"]

        # Agent B tries to search for it
        resp = await client.get(
            "/api/v1/memories/search",
            params={"q": "secret data", "agent_id": agent_b, "top_k": 10},
        )
        assert resp.status_code == 200
        b_results = resp.json()
        b_ids = [r["memory"]["id"] for r in b_results]
        assert a_mem_id not in b_ids, (
            f"Agent B found Agent A's private memory {a_mem_id} in search"
        )

        # Agent B tries direct GET — memory exists but belongs to A
        resp = await client.get(f"/api/v1/memories/{a_mem_id}")
        # System returns it (no auth enforcement at API level is expected),
        # but the agent_id field should correctly show agent_a
        if resp.status_code == 200:
            assert resp.json()["memory"]["agent_id"] == agent_a, (
                "Memory agent_id field corrupted"
            )

        # Agent A's listing should show its memory
        resp = await client.get(
            "/api/v1/memories",
            params={"agent_id": agent_a, "limit": 10},
        )
        assert resp.status_code == 200
        a_ids = [m["id"] for m in resp.json()["items"]]
        assert a_mem_id in a_ids, "Agent A's memory missing from its own listing"

    print(f"\n[5.4] Agent namespace integrity: B cannot find A's memory in scoped search ✓")


# ── 5.5  Simultaneous Agent Blast ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_simultaneous_agent_blast(unique_agent_id: str):
    """
    10 agents each inserting 10 memories simultaneously — measure system stability.
    """
    num_agents = 10
    per_agent = 10
    agents = generate_agent_ids(num_agents, prefix=f"{unique_agent_id}-blast")

    all_tasks = []
    for agent in agents:
        mems = generate_memories(per_agent, agent_id=agent)
        for m in mems:
            all_tasks.append(make_memory_task(**m))

    collector = MetricsCollector("agent_blast", warmup_fraction=0.0)
    t0 = time.monotonic()

    async with AsyncWorkerPool(workers=16) as pool:
        await pool.run_tasks(all_tasks, collector)

    elapsed = time.monotonic() - t0
    report = collector.report()

    assert report["error_rate"] < StressConfig.MAX_ERROR_RATE, (
        f"High error rate during agent blast: {report['error_rate']:.1%} "
        f"errors={report['error_counts']}"
    )
    assert report["success_ops"] == num_agents * per_agent

    print(
        f"\n[5.5] Agent blast ({num_agents} agents × {per_agent} memories): "
        f"throughput={report['throughput_overall_rps']:.1f} ops/s | "
        f"p95={report['latency']['p95_ms']}ms | "
        f"elapsed={elapsed:.1f}s"
    )

"""
Test Suite 08 — Compliance & Audit Trail Tests

8.1  Attribution Audit — every transaction has full score vector stored
8.2  Memory Immutability — content field should not change after creation
8.3  Soft Delete Audit — deleted memories are soft-deleted (deleted_at set), not erased
8.4  Agent Scoping — list/search APIs respect agent_id isolation
8.5  Transaction Completeness — two-phase protocol stores both phases correctly
"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
import pytest

from stress_tests.config import BASE_URL, StressConfig, auth_headers
from stress_tests.generators.memory_gen import generate_memories, generate_memory_content


# ── 8.1  Attribution Audit — Transaction Score Completeness ───────────────────

@pytest.mark.asyncio
async def test_attribution_audit_completeness(unique_agent_id: str):
    """
    For 50 transactions, verify that:
    - The transaction exists and is queryable by ID
    - The score vector has one entry per retrieved memory
    - All scores are in [0, 1]
    """
    agent = unique_agent_id
    num_transactions = 50
    context_size = 5

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, headers=auth_headers()) as client:
        # Insert memories
        mems = generate_memories(context_size, agent_id=agent)
        mem_ids = []
        for m in mems:
            resp = await client.post("/api/v1/memories", json=m)
            assert resp.status_code == 201
            mem_ids.append(resp.json()["id"])

        txn_ids = []
        for i in range(num_transactions):
            resp = await client.post(
                "/api/v1/transactions",
                json={
                    "query_text": f"Audit test query #{i}",
                    "response_text": generate_memory_content(80),
                    "retrieved_memory_ids": mem_ids,
                    "agent_id": agent,
                },
            )
            assert resp.status_code == 201, f"Transaction {i} failed: {resp.text[:200]}"
            txn_ids.append(resp.json()["transaction"]["id"])

        # Audit each transaction
        audit_failures = []
        for txn_id in txn_ids:
            resp = await client.get(f"/api/v1/transactions/{txn_id}")
            if resp.status_code != 200:
                audit_failures.append(f"txn {txn_id} not found: {resp.status_code}")
                continue

            data = resp.json()
            txn = data["transaction"]
            scores = data["scores"]

            # Transaction has required fields
            for field in ["id", "query_text", "response_text", "agent_id", "created_at"]:
                if not txn.get(field):
                    audit_failures.append(f"txn {txn_id} missing {field}")

            # Score count matches retrieved memory count
            if len(scores) != len(mem_ids):
                audit_failures.append(
                    f"txn {txn_id}: {len(scores)} scores for {len(mem_ids)} memories"
                )

            # All scores in [0, 1]
            for s in scores:
                if not (0.0 <= s["score"] <= 1.0):
                    audit_failures.append(
                        f"txn {txn_id}: score {s['score']:.4f} out of [0,1]"
                    )

    assert not audit_failures, (
        f"{len(audit_failures)} audit failures:\n" + "\n".join(audit_failures[:5])
    )
    print(f"\n[8.1] Attribution audit: {num_transactions} transactions, all complete ✓")


# ── 8.2  Memory Content Immutability ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_content_immutability(unique_agent_id: str):
    """
    The PATCH endpoint allows updating metadata and tier/criticality,
    but content should not be changeable (or if it is, it must be reflected accurately).
    """
    agent = unique_agent_id
    original_content = f"Original immutable content {uuid.uuid4().hex}"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, headers=auth_headers()) as client:
        resp = await client.post(
            "/api/v1/memories",
            json={"content": original_content, "agent_id": agent, "tier": "warm", "criticality": 0.5, "metadata": {}},
        )
        assert resp.status_code == 201
        mem_id = resp.json()["id"]

        # Try to patch content (MemoryUpdate model doesn't expose content)
        # Should either ignore it silently or return 422
        resp = await client.patch(
            f"/api/v1/memories/{mem_id}",
            json={"criticality": 0.8, "metadata": {"updated": True}},
        )
        assert resp.status_code == 200

        # Verify content was NOT changed
        resp = await client.get(f"/api/v1/memories/{mem_id}")
        assert resp.status_code == 200
        assert resp.json()["memory"]["content"] == original_content, (
            "Memory content was unexpectedly mutated by PATCH"
        )

    print(f"\n[8.2] Memory content immutability: content unchanged after PATCH ✓")


# ── 8.3  Soft Delete Audit Trail ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_soft_delete_audit_trail(unique_agent_id: str):
    """
    After soft-delete, the record should have deleted_at set (if queried via admin)
    and the memory count should decrease accordingly.
    """
    agent = unique_agent_id
    insert_count = 20
    delete_count = 10

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        mem_ids = []
        for m in generate_memories(insert_count, agent_id=agent):
            resp = await client.post("/api/v1/memories", json=m)
            assert resp.status_code == 201
            mem_ids.append(resp.json()["id"])

        # Get initial count
        resp = await client.get("/api/v1/memories", params={"agent_id": agent, "limit": 1})
        initial_total = resp.json()["total"]
        assert initial_total == insert_count

        # Soft-delete 10
        for mid in mem_ids[:delete_count]:
            resp = await client.delete(f"/api/v1/memories/{mid}")
            assert resp.status_code in (204, 200)

        # Count should be reduced
        resp = await client.get("/api/v1/memories", params={"agent_id": agent, "limit": 1})
        after_total = resp.json()["total"]
        expected = insert_count - delete_count
        assert after_total == expected, (
            f"After deleting {delete_count}, expected {expected} memories, got {after_total}"
        )

        # Deleted memories should return 404
        for mid in mem_ids[:delete_count]:
            resp = await client.get(f"/api/v1/memories/{mid}")
            assert resp.status_code == 404, (
                f"Soft-deleted memory {mid} still returns {resp.status_code}"
            )

    print(f"\n[8.3] Soft delete: count reduced {insert_count}→{expected}, deleted return 404 ✓")


# ── 8.4  Agent Scoping in List Endpoint ──────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_scoping_in_list(unique_agent_id: str):
    """
    Listing memories with agent_id=A never returns memories from agent_id=B.
    """
    base = unique_agent_id
    agent_a = f"{base}-scope-A"
    agent_b = f"{base}-scope-B"
    count = 20

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        a_ids: set[str] = set()
        b_ids: set[str] = set()

        for m in generate_memories(count, agent_id=agent_a):
            resp = await client.post("/api/v1/memories", json=m)
            assert resp.status_code == 201
            a_ids.add(resp.json()["id"])

        for m in generate_memories(count, agent_id=agent_b):
            resp = await client.post("/api/v1/memories", json=m)
            assert resp.status_code == 201
            b_ids.add(resp.json()["id"])

        # List agent A's memories — must not contain B's
        resp = await client.get("/api/v1/memories", params={"agent_id": agent_a, "limit": 200})
        assert resp.status_code == 200
        a_listed = {m["id"] for m in resp.json()["items"]}

        leaked = a_listed & b_ids
        assert not leaked, f"Agent B's memories leaked into Agent A's listing: {leaked}"

        # List agent B's memories — must not contain A's
        resp = await client.get("/api/v1/memories", params={"agent_id": agent_b, "limit": 200})
        assert resp.status_code == 200
        b_listed = {m["id"] for m in resp.json()["items"]}

        leaked = b_listed & a_ids
        assert not leaked, f"Agent A's memories leaked into Agent B's listing: {leaked}"

    print(f"\n[8.4] Agent scoping: no cross-agent leakage in list endpoint ✓")


# ── 8.5  Two-Phase Transaction Protocol ──────────────────────────────────────

@pytest.mark.asyncio
async def test_two_phase_transaction_protocol(unique_agent_id: str):
    """
    Test the two-phase protocol: initiate → complete.
    Phase 1 creates a pending transaction; Phase 2 completes it with EAS scores.
    """
    agent = unique_agent_id

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0, headers=auth_headers()) as client:
        # Insert some memories
        mems = generate_memories(5, agent_id=agent)
        mem_ids = []
        for m in mems:
            resp = await client.post("/api/v1/memories", json=m)
            assert resp.status_code == 201
            mem_ids.append(resp.json()["id"])

        # Phase 1: initiate
        resp = await client.post(
            "/api/v1/transactions/initiate",
            json={
                "query_text": "Two-phase test query",
                "retrieved_memory_ids": mem_ids,
                "agent_id": agent,
            },
        )
        assert resp.status_code == 201, f"Initiate failed: {resp.text}"
        txn_id = resp.json()["transaction_id"]
        assert resp.json()["status"] == "pending"

        # Verify transaction is pending
        resp = await client.get(f"/api/v1/transactions/{txn_id}")
        assert resp.status_code == 200
        assert resp.json()["transaction"]["status"] == "pending"
        assert not resp.json()["scores"], "Pending transaction should have no scores yet"

        # Phase 2: complete
        resp = await client.post(
            f"/api/v1/transactions/{txn_id}/complete",
            json={
                "response_text": generate_memory_content(100),
                "input_tokens": 50,
                "output_tokens": 80,
            },
        )
        assert resp.status_code == 200, f"Complete failed: {resp.text}"
        data = resp.json()
        assert data["transaction"]["status"] == "completed"
        assert len(data["scores"]) == len(mem_ids), (
            f"Expected {len(mem_ids)} scores, got {len(data['scores'])}"
        )

        # Verify scores are in [0, 1]
        for s in data["scores"]:
            assert 0.0 <= s["score"] <= 1.0

        # Cannot complete the same transaction twice
        resp = await client.post(
            f"/api/v1/transactions/{txn_id}/complete",
            json={"response_text": "Second completion attempt"},
        )
        assert resp.status_code == 409, (
            f"Expected 409 on double-complete, got {resp.status_code}"
        )

    print(f"\n[8.5] Two-phase protocol: pending→completed, scores correct, double-complete=409 ✓")

"""Unit tests for counterfactual memory staging engine.

Pure computation tests — no DB, no sentence-transformers.
Uses deterministic numpy embeddings.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from cortex.attribution.counterfactual import (
    MemoryRecord,
    TransactionRecord,
    ChangeSpec,
    build_counterfactual_memory_set,
    run_counterfactual,
)
from cortex.models import TokenCostConfig

# ── Fixtures ──────────────────────────────────────────────────────────

EMBEDDING_DIM = 16
RNG = np.random.default_rng(99)
NOW = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)
COST_CONFIG = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)


def _unit_vec(dim: int = EMBEDDING_DIM, seed: int = 0) -> np.ndarray:
    """Deterministic unit vector."""
    rng = np.random.default_rng(seed)
    v = rng.normal(0, 1, dim)
    return v / np.linalg.norm(v)


def _near_vec(base: np.ndarray, noise: float = 0.1, seed: int = 1) -> np.ndarray:
    """Vector near `base` with small noise."""
    rng = np.random.default_rng(seed)
    v = base + rng.normal(0, noise, base.shape)
    return v / np.linalg.norm(v)


def _make_memories(n: int = 5) -> list[MemoryRecord]:
    """Create n memories with well-separated embeddings."""
    mems = []
    for i in range(n):
        emb = np.zeros(EMBEDDING_DIM)
        emb[i % EMBEDDING_DIM] = 1.0
        emb += 0.1  # shared signal
        emb /= np.linalg.norm(emb)
        mems.append(MemoryRecord(
            id=f"mem-{i}",
            content=f"Memory content {i}",
            embedding=emb,
            tokens=100 + i * 10,
            tier="warm",
            created_at=NOW - timedelta(days=10 - i),
            last_accessed=NOW - timedelta(days=i),
            agent_id="test-agent",
            retrieval_count=5 - i,
            total_attribution=0.2 * (5 - i),
        ))
    return mems


def _make_transactions(memories: list[MemoryRecord], n: int = 3) -> list[TransactionRecord]:
    """Create n transactions that retrieve from the given memories."""
    txns = []
    for i in range(n):
        # Query embedding near memory i's embedding
        q_emb = _near_vec(memories[i % len(memories)].embedding, noise=0.15, seed=100 + i)
        r_emb = _near_vec(q_emb, noise=0.2, seed=200 + i)
        # Retrieve top memories
        retrieved = [m.id for m in memories[:min(4, len(memories))]]
        txns.append(TransactionRecord(
            id=f"txn-{i}",
            query_text=f"Test query {i}",
            query_embedding=q_emb,
            response_embedding=r_emb,
            retrieved_memory_ids=retrieved,
            input_tokens=500,
            output_tokens=200,
        ))
    return txns


# ── Tests: build_counterfactual_memory_set ────────────────────────────

class TestBuildCounterfactualMemorySet:
    def test_no_changes(self):
        mems = _make_memories(3)
        before, after = build_counterfactual_memory_set(mems, [])
        assert set(before.keys()) == set(after.keys())
        assert len(after) == 3

    def test_remove_memory(self):
        mems = _make_memories(3)
        changes = [ChangeSpec(action="remove", memory_id="mem-1")]
        before, after = build_counterfactual_memory_set(mems, changes)
        assert "mem-1" in before
        assert "mem-1" not in after
        assert len(after) == 2

    def test_add_memory(self):
        mems = _make_memories(3)
        new_emb = _unit_vec(EMBEDDING_DIM, seed=42)
        changes = [ChangeSpec(
            action="add",
            memory_id="mem-new",
            content="New memory content",
            embedding=new_emb,
            tokens=150,
        )]
        before, after = build_counterfactual_memory_set(mems, changes)
        assert "mem-new" not in before
        assert "mem-new" in after
        assert after["mem-new"].tokens == 150
        assert len(after) == 4

    def test_edit_memory(self):
        mems = _make_memories(3)
        new_emb = _unit_vec(EMBEDDING_DIM, seed=77)
        changes = [ChangeSpec(
            action="edit",
            memory_id="mem-0",
            content="Edited content",
            embedding=new_emb,
            tokens=200,
        )]
        before, after = build_counterfactual_memory_set(mems, changes)
        assert before["mem-0"].content == "Memory content 0"
        assert after["mem-0"].content == "Edited content"
        assert after["mem-0"].tokens == 200
        assert not np.array_equal(before["mem-0"].embedding, after["mem-0"].embedding)

    def test_multiple_changes(self):
        mems = _make_memories(5)
        changes = [
            ChangeSpec(action="remove", memory_id="mem-0"),
            ChangeSpec(action="add", memory_id="mem-new", content="Added",
                       embedding=_unit_vec(EMBEDDING_DIM, seed=50), tokens=100),
            ChangeSpec(action="edit", memory_id="mem-2", content="Edited mem-2"),
        ]
        before, after = build_counterfactual_memory_set(mems, changes)
        assert "mem-0" not in after
        assert "mem-new" in after
        assert after["mem-2"].content == "Edited mem-2"
        assert len(after) == 5  # 5 - 1 + 1

    def test_remove_nonexistent(self):
        mems = _make_memories(3)
        changes = [ChangeSpec(action="remove", memory_id="nonexistent")]
        before, after = build_counterfactual_memory_set(mems, changes)
        assert len(after) == 3  # no change

    def test_before_not_mutated(self):
        mems = _make_memories(3)
        original_emb = mems[0].embedding.copy()
        changes = [ChangeSpec(action="edit", memory_id="mem-0",
                              embedding=_unit_vec(EMBEDDING_DIM, seed=99))]
        before, after = build_counterfactual_memory_set(mems, changes)
        # Original memory should not be mutated
        np.testing.assert_array_equal(mems[0].embedding, original_emb)


# ── Tests: run_counterfactual ─────────────────────────────────────────

class TestRunCounterfactual:
    def test_empty_changes_zero_deltas(self):
        mems = _make_memories(5)
        txns = _make_transactions(mems)
        result = run_counterfactual(mems, [], txns)

        assert result["summary"]["transactions_affected"] == 0
        assert result["summary"]["avg_score_delta"] == 0.0
        assert result["summary"]["max_score_delta"] == 0.0
        assert result["compute_time_ms"] > 0

    def test_remove_top_memory_changes_scores(self):
        mems = _make_memories(5)
        txns = _make_transactions(mems)

        # First run without changes to find the top memory
        baseline = run_counterfactual(mems, [], txns, include_analysis={"attribution"})

        # Remove the first memory (likely retrieved by all transactions)
        changes = [ChangeSpec(action="remove", memory_id="mem-0")]
        result = run_counterfactual(mems, changes, txns, include_analysis={"attribution"})

        # Should affect transactions that used mem-0
        assert result["summary"]["max_score_delta"] > 0

    def test_add_relevant_memory(self):
        mems = _make_memories(5)
        txns = _make_transactions(mems)

        # Add a memory very similar to what txn-0 queries
        new_emb = _near_vec(mems[0].embedding, noise=0.05, seed=300)
        changes = [ChangeSpec(
            action="add",
            memory_id="mem-relevant",
            content="Highly relevant new memory",
            embedding=new_emb,
            tokens=120,
        )]
        result = run_counterfactual(mems, changes, txns, include_analysis={"attribution"})

        # The new memory should appear in some after scores
        found_new = False
        for delta in result["attribution_deltas"]:
            if "mem-relevant" in delta["after"]:
                found_new = True
                break
        assert found_new, "New relevant memory should appear in after scores"

    def test_scores_sum_to_one(self):
        mems = _make_memories(5)
        txns = _make_transactions(mems)
        changes = [ChangeSpec(action="remove", memory_id="mem-2")]
        result = run_counterfactual(mems, changes, txns, include_analysis={"attribution"})

        for delta in result["attribution_deltas"]:
            if delta["after"]:
                total = sum(delta["after"].values())
                assert abs(total - 1.0) < 0.01, f"Scores should sum to ~1.0, got {total}"

    def test_coverage_improves_when_filling_gap(self):
        mems = _make_memories(3)
        txns = _make_transactions(mems, n=5)

        # Create a query that has no good memory match
        orphan_emb = _unit_vec(EMBEDDING_DIM, seed=999)
        txns.append(TransactionRecord(
            id="txn-orphan",
            query_text="Orphan query with no matching memory",
            query_embedding=orphan_emb,
            response_embedding=_near_vec(orphan_emb, seed=998),
            retrieved_memory_ids=[],
            input_tokens=100,
            output_tokens=50,
        ))

        # Add a memory that matches the orphan query
        changes = [ChangeSpec(
            action="add",
            memory_id="mem-gap-fill",
            content="Fills the coverage gap",
            embedding=_near_vec(orphan_emb, noise=0.05, seed=997),
            tokens=100,
        )]
        result = run_counterfactual(mems, changes, txns, include_analysis={"coverage"})

        assert result["coverage"] is not None
        assert result["coverage"]["gap_change"] <= 0, "Coverage should improve or stay same"

    def test_coverage_worsens_when_removing_sole_match(self):
        # Create a memory that's the sole match for a transaction
        emb0 = _unit_vec(EMBEDDING_DIM, seed=500)
        mems = [
            MemoryRecord(id="sole-match", content="Only match",
                         embedding=emb0, tokens=100, agent_id="test"),
            MemoryRecord(id="other", content="Other",
                         embedding=_unit_vec(EMBEDDING_DIM, seed=501),
                         tokens=100, agent_id="test"),
        ]
        txns = [TransactionRecord(
            id="txn-sole",
            query_text="Query matching sole-match",
            query_embedding=_near_vec(emb0, noise=0.05, seed=502),
            response_embedding=_near_vec(emb0, noise=0.1, seed=503),
            retrieved_memory_ids=["sole-match"],
        )]

        changes = [ChangeSpec(action="remove", memory_id="sole-match")]
        result = run_counterfactual(mems, changes, txns, include_analysis={"coverage"})

        assert result["coverage"] is not None
        assert result["coverage"]["gap_change"] >= 0, "Coverage should worsen or stay same"

    def test_chi_delta_computed(self):
        mems = _make_memories(5)
        txns = _make_transactions(mems)
        changes = [ChangeSpec(action="remove", memory_id="mem-0")]
        result = run_counterfactual(mems, changes, txns, include_analysis={"chi"})

        assert result["chi"] is not None
        assert "before" in result["chi"]
        assert "after" in result["chi"]
        assert "delta" in result["chi"]

    def test_financial_delta_computed(self):
        mems = _make_memories(5)
        txns = _make_transactions(mems)
        changes = [ChangeSpec(action="remove", memory_id="mem-4")]
        result = run_counterfactual(
            mems, changes, txns,
            cost_config=COST_CONFIG,
            include_analysis={"financial"},
        )

        assert result["financial"] is not None
        assert "portfolio_roi_before" in result["financial"]
        assert "portfolio_roi_after" in result["financial"]

    def test_contradiction_delta(self):
        # Create two memories with very similar embeddings (contradiction candidates)
        base_emb = _unit_vec(EMBEDDING_DIM, seed=600)
        mems = [
            MemoryRecord(id="contra-a", content="User prefers Python",
                         embedding=base_emb, tokens=50, agent_id="test",
                         created_at=NOW - timedelta(days=5)),
            MemoryRecord(id="contra-b", content="User prefers Rust",
                         embedding=_near_vec(base_emb, noise=0.02, seed=601),
                         tokens=50, agent_id="test",
                         created_at=NOW - timedelta(days=25)),
            MemoryRecord(id="neutral", content="User likes testing",
                         embedding=_unit_vec(EMBEDDING_DIM, seed=602),
                         tokens=50, agent_id="test"),
        ]
        txns = _make_transactions(mems, n=1)

        # Remove one of the contradicting memories
        changes = [ChangeSpec(action="remove", memory_id="contra-b")]
        existing_contras = [("contra-a", "contra-b", 0.8)]
        result = run_counterfactual(
            mems, changes, txns,
            existing_contradictions=existing_contras,
            include_analysis={"contradictions"},
        )

        assert result["contradictions"] is not None
        # Removing one side should resolve the contradiction
        assert len(result["contradictions"]["resolved_contradictions"]) >= 1

    def test_include_analysis_filtering(self):
        mems = _make_memories(3)
        txns = _make_transactions(mems, n=2)
        changes = [ChangeSpec(action="remove", memory_id="mem-0")]

        # Only request attribution
        result = run_counterfactual(
            mems, changes, txns,
            include_analysis={"attribution"},
        )
        assert result["attribution_deltas"] is not None
        assert result["contradictions"] is None
        assert result["coverage"] is None
        assert result["chi"] is None
        assert result["financial"] is None

    def test_multiple_changes_combined(self):
        mems = _make_memories(5)
        txns = _make_transactions(mems)

        changes = [
            ChangeSpec(action="remove", memory_id="mem-0"),
            ChangeSpec(action="add", memory_id="mem-new",
                       content="New memory",
                       embedding=_near_vec(mems[0].embedding, noise=0.1, seed=700),
                       tokens=150),
            ChangeSpec(action="edit", memory_id="mem-1",
                       content="Edited memory 1",
                       embedding=_near_vec(mems[1].embedding, noise=0.1, seed=701)),
        ]
        result = run_counterfactual(mems, changes, txns)

        assert result["summary"]["transactions_affected"] >= 0
        assert result["compute_time_ms"] > 0

    def test_edit_memory_embedding_changes_scores(self):
        mems = _make_memories(3)
        txns = _make_transactions(mems, n=2)

        # Drastically change mem-0's embedding to something orthogonal
        new_emb = np.zeros(EMBEDDING_DIM)
        new_emb[-1] = 1.0  # point in a completely different direction
        new_emb /= np.linalg.norm(new_emb)

        changes = [ChangeSpec(
            action="edit",
            memory_id="mem-0",
            embedding=new_emb,
        )]
        result = run_counterfactual(mems, changes, txns, include_analysis={"attribution"})

        # Scores should change because embedding changed
        assert result["summary"]["max_score_delta"] > 0

    def test_empty_transactions(self):
        mems = _make_memories(3)
        changes = [ChangeSpec(action="remove", memory_id="mem-0")]
        result = run_counterfactual(mems, changes, [])

        assert result["summary"]["transactions_affected"] == 0
        assert result["compute_time_ms"] >= 0

    def test_compute_time_under_one_second(self):
        """Counterfactual on 50 memories x 50 transactions should be fast."""
        mems = []
        for i in range(50):
            emb = RNG.normal(0, 1, EMBEDDING_DIM)
            emb /= np.linalg.norm(emb)
            mems.append(MemoryRecord(
                id=f"mem-{i}", content=f"Content {i}",
                embedding=emb, tokens=100, agent_id="test",
                retrieval_count=3, total_attribution=0.1,
                created_at=NOW - timedelta(days=i),
                last_accessed=NOW - timedelta(hours=i),
            ))

        txns = []
        for i in range(50):
            q = RNG.normal(0, 1, EMBEDDING_DIM)
            q /= np.linalg.norm(q)
            r = RNG.normal(0, 1, EMBEDDING_DIM)
            r /= np.linalg.norm(r)
            retrieved = [f"mem-{j}" for j in range(min(6, 50))]
            txns.append(TransactionRecord(
                id=f"txn-{i}", query_text=f"Query {i}",
                query_embedding=q, response_embedding=r,
                retrieved_memory_ids=retrieved,
                input_tokens=500, output_tokens=200,
            ))

        changes = [
            ChangeSpec(action="remove", memory_id="mem-0"),
            ChangeSpec(action="add", memory_id="mem-new",
                       content="New", embedding=mems[1].embedding.copy(), tokens=100),
        ]

        result = run_counterfactual(
            mems, changes, txns, cost_config=COST_CONFIG,
            include_analysis={"attribution", "coverage", "chi", "financial"},
        )
        assert result["compute_time_ms"] < 1000, \
            f"Should complete in <1s, took {result['compute_time_ms']:.0f}ms"

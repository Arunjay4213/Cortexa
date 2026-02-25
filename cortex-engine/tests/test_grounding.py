"""Unit tests for grounding score and contamination detection.

Pure computation tests — no DB, no sentence-transformers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from cortex.attribution.grounding import (
    MemoryForGrounding,
    TransactionForGrounding,
    GroundingWeights,
    GroundingResult,
    compute_grounding_scores,
    _score_provenance,
    _score_corroboration,
    _score_empirical,
    _score_counterfactual,
)
from cortex.attribution.contamination import (
    scan_contamination,
    gate_memory,
    simulate_quarantine,
    ContaminationFlag,
    ScanResult,
    GateResult,
)

EMBEDDING_DIM = 16
NOW = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)


def _unit_vec(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.normal(0, 1, EMBEDDING_DIM)
    return v / np.linalg.norm(v)


def _near_vec(base: np.ndarray, noise: float = 0.1, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = base + rng.normal(0, noise, base.shape)
    return v / np.linalg.norm(v)


def _make_grounding_memories() -> list[MemoryForGrounding]:
    """Create a diverse set of memories with different grounding profiles."""
    return [
        # Well-grounded: user input, high retrieval, high attribution
        MemoryForGrounding(
            id="mem-trusted",
            content="User always uses type hints in Python code",
            embedding=_unit_vec(0),
            tokens=100,
            retrieval_count=10,
            total_attribution=2.5,
            mean_attribution=0.25,
            source_type="user_input",
            created_at=NOW - timedelta(days=5),
        ),
        # Moderate: agent generated, some retrieval
        MemoryForGrounding(
            id="mem-moderate",
            content="Project uses FastAPI for the REST API layer",
            embedding=_unit_vec(1),
            tokens=80,
            retrieval_count=4,
            total_attribution=0.8,
            mean_attribution=0.2,
            source_type="agent_generated",
            created_at=NOW - timedelta(days=10),
        ),
        # Suspect: unknown origin, never retrieved
        MemoryForGrounding(
            id="mem-suspect",
            content="Database uses MongoDB for all storage needs",
            embedding=_unit_vec(2),
            tokens=60,
            retrieval_count=0,
            total_attribution=0.0,
            mean_attribution=0.0,
            source_type="unknown",
            created_at=NOW - timedelta(days=15),
        ),
        # Contradicted: has a contradiction with mem-trusted
        MemoryForGrounding(
            id="mem-contradicted",
            content="User never uses type annotations and avoids them",
            embedding=_near_vec(_unit_vec(0), noise=0.05, seed=10),  # similar to mem-trusted
            tokens=90,
            retrieval_count=1,
            total_attribution=0.05,
            mean_attribution=0.05,
            source_type="agent_generated",
            created_at=NOW - timedelta(days=20),
        ),
    ]


def _make_grounding_transactions(memories: list[MemoryForGrounding]) -> list[TransactionForGrounding]:
    """Create transactions that use the test memories."""
    txns = []
    for i in range(5):
        q = _near_vec(memories[i % len(memories)].embedding, noise=0.15, seed=100 + i)
        r = _near_vec(q, noise=0.2, seed=200 + i)
        # First transaction retrieves trusted memory, etc.
        retrieved = [memories[i % len(memories)].id]
        if i < len(memories) - 1:
            retrieved.append(memories[(i + 1) % len(memories)].id)
        txns.append(TransactionForGrounding(
            id=f"txn-{i}",
            query_text=f"Test query {i}",
            query_embedding=q,
            response_embedding=r,
            retrieved_memory_ids=retrieved,
        ))
    return txns


# ── Grounding Score Tests ─────────────────────────────────────────────

class TestGroundingScores:
    def test_user_input_scores_higher_than_unknown(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        results = compute_grounding_scores(mems, txns)

        trusted = next(r for r in results if r.memory_id == "mem-trusted")
        suspect = next(r for r in results if r.memory_id == "mem-suspect")

        assert trusted.grounding_score > suspect.grounding_score

    def test_high_retrieval_boosts_empirical(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        results = compute_grounding_scores(mems, txns)

        trusted = next(r for r in results if r.memory_id == "mem-trusted")
        suspect = next(r for r in results if r.memory_id == "mem-suspect")

        assert trusted.empirical_score > suspect.empirical_score

    def test_never_retrieved_low_empirical(self):
        mem = MemoryForGrounding(
            id="never", content="Test", embedding=_unit_vec(99),
            tokens=50, retrieval_count=0, mean_attribution=0.0,
        )
        score = _score_empirical(mem)
        assert score <= 0.3

    def test_high_retrieval_high_attribution(self):
        mem = MemoryForGrounding(
            id="hero", content="Test", embedding=_unit_vec(88),
            tokens=50, retrieval_count=15, mean_attribution=0.4,
        )
        score = _score_empirical(mem)
        assert score >= 0.7

    def test_provenance_user_input_high(self):
        mem = MemoryForGrounding(
            id="user", content="Test", embedding=_unit_vec(77),
            tokens=50, source_type="user_input",
        )
        prov = _score_provenance(mem, None)
        assert prov.confidence >= 0.9

    def test_provenance_unknown_low(self):
        mem = MemoryForGrounding(
            id="unknown", content="Test", embedding=_unit_vec(66),
            tokens=50, source_type="unknown",
        )
        prov = _score_provenance(mem, None)
        assert prov.confidence <= 0.3

    def test_corroboration_with_contradiction(self):
        mems = _make_grounding_memories()
        contradictions = {("mem-contradicted", "mem-trusted")}
        score = _score_corroboration(
            mems[3], mems, contradictions,
        )
        # Should be low because it's contradicted
        assert score < 0.5

    def test_results_sorted_ascending(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        results = compute_grounding_scores(mems, txns)

        scores = [r.grounding_score for r in results]
        assert scores == sorted(scores)

    def test_risk_levels_assigned(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        results = compute_grounding_scores(mems, txns)

        risk_levels = {r.risk_level for r in results}
        # Should have diverse risk levels with our test data
        assert len(risk_levels) >= 2

    def test_scores_in_valid_range(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        results = compute_grounding_scores(mems, txns)

        for r in results:
            assert 0.0 <= r.grounding_score <= 1.0
            assert 0.0 <= r.provenance_score <= 1.0
            assert 0.0 <= r.empirical_score <= 1.0


# ── Contamination Scan Tests ─────────────────────────────────────────

class TestContaminationScan:
    def test_scan_returns_all_memories(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        result = scan_contamination(mems, txns)

        assert result.total_memories == len(mems)
        assert len(result.flags) == len(mems)
        assert result.trusted + result.uncertain + result.suspect + result.contaminated == len(mems)

    def test_contamination_rate_valid(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        result = scan_contamination(mems, txns)

        assert 0.0 <= result.system_contamination_rate <= 1.0

    def test_flags_have_reasons(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        result = scan_contamination(mems, txns)

        for flag in result.flags:
            assert len(flag.reasons) > 0
            assert flag.recommended_action in ("keep", "review", "quarantine", "remove")

    def test_compute_time_reasonable(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        result = scan_contamination(mems, txns)

        assert result.compute_time_ms < 5000  # should be well under 5s


# ── Gate Tests ────────────────────────────────────────────────────────

class TestGateMemory:
    def test_redundant_blocked(self):
        existing = _make_grounding_memories()
        # Create a near-duplicate of the first memory
        candidate = MemoryForGrounding(
            id="candidate",
            content="User always uses type hints in Python code",
            embedding=_near_vec(existing[0].embedding, noise=0.01, seed=500),
            tokens=100,
            source_type="agent_generated",
        )
        txns = _make_grounding_transactions(existing)
        result = gate_memory(candidate, existing, txns)

        assert not result.should_store
        assert len(result.redundant_with) > 0

    def test_novel_memory_passes(self):
        existing = _make_grounding_memories()
        # Create something completely different
        candidate = MemoryForGrounding(
            id="candidate-novel",
            content="Kubernetes cluster runs on GKE with autopilot mode",
            embedding=_unit_vec(999),  # very different from all existing
            tokens=80,
            source_type="user_input",
        )
        txns = _make_grounding_transactions(existing)
        result = gate_memory(candidate, existing, txns)

        assert result.should_store
        assert len(result.redundant_with) == 0

    def test_gate_returns_grounding_score(self):
        existing = _make_grounding_memories()
        candidate = MemoryForGrounding(
            id="candidate-scored",
            content="New information about the project",
            embedding=_unit_vec(888),
            tokens=60,
            source_type="user_input",
        )
        txns = _make_grounding_transactions(existing)
        result = gate_memory(candidate, existing, txns)

        assert 0.0 <= result.grounding_score <= 1.0
        assert result.risk_level in ("trusted", "uncertain", "suspect", "contaminated")

    def test_hallucination_with_unknown_provenance_blocked(self):
        """A memory that contradicts existing knowledge with no provenance
        should be blocked — the original bug that let hallucinations through."""
        existing = _make_grounding_memories()
        # Contradicts mem-trusted ("User always uses type hints in Python code")
        # by claiming the opposite, with similar embedding but unknown source
        hallucinated = MemoryForGrounding(
            id="candidate-hallucination",
            content="User never uses type hints and avoids Python typing",
            embedding=_near_vec(_unit_vec(0), noise=0.05, seed=777),
            tokens=80,
            source_type="unknown",
        )
        txns = _make_grounding_transactions(existing)
        result = gate_memory(hallucinated, existing, txns)

        # Must be blocked: contradicts existing + unknown provenance
        assert not result.should_store
        assert result.grounding_score < 0.65

    def test_contradicting_memory_with_user_provenance_passes(self):
        """A contradicting memory FROM the user should still pass —
        the user might be updating their preference."""
        existing = _make_grounding_memories()
        # Same contradiction, but from a verified user source
        user_update = MemoryForGrounding(
            id="candidate-user-update",
            content="User now prefers dynamic typing over type hints",
            embedding=_near_vec(_unit_vec(0), noise=0.08, seed=778),
            tokens=80,
            source_type="user_input",
            retrieval_count=0,
        )
        txns = _make_grounding_transactions(existing)
        result = gate_memory(user_update, existing, txns)

        # User-sourced updates get high provenance, so grounding should be
        # strong enough to pass even with contradiction
        assert result.grounding_score >= 0.5


# ── Quarantine Simulation Tests ──────────────────────────────────────

class TestQuarantineSimulation:
    def test_quarantine_returns_metrics(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        result = simulate_quarantine(
            suspect_ids=["mem-suspect"],
            all_memories=mems,
            transactions=txns,
        )

        assert result["quarantined_count"] == 1
        assert "chi_improvement" in result
        assert "health_improved" in result
        assert "recommendation" in result

    def test_quarantine_empty_suspects(self):
        mems = _make_grounding_memories()
        txns = _make_grounding_transactions(mems)
        result = simulate_quarantine([], mems, txns)

        assert result["quarantined_count"] == 0

    def test_quarantine_no_transactions(self):
        mems = _make_grounding_memories()
        result = simulate_quarantine(["mem-suspect"], mems, [])

        assert result["quarantined_count"] == 1

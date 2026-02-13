"""Tests for EAS computation — verify formula against hand-computed examples."""

import numpy as np
import pytest

from cortex.attribution.eas import compute_eas


def _norm(v):
    """L2-normalize a vector."""
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


class TestComputeEAS:
    def test_single_memory_gets_score_1(self):
        """One memory → score should be 1.0."""
        q = _norm(np.array([1.0, 0.0, 0.0]))
        r = _norm(np.array([1.0, 0.0, 0.0]))
        m = _norm(np.array([1.0, 0.0, 0.0]))

        result = compute_eas([m], q, r)
        assert result["scores"].shape == (1,)
        assert pytest.approx(result["scores"][0], abs=1e-9) == 1.0

    def test_scores_sum_to_one(self):
        """Multiple memories → scores should sum to 1.0."""
        rng = np.random.default_rng(42)
        q = _norm(rng.standard_normal(384))
        r = _norm(rng.standard_normal(384))
        M = np.array([_norm(rng.standard_normal(384)) for _ in range(10)])

        result = compute_eas(M, q, r)
        assert result["scores"].shape == (10,)
        assert pytest.approx(result["scores"].sum(), abs=1e-9) == 1.0

    def test_all_scores_non_negative(self):
        """All EAS scores must be >= 0 (negatives clamped)."""
        rng = np.random.default_rng(123)
        q = _norm(rng.standard_normal(384))
        r = _norm(rng.standard_normal(384))
        M = np.array([_norm(rng.standard_normal(384)) for _ in range(20)])

        result = compute_eas(M, q, r)
        assert (result["scores"] >= 0).all()
        assert (result["raw_scores"] >= 0).all()

    def test_hand_computed_two_memories(self):
        """Verify against manual calculation with simple 3D vectors."""
        q = _norm(np.array([1.0, 0.5, 0.0]))
        r = _norm(np.array([0.8, 0.6, 0.0]))
        m1 = _norm(np.array([1.0, 0.0, 0.0]))
        m2 = _norm(np.array([0.0, 1.0, 0.0]))

        # Hand-compute:
        # cosim(m1, r) = dot(m1_n, r_n), cosim(m1, q) = dot(m1_n, q_n)
        q_n = q / np.linalg.norm(q)
        r_n = r / np.linalg.norm(r)
        m1_n = m1 / np.linalg.norm(m1)
        m2_n = m2 / np.linalg.norm(m2)

        s1_mr = max(np.dot(m1_n, r_n), 0)
        s1_mq = max(np.dot(m1_n, q_n), 0)
        raw1 = s1_mr * s1_mq

        s2_mr = max(np.dot(m2_n, r_n), 0)
        s2_mq = max(np.dot(m2_n, q_n), 0)
        raw2 = s2_mr * s2_mq

        total = raw1 + raw2
        expected1 = raw1 / total
        expected2 = raw2 / total

        result = compute_eas([m1, m2], q, r)
        assert pytest.approx(result["scores"][0], abs=1e-6) == expected1
        assert pytest.approx(result["scores"][1], abs=1e-6) == expected2

    def test_empty_memories(self):
        """No memories → empty result."""
        q = np.array([1.0, 0.0, 0.0])
        r = np.array([0.0, 1.0, 0.0])

        result = compute_eas(np.empty((0, 3)), q, r)
        assert result["scores"].shape == (0,)

    def test_orthogonal_memory_gets_zero(self):
        """A memory orthogonal to both query and response gets zero score."""
        q = _norm(np.array([1.0, 0.0, 0.0]))
        r = _norm(np.array([1.0, 0.0, 0.0]))
        m_relevant = _norm(np.array([1.0, 0.0, 0.0]))
        m_orthogonal = _norm(np.array([0.0, 0.0, 1.0]))  # orthogonal to q and r

        result = compute_eas([m_relevant, m_orthogonal], q, r)
        # Orthogonal memory should have cosim=0 with both q and r
        assert result["scores"][0] == pytest.approx(1.0, abs=1e-6)
        assert result["scores"][1] == pytest.approx(0.0, abs=1e-6)

    def test_compute_time_is_reported(self):
        rng = np.random.default_rng(99)
        result = compute_eas(
            rng.standard_normal((10, 384)),
            rng.standard_normal(384),
            rng.standard_normal(384),
        )
        assert result["compute_ms"] >= 0

"""Tests for NLI-based contradiction detection."""

import numpy as np
import pytest

from cortex.attribution.contradiction import (
    _classify_contradiction_type,
    _find_candidate_pairs,
    _softmax,
)
from datetime import datetime, timedelta


class TestCandidateGeneration:
    def test_similar_vectors(self):
        """High similarity vectors should be candidates."""
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [0.99, 0.1, 0.0],  # very similar to first
            [0.0, 0.0, 1.0],  # orthogonal
        ])
        pairs = _find_candidate_pairs(embeddings, threshold=0.9)
        # First two should be candidates
        assert (0, 1) in pairs
        # Third should not pair with either
        assert (0, 2) not in pairs
        assert (1, 2) not in pairs

    def test_dissimilar_vectors(self):
        """Orthogonal vectors should not be candidates."""
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        pairs = _find_candidate_pairs(embeddings, threshold=0.7)
        assert len(pairs) == 0

    def test_all_identical(self):
        """Identical vectors should all be candidates."""
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
        ])
        pairs = _find_candidate_pairs(embeddings, threshold=0.9)
        assert len(pairs) == 3  # (0,1), (0,2), (1,2)

    def test_single_vector(self):
        embeddings = np.array([[1.0, 0.0, 0.0]])
        pairs = _find_candidate_pairs(embeddings)
        assert len(pairs) == 0

    def test_empty_embeddings(self):
        embeddings = np.array([]).reshape(0, 3)
        pairs = _find_candidate_pairs(embeddings)
        assert len(pairs) == 0


class TestTypeClassification:
    def test_temporal_update(self):
        """Timestamps >24h apart → temporal_update."""
        t1 = datetime(2024, 1, 1)
        t2 = datetime(2024, 1, 3)  # 2 days later
        assert _classify_contradiction_type(t1, t2, "agent1", "agent2") == "temporal_update"

    def test_concurrent_conflict(self):
        """Same agent, <1h apart → concurrent_conflict."""
        t1 = datetime(2024, 1, 1, 12, 0)
        t2 = datetime(2024, 1, 1, 12, 30)
        assert _classify_contradiction_type(t1, t2, "agent1", "agent1") == "concurrent_conflict"

    def test_logical(self):
        """Different agents, <24h apart → logical."""
        t1 = datetime(2024, 1, 1, 10, 0)
        t2 = datetime(2024, 1, 1, 20, 0)
        assert _classify_contradiction_type(t1, t2, "agent1", "agent2") == "logical"

    def test_ambiguous_null_timestamps(self):
        assert _classify_contradiction_type(None, None, "a", "b") == "ambiguous"
        assert _classify_contradiction_type(datetime.now(), None, "a", "b") == "ambiguous"


class TestSoftmax:
    def test_sums_to_one(self):
        result = _softmax(np.array([1.0, 2.0, 3.0]))
        assert abs(result.sum() - 1.0) < 1e-6

    def test_numerically_stable(self):
        """Should not overflow with large values."""
        result = _softmax(np.array([1000.0, 1001.0, 1002.0]))
        assert abs(result.sum() - 1.0) < 1e-6
        assert all(np.isfinite(result))

    def test_correct_order(self):
        result = _softmax(np.array([1.0, 2.0, 3.0]))
        assert result[2] > result[1] > result[0]


from datetime import UTC

from cortex.attribution.contradiction import classify_contradiction_with_probability


class TestTemporalSemantics:
    def test_temporal_update_probability(self):
        """Temporal updates (>24h gap) should have probability > 0.5."""
        now = datetime.now(UTC)
        result = classify_contradiction_with_probability(
            now - timedelta(days=5), now, "agent-1", "agent-1", nli_confidence=0.85
        )
        assert result["type"] == "temporal_update"
        assert result["probability"] > 0.5
        assert result["is_superseded"] is True
        assert result["resolution_hint"] == "keep_newer"

    def test_concurrent_conflict_probability(self):
        """Concurrent conflicts (same agent, <1h) should have reasonable probability."""
        now = datetime.now(UTC)
        result = classify_contradiction_with_probability(
            now - timedelta(minutes=15), now, "agent-1", "agent-1", nli_confidence=0.9
        )
        assert result["type"] == "concurrent_conflict"
        assert result["probability"] > 0.3
        assert result["resolution_hint"] == "merge_or_resolve"

    def test_logical_contradiction_probability(self):
        """Logical contradictions should scale with NLI confidence."""
        now = datetime.now(UTC)
        r_high = classify_contradiction_with_probability(
            now - timedelta(hours=3), now, "a1", "a2", nli_confidence=0.95
        )
        r_low = classify_contradiction_with_probability(
            now - timedelta(hours=3), now, "a1", "a2", nli_confidence=0.3
        )
        assert r_high["type"] == "logical"
        assert r_high["probability"] > r_low["probability"]

    def test_ambiguous_no_timestamps(self):
        """No timestamps should return ambiguous with 0.5 probability."""
        result = classify_contradiction_with_probability(None, None, "a", "b")
        assert result["type"] == "ambiguous"
        assert result["probability"] == 0.5
        assert result["temporal_marker"] == "unknown"

    def test_temporal_markers(self):
        """Temporal markers should reflect time distance."""
        now = datetime.now(UTC)
        r1 = classify_contradiction_with_probability(
            now - timedelta(minutes=30), now, "a", "b", 0.5
        )
        assert r1["temporal_marker"] == "simultaneous"

        r2 = classify_contradiction_with_probability(
            now - timedelta(hours=5), now, "a", "b", 0.5
        )
        assert r2["temporal_marker"] == "same_day"

        r3 = classify_contradiction_with_probability(
            now - timedelta(days=3), now, "a", "b", 0.5
        )
        assert r3["temporal_marker"] == "same_week"

    def test_probability_in_range(self):
        """Probability should always be in [0, 1]."""
        now = datetime.now(UTC)
        for days in [0.01, 0.5, 1, 7, 30, 365]:
            for conf in [0.0, 0.3, 0.5, 0.8, 1.0]:
                result = classify_contradiction_with_probability(
                    now - timedelta(days=days), now, "a", "b", conf
                )
                assert 0.0 <= result["probability"] <= 1.0, f"Out of range for days={days}, conf={conf}"

    def test_time_delta_hours_present(self):
        """Result should contain time_delta_hours."""
        now = datetime.now(UTC)
        result = classify_contradiction_with_probability(
            now - timedelta(hours=5), now, "a", "b", 0.5
        )
        assert "time_delta_hours" in result
        assert abs(result["time_delta_hours"] - 5.0) < 0.1

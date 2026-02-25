"""Tests for cortex.metrics.health — Staleness & Composite Health Index."""

import math
import pytest
from datetime import datetime, UTC, timedelta
from cortex.metrics.health import staleness_score, batch_staleness, compute_chi, CHIWeights, CHIResult


# --- Staleness Tests ---

def test_staleness_just_accessed():
    """Staleness of a just-accessed memory should be ~0."""
    now = datetime.now(UTC)
    assert staleness_score(now, now) < 0.001


def test_staleness_at_half_life():
    """At exactly half_life days, staleness should be 0.5."""
    now = datetime.now(UTC)
    half_life = 7.0
    s = staleness_score(now - timedelta(days=half_life), now, half_life)
    assert abs(s - 0.5) < 0.001


def test_staleness_very_old():
    """Very old memory should approach 1.0."""
    now = datetime.now(UTC)
    s = staleness_score(now - timedelta(days=365), now)
    assert s > 0.99


def test_staleness_none_is_fully_stale():
    """None last_accessed means fully stale."""
    assert staleness_score(None) == 1.0


def test_staleness_future_is_zero():
    """Future access time should give 0."""
    now = datetime.now(UTC)
    s = staleness_score(now + timedelta(days=1), now)
    assert s == 0.0


def test_staleness_custom_half_life():
    """Custom half-life should work: at half_life=30, 30 days = 0.5."""
    now = datetime.now(UTC)
    s = staleness_score(now - timedelta(days=30), now, half_life_days=30.0)
    assert abs(s - 0.5) < 0.001


def test_staleness_monotonic():
    """Staleness should be monotonically increasing with age."""
    now = datetime.now(UTC)
    values = [staleness_score(now - timedelta(days=d), now) for d in range(0, 60, 5)]
    for i in range(len(values) - 1):
        assert values[i] <= values[i + 1]


def test_staleness_in_range():
    """Staleness should always be in [0, 1]."""
    now = datetime.now(UTC)
    for days in [0, 0.01, 1, 7, 30, 365, 3650]:
        s = staleness_score(now - timedelta(days=days), now)
        assert 0.0 <= s <= 1.0


def test_batch_staleness():
    """Batch staleness should match individual calls."""
    now = datetime.now(UTC)
    times = [now, now - timedelta(days=7), now - timedelta(days=30), None]
    batch = batch_staleness(times, now)
    individual = [staleness_score(t, now) for t in times]
    assert len(batch) == len(individual)
    for b, i in zip(batch, individual):
        assert abs(b - i) < 1e-10


def test_batch_staleness_empty():
    """Empty batch should return empty list."""
    assert batch_staleness([], datetime.now(UTC)) == []


# --- CHI Tests ---

def test_chi_weights_normalize():
    """CHIWeights should auto-normalize to sum=1."""
    w = CHIWeights(accuracy=2, freshness=2, coverage=2, consistency=2, efficiency=2)
    total = w.accuracy + w.freshness + w.coverage + w.consistency + w.efficiency
    assert abs(total - 1.0) < 1e-6


def test_chi_default_weights():
    """Default weights should sum to 1."""
    w = CHIWeights()
    total = w.accuracy + w.freshness + w.coverage + w.consistency + w.efficiency
    assert abs(total - 1.0) < 1e-6


def test_chi_perfect_score():
    """All 1.0 inputs should give score = 1.0."""
    result = compute_chi(1.0, 1.0, 1.0, 1.0, 1.0)
    assert result.score == 1.0
    assert result.grade == "A"


def test_chi_zero_score():
    """All 0.0 inputs should give score = 0.0."""
    result = compute_chi(0.0, 0.0, 0.0, 0.0, 0.0)
    assert result.score == 0.0
    assert result.grade == "F"


def test_chi_grades():
    """Test grade boundaries."""
    assert compute_chi(0.95, 0.95, 0.95, 0.95, 0.95).grade == "A"  # 0.95
    assert compute_chi(0.85, 0.85, 0.85, 0.85, 0.85).grade == "B"  # 0.85
    assert compute_chi(0.75, 0.75, 0.75, 0.75, 0.75).grade == "C"  # 0.75
    assert compute_chi(0.65, 0.65, 0.65, 0.65, 0.65).grade == "D"  # 0.65
    assert compute_chi(0.45, 0.45, 0.45, 0.45, 0.45).grade == "F"  # 0.45


def test_chi_clamping():
    """Values outside [0,1] should be clamped."""
    result = compute_chi(1.5, -0.5, 0.5, 0.5, 0.5)
    assert 0.0 <= result.score <= 1.0
    assert result.accuracy_component == 1.0
    assert result.freshness_component == 0.0


def test_chi_weighted():
    """Custom weights should shift the score toward weighted component."""
    # Weight accuracy at 1.0, others at 0
    w = CHIWeights(accuracy=1.0, freshness=0, coverage=0, consistency=0, efficiency=0)
    result = compute_chi(0.9, 0.1, 0.1, 0.1, 0.1, w)
    assert abs(result.score - 0.9) < 0.01


def test_chi_result_contains_components():
    """CHIResult should expose all 5 component values."""
    result = compute_chi(0.8, 0.7, 0.6, 0.9, 0.85)
    assert result.accuracy_component == 0.8
    assert result.freshness_component == 0.7
    assert result.coverage_component == 0.6
    assert result.consistency_component == 0.9
    assert result.efficiency_component == 0.85

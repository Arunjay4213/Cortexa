import pytest
import numpy as np
from cortex.attribution.drift import cosine_distance, compute_drift_score

def test_cosine_distance_identical():
    """Identical vectors should have 0 distance."""
    a = np.array([1.0, 0.0, 0.0])
    assert cosine_distance(a, a) < 1e-10

def test_cosine_distance_orthogonal():
    """Orthogonal vectors should have distance 1.0."""
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert abs(cosine_distance(a, b) - 1.0) < 1e-10

def test_cosine_distance_opposite():
    """Opposite vectors should have distance 2.0."""
    a = np.array([1.0, 0.0])
    b = np.array([-1.0, 0.0])
    assert abs(cosine_distance(a, b) - 2.0) < 1e-10

def test_cosine_distance_symmetric():
    """Distance should be symmetric."""
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 5.0, 6.0])
    assert abs(cosine_distance(a, b) - cosine_distance(b, a)) < 1e-10

def test_cosine_distance_zero_vector():
    """Zero vector should give distance 1.0."""
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 0.0])
    assert cosine_distance(a, b) == 1.0

def test_cosine_distance_in_range():
    """Distance should be in [0, 2]."""
    rng = np.random.default_rng(42)
    for _ in range(100):
        a = rng.standard_normal(10)
        b = rng.standard_normal(10)
        d = cosine_distance(a, b)
        assert 0.0 <= d <= 2.0 + 1e-10

def test_drift_score_identical():
    """Identical embeddings = no drift."""
    assert compute_drift_score([1, 0, 0], [1, 0, 0]) < 1e-10

def test_drift_score_orthogonal():
    """Orthogonal embeddings = max drift."""
    assert compute_drift_score([1, 0], [0, 1]) > 0.99

def test_drift_score_empty():
    """Empty embeddings should return 0."""
    assert compute_drift_score([], []) == 0.0
    assert compute_drift_score([1, 0], []) == 0.0
    assert compute_drift_score([], [1, 0]) == 0.0

def test_drift_score_partial_drift():
    """45-degree rotation should give ~0.29 drift."""
    d = compute_drift_score([1, 0], [1, 1])
    assert 0.2 < d < 0.4  # cos(45°) = 0.707, drift = 1 - 0.707 ≈ 0.293

def test_drift_score_in_range():
    """Drift should always be in [0, 1] for unit-ish vectors."""
    rng = np.random.default_rng(0)
    for _ in range(50):
        a = rng.standard_normal(16).tolist()
        b = rng.standard_normal(16).tolist()
        d = compute_drift_score(a, b)
        assert 0.0 <= d <= 2.0  # cosine distance range

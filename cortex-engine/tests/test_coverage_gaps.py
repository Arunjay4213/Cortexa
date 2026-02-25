import pytest
import numpy as np
from cortex.attribution.coverage import _cosine_similarity_matrix, _simple_kmeans

# --- Similarity Matrix Tests ---

def test_similarity_self():
    """Self-similarity should be 1.0."""
    A = np.array([[1.0, 0.0], [0.0, 1.0]])
    sim = _cosine_similarity_matrix(A, A)
    assert sim.shape == (2, 2)
    assert abs(sim[0, 0] - 1.0) < 1e-6
    assert abs(sim[1, 1] - 1.0) < 1e-6

def test_similarity_orthogonal():
    """Orthogonal vectors should have ~0 similarity."""
    A = np.array([[1.0, 0.0]])
    B = np.array([[0.0, 1.0]])
    sim = _cosine_similarity_matrix(A, B)
    assert abs(sim[0, 0]) < 1e-6

def test_similarity_shape():
    """Output shape should be (n_A, n_B)."""
    A = np.random.randn(5, 10)
    B = np.random.randn(3, 10)
    sim = _cosine_similarity_matrix(A, B)
    assert sim.shape == (5, 3)

def test_similarity_range():
    """Cosine similarity should be in [-1, 1]."""
    rng = np.random.default_rng(42)
    A = rng.standard_normal((20, 8))
    B = rng.standard_normal((15, 8))
    sim = _cosine_similarity_matrix(A, B)
    assert sim.min() >= -1.0 - 1e-6
    assert sim.max() <= 1.0 + 1e-6

def test_similarity_symmetric():
    """sim(A, B) should be transpose of sim(B, A)."""
    rng = np.random.default_rng(0)
    A = rng.standard_normal((4, 6))
    B = rng.standard_normal((3, 6))
    sim_ab = _cosine_similarity_matrix(A, B)
    sim_ba = _cosine_similarity_matrix(B, A)
    np.testing.assert_allclose(sim_ab, sim_ba.T, atol=1e-10)

# --- K-Means Tests ---

def test_kmeans_basic():
    """K-means should produce k clusters."""
    X = np.vstack([
        np.random.randn(20, 2) + [5, 5],
        np.random.randn(20, 2) + [-5, -5],
    ])
    centroids, labels = _simple_kmeans(X, 2, seed=42)
    assert centroids.shape == (2, 2)
    assert len(labels) == 40
    assert set(np.unique(labels)) == {0, 1}

def test_kmeans_single_cluster():
    """k=1 should assign all to cluster 0."""
    rng = np.random.default_rng(10)
    X = rng.standard_normal((10, 3))
    centroids, labels = _simple_kmeans(X, 1, seed=10)
    assert np.all(labels == 0)

def test_kmeans_separable_clusters():
    """Well-separated clusters should be found."""
    rng = np.random.default_rng(42)
    c1 = rng.standard_normal((30, 4)) + 10
    c2 = rng.standard_normal((30, 4)) - 10
    X = np.vstack([c1, c2])
    _, labels = _simple_kmeans(X, 2, seed=42)
    # First 30 should be same cluster, last 30 different
    assert len(set(labels[:30])) == 1
    assert len(set(labels[30:])) == 1
    assert labels[0] != labels[30]

def test_kmeans_labels_valid():
    """All labels should be in [0, k)."""
    rng = np.random.default_rng(77)
    X = rng.standard_normal((50, 5))
    k = 4
    _, labels = _simple_kmeans(X, k, seed=77)
    assert all(0 <= l < k for l in labels)

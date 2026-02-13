"""
EAS — Embedding Attribution Score.

The O(kd) fast-path from Section 3.3 of the CortexOS paper:

    aᵢ_fast = [cosim(φ(mᵢ), φ(r)) · cosim(φ(mᵢ), φ(q))] / Σⱼ[...]

- Numpy-vectorized: batch matrix multiply for cosine similarity
- Negative cosines clamped to 0
- Returns normalized scores summing to 1.0
- k = number of retrieved memories, d = embedding dim (384)
"""

from __future__ import annotations

import time

import numpy as np


def _cosine_similarities(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
    """Cosine similarity between each row of *matrix* and *vector*.

    Assumes both are already L2-normalized (sentence-transformers default).
    Falls back to safe normalization if not.
    """
    # Normalize just in case
    norms_m = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms_m = np.where(norms_m == 0, 1.0, norms_m)
    matrix_n = matrix / norms_m

    norm_v = np.linalg.norm(vector)
    if norm_v == 0:
        return np.zeros(matrix.shape[0])
    vector_n = vector / norm_v

    return matrix_n @ vector_n  # (k,)


def compute_eas(
    memory_embeddings: np.ndarray | list[list[float]],
    query_embedding: np.ndarray | list[float],
    response_embedding: np.ndarray | list[float],
) -> dict:
    """Compute EAS attribution scores.

    Parameters
    ----------
    memory_embeddings : (k, d) array of retrieved-memory embeddings
    query_embedding   : (d,) query embedding
    response_embedding: (d,) response embedding

    Returns
    -------
    dict with keys:
        scores        – normalized aᵢ ∈ [0,1], sums to ~1.0  (k,)
        raw_scores    – unnormalized product terms              (k,)
        compute_ms    – wall-clock time in milliseconds
    """
    t0 = time.perf_counter()

    M = np.asarray(memory_embeddings, dtype=np.float64)
    q = np.asarray(query_embedding, dtype=np.float64)
    r = np.asarray(response_embedding, dtype=np.float64)

    if M.ndim == 1:
        M = M.reshape(1, -1)

    k = M.shape[0]
    if k == 0:
        return {"scores": np.array([]), "raw_scores": np.array([]), "compute_ms": 0.0}

    # cosim(φ(mᵢ), φ(r))  and  cosim(φ(mᵢ), φ(q))
    sim_mr = _cosine_similarities(M, r)  # (k,)
    sim_mq = _cosine_similarities(M, q)  # (k,)

    # Clamp negatives to zero
    sim_mr = np.maximum(sim_mr, 0.0)
    sim_mq = np.maximum(sim_mq, 0.0)

    raw = sim_mr * sim_mq  # element-wise product  (k,)

    total = raw.sum()
    if total > 0:
        scores = raw / total
    else:
        # Uniform fallback when all scores are zero
        scores = np.full(k, 1.0 / k)

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return {
        "scores": scores,
        "raw_scores": raw,
        "compute_ms": elapsed_ms,
    }

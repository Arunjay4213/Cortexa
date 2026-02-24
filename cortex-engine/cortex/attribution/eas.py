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


def compute_contrastive_eas(
    query_embedding: np.ndarray | list[float],
    response_embedding: np.ndarray | list[float],
    memory_embeddings: np.ndarray | list[list[float]],
    memory_texts: list[str],
    response_text: str,
    tau: float = 0.5,
    alpha: float = 0.7,
) -> np.ndarray:
    """Contrastive EAS with lexical anchoring.

    Addresses the query-irrelevance problem by using contrastive response
    similarity and lexical overlap instead of raw cosine products.

    Args:
        query_embedding: Query embedding vector (d,)
        response_embedding: Response embedding vector (d,)
        memory_embeddings: Memory embedding matrix (k, d)
        memory_texts: List of k memory content strings
        response_text: Full response text
        tau: Temperature for softmax (lower = more peaked)
        alpha: Weight for contrastive vs lexical (0-1)

    Returns:
        Attribution scores summing to 1.0 (k,)
    """
    # Convert to numpy arrays
    M = np.asarray(memory_embeddings, dtype=np.float64)
    q = np.asarray(query_embedding, dtype=np.float64)
    r = np.asarray(response_embedding, dtype=np.float64)

    if M.ndim == 1:
        M = M.reshape(1, -1)

    k = M.shape[0]
    if k == 0:
        return np.array([])

    # Normalize all embeddings (L2 normalization)
    def normalize(v):
        norm = np.linalg.norm(v)
        return v / max(norm, 1e-8)

    q = normalize(q)
    r = normalize(r)

    norms = np.linalg.norm(M, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    M = M / norms

    # Step 1 — Contrastive response similarity
    centroid = np.mean(M, axis=0)  # (d,)
    centroid = normalize(centroid)

    # Cosine similarities: (k,) array
    mem_resp_sims = M @ r
    centroid_resp_sim = centroid @ r  # scalar

    # Contrastive: how much closer is this memory vs the average?
    # Negative values mean less similar than average (should get lower scores)
    # DO NOT clip - we want to preserve the relative ordering
    contrast = mem_resp_sims - centroid_resp_sim  # (k,)

    # Step 2 — Lexical anchor (trigram overlap)
    def trigram_overlap(text_a: str, text_b: str) -> float:
        """Compute trigram overlap between two texts."""
        a_lower = text_a.lower()
        b_lower = text_b.lower()
        trigrams_a = set(a_lower[i:i+3] for i in range(len(a_lower)-2))
        trigrams_b = set(b_lower[i:i+3] for i in range(len(b_lower)-2))
        if not trigrams_a:
            return 0.0
        return len(trigrams_a & trigrams_b) / len(trigrams_a)

    lexical = np.array([trigram_overlap(m, response_text) for m in memory_texts])

    # Step 3 — Combined score (NO query gate)
    # Phase 1 showed query has 0.029 correlation - it adds noise, not signal
    # Only use response-based contrast and lexical overlap
    raw = alpha * contrast + (1 - alpha) * lexical

    # Step 5 — Temperature-scaled softmax
    # Handle all-zeros edge case
    if np.max(raw) == 0:
        return np.ones(k) / k  # uniform fallback

    raw_shifted = raw - np.max(raw)  # numerical stability
    exp_scores = np.exp(raw_shifted / tau)
    scores = exp_scores / np.sum(exp_scores)

    return scores


def compute_eas(
    memory_embeddings: np.ndarray | list[list[float]],
    query_embedding: np.ndarray | list[float],
    response_embedding: np.ndarray | list[float],
    method: str = "response_only",
    memory_texts: list[str] | None = None,
    response_text: str | None = None,
    tau: float = 0.7,
    alpha: float = 0.9,
) -> dict:
    """Compute EAS attribution scores.

    Parameters
    ----------
    memory_embeddings : (k, d) array of retrieved-memory embeddings
    query_embedding   : (d,) query embedding
    response_embedding: (d,) response embedding
    method           : "response_only" (default, best), "response_weighted", "contrastive", or "cosine"
                       - response_only: Just response similarity (Phase 1: 0.782 correlation)
                       - response_weighted: 90% response + 10% query
                       - contrastive: Contrastive similarity with lexical anchoring
                       - cosine: Original query × response product (Phase 1: 0.670 correlation)
    memory_texts     : list of memory content strings (required for method="contrastive")
    response_text    : response text (required for method="contrastive")
    tau              : temperature for contrastive softmax (default 0.7)
    alpha            : weight for contrastive vs lexical (default 0.9)

    Returns
    -------
    dict with keys:
        scores        – normalized aᵢ ∈ [0,1], sums to ~1.0  (k,)
        raw_scores    – unnormalized product terms              (k,)
        compute_ms    – wall-clock time in milliseconds
        method        – attribution method used
    """
    t0 = time.perf_counter()

    M = np.asarray(memory_embeddings, dtype=np.float64)
    q = np.asarray(query_embedding, dtype=np.float64)
    r = np.asarray(response_embedding, dtype=np.float64)

    if M.ndim == 1:
        M = M.reshape(1, -1)

    k = M.shape[0]
    if k == 0:
        return {"scores": np.array([]), "raw_scores": np.array([]), "compute_ms": 0.0, "method": method}

    # Select method
    if method == "response_only":
        # Phase 1 proved: response similarity alone gives 0.782 correlation
        # Query term has 0.029 correlation — it's pure noise
        # Just use normalized response similarity
        sim_mr = _cosine_similarities(M, r)  # (k,)
        sim_mr = np.maximum(sim_mr, 0.0)

        print(f"[RESPONSE_ONLY] sim_mr range: [{np.min(sim_mr):.4f}, {np.max(sim_mr):.4f}]")

        total = sim_mr.sum()
        if total > 1e-8:
            scores = sim_mr / total
            low_confidence = False
        else:
            scores = np.ones(k) / k
            low_confidence = True

        print(f"[RESPONSE_ONLY] final scores: {scores}")
        raw = sim_mr

    elif method == "response_weighted":
        # 90% response, 10% query — slight query boost without destroying signal
        sim_mr = _cosine_similarities(M, r)  # (k,)
        sim_mq = _cosine_similarities(M, q)  # (k,)
        sim_mr = np.maximum(sim_mr, 0.0)
        sim_mq = np.maximum(sim_mq, 0.0)

        raw = 0.9 * sim_mr + 0.1 * sim_mq
        total = raw.sum()
        if total > 1e-8:
            scores = raw / total
            low_confidence = False
        else:
            scores = np.ones(k) / k
            low_confidence = True

    elif method == "contrastive":
        if memory_texts is None or response_text is None:
            raise ValueError("method='contrastive' requires memory_texts and response_text parameters")

        scores = compute_contrastive_eas(
            q, r, M, memory_texts, response_text,
            tau=tau, alpha=alpha
        )
        raw = scores  # Contrastive returns normalized scores directly
        low_confidence = False

    else:  # method == "cosine" (original)
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
            low_confidence = False
        else:
            # All similarities are zero — no memory relates to both query and response.
            # Return zeros instead of pretending every memory is equally relevant.
            scores = np.zeros(k)
            low_confidence = True

    elapsed_ms = (time.perf_counter() - t0) * 1000

    return {
        "scores": scores,
        "raw_scores": raw,
        "compute_ms": elapsed_ms,
        "low_confidence": low_confidence,
        "method": method,
        "params": {"tau": tau, "alpha": alpha} if method == "contrastive" else {},
    }

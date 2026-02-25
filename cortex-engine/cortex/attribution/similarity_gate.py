"""
Cosine similarity pre-filter for CAMA.

Before running expensive NLI inference on every (claim, memory) pair,
we gate by cosine similarity. Only memory-claim pairs above the threshold
proceed to DeBERTa entailment.

Threshold is configurable via CORTEX_CAMA_SIMILARITY_THRESHOLD (default 0.3).

This reduces NLI calls from O(claims × memories) to O(claims × candidates),
where candidates << memories for focused responses.
"""

from __future__ import annotations

import numpy as np


def _default_threshold() -> float:
    """Read default threshold from config (lazy import to avoid circular deps)."""
    try:
        from cortex.config import settings
        return settings.cama_similarity_threshold
    except Exception:
        return 0.3


def cosine_similarity_matrix(
    claim_embeddings: np.ndarray,
    memory_embeddings: np.ndarray,
) -> np.ndarray:
    """Compute cosine similarity between all (claim, memory) pairs.

    Args:
        claim_embeddings:  (num_claims, dim) array
        memory_embeddings: (num_memories, dim) array

    Returns:
        (num_claims, num_memories) similarity matrix
    """
    # L2 normalize rows
    claim_norms = np.linalg.norm(claim_embeddings, axis=1, keepdims=True)
    claim_norms = np.maximum(claim_norms, 1e-8)
    claims_normed = claim_embeddings / claim_norms

    mem_norms = np.linalg.norm(memory_embeddings, axis=1, keepdims=True)
    mem_norms = np.maximum(mem_norms, 1e-8)
    mems_normed = memory_embeddings / mem_norms

    # Matrix multiply: (C, d) @ (d, M) → (C, M)
    return claims_normed @ mems_normed.T


def apply_gate(
    similarity_matrix: np.ndarray,
    memory_ids: list[str],
    threshold: float | None = None,
    max_candidates: int = 5,
) -> list[list[str]]:
    """For each claim, return the memory IDs that pass the similarity gate.

    Args:
        similarity_matrix: (num_claims, num_memories) cosine similarity matrix
        memory_ids: list of memory IDs corresponding to columns
        threshold: minimum cosine similarity to pass
        max_candidates: maximum candidates per claim (top-k after threshold)

    Returns:
        List of lists — candidates[i] is the list of memory_ids for claim i
    """
    if threshold is None:
        threshold = _default_threshold()

    num_claims = similarity_matrix.shape[0]
    candidates: list[list[str]] = []

    for i in range(num_claims):
        sims = similarity_matrix[i]
        # Get indices above threshold
        above = np.where(sims >= threshold)[0]

        if len(above) == 0:
            candidates.append([])
            continue

        # Sort by similarity descending, take top max_candidates
        sorted_indices = above[np.argsort(-sims[above])][:max_candidates]
        candidates.append([memory_ids[j] for j in sorted_indices])

    return candidates


def find_dead_memories(
    similarity_matrix: np.ndarray,
    memory_ids: list[str],
    threshold: float | None = None,
) -> list[str]:
    """Find memories that never passed the similarity gate for any claim.

    These "dead memories" are retrieved context that has zero relevance
    to any claim in the response — pure waste.

    Args:
        similarity_matrix: (num_claims, num_memories) cosine similarity matrix
        memory_ids: list of memory IDs
        threshold: the gate threshold

    Returns:
        List of memory_ids that never passed the gate
    """
    if threshold is None:
        threshold = _default_threshold()

    if similarity_matrix.size == 0:
        return list(memory_ids)

    # For each memory (column), check if ANY claim has similarity >= threshold
    max_per_memory = np.max(similarity_matrix, axis=0)  # (num_memories,)
    dead_mask = max_per_memory < threshold
    return [memory_ids[j] for j in range(len(memory_ids)) if dead_mask[j]]

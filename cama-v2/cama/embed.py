"""Embedding utilities — sentence-transformers wrapper."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

_model_cache: dict[str, object] = {}


def _get_model(model_name: str = "all-MiniLM-L6-v2") -> object:
    """Lazy-load and cache sentence-transformers model."""
    if model_name not in _model_cache:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embedding. "
                "Install with: pip install cama-v2[cpu]"
            )
        logger.info("Loading embedding model: %s", model_name)
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def embed_texts(
    texts: list[str],
    model_name: str = "all-MiniLM-L6-v2",
) -> NDArray[np.float32]:
    """Embed a list of texts using sentence-transformers.

    Returns array of shape (len(texts), embedding_dim).
    """
    if not texts:
        return np.array([], dtype=np.float32).reshape(0, 0)

    model = _get_model(model_name)
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.astype(np.float32)


def cosine_similarity_matrix(
    a: NDArray[np.float32],
    b: NDArray[np.float32],
) -> NDArray[np.float32]:
    """Compute pairwise cosine similarity between two embedding matrices.

    Args:
        a: shape (N, D)
        b: shape (M, D)

    Returns:
        Similarity matrix of shape (N, M).
    """
    if a.size == 0 or b.size == 0:
        return np.array([], dtype=np.float32).reshape(0, 0)

    # Normalize
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
    return a_norm @ b_norm.T


def max_similarity(
    query_embeddings: NDArray[np.float32],
    memory_embeddings: NDArray[np.float32],
) -> NDArray[np.float32]:
    """For each query, compute max cosine similarity to any memory.

    Args:
        query_embeddings: shape (N, D) — e.g., sentence embeddings
        memory_embeddings: shape (M, D) — memory embeddings

    Returns:
        Array of shape (N,) with max similarity per query.
    """
    sim_matrix = cosine_similarity_matrix(query_embeddings, memory_embeddings)
    if sim_matrix.size == 0:
        return np.zeros(len(query_embeddings), dtype=np.float32)
    return sim_matrix.max(axis=1)

"""Embedding utility — lazy-loaded sentence-transformers model."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def _load_model() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer as ST

    from cortex.config import settings

    return ST(settings.embedding_model)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts → list of float vectors.

    Uses all-MiniLM-L6-v2 by default (~90 MB, 384-dim).
    """
    if not texts:
        return []
    model = _load_model()
    vectors: np.ndarray = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()


def embed_single(text: str) -> list[float]:
    return embed([text])[0]

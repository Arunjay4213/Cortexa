"""Embedding utility — routes between local and API-based models."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

USE_LOCAL_MODELS = os.environ.get("USE_LOCAL_MODELS", "false").lower() == "true"

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


# ── Local model path (USE_LOCAL_MODELS=true) ─────────────────

@lru_cache(maxsize=1)
def _load_model() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer as ST
    from cortex.config import settings
    return ST(settings.embedding_model)


def _embed_local(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    vectors: np.ndarray = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()


# ── API path (USE_LOCAL_MODELS=false) ────────────────────────

def _embed_api(texts: list[str]) -> list[list[float]]:
    from cortex.config import settings
    from cortex.embeddings.api_embeddings import embed_batch
    return embed_batch(texts, api_key=settings.openai_api_key)


# ── Public interface (unchanged) ─────────────────────────────

def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts -> list of float vectors.

    Routes to local sentence-transformers or OpenAI API based on
    USE_LOCAL_MODELS environment variable.
    """
    if not texts:
        return []
    if USE_LOCAL_MODELS:
        return _embed_local(texts)
    return _embed_api(texts)


def embed_single(text: str) -> list[float]:
    return embed([text])[0]

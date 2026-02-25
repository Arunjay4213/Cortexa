"""
OpenAI API embeddings for CortexOS.

Uses text-embedding-3-small (1536 dims, $0.02/1M tokens).
"""

from __future__ import annotations

import logging

import httpx
import numpy as np

log = logging.getLogger("cortex")

_OPENAI_URL = "https://api.openai.com/v1/embeddings"
_DEFAULT_MODEL = "text-embedding-3-small"


def embed_batch(
    texts: list[str],
    api_key: str,
) -> list[list[float]]:
    if not texts:
        return []

    resp = httpx.post(
        _OPENAI_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"input": texts, "model": _DEFAULT_MODEL},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda x: x["index"])
    embeddings = [item["embedding"] for item in data]

    arr = np.array(embeddings)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    return (arr / norms).tolist()

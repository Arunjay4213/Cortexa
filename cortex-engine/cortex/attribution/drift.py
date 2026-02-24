"""Semantic Drift Detection — §4.2.

Monitors how memory representations diverge from their original embeddings.
Drift(mᵢ, t) = 1 − cos(φ(mᵢ, t₀), φ(mᵢ, t))

High drift indicates the memory content has evolved semantically and may
no longer serve its original purpose. Threshold: drift > 0.15 triggers alert.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select, insert, and_
from sqlalchemy.ext.asyncio import AsyncConnection

from cortex.db.tables import memories


# We need a table to store drift history. For now, compute on-demand
# by comparing current embedding to the embedding stored at creation.
# Future: add a `memory_embedding_history` table for temporal tracking.


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """1 - cosine_similarity. Returns 0 for identical, 1 for orthogonal."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 1.0
    return float(1.0 - np.dot(a, b) / (norm_a * norm_b))


def compute_drift_score(
    original_embedding: list[float],
    current_embedding: list[float],
) -> float:
    """Drift(mᵢ, t) = 1 − cos(φ(mᵢ, t₀), φ(mᵢ, t)).

    Returns value in [0, 1]. 0 = no drift, 1 = complete drift.
    """
    if not original_embedding or not current_embedding:
        return 0.0
    orig = np.array(original_embedding)
    curr = np.array(current_embedding)
    return cosine_distance(orig, curr)


async def detect_drifted_memories(
    db: AsyncConnection,
    agent_id: str,
    drift_threshold: float = 0.15,
) -> list[dict]:
    """Find memories whose embeddings have drifted beyond threshold.

    Since we currently store only the latest embedding, this compares
    against the mean embedding of the agent's memory cluster as a proxy
    for detecting outlier drift.

    Returns list of {memory_id, drift_score, content_preview, created_at}.
    """
    stmt = (
        select(memories.c.id, memories.c.content, memories.c.embedding, memories.c.created_at)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.archived_at.is_(None),
                memories.c.embedding.isnot(None),
            )
        )
    )
    rows = (await db.execute(stmt)).fetchall()

    if len(rows) < 2:
        return []

    # Build embedding matrix
    valid_rows = [(r, np.array(r.embedding)) for r in rows if r.embedding]
    if len(valid_rows) < 2:
        return []

    embeddings = np.array([e for _, e in valid_rows])

    # Compute centroid (mean embedding of the cluster)
    centroid = embeddings.mean(axis=0)

    # Compute drift as distance from centroid — outliers have high drift
    drifted = []
    for row, emb in valid_rows:
        drift = cosine_distance(emb, centroid)
        if drift >= drift_threshold:
            drifted.append({
                "memory_id": row.id,
                "drift_score": round(drift, 4),
                "content_preview": row.content[:100] if row.content else "",
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

    # Sort by drift score descending
    drifted.sort(key=lambda x: x["drift_score"], reverse=True)
    return drifted


async def compute_agent_drift_summary(
    db: AsyncConnection,
    agent_id: str,
    drift_threshold: float = 0.15,
) -> dict:
    """Compute aggregate drift statistics for an agent.

    Returns {mean_drift, max_drift, drifted_count, total_count, drift_rate}.
    """
    stmt = (
        select(memories.c.id, memories.c.embedding)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.archived_at.is_(None),
                memories.c.embedding.isnot(None),
            )
        )
    )
    rows = (await db.execute(stmt)).fetchall()

    if len(rows) < 2:
        return {
            "mean_drift": 0.0,
            "max_drift": 0.0,
            "drifted_count": 0,
            "total_count": len(rows),
            "drift_rate": 0.0,
        }

    valid = [(r, np.array(r.embedding)) for r in rows if r.embedding]
    if len(valid) < 2:
        return {
            "mean_drift": 0.0,
            "max_drift": 0.0,
            "drifted_count": 0,
            "total_count": len(valid),
            "drift_rate": 0.0,
        }

    embeddings = np.array([e for _, e in valid])
    centroid = embeddings.mean(axis=0)

    drifts = [cosine_distance(e, centroid) for _, e in valid]

    drifted_count = sum(1 for d in drifts if d >= drift_threshold)

    return {
        "mean_drift": round(float(np.mean(drifts)), 4),
        "max_drift": round(float(np.max(drifts)), 4),
        "drifted_count": drifted_count,
        "total_count": len(valid),
        "drift_rate": round(drifted_count / len(valid), 4) if valid else 0.0,
    }

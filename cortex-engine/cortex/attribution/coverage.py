"""Coverage Gap Analysis — §4.3.

Identifies topics/domains where an agent's memory has insufficient coverage
by analyzing the distribution of query embeddings vs. memory embeddings.

Coverage(A, Q) = |{q ∈ Q : max_i cos(φ(q), φ(mᵢ)) > τ}| / |Q|

Queries with no high-similarity memory hit represent coverage gaps.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncConnection

from cortex.db.tables import memories, transactions


def _cosine_similarity_matrix(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Compute cosine similarity matrix between rows of A and rows of B."""
    norms_a = np.linalg.norm(A, axis=1, keepdims=True)
    norms_b = np.linalg.norm(B, axis=1, keepdims=True)
    norms_a = np.where(norms_a == 0, 1.0, norms_a)
    norms_b = np.where(norms_b == 0, 1.0, norms_b)
    A_norm = A / norms_a
    B_norm = B / norms_b
    return A_norm @ B_norm.T


async def compute_coverage(
    db: AsyncConnection,
    agent_id: str,
    similarity_threshold: float = 0.5,
    query_limit: int = 500,
) -> dict:
    """Compute memory coverage for an agent's recent queries.

    Returns:
        coverage_rate: fraction of queries with at least one strong memory match
        gap_count: number of queries with no strong match
        total_queries: total queries analyzed
        gap_queries: list of query previews that had no strong match
    """
    # Fetch memory embeddings
    mem_stmt = (
        select(memories.c.id, memories.c.embedding)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.embedding.isnot(None),
            )
        )
    )
    mem_rows = (await db.execute(mem_stmt)).fetchall()

    # Fetch recent query embeddings
    query_stmt = (
        select(transactions.c.id, transactions.c.query_text, transactions.c.query_embedding)
        .where(
            and_(
                transactions.c.agent_id == agent_id,
                transactions.c.query_embedding.isnot(None),
            )
        )
        .order_by(transactions.c.created_at.desc())
        .limit(query_limit)
    )
    query_rows = (await db.execute(query_stmt)).fetchall()

    if not mem_rows or not query_rows:
        return {
            "coverage_rate": 0.0 if query_rows else 1.0,
            "gap_count": len(query_rows),
            "total_queries": len(query_rows),
            "gap_queries": [],
        }

    # Build matrices
    valid_mems = [(r, np.array(r.embedding)) for r in mem_rows if r.embedding]
    valid_queries = [(r, np.array(r.query_embedding)) for r in query_rows if r.query_embedding]

    if not valid_mems or not valid_queries:
        return {
            "coverage_rate": 0.0,
            "gap_count": len(valid_queries),
            "total_queries": len(valid_queries),
            "gap_queries": [],
        }

    mem_embeddings = np.array([e for _, e in valid_mems])
    query_embeddings = np.array([e for _, e in valid_queries])

    # Compute similarity matrix: (num_queries x num_memories)
    sim_matrix = _cosine_similarity_matrix(query_embeddings, mem_embeddings)

    # For each query, check if max similarity exceeds threshold
    max_sims = sim_matrix.max(axis=1)
    covered = max_sims >= similarity_threshold

    gap_indices = np.where(~covered)[0]
    gap_queries = []
    for idx in gap_indices[:20]:  # limit to 20 gap examples
        row = valid_queries[idx][0]
        gap_queries.append({
            "query_id": row.id,
            "query_preview": row.query_text[:120] if row.query_text else "",
            "best_match_similarity": round(float(max_sims[idx]), 4),
        })

    total = len(valid_queries)
    gap_count = int((~covered).sum())

    return {
        "coverage_rate": round(float(covered.sum() / total), 4) if total > 0 else 0.0,
        "gap_count": gap_count,
        "total_queries": total,
        "gap_queries": gap_queries,
    }


async def identify_cluster_gaps(
    db: AsyncConnection,
    agent_id: str,
    n_clusters: int = 5,
) -> list[dict]:
    """Identify underserved topic clusters via k-means on query embeddings.

    Returns clusters sorted by coverage (worst first), each with:
    - cluster_id, centroid_queries (representative queries), coverage_rate, query_count
    """
    query_stmt = (
        select(transactions.c.id, transactions.c.query_text, transactions.c.query_embedding)
        .where(
            and_(
                transactions.c.agent_id == agent_id,
                transactions.c.query_embedding.isnot(None),
            )
        )
        .order_by(transactions.c.created_at.desc())
        .limit(1000)
    )
    query_rows = (await db.execute(query_stmt)).fetchall()

    valid_queries = [(r, np.array(r.query_embedding)) for r in query_rows if r.query_embedding]

    if len(valid_queries) < n_clusters:
        return []

    query_embeddings = np.array([e for _, e in valid_queries])

    # Simple k-means (avoid sklearn dependency for lightweight deploy)
    centroids, labels = _simple_kmeans(query_embeddings, n_clusters, max_iter=50)

    # Fetch memory embeddings for coverage check
    mem_stmt = (
        select(memories.c.embedding)
        .where(
            and_(
                memories.c.agent_id == agent_id,
                memories.c.deleted_at.is_(None),
                memories.c.embedding.isnot(None),
            )
        )
    )
    mem_rows = (await db.execute(mem_stmt)).fetchall()
    mem_embeddings = np.array([np.array(r.embedding) for r in mem_rows if r.embedding]) if mem_rows else np.array([])

    clusters = []
    for c_idx in range(n_clusters):
        mask = labels == c_idx
        cluster_queries = [valid_queries[i] for i in range(len(valid_queries)) if mask[i]]

        if not cluster_queries:
            continue

        # Check coverage against memories
        coverage_rate = 0.0
        if mem_embeddings.size > 0:
            cluster_embs = np.array([e for _, e in cluster_queries])
            sims = _cosine_similarity_matrix(cluster_embs, mem_embeddings)
            covered = (sims.max(axis=1) >= 0.5).sum()
            coverage_rate = float(covered / len(cluster_queries))

        # Pick representative queries (closest to centroid)
        representatives = []
        for row, emb in cluster_queries[:3]:
            representatives.append(row.query_text[:100] if row.query_text else "")

        clusters.append({
            "cluster_id": c_idx,
            "query_count": int(mask.sum()),
            "coverage_rate": round(coverage_rate, 4),
            "representative_queries": representatives,
        })

    # Sort by worst coverage first
    clusters.sort(key=lambda x: x["coverage_rate"])
    return clusters


def _simple_kmeans(
    X: np.ndarray, k: int, max_iter: int = 50, seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Minimal k-means implementation (no sklearn dependency).

    Args:
        X: (n, d) embedding matrix
        k: number of clusters
        max_iter: convergence limit
        seed: RNG seed. None = non-deterministic. Pass explicit seed for tests.
    """
    n = X.shape[0]
    rng = np.random.default_rng(seed)
    indices = rng.choice(n, size=k, replace=False)
    centroids = X[indices].copy()

    labels = np.zeros(n, dtype=np.int32)

    for _ in range(max_iter):
        # Assign labels
        sims = _cosine_similarity_matrix(X, centroids)
        new_labels = sims.argmax(axis=1)

        if np.array_equal(new_labels, labels):
            break
        labels = new_labels

        # Update centroids — check centroid movement for true convergence
        old_centroids = centroids.copy()
        for c in range(k):
            mask = labels == c
            if mask.sum() > 0:
                centroids[c] = X[mask].mean(axis=0)

        if np.allclose(centroids, old_centroids, atol=1e-6):
            break

    return centroids, labels

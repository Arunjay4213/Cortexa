"""SISA-Adapted Memory Partitioning — §6.2.

Sharded-Isolated-Sliced-Aggregated framework for efficient memory unlearning.

Instead of retraining an entire model, SISA partitions memories into shards.
When a memory needs to be forgotten, only its shard needs reprocessing.

Unlearning cost: O(|S_j|) instead of O(|M|) where |S_j| << |M|
"""

from __future__ import annotations

import uuid
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np


@dataclass
class MemoryShard:
    """A partition of memories for SISA unlearning."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    shard_index: int = 0
    memory_ids: list[str] = field(default_factory=list)
    embedding_centroid: list[float] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_retrained: datetime | None = None
    retraining_count: int = 0

    @property
    def size(self) -> int:
        return len(self.memory_ids)


@dataclass
class UnlearningResult:
    """Result of an unlearning operation."""
    memory_id: str
    shard_id: str
    shard_size: int
    reprocessing_cost: float    # estimated cost in tokens
    memories_affected: int       # how many memories in the shard
    total_memories: int          # total memories across all shards
    efficiency_gain: float       # ratio of full retrain cost saved


class SISAPartitioner:
    """Partition memories into shards for efficient unlearning.

    Uses embedding-based clustering to group related memories,
    so unlearning one memory only requires reprocessing its cluster.
    """

    def __init__(self, num_shards: int = 8):
        self.num_shards = num_shards
        self.shards: list[MemoryShard] = []

    def partition(
        self,
        memory_ids: list[str],
        embeddings: np.ndarray | None = None,
    ) -> list[MemoryShard]:
        """Partition memories into shards.

        If embeddings are provided, uses k-means clustering for semantic grouping.
        Otherwise, uses round-robin assignment.
        """
        if embeddings is not None and embeddings.shape[0] == len(memory_ids):
            return self._partition_by_embedding(memory_ids, embeddings)
        return self._partition_round_robin(memory_ids)

    def _partition_round_robin(self, memory_ids: list[str]) -> list[MemoryShard]:
        """Simple round-robin partitioning."""
        self.shards = [
            MemoryShard(shard_index=i)
            for i in range(self.num_shards)
        ]

        for i, mid in enumerate(memory_ids):
            shard_idx = i % self.num_shards
            self.shards[shard_idx].memory_ids.append(mid)

        return self.shards

    def _partition_by_embedding(
        self, memory_ids: list[str], embeddings: np.ndarray
    ) -> list[MemoryShard]:
        """Embedding-based partitioning via k-means."""
        n = len(memory_ids)
        k = min(self.num_shards, n)

        if k <= 1:
            shard = MemoryShard(shard_index=0, memory_ids=list(memory_ids))
            if embeddings.shape[0] > 0:
                shard.embedding_centroid = embeddings.mean(axis=0).tolist()
            self.shards = [shard]
            return self.shards

        # K-means clustering
        labels = self._kmeans(embeddings, k)

        self.shards = []
        for c in range(k):
            mask = labels == c
            shard_ids = [memory_ids[i] for i in range(n) if mask[i]]
            centroid = embeddings[mask].mean(axis=0).tolist() if mask.sum() > 0 else []

            self.shards.append(MemoryShard(
                shard_index=c,
                memory_ids=shard_ids,
                embedding_centroid=centroid,
            ))

        return self.shards

    @staticmethod
    def _kmeans(X: np.ndarray, k: int, max_iter: int = 30) -> np.ndarray:
        """Minimal k-means for shard assignment."""
        n = X.shape[0]
        rng = np.random.default_rng(42)
        indices = rng.choice(n, size=k, replace=False)
        centroids = X[indices].copy()

        labels = np.zeros(n, dtype=np.int32)
        for _ in range(max_iter):
            # Assign to nearest centroid (L2 distance)
            dists = np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2)
            new_labels = dists.argmin(axis=1)

            if np.array_equal(new_labels, labels):
                break
            labels = new_labels

            for c in range(k):
                mask = labels == c
                if mask.sum() > 0:
                    centroids[c] = X[mask].mean(axis=0)

        return labels

    def find_shard(self, memory_id: str) -> MemoryShard | None:
        """Find which shard contains a given memory."""
        for shard in self.shards:
            if memory_id in shard.memory_ids:
                return shard
        return None

    def unlearn(self, memory_id: str, avg_tokens_per_memory: int = 200) -> UnlearningResult | None:
        """Simulate unlearning a memory from its shard.

        Returns the cost/efficiency of the unlearning operation.
        """
        shard = self.find_shard(memory_id)
        if shard is None:
            return None

        total_memories = sum(s.size for s in self.shards)
        shard_cost = shard.size * avg_tokens_per_memory  # tokens to reprocess
        full_cost = total_memories * avg_tokens_per_memory

        # Remove memory from shard
        shard.memory_ids.remove(memory_id)
        shard.retraining_count += 1
        shard.last_retrained = datetime.now(UTC)

        efficiency = 1.0 - (shard_cost / full_cost) if full_cost > 0 else 0.0

        return UnlearningResult(
            memory_id=memory_id,
            shard_id=shard.id,
            shard_size=shard.size + 1,  # before removal
            reprocessing_cost=float(shard_cost),
            memories_affected=shard.size + 1,
            total_memories=total_memories,
            efficiency_gain=round(efficiency, 4),
        )

    def stats(self) -> dict:
        """Aggregate shard statistics."""
        sizes = [s.size for s in self.shards]
        return {
            "num_shards": len(self.shards),
            "total_memories": sum(sizes),
            "min_shard_size": min(sizes) if sizes else 0,
            "max_shard_size": max(sizes) if sizes else 0,
            "mean_shard_size": round(float(np.mean(sizes)), 1) if sizes else 0.0,
            "balance_ratio": round(min(sizes) / max(sizes), 4) if sizes and max(sizes) > 0 else 0.0,
        }

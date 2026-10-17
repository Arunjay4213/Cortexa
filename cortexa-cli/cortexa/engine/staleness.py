"""Staleness detection — memories whose source data has changed.

A memory is stale if:
- source_updated_at > created_at (source was updated after memory creation)
- Memory hasn't been refreshed in a configurable window
- Content diverges from current source (if embedding comparison available)
"""

from datetime import datetime, timedelta

from cortexa.engine.models import Memory, StaleMemory


class StalenessDetector:
    """Detects memories that may be outdated."""

    def __init__(
        self,
        staleness_days: int = 30,
        similarity_threshold: float = 0.85,
    ) -> None:
        self.staleness_days = staleness_days
        self.similarity_threshold = similarity_threshold

    def detect(
        self,
        memories: list[Memory],
        source_embeddings: dict[str, list[float]] | None = None,
    ) -> list[StaleMemory]:
        """Detect stale memories.

        Args:
            memories: Memories to check for staleness.
            source_embeddings: Optional dict mapping memory_id to current source embeddings.
        """
        stale: list[StaleMemory] = []
        now = datetime.utcnow()

        for memory in memories:
            # Check 1: Source was updated after memory creation
            if (
                memory.source_updated_at is not None
                and memory.source_updated_at > memory.created_at
            ):
                days = (memory.source_updated_at - memory.created_at).days
                stale.append(
                    StaleMemory(
                        memory_id=memory.id,
                        created_at=memory.created_at,
                        source_updated_at=memory.source_updated_at,
                        days_since_update=days,
                        reason=(
                            f"Source updated {days} days after memory creation"
                        ),
                    )
                )
                continue

            # Check 2: Memory hasn't been refreshed in staleness window
            age_days = (now - memory.created_at).days
            if age_days > self.staleness_days and memory.source is not None:
                # Check embedding similarity if available
                similarity = None
                if (
                    source_embeddings
                    and memory.id in source_embeddings
                    and memory.embedding is not None
                ):
                    similarity = self._cosine_similarity(
                        memory.embedding, source_embeddings[memory.id]
                    )
                    if similarity >= self.similarity_threshold:
                        continue  # content still matches, not stale

                stale.append(
                    StaleMemory(
                        memory_id=memory.id,
                        created_at=memory.created_at,
                        source_updated_at=memory.source_updated_at,
                        days_since_update=age_days,
                        similarity_to_source=similarity,
                        reason=(
                            f"Memory is {age_days} days old with source "
                            f"'{memory.source}' (threshold: {self.staleness_days} days)"
                            + (f", similarity: {similarity:.2f}" if similarity is not None else "")
                        ),
                    )
                )

        return stale

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

"""In-memory dict-based backend — for testing, demos, and quick prototyping.

No external dependencies. Memories are stored in a plain dict keyed by ID.
Search is basic substring matching (no vector search).
"""

from __future__ import annotations

from datetime import datetime

from cortexa.engine.models import Memory
from cortexa.sdk.backends.base import MemoryBackend


class InMemoryBackend(MemoryBackend):
    """Dict-backed memory store — zero dependencies, ephemeral."""

    def __init__(self) -> None:
        self._store: dict[str, Memory] = {}

    async def add(self, memory: Memory) -> str:
        self._store[memory.id] = memory
        return memory.id

    async def get(self, memory_id: str) -> Memory | None:
        return self._store.get(memory_id)

    async def search(self, query: str, limit: int = 10) -> list[Memory]:
        query_lower = query.lower()
        scored: list[tuple[float, Memory]] = []

        for mem in self._store.values():
            content_lower = mem.content.lower()
            if query_lower in content_lower:
                # Simple relevance: shorter content with match = more relevant
                score = len(query_lower) / max(len(content_lower), 1)
                scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:limit]]

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        # Sort by created_at descending (newest first)
        all_mems = sorted(
            self._store.values(),
            key=lambda m: m.created_at,
            reverse=True,
        )
        return all_mems[offset : offset + limit]

    async def delete(self, memory_id: str) -> bool:
        if memory_id in self._store:
            del self._store[memory_id]
            return True
        return False

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict | None = None,
    ) -> Memory | None:
        existing = self._store.get(memory_id)
        if existing is None:
            return None

        updates: dict = {}
        if content is not None:
            updates["content"] = content
        if metadata is not None:
            updates["metadata"] = {**existing.metadata, **metadata}

        updated = existing.model_copy(update=updates)
        self._store[memory_id] = updated
        return updated

    async def count(self) -> int:
        return len(self._store)

    async def clear(self) -> int:
        n = len(self._store)
        self._store.clear()
        return n

    async def add_bulk(self, memories: list[Memory]) -> list[str]:
        """Convenience method to add multiple memories at once."""
        return [await self.add(m) for m in memories]

"""Abstract base class for memory backend adapters.

All memory backends (InMemory, Mem0, ChromaDB, custom) implement this ABC.
Methods are async to support both local and networked backends uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from cortexa.engine.models import Memory


class MemoryBackend(ABC):
    """Abstract memory backend — defines the contract for all adapters."""

    @abstractmethod
    async def add(self, memory: Memory) -> str:
        """Store a memory and return its ID.

        If the memory already has an ID that exists in the store,
        the behavior is backend-specific (upsert or error).
        """

    @abstractmethod
    async def get(self, memory_id: str) -> Memory | None:
        """Retrieve a single memory by ID, or None if not found."""

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[Memory]:
        """Search memories by text relevance.

        Backends with vector search use semantic similarity.
        Simple backends fall back to substring matching.

        Args:
            query: Search query text.
            limit: Maximum number of results to return.

        Returns:
            List of matching memories, ordered by relevance (best first).
        """

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        """List all memories with pagination.

        Args:
            limit: Maximum number to return.
            offset: Number of memories to skip.

        Returns:
            List of memories ordered by creation time (newest first).
        """

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Returns:
            True if the memory was deleted, False if it didn't exist.
        """

    @abstractmethod
    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict | None = None,
    ) -> Memory | None:
        """Update a memory's content and/or metadata.

        Only provided fields are updated; None fields are left unchanged.

        Returns:
            The updated memory, or None if the memory doesn't exist.
        """

    @abstractmethod
    async def count(self) -> int:
        """Return the total number of memories in the store."""

    async def clear(self) -> int:
        """Delete all memories. Returns the number deleted.

        Default implementation lists and deletes one by one.
        Backends should override for efficiency.
        """
        all_memories = await self.list_all(limit=10_000)
        deleted = 0
        for m in all_memories:
            if await self.delete(m.id):
                deleted += 1
        return deleted

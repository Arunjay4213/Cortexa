"""Abstract adapter interface for memory backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MemoryRecord:
    """A single memory from any backend."""

    id: str
    content: str
    collection: str = "default"
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    last_accessed: datetime | None = None
    access_count: int = 0
    source: str | None = None
    source_updated_at: datetime | None = None
    mas_score: float | None = None
    mas_history: list[float] = field(default_factory=list)


class MemoryAdapter(ABC):
    """Abstract interface for memory system backends.

    Every adapter must implement these methods to enable
    audit, watch, and chat functionality.
    """

    @abstractmethod
    def connect(self) -> str:
        """Connect to the memory store. Returns a description string (e.g. 'Mem0 (local)')."""

    @abstractmethod
    def list_memories(self, collection: str | None = None) -> list[MemoryRecord]:
        """Return all memories, optionally filtered by collection."""

    @abstractmethod
    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        """Return a single memory by ID, or None if not found."""

    @abstractmethod
    def list_collections(self) -> list[str]:
        """Return all collection names."""

    @abstractmethod
    def get_embeddings(self, memory_ids: list[str]) -> dict[str, list[float]]:
        """Return embedding vectors keyed by memory ID."""

    @abstractmethod
    def archive_memory(self, memory_id: str) -> bool:
        """Mark a memory as archived (soft delete). Returns success."""

    @abstractmethod
    def delete_memory(self, memory_id: str) -> bool:
        """Hard delete a memory. Returns success."""

    @abstractmethod
    def update_memory(self, memory_id: str, content: str) -> bool:
        """Update a memory's content. Returns success."""

    def get_stats(self) -> dict[str, Any]:
        """Return summary stats about the memory store."""
        memories = self.list_memories()
        collections = self.list_collections()
        return {
            "total_memories": len(memories),
            "collections": len(collections),
            "collection_names": collections,
        }

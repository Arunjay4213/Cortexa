"""Mem0 memory backend adapter.

Wraps the mem0ai SDK to implement MemoryBackend.
Requires: pip install cortexa[mem0]
"""

from __future__ import annotations

import logging
from datetime import datetime

from cortexa.engine.exceptions import BackendError
from cortexa.engine.models import Memory
from cortexa.sdk.backends.base import MemoryBackend

logger = logging.getLogger(__name__)

try:
    from mem0 import MemoryClient
except ImportError:
    MemoryClient = None  # type: ignore[assignment,misc]


class Mem0Backend(MemoryBackend):
    """Mem0 cloud memory backend.

    Connects to the Mem0 API for managed memory storage with
    built-in vector search and automatic summarization.
    """

    def __init__(
        self,
        api_key: str | None = None,
        org_id: str | None = None,
        project_id: str | None = None,
    ) -> None:
        if MemoryClient is None:
            raise BackendError(
                "mem0ai package not installed. Install with: pip install cortexa[mem0]"
            )

        if not api_key:
            raise BackendError("Mem0 API key required. Set CORTEXA_MEM0_API_KEY or pass api_key.")

        try:
            self._client = MemoryClient(api_key=api_key)
        except Exception as e:
            raise BackendError(f"Failed to initialize Mem0 client: {e}")

        self._org_id = org_id
        self._project_id = project_id

    def _user_id(self) -> str:
        """Construct a user_id for Mem0 scoping."""
        parts = ["cortexa"]
        if self._org_id:
            parts.append(self._org_id)
        if self._project_id:
            parts.append(self._project_id)
        return ":".join(parts)

    async def add(self, memory: Memory) -> str:
        try:
            result = self._client.add(
                memory.content,
                user_id=self._user_id(),
                metadata={"source": memory.source or "", "cortexa_id": memory.id, **memory.metadata},
            )
            # Mem0 returns a list of memory results
            if isinstance(result, list) and result:
                return result[0].get("id", memory.id)
            if isinstance(result, dict):
                return result.get("id", memory.id)
            return memory.id
        except Exception as e:
            raise BackendError(f"Mem0 add failed: {e}")

    async def get(self, memory_id: str) -> Memory | None:
        try:
            result = self._client.get(memory_id)
            if result is None:
                return None
            return _mem0_to_memory(result)
        except Exception:
            return None

    async def search(self, query: str, limit: int = 10) -> list[Memory]:
        try:
            results = self._client.search(query, user_id=self._user_id(), limit=limit)
            if isinstance(results, dict):
                results = results.get("results", [])
            return [_mem0_to_memory(r) for r in results]
        except Exception as e:
            logger.warning("Mem0 search failed: %s", e)
            return []

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        try:
            results = self._client.get_all(user_id=self._user_id())
            if isinstance(results, dict):
                results = results.get("results", [])
            memories = [_mem0_to_memory(r) for r in results]
            return memories[offset : offset + limit]
        except Exception as e:
            logger.warning("Mem0 list_all failed: %s", e)
            return []

    async def delete(self, memory_id: str) -> bool:
        try:
            self._client.delete(memory_id)
            return True
        except Exception:
            return False

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict | None = None,
    ) -> Memory | None:
        try:
            existing = await self.get(memory_id)
            if existing is None:
                return None
            if content is not None:
                self._client.update(memory_id, data=content)
            return await self.get(memory_id)
        except Exception as e:
            logger.warning("Mem0 update failed: %s", e)
            return None

    async def count(self) -> int:
        memories = await self.list_all(limit=10_000)
        return len(memories)


def _mem0_to_memory(data: dict) -> Memory:
    """Convert a Mem0 result dict to a Cortexa Memory."""
    meta = data.get("metadata", {})
    return Memory(
        id=data.get("id", ""),
        content=data.get("memory", data.get("text", "")),
        source=meta.get("source"),
        metadata={k: v for k, v in meta.items() if k not in ("source", "cortexa_id")},
    )

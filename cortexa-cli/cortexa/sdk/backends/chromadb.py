"""ChromaDB memory backend adapter.

Wraps the chromadb client to implement MemoryBackend.
Supports both ephemeral (in-memory) and persistent (on-disk) modes.
Requires: pip install cortexa[chromadb]
"""

from __future__ import annotations

import logging
from datetime import datetime

from cortexa.engine.exceptions import BackendError
from cortexa.engine.models import Memory
from cortexa.sdk.backends.base import MemoryBackend

logger = logging.getLogger(__name__)

try:
    import chromadb
except ImportError:
    chromadb = None  # type: ignore[assignment]


class ChromaDBBackend(MemoryBackend):
    """ChromaDB vector-search memory backend.

    Uses ChromaDB's built-in embedding + vector search for semantic
    memory retrieval. Supports persistent local storage or remote server.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str = "cortexa_memories",
        persist_path: str | None = None,
    ) -> None:
        if chromadb is None:
            raise BackendError(
                "chromadb package not installed. Install with: pip install cortexa[chromadb]"
            )

        try:
            if host:
                self._client = chromadb.HttpClient(host=host, port=port or 8000)
            elif persist_path:
                self._client = chromadb.PersistentClient(path=persist_path)
            else:
                self._client = chromadb.EphemeralClient()

            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            raise BackendError(f"Failed to initialize ChromaDB: {e}")

    async def add(self, memory: Memory) -> str:
        try:
            meta = _build_chromadb_meta(memory)
            self._collection.upsert(
                ids=[memory.id],
                documents=[memory.content],
                metadatas=[meta],
            )
            return memory.id
        except Exception as e:
            raise BackendError(f"ChromaDB add failed: {e}")

    async def get(self, memory_id: str) -> Memory | None:
        try:
            result = self._collection.get(ids=[memory_id], include=["documents", "metadatas"])
            if not result["ids"]:
                return None
            return _chromadb_to_memory(
                memory_id,
                result["documents"][0],
                result["metadatas"][0],
            )
        except Exception:
            return None

    async def search(self, query: str, limit: int = 10) -> list[Memory]:
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=limit,
                include=["documents", "metadatas"],
            )
            memories = []
            for i, mid in enumerate(results["ids"][0]):
                memories.append(
                    _chromadb_to_memory(
                        mid,
                        results["documents"][0][i],
                        results["metadatas"][0][i],
                    )
                )
            return memories
        except Exception as e:
            logger.warning("ChromaDB search failed: %s", e)
            return []

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        try:
            result = self._collection.get(
                include=["documents", "metadatas"],
                limit=limit,
                offset=offset,
            )
            memories = []
            for i, mid in enumerate(result["ids"]):
                memories.append(
                    _chromadb_to_memory(
                        mid,
                        result["documents"][i],
                        result["metadatas"][i],
                    )
                )
            return memories
        except Exception as e:
            logger.warning("ChromaDB list_all failed: %s", e)
            return []

    async def delete(self, memory_id: str) -> bool:
        try:
            # Check existence first
            existing = self._collection.get(ids=[memory_id])
            if not existing["ids"]:
                return False
            self._collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict | None = None,
    ) -> Memory | None:
        existing = await self.get(memory_id)
        if existing is None:
            return None

        new_content = content if content is not None else existing.content
        new_meta = {**existing.metadata, **(metadata or {})}

        updated = existing.model_copy(
            update={"content": new_content, "metadata": new_meta}
        )

        try:
            meta = _build_chromadb_meta(updated)
            self._collection.update(
                ids=[memory_id],
                documents=[new_content],
                metadatas=[meta],
            )
            return updated
        except Exception as e:
            logger.warning("ChromaDB update failed: %s", e)
            return None

    async def count(self) -> int:
        try:
            return self._collection.count()
        except Exception:
            return 0

    async def clear(self) -> int:
        try:
            n = self._collection.count()
            # Delete and recreate the collection
            name = self._collection.name
            coll_meta = self._collection.metadata
            self._client.delete_collection(name)
            self._collection = self._client.get_or_create_collection(
                name=name,
                metadata=coll_meta,
            )
            return n
        except Exception as e:
            logger.warning("ChromaDB clear failed: %s", e)
            return 0


def _build_chromadb_meta(memory: Memory) -> dict:
    """Build a flat metadata dict for ChromaDB (only str/int/float/bool allowed)."""
    meta: dict = {}
    if memory.source:
        meta["source"] = memory.source
    if memory.created_at:
        meta["created_at"] = memory.created_at.isoformat()
    if memory.last_accessed:
        meta["last_accessed"] = memory.last_accessed.isoformat()
    meta["access_count"] = memory.access_count
    # Flatten user metadata (only scalar values)
    for k, v in memory.metadata.items():
        if isinstance(v, (str, int, float, bool)):
            meta[f"user_{k}"] = v
    return meta


def _chromadb_to_memory(
    memory_id: str, document: str, metadata: dict
) -> Memory:
    """Convert ChromaDB result to a Cortexa Memory."""
    source = metadata.get("source")
    created_str = metadata.get("created_at")
    accessed_str = metadata.get("last_accessed")

    user_meta = {}
    for k, v in metadata.items():
        if k.startswith("user_"):
            user_meta[k[5:]] = v

    return Memory(
        id=memory_id,
        content=document,
        source=source,
        created_at=datetime.fromisoformat(created_str) if created_str else datetime.utcnow(),
        last_accessed=datetime.fromisoformat(accessed_str) if accessed_str else None,
        access_count=metadata.get("access_count", 0),
        metadata=user_meta,
    )

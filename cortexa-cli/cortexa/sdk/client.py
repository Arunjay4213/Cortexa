"""Main Cortexa client — the public API.

Usage:
    from cortexa import Cortexa

    cx = Cortexa()                           # uses defaults
    cx = Cortexa(backend="memory")           # in-memory (testing/demo)
    cx = Cortexa(backend="mem0", ...)        # Mem0 adapter
    cx = Cortexa(backend="chromadb", ...)    # ChromaDB adapter

    # Add memories
    await cx.add_memory("Premium plan costs $49.99/month", source="pricing")

    # Trace a response
    result = await cx.trace(
        query="How much?",
        response="The price is $49.99",
    )

    # Full health audit
    audit = await cx.audit()
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from pathlib import Path

from cortexa.engine.exceptions import BackendError, ConfigError
from cortexa.engine.models import (
    AuditResult,
    GateResult,
    Memory,
    TraceResult,
)
from cortexa.engine.scorer import CortexaScorer
from cortexa.sdk.backends.base import MemoryBackend
from cortexa.sdk.config import CortexaConfig

logger = logging.getLogger(__name__)

# Max recent traces kept for rolling ghost detection
_DEFAULT_TRACE_WINDOW = 20


class Cortexa:
    """Cortexa client — unified interface to memory intelligence.

    Wraps:
    - A MemoryBackend for CRUD operations
    - A CortexaScorer for the CAMA verification pipeline
    - A CortexaConfig for settings management
    """

    def __init__(
        self,
        backend: str | MemoryBackend | None = None,
        config: CortexaConfig | None = None,
        config_path: Path | str | None = None,
        trace_window: int = _DEFAULT_TRACE_WINDOW,
        # Shortcut overrides (skip config file)
        nli_backend: str | None = None,
        ghost_threshold: float | None = None,
        contradiction_threshold: float | None = None,
        # Mem0 shortcuts
        mem0_api_key: str | None = None,
        # ChromaDB shortcuts
        chromadb_path: str | None = None,
        chromadb_collection: str | None = None,
    ) -> None:
        # Load config (file → env → explicit overrides)
        self.config = config or CortexaConfig.load(config_path)

        # Apply explicit overrides
        if nli_backend is not None:
            self.config.nli.backend = nli_backend
        if ghost_threshold is not None:
            self.config.thresholds.ghost_mas = ghost_threshold
        if contradiction_threshold is not None:
            self.config.thresholds.contradiction = contradiction_threshold
        if mem0_api_key is not None:
            self.config.backend.mem0_api_key = mem0_api_key
        if chromadb_path is not None:
            self.config.backend.chromadb_path = chromadb_path
        if chromadb_collection is not None:
            self.config.backend.chromadb_collection = chromadb_collection

        # Resolve backend
        if isinstance(backend, MemoryBackend):
            self._backend = backend
        else:
            backend_type = backend or self.config.backend.type
            self._backend = _create_backend(backend_type, self.config)

        # Initialize scorer
        self._scorer = CortexaScorer(
            decompose_mode=self.config.decompose_mode,
            nli_backend=self.config.nli.backend,
            nli_model=self.config.nli.model_name,
            ghost_threshold=self.config.thresholds.ghost_mas,
            contradiction_threshold=self.config.thresholds.contradiction,
            staleness_days=self.config.thresholds.staleness_days,
            temperature=self.config.thresholds.temperature,
        )

        # Rolling trace window for ghost detection
        self._recent_traces: deque[TraceResult] = deque(maxlen=trace_window)

    # ── Memory CRUD ──────────────────────────────────────────────

    async def add_memory(
        self,
        content: str,
        source: str | None = None,
        metadata: dict | None = None,
    ) -> Memory:
        """Create and store a new memory.

        Returns the created Memory object with its assigned ID.
        """
        memory = Memory(
            content=content,
            source=source,
            metadata=metadata or {},
        )
        await self._backend.add(memory)
        return memory

    async def get_memory(self, memory_id: str) -> Memory | None:
        """Retrieve a memory by ID."""
        return await self._backend.get(memory_id)

    async def search_memories(self, query: str, limit: int = 10) -> list[Memory]:
        """Search memories by text relevance."""
        return await self._backend.search(query, limit=limit)

    async def list_memories(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        """List all memories with pagination."""
        return await self._backend.list_all(limit=limit, offset=offset)

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID. Returns True if deleted."""
        return await self._backend.delete(memory_id)

    async def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict | None = None,
    ) -> Memory | None:
        """Update a memory's content and/or metadata."""
        return await self._backend.update(memory_id, content=content, metadata=metadata)

    async def memory_count(self) -> int:
        """Return the total number of stored memories."""
        return await self._backend.count()

    # ── CAMA Pipeline ────────────────────────────────────────────

    async def trace(
        self,
        query: str,
        response: str,
        memories: list[Memory] | None = None,
        memory_query: str | None = None,
        memory_limit: int = 10,
    ) -> TraceResult:
        """Run the full CAMA verification pipeline on a query-response pair.

        Args:
            query: The user's query.
            response: The LLM's generated response.
            memories: Explicit list of memories to check against.
                     If None, searches the backend using memory_query or query.
            memory_query: Custom search query for memory retrieval.
                         Defaults to the query parameter.
            memory_limit: Max memories to retrieve from backend.

        Returns:
            TraceResult with claims, attributions, ghosts, contradictions,
            stale memories, and a health score.
        """
        if memories is None:
            search_q = memory_query or query
            memories = await self._backend.search(search_q, limit=memory_limit)

        recent = list(self._recent_traces) if self._recent_traces else None

        result = self._scorer.trace(
            query=query,
            response=response,
            memories=memories,
            recent_traces=recent,
        )

        self._recent_traces.append(result)
        return result

    async def audit(
        self,
        memories: list[Memory] | None = None,
        limit: int = 1000,
    ) -> AuditResult:
        """Run a full health audit on the memory store.

        Args:
            memories: Explicit list to audit. If None, loads from backend.
            limit: Max memories to load from backend (when memories is None).

        Returns:
            AuditResult with ghost/stale/contradiction counts,
            health score, waste estimates, and recommendations.
        """
        if memories is None:
            memories = await self._backend.list_all(limit=limit)

        recent = list(self._recent_traces) if self._recent_traces else None
        return self._scorer.audit(memories, recent_traces=recent)

    async def gate(
        self,
        query: str,
        memories: list[Memory] | None = None,
        memory_limit: int = 10,
    ) -> GateResult:
        """Pre-generation memory risk scoring.

        Checks retrieved memories for contradictions and staleness
        BEFORE the LLM generates a response. Flags risky memories.

        Args:
            query: The user's query.
            memories: Explicit memories. If None, searches backend.
            memory_limit: Max memories to retrieve.

        Returns:
            GateResult with risk flags and safe_to_generate boolean.
        """
        if memories is None:
            memories = await self._backend.search(query, limit=memory_limit)

        if not memories:
            return GateResult(query=query, memories_scored=0)

        # Check staleness
        stale = self._scorer.staleness_detector.detect(memories)
        stale_ids = {s.memory_id for s in stale}

        # Check pairwise contradictions (on the small co-retrieved set)
        contradictions = self._scorer.contradiction_detector.detect_pairwise(memories)

        contradiction_ids = set()
        for c in contradictions:
            contradiction_ids.add(c.memory_id_1)
            contradiction_ids.add(c.memory_id_2)

        high_risk = list(stale_ids | contradiction_ids)

        safe = len(contradictions) == 0 and len(stale) == 0
        summary_parts = []
        if contradictions:
            summary_parts.append(f"{len(contradictions)} contradiction(s)")
        if stale:
            summary_parts.append(f"{len(stale)} stale memor{'y' if len(stale) == 1 else 'ies'}")

        return GateResult(
            query=query,
            memories_scored=len(memories),
            high_risk=high_risk,
            contradictions=contradictions,
            stale=stale,
            safe_to_generate=safe,
            risk_summary=", ".join(summary_parts) if summary_parts else "No risks detected",
        )

    # ── Utilities ────────────────────────────────────────────────

    async def health(self) -> float:
        """Quick health score (0-100) for the current memory store."""
        audit = await self.audit()
        return audit.health_score

    @property
    def backend(self) -> MemoryBackend:
        """Access the underlying memory backend."""
        return self._backend

    @property
    def scorer(self) -> CortexaScorer:
        """Access the underlying CAMA scorer."""
        return self._scorer


def _create_backend(backend_type: str, config: CortexaConfig) -> MemoryBackend:
    """Factory — instantiate a backend by type string."""
    if backend_type == "memory":
        from cortexa.sdk.backends.custom import InMemoryBackend

        return InMemoryBackend()

    elif backend_type == "mem0":
        try:
            from cortexa.sdk.backends.mem0 import Mem0Backend
        except ImportError:
            raise BackendError(
                "Mem0 backend requires the mem0ai package. "
                "Install with: pip install cortexa[mem0]"
            )
        return Mem0Backend(
            api_key=config.backend.mem0_api_key,
            org_id=config.backend.mem0_org_id,
            project_id=config.backend.mem0_project_id,
        )

    elif backend_type == "chromadb":
        try:
            from cortexa.sdk.backends.chromadb import ChromaDBBackend
        except ImportError:
            raise BackendError(
                "ChromaDB backend requires the chromadb package. "
                "Install with: pip install cortexa[chromadb]"
            )
        return ChromaDBBackend(
            host=config.backend.chromadb_host,
            port=config.backend.chromadb_port,
            collection_name=config.backend.chromadb_collection,
            persist_path=config.backend.chromadb_path,
        )

    else:
        raise ConfigError(
            f"Unknown backend type: {backend_type!r}. "
            "Use 'memory', 'mem0', or 'chromadb'."
        )

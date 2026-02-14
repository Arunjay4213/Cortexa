"""ProvenanceGraph — core graph operations for the compliance engine.

Implements:
- record_transaction(): create interaction node + attribution edges (Section 5.1)
- record_memory_creation(): create memory + creation edge + embedding + derivation (Section 5.2)
- record_consolidation(): create summary + derivation edges
- record_contextcite(): create response node + statement attribution edges
- update_attribution(): versioned calibration corrections (Section 3.2)
- compute_user_footprint(): F(u) via recursive CTE (Definition 6.2)
- compute_influence_footprint(): I(u) (Definition 6.2, Eq. 53)

See PROVENANCE.md Sections 5.1-5.4 for pseudocode and SQL.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db.models.provenance import (
    AttributionEdge,
    CreationEdge,
    Criticality,
    DerivationEdge,
    DerivationType,
    EmbeddingNode,
    InteractionNode,
    MemoryNode,
    MemoryStatus,
    MemoryType,
    NodeType,
    ResponseNode,
    ScoreType,
    StatementAttributionEdge,
    SummaryNode,
)

NUM_SHARDS = 16


@dataclass
class UserFootprint:
    """Result of F(u) computation — all nodes reachable from a user's interactions.

    See PROVENANCE.md Section 5.3, Definition 6.2.
    """

    user_id: str
    memory_node_ids: list[UUID] = field(default_factory=list)
    summary_node_ids: list[UUID] = field(default_factory=list)
    embedding_node_ids: list[UUID] = field(default_factory=list)
    interaction_node_ids: list[UUID] = field(default_factory=list)

    @property
    def all_node_ids(self) -> list[UUID]:
        return (
            self.memory_node_ids
            + self.summary_node_ids
            + self.embedding_node_ids
            + self.interaction_node_ids
        )

    def serialize(self) -> dict:
        return {
            "user_id": self.user_id,
            "memory_node_ids": [str(x) for x in self.memory_node_ids],
            "summary_node_ids": [str(x) for x in self.summary_node_ids],
            "embedding_node_ids": [str(x) for x in self.embedding_node_ids],
            "interaction_node_ids": [str(x) for x in self.interaction_node_ids],
        }

    def certificate_hash(self) -> str:
        """SHA-256 of the serialized footprint for compliance certificates."""
        return hashlib.sha256(
            json.dumps(self.serialize(), sort_keys=True).encode()
        ).hexdigest()


class ProvenanceGraph:
    """Core provenance graph operations.

    All methods accept an AsyncSession and operate within the caller's
    transaction boundary. The caller is responsible for commit/rollback.
    """

    # ── Write Path ──────────────────────────────────────────────────────

    async def record_transaction(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        query: str,
        response: str,
        agent_id: str,
        transaction_cost: float,
        memory_ids: list[UUID],
        attribution_scores: list[float],
        score_type: ScoreType = ScoreType.eas,
        timestamp: datetime | None = None,
        metadata: dict | None = None,
    ) -> InteractionNode:
        """Record a complete agent transaction with attribution.

        Creates an InteractionNode and one AttributionEdge per (memory, score)
        pair in a single DB transaction. See PROVENANCE.md Section 5.1.
        """
        now = timestamp or datetime.now(UTC)

        interaction = InteractionNode(
            user_id=user_id,
            query=query,
            response=response,
            timestamp=now,
            agent_id=agent_id,
            transaction_cost=transaction_cost,
            metadata_=metadata or {},
        )
        session.add(interaction)
        # Flush to materialise interaction.id before creating edges.
        await session.flush()

        for memory_id, score in zip(memory_ids, attribution_scores):
            edge = AttributionEdge(
                source_id=memory_id,
                target_id=interaction.id,
                score=score,
                score_type=score_type,
                version=1,
                is_current=True,
                created_at=now,
                metadata_={},
            )
            session.add(edge)

        return interaction

    async def record_memory_creation(
        self,
        session: AsyncSession,
        *,
        interaction_id: UUID,
        content: str,
        user_id: str,
        memory_type: MemoryType = MemoryType.raw,
        vector_ref: str,
        embedding_model: str,
        embedding_dim: int,
        token_count: int = 0,
        criticality: Criticality = Criticality.normal,
        metadata: dict | None = None,
    ) -> tuple[MemoryNode, EmbeddingNode]:
        """Record creation of a new memory from an interaction.

        Creates MemoryNode + CreationEdge + EmbeddingNode + DerivationEdge
        atomically. See PROVENANCE.md Section 5.2.
        """
        now = datetime.now(UTC)
        shard_id = hash(user_id) % NUM_SHARDS

        mem_node = MemoryNode(
            content=content,
            memory_type=memory_type,
            status=MemoryStatus.active,
            shard_id=shard_id,
            slice_id=await self._next_slice_id(session, user_id),
            created_at=now,
            created_by_user_id=user_id,
            token_count=token_count,
            criticality=criticality,
            metadata_=metadata or {},
        )
        session.add(mem_node)
        await session.flush()

        creation_edge = CreationEdge(
            source_id=interaction_id,
            target_id=mem_node.id,
            created_at=now,
            metadata_={},
        )
        session.add(creation_edge)

        emb_node = EmbeddingNode(
            vector_ref=vector_ref,
            model_version=embedding_model,
            dimensions=embedding_dim,
            created_at=now,
            metadata_={},
        )
        session.add(emb_node)
        await session.flush()

        deriv_edge = DerivationEdge(
            source_id=mem_node.id,
            source_type=NodeType.memory,
            target_id=emb_node.id,
            target_type=NodeType.embedding,
            derivation_type=DerivationType.embedding,
            created_at=now,
            metadata_={},
        )
        session.add(deriv_edge)

        return mem_node, emb_node

    async def record_consolidation(
        self,
        session: AsyncSession,
        *,
        source_memory_ids: list[UUID],
        summary_content: str,
        method: str = "llm_consolidation",
        metadata: dict | None = None,
    ) -> SummaryNode:
        """Record memory consolidation into a summary.

        Creates SummaryNode + one DerivationEdge from each source memory.
        """
        now = datetime.now(UTC)

        summary = SummaryNode(
            content=summary_content,
            source_memory_count=len(source_memory_ids),
            created_at=now,
            method=method,
            metadata_=metadata or {},
        )
        session.add(summary)
        await session.flush()

        for mem_id in source_memory_ids:
            edge = DerivationEdge(
                source_id=mem_id,
                source_type=NodeType.memory,
                target_id=summary.id,
                target_type=NodeType.summary,
                derivation_type=DerivationType.consolidation,
                created_at=now,
                metadata_={},
            )
            session.add(edge)

        return summary

    async def record_contextcite(
        self,
        session: AsyncSession,
        *,
        interaction_id: UUID,
        statements: list[dict],
        memory_scores: list[dict],
    ) -> ResponseNode:
        """Record ContextCite statement-level attribution.

        Creates a ResponseNode + StatementAttributionEdge per entry in
        memory_scores. See PROVENANCE.md Section 3.4.

        Args:
            statements: List of statement dicts, e.g. [{"text": "...", "index": 0}].
            memory_scores: List of dicts with keys memory_id, statement_index, score.
        """
        now = datetime.now(UTC)

        response_node = ResponseNode(
            interaction_id=interaction_id,
            statements=statements,
            created_at=now,
        )
        session.add(response_node)
        await session.flush()

        for entry in memory_scores:
            edge = StatementAttributionEdge(
                memory_id=entry["memory_id"],
                response_id=response_node.id,
                statement_index=entry["statement_index"],
                score=entry["score"],
                created_at=now,
            )
            session.add(edge)

        return response_node

    async def update_attribution(
        self,
        session: AsyncSession,
        *,
        source_id: UUID,
        target_id: UUID,
        new_score: float,
        new_score_type: ScoreType,
        metadata: dict | None = None,
    ) -> AttributionEdge:
        """Create a new version of an attribution edge (calibration correction).

        Marks existing current version as superseded and inserts a new row
        with incremented version. See PROVENANCE.md Section 3.2.
        """
        now = datetime.now(UTC)

        # Find the current version number.
        result = await session.execute(
            select(AttributionEdge.version)
            .where(
                AttributionEdge.source_id == source_id,
                AttributionEdge.target_id == target_id,
                AttributionEdge.is_current.is_(True),
            )
        )
        current = result.scalar_one_or_none()
        next_version = (current or 0) + 1

        # Mark old version as superseded.
        await session.execute(
            update(AttributionEdge)
            .where(
                AttributionEdge.source_id == source_id,
                AttributionEdge.target_id == target_id,
                AttributionEdge.is_current.is_(True),
            )
            .values(is_current=False)
        )

        new_edge = AttributionEdge(
            source_id=source_id,
            target_id=target_id,
            score=new_score,
            score_type=new_score_type,
            version=next_version,
            is_current=True,
            created_at=now,
            metadata_=metadata or {},
        )
        session.add(new_edge)

        return new_edge

    # ── Read Path ───────────────────────────────────────────────────────

    async def compute_user_footprint(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> UserFootprint:
        """Compute F(u) — all data nodes reachable from user's interactions.

        Uses a recursive CTE starting from memories created by the user's
        interactions, then following derivation edges to summaries and
        embeddings. See PROVENANCE.md Section 5.3, Definition 6.2.
        """
        footprint = UserFootprint(user_id=user_id)

        # 1. Collect the user's interaction node IDs.
        interactions = await session.execute(
            select(InteractionNode.id).where(InteractionNode.user_id == user_id)
        )
        footprint.interaction_node_ids = [row[0] for row in interactions]

        # 2. Recursive CTE: memories created by those interactions, then
        #    all derivation targets (summaries, embeddings, re-embeddings).
        result = await session.execute(
            text("""
                WITH RECURSIVE user_footprint AS (
                    -- Base: memories created from user's interactions
                    SELECT ce.target_id AS node_id,
                           CAST('memory' AS TEXT) AS node_type
                    FROM creation_edges ce
                    JOIN interaction_nodes i ON ce.source_id = i.id
                    WHERE i.user_id = :user_id

                    UNION

                    -- Recursive: all nodes derived from those memories
                    SELECT de.target_id AS node_id,
                           CAST(de.target_type AS TEXT) AS node_type
                    FROM derivation_edges de
                    JOIN user_footprint uf ON de.source_id = uf.node_id
                )
                SELECT node_id, node_type FROM user_footprint
            """),
            {"user_id": user_id},
        )

        for row in result:
            node_id = UUID(str(row[0])) if not isinstance(row[0], UUID) else row[0]
            node_type = row[1]
            if node_type == "memory":
                footprint.memory_node_ids.append(node_id)
            elif node_type == "summary":
                footprint.summary_node_ids.append(node_id)
            elif node_type == "embedding":
                footprint.embedding_node_ids.append(node_id)

        return footprint

    async def compute_influence_footprint(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> list[UUID]:
        """Compute I(u) — interaction IDs influenced by user u's memories.

        Finds all interactions that have current, positive attribution edges
        from any memory in user u's data footprint.
        See PROVENANCE.md Section 5.4, Eq. 53.
        """
        result = await session.execute(
            text("""
                WITH RECURSIVE user_footprint AS (
                    SELECT ce.target_id AS node_id,
                           CAST('memory' AS TEXT) AS node_type
                    FROM creation_edges ce
                    JOIN interaction_nodes i ON ce.source_id = i.id
                    WHERE i.user_id = :user_id

                    UNION

                    SELECT de.target_id AS node_id,
                           CAST(de.target_type AS TEXT) AS node_type
                    FROM derivation_edges de
                    JOIN user_footprint uf ON de.source_id = uf.node_id
                )
                SELECT DISTINCT ae.target_id AS influenced_interaction_id
                FROM attribution_edges ae
                JOIN user_footprint uf ON ae.source_id = uf.node_id
                WHERE uf.node_type = 'memory'
                  AND ae.is_current = TRUE
                  AND ae.score > 0
            """),
            {"user_id": user_id},
        )

        return [
            UUID(str(row[0])) if not isinstance(row[0], UUID) else row[0]
            for row in result
        ]

    # ── Helpers ─────────────────────────────────────────────────────────

    async def _next_slice_id(self, session: AsyncSession, user_id: str) -> int:
        """Get the next SISA slice_id for a user (monotonically increasing)."""
        result = await session.execute(
            text("""
                SELECT COALESCE(MAX(slice_id), -1) + 1
                FROM memory_nodes
                WHERE created_by_user_id = :user_id
            """),
            {"user_id": user_id},
        )
        return result.scalar_one()

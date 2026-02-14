"""SQLAlchemy 2.x ORM models for the provenance graph.

Five node types and four edge types implementing the directed acyclic graph
described in PROVENANCE.md. See Sections 2-3 for node/edge definitions,
Section 4 for storage layout, and Section 5 for core operations.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cortex.db.models.base import Base

try:
    from uuid_utils import uuid7 as _uuid7
except ImportError:
    from uuid import uuid4 as _uuid7  # fallback when uuid-utils not installed


def _generate_uuid() -> UUID:
    """Generate a UUID v7 for time-sortable primary keys."""
    return _uuid7()


# ── Enums ───────────────────────────────────────────────────────────────


class MemoryType(str, enum.Enum):
    """See PROVENANCE.md Section 2.2."""

    raw = "raw"
    consolidated = "consolidated"
    critical = "critical"


class MemoryStatus(str, enum.Enum):
    """See PROVENANCE.md Section 2.2."""

    active = "active"
    archived = "archived"
    deleted = "deleted"
    pending_deletion = "pending_deletion"


class Criticality(str, enum.Enum):
    """See PROVENANCE.md Section 2.2."""

    normal = "normal"
    safety_critical = "safety_critical"
    protected = "protected"


class ScoreType(str, enum.Enum):
    """See PROVENANCE.md Section 3.2."""

    eas = "eas"
    contextcite = "contextcite"
    calibrated = "calibrated"


class DerivationType(str, enum.Enum):
    """See PROVENANCE.md Section 3.3."""

    consolidation = "consolidation"
    embedding = "embedding"
    re_embedding = "re_embedding"
    summary = "summary"


class NodeType(str, enum.Enum):
    """Polymorphic node types for derivation edges. See PROVENANCE.md Section 3.3."""

    memory = "memory"
    summary = "summary"
    embedding = "embedding"


# ── Node Types ──────────────────────────────────────────────────────────


class InteractionNode(Base):
    """An agent query-response cycle. See PROVENANCE.md Section 2.1."""

    __tablename__ = "interaction_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    transaction_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    # Relationships
    creation_edges: Mapped[list[CreationEdge]] = relationship(
        back_populates="source_interaction", foreign_keys="CreationEdge.source_id"
    )
    attribution_edges: Mapped[list[AttributionEdge]] = relationship(
        back_populates="target_interaction", foreign_keys="AttributionEdge.target_id"
    )
    response_nodes: Mapped[list[ResponseNode]] = relationship(
        back_populates="interaction"
    )

    __table_args__ = (
        Index("ix_interaction_nodes_user_id", "user_id"),
        Index("ix_interaction_nodes_agent_id", "agent_id"),
    )


class MemoryNode(Base):
    """A memory unit in the provenance graph. See PROVENANCE.md Section 2.2.

    Partitioned by HASH(shard_id) with modulus 16 (Section 4.2).
    Partitioning is handled in the Alembic migration via raw DDL.
    """

    __tablename__ = "memory_nodes"

    # Composite PK: PostgreSQL requires partition key in PK for hash-partitioned tables.
    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    shard_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(MemoryType, name="memory_type_enum", create_constraint=False),
        nullable=False,
    )
    status: Mapped[MemoryStatus] = mapped_column(
        Enum(MemoryStatus, name="memory_status_enum", create_constraint=False),
        nullable=False,
        default=MemoryStatus.active,
    )
    slice_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criticality: Mapped[Criticality] = mapped_column(
        Enum(Criticality, name="criticality_enum", create_constraint=False),
        nullable=False,
        default=Criticality.normal,
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    deletion_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_memory_nodes_user", "created_by_user_id"),
        Index("idx_memory_nodes_shard_status", "shard_id", "status"),
    )


class SummaryNode(Base):
    """A consolidation summary derived from multiple memories. See PROVENANCE.md Section 2.3."""

    __tablename__ = "summary_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_memory_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")


class EmbeddingNode(Base):
    """A vector embedding reference. See PROVENANCE.md Section 2.4."""

    __tablename__ = "embedding_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    vector_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    model_version: Mapped[str] = mapped_column(String(255), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")


class ResponseNode(Base):
    """Statement-level response decomposition. See PROVENANCE.md Section 2.5.

    Created on-demand when ContextCite runs (~1% of queries).
    """

    __tablename__ = "response_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    interaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("interaction_nodes.id"), nullable=False
    )
    statements: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    interaction: Mapped[InteractionNode] = relationship(back_populates="response_nodes")

    __table_args__ = (
        Index("ix_response_nodes_interaction_id", "interaction_id"),
    )


# ── Edge Types (all append-only / immutable) ────────────────────────────


class CreationEdge(Base):
    """Interaction -> Memory creation link. See PROVENANCE.md Section 3.1."""

    __tablename__ = "creation_edges"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("interaction_nodes.id"), nullable=False
    )
    # Logical FK to memory_nodes.id — no DB constraint due to hash partitioning.
    target_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    source_interaction: Mapped[InteractionNode] = relationship(
        back_populates="creation_edges", foreign_keys=[source_id]
    )

    __table_args__ = (
        Index("idx_creation_edges_source", "source_id"),
        Index("idx_creation_edges_target", "target_id"),
    )


class AttributionEdge(Base):
    """Memory -> Interaction attribution score. See PROVENANCE.md Section 3.2.

    Append-only: calibration corrections produce new versioned rows.
    Old versions have is_current=False. Partitioned by RANGE(created_at).
    """

    __tablename__ = "attribution_edges"

    # Composite PK: PostgreSQL requires partition key in PK for range-partitioned tables.
    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    # Logical FK to memory_nodes.id — no DB constraint due to hash partitioning.
    source_id: Mapped[UUID] = mapped_column(nullable=False)
    target_id: Mapped[UUID] = mapped_column(
        ForeignKey("interaction_nodes.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_type: Mapped[ScoreType] = mapped_column(
        Enum(ScoreType, name="score_type_enum", create_constraint=False),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    target_interaction: Mapped[InteractionNode] = relationship(
        back_populates="attribution_edges", foreign_keys=[target_id]
    )

    __table_args__ = (
        Index(
            "idx_attr_edges_target_current", "target_id",
            postgresql_where=text("is_current = TRUE"),
        ),
        Index(
            "idx_attr_edges_source_current", "source_id",
            postgresql_where=text("is_current = TRUE"),
        ),
    )


class DerivationEdge(Base):
    """Source -> Derived node link. See PROVENANCE.md Section 3.3.

    Polymorphic: source_id/target_id can reference memory_nodes,
    summary_nodes, or embedding_nodes. No FK constraints.
    """

    __tablename__ = "derivation_edges"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    source_id: Mapped[UUID] = mapped_column(nullable=False)
    source_type: Mapped[NodeType] = mapped_column(
        Enum(NodeType, name="node_type_enum", create_constraint=False),
        nullable=False,
    )
    target_id: Mapped[UUID] = mapped_column(nullable=False)
    target_type: Mapped[NodeType] = mapped_column(
        Enum(NodeType, name="node_type_enum", create_constraint=False),
        nullable=False,
    )
    derivation_type: Mapped[DerivationType] = mapped_column(
        Enum(DerivationType, name="derivation_type_enum", create_constraint=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        Index("idx_deriv_edges_source", "source_id"),
        Index("idx_deriv_edges_target", "target_id"),
    )


class StatementAttributionEdge(Base):
    """Memory -> ResponseNode statement-level attribution. See PROVENANCE.md Section 3.4.

    Only created when ContextCite runs or hallucination tracing triggers.
    """

    __tablename__ = "statement_attribution_edges"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=_generate_uuid)
    # Logical FK to memory_nodes.id — no DB constraint due to hash partitioning.
    memory_id: Mapped[UUID] = mapped_column(nullable=False)
    response_id: Mapped[UUID] = mapped_column(
        ForeignKey("response_nodes.id"), nullable=False
    )
    statement_index: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_stmt_attr_memory", "memory_id"),
        Index("idx_stmt_attr_response", "response_id"),
    )

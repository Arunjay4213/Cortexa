"""Add provenance graph tables — 5 node types, 4 edge types, compliance certificates.

Includes HASH-partitioned memory_nodes (16 shards) and RANGE-partitioned
attribution_edges (monthly). See PROVENANCE.md Sections 2-4.

Revision ID: 003
Revises: 002
Create Date: 2026-02-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

NUM_SHARDS = 16


def upgrade() -> None:
    # ── Step 1: Create enum types ──────────────────────────────────────
    op.execute("CREATE TYPE memory_type_enum AS ENUM ('raw', 'consolidated', 'critical')")
    op.execute(
        "CREATE TYPE memory_status_enum AS ENUM "
        "('active', 'archived', 'deleted', 'pending_deletion')"
    )
    op.execute("CREATE TYPE criticality_enum AS ENUM ('normal', 'safety_critical', 'protected')")
    op.execute("CREATE TYPE score_type_enum AS ENUM ('eas', 'contextcite', 'calibrated')")
    op.execute(
        "CREATE TYPE derivation_type_enum AS ENUM "
        "('consolidation', 'embedding', 're_embedding', 'summary')"
    )
    op.execute("CREATE TYPE node_type_enum AS ENUM ('memory', 'summary', 'embedding')")
    op.execute(
        "CREATE TYPE request_type_enum AS ENUM "
        "('gdpr_deletion', 'audit_request', 'data_export')"
    )

    # ── Step 2: Non-partitioned node tables ────────────────────────────

    op.create_table(
        "interaction_nodes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("transaction_cost", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_interaction_nodes_user_id", "interaction_nodes", ["user_id"])
    op.create_index("ix_interaction_nodes_agent_id", "interaction_nodes", ["agent_id"])

    op.create_table(
        "summary_nodes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_memory_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(100), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    op.create_table(
        "embedding_nodes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("vector_ref", sa.String(512), nullable=False),
        sa.Column("model_version", sa.String(255), nullable=False),
        sa.Column("dimensions", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    op.create_table(
        "response_nodes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "interaction_id", sa.Uuid,
            sa.ForeignKey("interaction_nodes.id"), nullable=False,
        ),
        sa.Column("statements", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_response_nodes_interaction_id", "response_nodes", ["interaction_id"])

    # ── Step 3: Partitioned table — memory_nodes (HASH by shard_id) ────
    op.execute("""
        CREATE TABLE memory_nodes (
            id UUID NOT NULL,
            content TEXT NOT NULL,
            memory_type memory_type_enum NOT NULL,
            status memory_status_enum NOT NULL DEFAULT 'active',
            shard_id INTEGER NOT NULL,
            slice_id INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            created_by_user_id VARCHAR(255) NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            criticality criticality_enum NOT NULL DEFAULT 'normal',
            metadata JSONB NOT NULL DEFAULT '{}',
            deletion_scheduled_at TIMESTAMPTZ,
            PRIMARY KEY (id, shard_id)
        ) PARTITION BY HASH (shard_id)
    """)

    for i in range(NUM_SHARDS):
        op.execute(
            f"CREATE TABLE memory_nodes_p{i} PARTITION OF memory_nodes "
            f"FOR VALUES WITH (MODULUS {NUM_SHARDS}, REMAINDER {i})"
        )

    op.execute("CREATE INDEX idx_memory_nodes_user ON memory_nodes (created_by_user_id)")
    op.execute("CREATE INDEX idx_memory_nodes_shard_status ON memory_nodes (shard_id, status)")

    # ── Step 4: Edge tables ────────────────────────────────────────────

    # creation_edges (FK to interaction_nodes; logical FK to memory_nodes)
    op.create_table(
        "creation_edges",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "source_id", sa.Uuid,
            sa.ForeignKey("interaction_nodes.id"), nullable=False,
        ),
        sa.Column("target_id", sa.Uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("idx_creation_edges_source", "creation_edges", ["source_id"])
    op.create_index("idx_creation_edges_target", "creation_edges", ["target_id"])

    # attribution_edges — RANGE-partitioned by created_at
    op.execute("""
        CREATE TABLE attribution_edges (
            id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            source_id UUID NOT NULL,
            target_id UUID NOT NULL REFERENCES interaction_nodes(id),
            score DOUBLE PRECISION NOT NULL,
            score_type score_type_enum NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            is_current BOOLEAN NOT NULL DEFAULT TRUE,
            metadata JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)

    # Monthly partitions for 2026
    months = [
        ("2026-01-01", "2026-02-01"),
        ("2026-02-01", "2026-03-01"),
        ("2026-03-01", "2026-04-01"),
        ("2026-04-01", "2026-05-01"),
        ("2026-05-01", "2026-06-01"),
        ("2026-06-01", "2026-07-01"),
        ("2026-07-01", "2026-08-01"),
        ("2026-08-01", "2026-09-01"),
        ("2026-09-01", "2026-10-01"),
        ("2026-10-01", "2026-11-01"),
        ("2026-11-01", "2026-12-01"),
        ("2026-12-01", "2027-01-01"),
    ]
    for start, end in months:
        name = f"attribution_edges_{start[:7].replace('-', '_')}"
        op.execute(
            f"CREATE TABLE {name} PARTITION OF attribution_edges "
            f"FOR VALUES FROM ('{start}') TO ('{end}')"
        )

    # Default partition for dates outside defined ranges
    op.execute(
        "CREATE TABLE attribution_edges_default "
        "PARTITION OF attribution_edges DEFAULT"
    )

    # Partial indexes on the parent table (propagated to partitions)
    op.execute(
        "CREATE INDEX idx_attr_edges_target_current "
        "ON attribution_edges (target_id) WHERE is_current = TRUE"
    )
    op.execute(
        "CREATE INDEX idx_attr_edges_source_current "
        "ON attribution_edges (source_id) WHERE is_current = TRUE"
    )

    # derivation_edges (polymorphic source/target, no FK constraints)
    op.create_table(
        "derivation_edges",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("source_id", sa.Uuid, nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("memory", "summary", "embedding",
                    name="node_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("target_id", sa.Uuid, nullable=False),
        sa.Column(
            "target_type",
            sa.Enum("memory", "summary", "embedding",
                    name="node_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "derivation_type",
            sa.Enum("consolidation", "embedding", "re_embedding", "summary",
                    name="derivation_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("idx_deriv_edges_source", "derivation_edges", ["source_id"])
    op.create_index("idx_deriv_edges_target", "derivation_edges", ["target_id"])

    # statement_attribution_edges (logical FK to memory_nodes, FK to response_nodes)
    op.create_table(
        "statement_attribution_edges",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("memory_id", sa.Uuid, nullable=False),
        sa.Column(
            "response_id", sa.Uuid,
            sa.ForeignKey("response_nodes.id"), nullable=False,
        ),
        sa.Column("statement_index", sa.Integer, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_stmt_attr_memory", "statement_attribution_edges", ["memory_id"])
    op.create_index("idx_stmt_attr_response", "statement_attribution_edges", ["response_id"])

    # ── Step 5: Compliance certificates ────────────────────────────────

    op.create_table(
        "compliance_certificates",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column(
            "request_type",
            sa.Enum("gdpr_deletion", "audit_request", "data_export",
                    name="request_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("footprint_snapshot", JSONB, nullable=False),
        sa.Column("nodes_deleted", sa.Integer, nullable=False),
        sa.Column("edges_affected", sa.Integer, nullable=False),
        sa.Column("deletion_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grace_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hard_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certificate_hash", sa.String(64), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index(
        "ix_compliance_certificates_user_id", "compliance_certificates", ["user_id"]
    )


def downgrade() -> None:
    op.drop_table("compliance_certificates")
    op.drop_table("statement_attribution_edges")
    op.drop_table("derivation_edges")

    # Partitioned tables: CASCADE drops all partitions
    op.execute("DROP TABLE IF EXISTS attribution_edges CASCADE")

    op.drop_table("creation_edges")

    op.execute("DROP TABLE IF EXISTS memory_nodes CASCADE")

    op.drop_table("response_nodes")
    op.drop_table("embedding_nodes")
    op.drop_table("summary_nodes")
    op.drop_table("interaction_nodes")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS request_type_enum")
    op.execute("DROP TYPE IF EXISTS node_type_enum")
    op.execute("DROP TYPE IF EXISTS derivation_type_enum")
    op.execute("DROP TYPE IF EXISTS score_type_enum")
    op.execute("DROP TYPE IF EXISTS criticality_enum")
    op.execute("DROP TYPE IF EXISTS memory_status_enum")
    op.execute("DROP TYPE IF EXISTS memory_type_enum")

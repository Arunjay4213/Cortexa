"""Initial schema – 6 tables.

Revision ID: 001
Create Date: 2025-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.ARRAY(sa.Float(precision=53)), nullable=True),
        sa.Column("tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("agent_id", sa.String, nullable=False, server_default="default"),
        sa.Column("tier", sa.String, nullable=False, server_default="warm"),
        sa.Column("criticality", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("metadata_", JSONB, nullable=False, server_default="{}"),
        sa.Column("retrieval_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("last_accessed", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_memories_agent_id", "memories", ["agent_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("query_embedding", sa.ARRAY(sa.Float(precision=53)), nullable=True),
        sa.Column("response_text", sa.Text, nullable=False),
        sa.Column("response_embedding", sa.ARRAY(sa.Float(precision=53)), nullable=True),
        sa.Column("retrieved_memory_ids", sa.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("agent_id", sa.String, nullable=False, server_default="default"),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("model", sa.String, nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_transactions_agent_id", "transactions", ["agent_id"])

    op.create_table(
        "attribution_scores",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("memory_id", sa.String, nullable=False),
        sa.Column("transaction_id", sa.String, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("raw_score", sa.Float, nullable=False),
        sa.Column("method", sa.String, nullable=False, server_default="eas"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("compute_time_ms", sa.Float, nullable=False, server_default="0.0"),
    )
    op.create_index("ix_attribution_scores_memory_id", "attribution_scores", ["memory_id"])
    op.create_index("ix_attribution_scores_transaction_id", "attribution_scores", ["transaction_id"])

    op.create_table(
        "memory_profiles",
        sa.Column("memory_id", sa.String, primary_key=True),
        sa.Column("mean_attribution", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("attribution_variance", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("retrieval_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_attribution", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("trend", sa.String, nullable=False, server_default="stable"),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "contradictions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("memory_id_1", sa.String, nullable=False),
        sa.Column("memory_id_2", sa.String, nullable=False),
        sa.Column("type", sa.String, nullable=False, server_default="logical"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("detected_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_contradictions_memory_id_1", "contradictions", ["memory_id_1"])
    op.create_index("ix_contradictions_memory_id_2", "contradictions", ["memory_id_2"])

    op.create_table(
        "health_snapshots",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("agent_id", sa.String, nullable=False),
        sa.Column("contradiction_rate", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("retrieval_efficiency", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("semantic_drift", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("memory_quality", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("timestamp", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_health_snapshots_agent_id", "health_snapshots", ["agent_id"])


def downgrade() -> None:
    op.drop_table("health_snapshots")
    op.drop_table("contradictions")
    op.drop_table("memory_profiles")
    op.drop_table("attribution_scores")
    op.drop_table("transactions")
    op.drop_table("memories")

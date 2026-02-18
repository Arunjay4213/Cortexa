"""Phase 2 schema additions: content_hash on memories, resolved_at/resolved_by on
contradictions, compound index on contradictions(memory_id_1, memory_id_2),
description/status on agent_cost_configs.

Revision ID: 003
Revises: 002
Create Date: 2025-02-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- memories: add content_hash for fast duplicate detection
    op.add_column(
        "memories",
        sa.Column("content_hash", sa.String, nullable=True),
    )
    op.create_index("ix_memories_content_hash", "memories", ["content_hash"])

    # -- contradictions: add resolved_at, resolved_by
    op.add_column(
        "contradictions",
        sa.Column("resolved_at", sa.DateTime, nullable=True),
    )
    op.add_column(
        "contradictions",
        sa.Column("resolved_by", sa.String, nullable=True),
    )

    # -- contradictions: compound index for fast pair lookups
    op.create_index(
        "ix_contradictions_pair",
        "contradictions",
        ["memory_id_1", "memory_id_2"],
    )

    # -- agent_cost_configs: add description and status
    op.add_column(
        "agent_cost_configs",
        sa.Column("description", sa.String, nullable=True),
    )
    op.add_column(
        "agent_cost_configs",
        sa.Column("status", sa.String, nullable=False, server_default="active"),
    )


def downgrade() -> None:
    op.drop_column("agent_cost_configs", "status")
    op.drop_column("agent_cost_configs", "description")
    op.drop_index("ix_contradictions_pair", table_name="contradictions")
    op.drop_column("contradictions", "resolved_by")
    op.drop_column("contradictions", "resolved_at")
    op.drop_index("ix_memories_content_hash", table_name="memories")
    op.drop_column("memories", "content_hash")

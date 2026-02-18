"""Phase 3: Lifecycle automation — archived_at/archive_reason on memories,
lifecycle_events table for audit trail.

Revision ID: 004
Revises: 003
Create Date: 2026-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- memories: add archived_at, archive_reason
    op.add_column(
        "memories",
        sa.Column("archived_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_memories_archived_at", "memories", ["archived_at"])
    op.add_column(
        "memories",
        sa.Column("archive_reason", sa.String, nullable=True),
    )

    # -- lifecycle_events: audit trail for lifecycle actions
    op.create_table(
        "lifecycle_events",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("agent_id", sa.String, nullable=False, index=True),
        sa.Column("action", sa.String, nullable=False),  # archive | tier_change | consolidate
        sa.Column("memory_id", sa.String, nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("estimated_savings", sa.Float, nullable=True),
        sa.Column("executed_by", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_events")
    op.drop_column("memories", "archive_reason")
    op.drop_index("ix_memories_archived_at", table_name="memories")
    op.drop_column("memories", "archived_at")

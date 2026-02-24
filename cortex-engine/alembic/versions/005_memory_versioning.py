"""Phase 4: Memory versioning — snapshots, branches, diff.

Revision ID: 005
Revises: 004
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_snapshots",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("agent_id", sa.String, nullable=False, index=True),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("memory_count", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String, nullable=True),
    )

    op.create_table(
        "memory_snapshot_entries",
        sa.Column("snapshot_id", sa.String, sa.ForeignKey("memory_snapshots.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("memory_id", sa.String, primary_key=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", JSONB, nullable=True),
        sa.Column("tier", sa.String, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False, default=0),
        sa.Column("total_attribution", sa.Float, nullable=False, default=0.0),
    )

    op.create_table(
        "memory_branches",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("parent_snapshot_id", sa.String, sa.ForeignKey("memory_snapshots.id"), nullable=False),
        sa.Column("agent_id", sa.String, nullable=False, index=True),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("memory_branches")
    op.drop_table("memory_snapshot_entries")
    op.drop_table("memory_snapshots")

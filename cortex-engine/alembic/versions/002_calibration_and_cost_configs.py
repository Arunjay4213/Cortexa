"""Add calibration_pairs, agent_cost_configs tables; rename attribution_variance→m2;
add transaction status column for two-phase protocol; allow nullable response_text.

Revision ID: 002
Revises: 001
Create Date: 2025-01-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- calibration_pairs for §3.4 two-speed loop
    op.create_table(
        "calibration_pairs",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("memory_id", sa.String, nullable=False),
        sa.Column("transaction_id", sa.String, nullable=False),
        sa.Column("eas_score", sa.Float, nullable=False),
        sa.Column("exact_score", sa.Float, nullable=False),
        sa.Column("method", sa.String, nullable=False, server_default="contextcite"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_calibration_pairs_memory_id", "calibration_pairs", ["memory_id"])
    op.create_index("ix_calibration_pairs_transaction_id", "calibration_pairs", ["transaction_id"])

    # -- per-agent token cost configuration
    op.create_table(
        "agent_cost_configs",
        sa.Column("agent_id", sa.String, primary_key=True),
        sa.Column("input_token_cost", sa.Float, nullable=False),
        sa.Column("output_token_cost", sa.Float, nullable=False),
        sa.Column("provider", sa.String, nullable=True),
        sa.Column("model_id", sa.String, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # -- memory_profiles: rename attribution_variance → m2 for atomic Welford
    op.alter_column("memory_profiles", "attribution_variance", new_column_name="m2")

    # -- transactions: add status column for two-phase protocol
    op.add_column(
        "transactions",
        sa.Column("status", sa.String, nullable=False, server_default="completed"),
    )

    # -- transactions: allow NULL response_text (pending transactions have no response)
    op.alter_column("transactions", "response_text", nullable=True)


def downgrade() -> None:
    op.alter_column("transactions", "response_text", nullable=False)
    op.drop_column("transactions", "status")
    op.alter_column("memory_profiles", "m2", new_column_name="attribution_variance")
    op.drop_table("agent_cost_configs")
    op.drop_table("calibration_pairs")

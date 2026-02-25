"""Reconciliation migration: ensure all tables from 005-007 exist.

The DB was originally created via a raw schema script and stamped at revision 007,
so migrations 005-007 were never executed by alembic. This migration idempotently
creates any tables or columns that should have been created by those migrations,
using IF NOT EXISTS / DO NOTHING guards so it is safe to run on any DB state.

Revision ID: 009
Revises: 008
Create Date: 2026-02-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── From 004: lifecycle_events table ──────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS lifecycle_events (
            id               VARCHAR PRIMARY KEY,
            agent_id         VARCHAR NOT NULL,
            action           VARCHAR NOT NULL,
            memory_id        VARCHAR,
            details          JSONB NOT NULL DEFAULT '{}',
            estimated_savings FLOAT,
            executed_by      VARCHAR,
            created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_lifecycle_events_agent_id
            ON lifecycle_events (agent_id)
    """)

    # ── From 005: memory versioning tables ────────────────────────────────────
    # These were created manually when discovered missing; the IF NOT EXISTS
    # guards make this migration safe to run regardless.
    op.execute("""
        CREATE TABLE IF NOT EXISTS memory_snapshots (
            id          VARCHAR PRIMARY KEY,
            name        VARCHAR NOT NULL,
            agent_id    VARCHAR NOT NULL,
            description VARCHAR,
            memory_count INTEGER NOT NULL DEFAULT 0,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            created_by  VARCHAR
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_memory_snapshots_agent_id
            ON memory_snapshots (agent_id)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS memory_snapshot_entries (
            snapshot_id  VARCHAR NOT NULL
                REFERENCES memory_snapshots(id) ON DELETE CASCADE,
            memory_id    VARCHAR NOT NULL,
            content      TEXT NOT NULL,
            embedding    JSONB,
            tier         VARCHAR NOT NULL,
            token_count  INTEGER NOT NULL DEFAULT 0,
            total_attribution FLOAT NOT NULL DEFAULT 0.0,
            PRIMARY KEY (snapshot_id, memory_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS memory_branches (
            id                 VARCHAR PRIMARY KEY,
            name               VARCHAR NOT NULL,
            parent_snapshot_id VARCHAR REFERENCES memory_snapshots(id),
            agent_id           VARCHAR NOT NULL,
            description        VARCHAR,
            created_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_memory_branches_agent_id
            ON memory_branches (agent_id)
    """)

    # ── From 006: chi columns on health_snapshots ─────────────────────────────
    # Add each column only if it doesn't already exist.
    for col, coltype in [
        ("chi_score",             "FLOAT"),
        ("chi_grade",             "VARCHAR"),
        ("accuracy_component",    "FLOAT"),
        ("freshness_component",   "FLOAT"),
        ("coverage_component",    "FLOAT"),
        ("consistency_component", "FLOAT"),
        ("efficiency_component",  "FLOAT"),
    ]:
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'health_snapshots'
                      AND column_name = '{col}'
                ) THEN
                    ALTER TABLE health_snapshots ADD COLUMN {col} {coltype};
                END IF;
            END
            $$
        """)

    # ── From 007: health_snapshots.timestamp → TIMESTAMP WITH TIME ZONE ───────
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name  = 'health_snapshots'
                  AND column_name = 'timestamp'
                  AND data_type   = 'timestamp without time zone'
            ) THEN
                ALTER TABLE health_snapshots
                    ALTER COLUMN timestamp TYPE TIMESTAMP WITH TIME ZONE;
            END IF;
        END
        $$
    """)


def downgrade() -> None:
    # This reconciliation migration is intentionally non-reversible —
    # downgrading would risk dropping data that pre-existed it.
    pass

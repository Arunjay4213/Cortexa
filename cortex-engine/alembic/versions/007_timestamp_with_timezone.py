"""Change health_snapshots timestamp to TIMESTAMP WITH TIME ZONE

Revision ID: 007_timestamp_with_timezone
Revises: 006_add_chi_columns
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Change timestamp column from TIMESTAMP WITHOUT TIME ZONE to TIMESTAMP WITH TIME ZONE
    # PostgreSQL preserves existing values and treats them as UTC
    op.execute(
        "ALTER TABLE health_snapshots ALTER COLUMN timestamp TYPE TIMESTAMP WITH TIME ZONE"
    )


def downgrade():
    # Revert to TIMESTAMP WITHOUT TIME ZONE
    op.execute("""
        ALTER TABLE health_snapshots
        ALTER COLUMN timestamp TYPE TIMESTAMP WITHOUT TIME ZONE
    """)

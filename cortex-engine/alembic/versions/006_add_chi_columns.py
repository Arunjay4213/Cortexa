"""Add CHI columns to health_snapshots

Revision ID: 006_add_chi_columns
Revises: 005_memory_versioning
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Add new CHI component columns to health_snapshots
    op.add_column('health_snapshots', sa.Column('chi_score', sa.Float(), nullable=True))
    op.add_column('health_snapshots', sa.Column('chi_grade', sa.String(), nullable=True))
    op.add_column('health_snapshots', sa.Column('accuracy_component', sa.Float(), nullable=True))
    op.add_column('health_snapshots', sa.Column('freshness_component', sa.Float(), nullable=True))
    op.add_column('health_snapshots', sa.Column('coverage_component', sa.Float(), nullable=True))
    op.add_column('health_snapshots', sa.Column('consistency_component', sa.Float(), nullable=True))
    op.add_column('health_snapshots', sa.Column('efficiency_component', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('health_snapshots', 'efficiency_component')
    op.drop_column('health_snapshots', 'consistency_component')
    op.drop_column('health_snapshots', 'coverage_component')
    op.drop_column('health_snapshots', 'freshness_component')
    op.drop_column('health_snapshots', 'accuracy_component')
    op.drop_column('health_snapshots', 'chi_grade')
    op.drop_column('health_snapshots', 'chi_score')

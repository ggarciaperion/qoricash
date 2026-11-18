"""Add hunter_snapshots table for Hunter worker panel sync

Revision ID: h1u2n3t4e5r6
Revises: z9merge_all_heads
Create Date: 2026-11-17

Stores latest JSON snapshot pushed by qoricash-hunter-worker every 5 min.
Single-row upsert by snapshot_key='latest'.
"""
from alembic import op
import sqlalchemy as sa

revision = 'h1u2n3t4e5r6'
down_revision = 'z9merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'hunter_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_key', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('worker_hostname', sa.String(length=128), nullable=True),
        sa.Column('schema_version', sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('snapshot_key'),
    )


def downgrade():
    op.drop_table('hunter_snapshots')

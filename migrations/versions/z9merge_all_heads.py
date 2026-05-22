"""Merge all migration heads into a single linear history

Revision ID: z9merge_all_heads
Revises: a1b2c3d4e5f6, d2a3t4e5c6r7, l1s2o3u4r5c6, p1r2o3s4p5e6, t1e2m3p4l5a6
Create Date: 2026-05-22

Merges the 5 divergent heads so that flask db upgrade works correctly.
This is a no-op migration (no schema changes).
"""
from alembic import op
import sqlalchemy as sa

revision = 'z9merge_all_heads'
down_revision = ('a1b2c3d4e5f6', 'd2a3t4e5c6r7', 'l1s2o3u4r5c6', 'p1r2o3s4p5e6', 't1e2m3p4l5a6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass

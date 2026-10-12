"""wa_messages: add missing columns wa_id, tipo, origen, media_id, media_tipo

Revision ID: w2a3m4s5g6c7
Revises: m1o2d3i4m5p6
Create Date: 2026-10-12

Adds columns that exist in the WaMessage model but were never migrated.
Uses IF NOT EXISTS (via raw SQL) to be safe if some columns already exist.
"""
from alembic import op
import sqlalchemy as sa

revision = 'w2a3m4s5g6c7'
down_revision = 'm1o2d3i4m5p6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Each statement uses IF NOT EXISTS to be idempotent
    statements = [
        "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS wa_id        VARCHAR(120) DEFAULT ''",
        "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS media_id     VARCHAR(120) DEFAULT ''",
        "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS media_tipo   VARCHAR(20)  DEFAULT ''",
        "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS tipo         VARCHAR(20)  DEFAULT 'mensaje'",
        "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS origen       VARCHAR(20)  DEFAULT 'bot'",
    ]
    for stmt in statements:
        conn.execute(sa.text(stmt))


def downgrade():
    with op.batch_alter_table('wa_messages') as batch_op:
        batch_op.drop_column('origen')
        batch_op.drop_column('tipo')
        batch_op.drop_column('media_tipo')
        batch_op.drop_column('media_id')
        batch_op.drop_column('wa_id')

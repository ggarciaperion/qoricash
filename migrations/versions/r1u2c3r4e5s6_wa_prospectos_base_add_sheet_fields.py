"""wa_prospectos_base: add ruc, resultado, email, cargo (Sheet columns)

Revision ID: r1u2c3r4e5s6
Revises: s1h2e3e4t5b6
Create Date: 2026-11-24

Adds the Sheet columns that were missing from the initial sync:
- ruc:       for cross-reference with Client.dni (key for escalation)
- resultado: Sheet's classification (CLIENTE, INTERESADO, COTIZO, etc.)
- email:     from Sheet 'Email' column
- cargo:     contact's title/position
"""
from alembic import op
import sqlalchemy as sa

revision = 'r1u2c3r4e5s6'
down_revision = 's1h2e3e4t5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('wa_prospectos_base',
        sa.Column('ruc',       sa.String(15),  nullable=True))
    op.add_column('wa_prospectos_base',
        sa.Column('resultado', sa.String(100), nullable=True))
    op.add_column('wa_prospectos_base',
        sa.Column('email',     sa.String(200), nullable=True))
    op.add_column('wa_prospectos_base',
        sa.Column('cargo',     sa.String(150), nullable=True))
    op.create_index('ix_wa_prospectos_base_ruc', 'wa_prospectos_base', ['ruc'])


def downgrade():
    op.drop_index('ix_wa_prospectos_base_ruc', table_name='wa_prospectos_base')
    op.drop_column('wa_prospectos_base', 'cargo')
    op.drop_column('wa_prospectos_base', 'email')
    op.drop_column('wa_prospectos_base', 'resultado')
    op.drop_column('wa_prospectos_base', 'ruc')

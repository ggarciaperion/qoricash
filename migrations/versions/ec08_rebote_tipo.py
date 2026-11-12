"""Add rebote_tipo to ec_lote_items

Revision ID: ec08_rebote_tipo
Revises: ec07_rebote_detectado_en
Create Date: 2026-11-11

Columna:
  ec_lote_items.rebote_tipo  TEXT  NULL
    NULL           → sin rebote
    'hard'         → rebote permanente (5xx, dirección inválida)
    'soft'         → rebote temporal (buzón lleno, timeout)
    'reputacion'   → rebote por reputación del remitente

Migración idempotente: usa ADD COLUMN IF NOT EXISTS.
Segura en bases con y sin la columna.

Contexto:
  ec02_lotes.py creó ec_lote_items con rebote_motivo (texto libre).
  ec07_rebote_detectado_en.py agregó rebote_detectado_en (timestamp).
  sync_repo.py requiere rebote_tipo para clasificar el rebote en el INSERT/UPSERT.
  Esta migración completa el trío: rebote_tipo + rebote_motivo + rebote_detectado_en.
"""
from alembic import op


revision      = 'ec08_rebote_tipo'
down_revision = 'ec07_rebote_detectado_en'
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        ALTER TABLE ec_lote_items
            ADD COLUMN IF NOT EXISTS rebote_tipo TEXT
    """)


def downgrade():
    op.execute("""
        ALTER TABLE ec_lote_items
            DROP COLUMN IF EXISTS rebote_tipo
    """)

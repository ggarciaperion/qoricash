"""Add rebote_detectado_en to ec_lote_items

Revision ID: ec07_rebote_detectado_en
Revises: ec06_agent_heartbeat_dry_run
Create Date: 2026-11-11

Columna:
  ec_lote_items.rebote_detectado_en  TIMESTAMP WITH TIME ZONE  NULL
    NULL  → registro anterior a esta migración, fecha de detección desconocida.
            No se inventan fechas retroactivamente.
    value → timestamp UTC enviado por T1 (campo rebote_detectado_en del payload).

Migración idempotente: usa ADD COLUMN IF NOT EXISTS.
Segura tanto en bases sin la columna (producción, staging) como en bases donde
el script scripts/ec06_rebote_detectado_en.py ya la añadió (dev local).
Preserva todos los datos existentes.

Downgrade: elimina la columna con IF EXISTS (no falla si ya fue eliminada).
"""
from alembic import op
import sqlalchemy as sa

revision      = 'ec07_rebote_detectado_en'
down_revision = 'ec06_agent_heartbeat_dry_run'
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        ALTER TABLE ec_lote_items
            ADD COLUMN IF NOT EXISTS rebote_detectado_en TIMESTAMP WITH TIME ZONE
    """)


def downgrade():
    op.execute("""
        ALTER TABLE ec_lote_items
            DROP COLUMN IF EXISTS rebote_detectado_en
    """)

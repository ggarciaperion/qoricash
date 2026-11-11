"""[SUPERSEDED] Seed lote de prueba — migración convertida en no-op

Revision ID: ec03_lotes_test_seed
Revises: ec02_lotes
Create Date: 2026-11-09

Este archivo ya no inserta datos. El seed de prueba fue movido a un script
explícito para no contaminar producción al ejecutar `alembic upgrade head`.

Para crear datos de prueba:
    python scripts/seed_lote_test.py

Para eliminar datos de prueba existentes (si se aplicó la versión anterior):
    DELETE FROM ec_lote_items WHERE lote_id LIKE '%-TEST%';
    DELETE FROM ec_lotes WHERE lote_id LIKE '%-TEST%';
"""
revision      = 'ec03_lotes_test_seed'
down_revision = 'ec02_lotes'
branch_labels = None
depends_on    = None


def upgrade():
    pass


def downgrade():
    pass

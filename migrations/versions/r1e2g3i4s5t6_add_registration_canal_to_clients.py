"""Add registration_canal column to clients

Revision ID: r1e2g3i4s5t6
Revises: p7q8r9s0
Create Date: 2026-04-07

Agrega columna registration_canal a la tabla clients para identificar
el canal de origen del registro: 'app', 'web', 'system'.
También repara registros existentes basándose en el email del creator.
"""
from alembic import op
from sqlalchemy import text

revision = 'r1e2g3i4s5t6'
down_revision = 'p7q8r9s0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Añadir columna
    conn.execute(text(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS registration_canal VARCHAR(20)"
    ))

    # Reparar registros existentes:
    # - Si el creator es web@qoricash.pe → canal 'web'
    # - Si el creator es app@qoricash.pe → canal 'app'
    # - Si created_by es NULL → canal 'app' (registros antiguos del app móvil)
    conn.execute(text("""
        UPDATE clients
        SET registration_canal = 'web'
        WHERE created_by IN (
            SELECT id FROM users WHERE email = 'web@qoricash.pe'
        )
        AND registration_canal IS NULL
    """))

    conn.execute(text("""
        UPDATE clients
        SET registration_canal = 'app'
        WHERE created_by IN (
            SELECT id FROM users WHERE email = 'app@qoricash.pe'
        )
        AND registration_canal IS NULL
    """))

    conn.execute(text("""
        UPDATE clients
        SET registration_canal = 'app'
        WHERE created_by IS NULL
        AND registration_canal IS NULL
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE clients DROP COLUMN IF EXISTS registration_canal"))

"""partial_unique_active_users

Revision ID: y1u2s3e4r5s6
Revises: x1f2i3x4d5e6
Create Date: 2026-05-27

Reemplaza los constraints UNIQUE absolutos en users (email, username, dni)
por índices únicos PARCIALES que solo aplican a usuarios Activos.

Esto permite:
  - Soft-delete sin obfuscar datos (status = 'Inactivo' libera el slot)
  - Re-registrar el mismo email/username/dni después de eliminar un usuario

También deshace la obfuscación aplicada por x1f2i3x4d5e6 (restaura
email/username/dni originales en usuarios Inactivo obfuscados).
"""
from alembic import op
from sqlalchemy.sql import text

revision = 'y1u2s3e4r5s6'
down_revision = 'x1f2i3x4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        # 1. Deshacer obfuscación de x1f2i3x4d5e6
        #    (restaurar email/username/dni que quedaron como 'deleted_N_...')
        conn.execute(text(r"""
            UPDATE users
            SET
                email    = REGEXP_REPLACE(email,    '^deleted_[0-9]+_', ''),
                username = REGEXP_REPLACE(username, '^deleted_[0-9]+_', ''),
                dni      = REGEXP_REPLACE(dni,      '^deleted_[0-9]+_', '')
            WHERE status = 'Inactivo'
              AND email ~ '^deleted_[0-9]+_'
        """))

        # 2. Eliminar índices únicos absolutos en email y username
        conn.execute(text("DROP INDEX IF EXISTS ix_users_email"))
        conn.execute(text("DROP INDEX IF EXISTS ix_users_username"))

        # 3. Eliminar el UniqueConstraint en dni (nombre auto-generado por PostgreSQL)
        conn.execute(text("""
            DO $$
            DECLARE r RECORD;
            BEGIN
                FOR r IN (
                    SELECT c.conname
                    FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    JOIN pg_attribute a ON a.attrelid = t.oid
                        AND a.attnum = ANY(c.conkey)
                    WHERE t.relname = 'users'
                      AND c.contype = 'u'
                      AND a.attname = 'dni'
                ) LOOP
                    EXECUTE 'ALTER TABLE users DROP CONSTRAINT ' || quote_ident(r.conname);
                END LOOP;
            END $$;
        """))

        # 4. Crear índices únicos PARCIALES: solo usuarios Activos
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_active
            ON users (email) WHERE status = 'Activo'
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_active
            ON users (username) WHERE status = 'Activo'
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_dni_active
            ON users (dni) WHERE status = 'Activo'
        """))

        # 5. Recrear índices normales (no únicos) para búsqueda rápida
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_email
            ON users (email)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_username
            ON users (username)
        """))

    # SQLite (entorno local): no requiere cambios, los checks se hacen en service layer


def downgrade():
    pass

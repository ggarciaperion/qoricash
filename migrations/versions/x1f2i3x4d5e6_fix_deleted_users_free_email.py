"""fix_deleted_users_free_email

Revision ID: x1f2i3x4d5e6
Revises: z9merge_all_heads, w1p2r3o4s5p6
Create Date: 2026-05-27

Merge dos heads y libera email/username/dni de usuarios eliminados (Inactivo)
para que puedan ser reutilizados en nuevos registros.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = 'x1f2i3x4d5e6'
down_revision = ('z9merge_all_heads', 'w1p2r3o4s5p6')
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Obfuscar email/username/dni de usuarios Inactivo que aún no fueron obfuscados
    # (usuarios eliminados antes del fix en user_service.delete_user)
    conn.execute(text("""
        UPDATE users
        SET
            email    = 'deleted_' || id || '_' || email,
            username = 'deleted_' || id || '_' || username,
            dni      = 'deleted_' || id || '_' || dni
        WHERE status = 'Inactivo'
          AND email NOT LIKE 'deleted\\_%' ESCAPE '\\'
    """))


def downgrade():
    pass

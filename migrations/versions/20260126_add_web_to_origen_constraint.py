"""Add web to origen constraint

Revision ID: n7o8p9q1r2s3
Revises: m6n7o8p9q1r2
Create Date: 2026-01-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n7o8p9q1r2s3'
down_revision = 'm6n7o8p9q1r2'
branch_labels = None
depends_on = None


def upgrade():
    # Actualizar constraint de origen para incluir 'web'
    op.drop_constraint('check_operation_origen', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('sistema', 'plataforma', 'app', 'web')"
    )


def downgrade():
    # Revertir constraint de origen (eliminar 'web')
    op.drop_constraint('check_operation_origen', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('sistema', 'plataforma', 'app')"
    )

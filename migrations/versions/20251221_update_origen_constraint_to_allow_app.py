"""Update origen constraint to allow app

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2025-12-21 17:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p8q9r0s1t2u3'
down_revision = 'o7p8q9r0s1t2'
branch_labels = None
depends_on = None


def upgrade():
    # Drop old constraint that only allows 'sistema' and 'plataforma'
    op.drop_constraint('check_operation_origen', 'operations', type_='check')

    # Create new constraint that also allows 'app'
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('sistema', 'plataforma', 'app')"
    )


def downgrade():
    # Revert to old constraint (only 'sistema' and 'plataforma')
    op.drop_constraint('check_operation_origen', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('sistema', 'plataforma')"
    )

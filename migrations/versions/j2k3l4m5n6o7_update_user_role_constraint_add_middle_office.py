"""Update user role constraint add middle office

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2025-12-02 03:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j2k3l4m5n6o7'
down_revision = 'i1j2k3l4m5n6'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the old constraint
    op.drop_constraint('check_user_role', 'users', type_='check')

    # Create the new constraint with Middle Office included
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador', 'Middle Office')"
    )


def downgrade():
    # Drop the new constraint
    op.drop_constraint('check_user_role', 'users', type_='check')

    # Recreate the old constraint
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador')"
    )

"""Make operations.user_id nullable for mobile app

This migration makes the user_id column in operations table nullable.
This is required because mobile app clients create their own operations
and they do NOT have entries in the users table (users table is only
for internal staff: admin, operator, trader, etc.).

- user_id = NULL → Operation created from mobile app by client
- user_id = <id> → Operation created manually by internal staff
- origen field identifies the channel: 'app', 'sistema', 'plataforma', 'web'

Revision ID: 20260221_make_operation_user_id_nullable
Revises: 20260126_add_web_to_origen_constraint
Create Date: 2026-02-21
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o8p9q1r2s3t4'
down_revision = 'n7o8p9q1r2s3'
branch_labels = None
depends_on = None


def upgrade():
    """
    Make user_id nullable in operations table
    """
    # Hacer nullable el campo user_id
    op.alter_column('operations', 'user_id',
                    existing_type=sa.Integer(),
                    nullable=True)


def downgrade():
    """
    Revert user_id back to NOT NULL
    WARNING: This will fail if there are any NULL values in user_id
    """
    # Revertir a NOT NULL (puede fallar si hay NULLs)
    op.alter_column('operations', 'user_id',
                    existing_type=sa.Integer(),
                    nullable=False)

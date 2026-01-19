"""add referral system to clients

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-01-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k3l4m5n6o7p8'
down_revision = 'j2k3l4m5n6o7'

def upgrade():
    # Add referral system columns to clients table
    op.add_column('clients', sa.Column('referral_code', sa.String(length=6), nullable=True))
    op.add_column('clients', sa.Column('used_referral_code', sa.String(length=6), nullable=True))
    op.add_column('clients', sa.Column('referred_by', sa.Integer(), nullable=True))

    # Create unique index on referral_code
    op.create_index(op.f('ix_clients_referral_code'), 'clients', ['referral_code'], unique=True)

    # Create foreign key constraint
    op.create_foreign_key('fk_clients_referred_by', 'clients', 'clients', ['referred_by'], ['id'])


def downgrade():
    # Drop foreign key and columns
    op.drop_constraint('fk_clients_referred_by', 'clients', type_='foreignkey')
    op.drop_index(op.f('ix_clients_referral_code'), table_name='clients')
    op.drop_column('clients', 'referred_by')
    op.drop_column('clients', 'used_referral_code')
    op.drop_column('clients', 'referral_code')

"""add bank_balances table

Revision ID: add_bank_balances
Revises: add_trader_goals_profits
Create Date: 2025-11-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_bank_balances'
down_revision = 'add_notes_read_by'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla bank_balances
    op.create_table('bank_balances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bank_name', sa.String(length=50), nullable=False),
        sa.Column('balance_usd', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('balance_pen', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.CheckConstraint('balance_usd >= 0', name='check_balance_usd_positive'),
        sa.CheckConstraint('balance_pen >= 0', name='check_balance_pen_positive'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bank_name', name='uq_bank_name')
    )
    op.create_index(op.f('ix_bank_balances_bank_name'), 'bank_balances', ['bank_name'], unique=False)

    # Insertar bancos iniciales
    op.execute("""
        INSERT INTO bank_balances (bank_name, balance_usd, balance_pen) VALUES
        ('BCP', 0, 0),
        ('BBVA', 0, 0),
        ('INTERBANK', 0, 0),
        ('SCOTIABANK', 0, 0),
        ('PICHINCHA', 0, 0),
        ('BANBIF', 0, 0)
    """)


def downgrade():
    op.drop_index(op.f('ix_bank_balances_bank_name'), table_name='bank_balances')
    op.drop_table('bank_balances')

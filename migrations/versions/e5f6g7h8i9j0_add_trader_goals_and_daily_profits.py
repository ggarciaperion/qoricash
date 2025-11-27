"""add trader_goals and trader_daily_profits tables

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2025-11-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla trader_goals
    op.create_table('trader_goals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('goal_amount_pen', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.CheckConstraint('month >= 1 AND month <= 12', name='check_month_valid'),
        sa.CheckConstraint('goal_amount_pen >= 0', name='check_goal_positive'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'month', 'year', name='uq_trader_month_year')
    )
    op.create_index('idx_trader_goals_user_id', 'trader_goals', ['user_id'], unique=False)
    op.create_index('idx_trader_goals_month_year', 'trader_goals', ['month', 'year'], unique=False)

    # Crear tabla trader_daily_profits
    op.create_table('trader_daily_profits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('profit_date', sa.Date(), nullable=False),
        sa.Column('profit_amount_pen', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'profit_date', name='uq_trader_profit_date')
    )
    op.create_index('idx_trader_daily_profits_user_id', 'trader_daily_profits', ['user_id'], unique=False)
    op.create_index('idx_trader_daily_profits_date', 'trader_daily_profits', ['profit_date'], unique=False)


def downgrade():
    # Eliminar tabla trader_daily_profits
    op.drop_index('idx_trader_daily_profits_date', table_name='trader_daily_profits')
    op.drop_index('idx_trader_daily_profits_user_id', table_name='trader_daily_profits')
    op.drop_table('trader_daily_profits')

    # Eliminar tabla trader_goals
    op.drop_index('idx_trader_goals_month_year', table_name='trader_goals')
    op.drop_index('idx_trader_goals_user_id', table_name='trader_goals')
    op.drop_table('trader_goals')

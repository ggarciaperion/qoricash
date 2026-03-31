"""Accounting module phase 1: accounts, periods, journal entries, expenses

Revision ID: a1b2c3d4e5f6
Revises: p7q8r9s0
Create Date: 2026-03-31

Tables created:
  - accounting_accounts    (catálogo PCGE)
  - accounting_periods     (períodos mensuales)
  - journal_entries        (libro diario — cabecera)
  - journal_entry_lines    (libro diario — líneas/partidas)
  - expense_records        (registro de gastos)
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'p7q8r9s0'
branch_labels = None
depends_on = None


def upgrade():
    # ── accounting_accounts ───────────────────────────────────────────────────
    op.create_table(
        'accounting_accounts',
        sa.Column('id',          sa.Integer(),     nullable=False),
        sa.Column('code',        sa.String(10),    nullable=False),
        sa.Column('name',        sa.String(120),   nullable=False),
        sa.Column('type',        sa.String(20),    nullable=False),
        sa.Column('nature',      sa.String(10),    nullable=False),
        sa.Column('currency',    sa.String(5),     server_default='PEN'),
        sa.Column('is_active',   sa.Boolean(),     server_default=sa.text('true')),
        sa.Column('parent_code', sa.String(10),    nullable=True),
        sa.Column('created_at',  sa.DateTime(),    server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_accounting_accounts_code'),
    )
    op.create_index('idx_aa_code', 'accounting_accounts', ['code'])

    # ── accounting_periods ────────────────────────────────────────────────────
    op.create_table(
        'accounting_periods',
        sa.Column('id',        sa.Integer(),  nullable=False),
        sa.Column('year',      sa.Integer(),  nullable=False),
        sa.Column('month',     sa.Integer(),  nullable=False),
        sa.Column('status',    sa.String(20), server_default='abierto'),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('closed_by', sa.Integer(),  nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', 'month', name='uq_accounting_period_year_month'),
        sa.ForeignKeyConstraint(['closed_by'], ['users.id'], name='fk_ap_closed_by'),
    )

    # ── journal_entries ───────────────────────────────────────────────────────
    op.create_table(
        'journal_entries',
        sa.Column('id',             sa.Integer(),      nullable=False),
        sa.Column('entry_number',   sa.String(20),     nullable=False),
        sa.Column('period_id',      sa.Integer(),      nullable=False),
        sa.Column('entry_date',     sa.Date(),         nullable=False),
        sa.Column('description',    sa.Text(),         nullable=False),
        sa.Column('entry_type',     sa.String(30),     nullable=False),
        sa.Column('source_type',    sa.String(30),     nullable=True),
        sa.Column('source_id',      sa.Integer(),      nullable=True),
        sa.Column('total_debe',     sa.Numeric(18, 2), nullable=False),
        sa.Column('total_haber',    sa.Numeric(18, 2), nullable=False),
        sa.Column('status',         sa.String(20),     server_default='activo'),
        sa.Column('created_by',     sa.Integer(),      nullable=True),
        sa.Column('created_at',     sa.DateTime(),     server_default=sa.text('NOW()')),
        sa.Column('annulled_at',    sa.DateTime(),     nullable=True),
        sa.Column('annulled_by',    sa.Integer(),      nullable=True),
        sa.Column('annulled_reason', sa.Text(),        nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entry_number', name='uq_journal_entries_number'),
        sa.ForeignKeyConstraint(['period_id'], ['accounting_periods.id'], name='fk_je_period'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],  name='fk_je_created_by'),
        sa.ForeignKeyConstraint(['annulled_by'], ['users.id'], name='fk_je_annulled_by'),
    )
    op.create_index('idx_je_period_date',  'journal_entries', ['period_id', 'entry_date'])
    op.create_index('idx_je_source',       'journal_entries', ['source_type', 'source_id'])
    op.create_index('idx_je_entry_number', 'journal_entries', ['entry_number'])

    # ── journal_entry_lines ───────────────────────────────────────────────────
    op.create_table(
        'journal_entry_lines',
        sa.Column('id',               sa.Integer(),      nullable=False),
        sa.Column('journal_entry_id', sa.Integer(),      nullable=False),
        sa.Column('account_code',     sa.String(10),     nullable=False),
        sa.Column('description',      sa.Text(),         nullable=True),
        sa.Column('debe',             sa.Numeric(18, 2), server_default='0'),
        sa.Column('haber',            sa.Numeric(18, 2), server_default='0'),
        sa.Column('currency',         sa.String(5),      server_default='PEN'),
        sa.Column('amount_usd',       sa.Numeric(18, 2), nullable=True),
        sa.Column('exchange_rate',    sa.Numeric(10, 4), nullable=True),
        sa.Column('line_order',       sa.Integer(),      nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['journal_entry_id'], ['journal_entries.id'],
            name='fk_jel_journal_entry', ondelete='CASCADE'
        ),
    )
    op.create_index('idx_jel_entry',   'journal_entry_lines', ['journal_entry_id'])
    op.create_index('idx_jel_account', 'journal_entry_lines', ['account_code'])

    # ── expense_records ───────────────────────────────────────────────────────
    op.create_table(
        'expense_records',
        sa.Column('id',                 sa.Integer(),      nullable=False),
        sa.Column('period_id',          sa.Integer(),      nullable=False),
        sa.Column('expense_date',       sa.Date(),         nullable=False),
        sa.Column('category',           sa.String(50),     nullable=False),
        sa.Column('description',        sa.Text(),         nullable=False),
        sa.Column('amount_pen',         sa.Numeric(18, 2), nullable=False),
        sa.Column('amount_usd',         sa.Numeric(18, 2), nullable=True),
        sa.Column('exchange_rate_used', sa.Numeric(10, 4), nullable=True),
        sa.Column('voucher_type',       sa.String(30),     nullable=True),
        sa.Column('voucher_number',     sa.String(50),     nullable=True),
        sa.Column('supplier_ruc',       sa.String(20),     nullable=True),
        sa.Column('supplier_name',      sa.String(120),    nullable=True),
        sa.Column('voucher_url',        sa.Text(),         nullable=True),
        sa.Column('journal_entry_id',   sa.Integer(),      nullable=True),
        sa.Column('created_by',         sa.Integer(),      nullable=True),
        sa.Column('created_at',         sa.DateTime(),     server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['period_id'],        ['accounting_periods.id'], name='fk_er_period'),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id'],    name='fk_er_journal_entry'),
        sa.ForeignKeyConstraint(['created_by'],       ['users.id'],              name='fk_er_created_by'),
    )
    op.create_index('idx_er_period', 'expense_records', ['period_id', 'expense_date'])


def downgrade():
    op.drop_index('idx_er_period',    table_name='expense_records')
    op.drop_table('expense_records')
    op.drop_index('idx_jel_account',  table_name='journal_entry_lines')
    op.drop_index('idx_jel_entry',    table_name='journal_entry_lines')
    op.drop_table('journal_entry_lines')
    op.drop_index('idx_je_entry_number', table_name='journal_entries')
    op.drop_index('idx_je_source',    table_name='journal_entries')
    op.drop_index('idx_je_period_date', table_name='journal_entries')
    op.drop_table('journal_entries')
    op.drop_table('accounting_periods')
    op.drop_index('idx_aa_code',      table_name='accounting_accounts')
    op.drop_table('accounting_accounts')

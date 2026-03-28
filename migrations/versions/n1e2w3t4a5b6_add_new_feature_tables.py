"""Add new feature tables: sanctions, fx_monitor, market

Revision ID: n1e2w3t4a5b6
Revises: 85a767945dcc
Create Date: 2026-03-27

NOTA: Esta migración usa IF NOT EXISTS (via inspector) para ser
segura en producción donde las tablas base ya existen.
Las nuevas tablas son: sanctions_entries, fx_competitors,
fx_rate_history, fx_rate_current, fx_change_events,
market_snapshots, macro_indicators, market_news, market_signals,
economic_events, daily_analyses
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'n1e2w3t4a5b6'
down_revision = '85a767945dcc'
branch_labels = None
depends_on = None


def _table_exists(conn, table_name):
    return table_name in inspect(conn).get_table_names()


def upgrade():
    conn = op.get_bind()

    # ── sanctions_entries ─────────────────────────────────────────────────────
    if not _table_exists(conn, 'sanctions_entries'):
        op.create_table(
            'sanctions_entries',
            sa.Column('id',              sa.Integer,     primary_key=True),
            sa.Column('source',          sa.String(20),  nullable=False),
            sa.Column('entity_type',     sa.String(20)),
            sa.Column('uid',             sa.String(100)),
            sa.Column('name',            sa.String(400), nullable=False),
            sa.Column('name_normalized', sa.String(400)),
            sa.Column('aliases_json',    sa.Text),
            sa.Column('nationality',     sa.String(100)),
            sa.Column('program',         sa.String(300)),
            sa.Column('loaded_at',       sa.DateTime),
        )
        op.create_index('ix_sanctions_entries_source',          'sanctions_entries', ['source'])
        op.create_index('ix_sanctions_entries_name_normalized', 'sanctions_entries', ['name_normalized'])

    # ── fx_competitors ────────────────────────────────────────────────────────
    if not _table_exists(conn, 'fx_competitors'):
        op.create_table(
            'fx_competitors',
            sa.Column('id',           sa.Integer,     primary_key=True),
            sa.Column('slug',         sa.String(50),  unique=True, nullable=False),
            sa.Column('name',         sa.String(100), nullable=False),
            sa.Column('website',      sa.String(255), nullable=False),
            sa.Column('scraper_type', sa.String(20),  server_default='requests'),
            sa.Column('is_active',    sa.Boolean,     server_default=sa.text('true')),
            sa.Column('created_at',   sa.DateTime),
        )

    # ── fx_rate_history ───────────────────────────────────────────────────────
    if not _table_exists(conn, 'fx_rate_history'):
        op.create_table(
            'fx_rate_history',
            sa.Column('id',            sa.Integer,      primary_key=True, autoincrement=True),
            sa.Column('competitor_id', sa.Integer,      sa.ForeignKey('fx_competitors.id'), nullable=False),
            sa.Column('buy_rate',      sa.Numeric(8,4), nullable=False),
            sa.Column('sell_rate',     sa.Numeric(8,4), nullable=False),
            sa.Column('scraped_at',    sa.DateTime,     nullable=False),
            sa.Column('response_ms',   sa.Integer),
            sa.Column('error',         sa.String(255)),
        )
        op.create_index('idx_fx_history_competitor_time', 'fx_rate_history', ['competitor_id', 'scraped_at'])

    # ── fx_rate_current ───────────────────────────────────────────────────────
    if not _table_exists(conn, 'fx_rate_current'):
        op.create_table(
            'fx_rate_current',
            sa.Column('competitor_id',  sa.Integer,      sa.ForeignKey('fx_competitors.id'), primary_key=True),
            sa.Column('buy_rate',       sa.Numeric(8,4), nullable=False),
            sa.Column('sell_rate',      sa.Numeric(8,4), nullable=False),
            sa.Column('prev_buy_rate',  sa.Numeric(8,4)),
            sa.Column('prev_sell_rate', sa.Numeric(8,4)),
            sa.Column('updated_at',     sa.DateTime,     nullable=False),
            sa.Column('scrape_ok',      sa.Boolean,      server_default=sa.text('true')),
        )

    # ── fx_change_events ──────────────────────────────────────────────────────
    if not _table_exists(conn, 'fx_change_events'):
        op.create_table(
            'fx_change_events',
            sa.Column('id',             sa.Integer,      primary_key=True, autoincrement=True),
            sa.Column('competitor_id',  sa.Integer,      sa.ForeignKey('fx_competitors.id'), nullable=False),
            sa.Column('field',          sa.String(10),   nullable=False),
            sa.Column('old_buy',        sa.Numeric(8,4)),
            sa.Column('new_buy',        sa.Numeric(8,4)),
            sa.Column('old_sell',       sa.Numeric(8,4)),
            sa.Column('new_sell',       sa.Numeric(8,4)),
            sa.Column('buy_delta',      sa.Numeric(8,4)),
            sa.Column('sell_delta',     sa.Numeric(8,4)),
            sa.Column('buy_delta_pct',  sa.Numeric(6,3)),
            sa.Column('sell_delta_pct', sa.Numeric(6,3)),
            sa.Column('detected_at',    sa.DateTime),
            sa.Column('alert_sent',     sa.Boolean, server_default=sa.text('false')),
        )

    # ── market_snapshots ──────────────────────────────────────────────────────
    if not _table_exists(conn, 'market_snapshots'):
        op.create_table(
            'market_snapshots',
            sa.Column('id',                sa.Integer,       primary_key=True),
            sa.Column('captured_at',       sa.DateTime,      nullable=False),
            sa.Column('usdpen',            sa.Numeric(8,4)),
            sa.Column('usdpen_prev',       sa.Numeric(8,4)),
            sa.Column('usdpen_chg_pct',    sa.Numeric(6,3)),
            sa.Column('gold',              sa.Numeric(10,2)),
            sa.Column('gold_prev',         sa.Numeric(10,2)),
            sa.Column('gold_chg_pct',      sa.Numeric(6,3)),
            sa.Column('oil',               sa.Numeric(8,2)),
            sa.Column('oil_prev',          sa.Numeric(8,2)),
            sa.Column('oil_chg_pct',       sa.Numeric(6,3)),
            sa.Column('sp500',             sa.Numeric(10,2)),
            sa.Column('sp500_prev',        sa.Numeric(10,2)),
            sa.Column('sp500_chg_pct',     sa.Numeric(6,3)),
            sa.Column('nasdaq',            sa.Numeric(10,2)),
            sa.Column('nasdaq_prev',       sa.Numeric(10,2)),
            sa.Column('nasdaq_chg_pct',    sa.Numeric(6,3)),
            sa.Column('dxy',               sa.Numeric(8,3)),
            sa.Column('dxy_prev',          sa.Numeric(8,3)),
            sa.Column('dxy_chg_pct',       sa.Numeric(6,3)),
            sa.Column('vix',               sa.Numeric(8,2)),
            sa.Column('vix_prev',          sa.Numeric(8,2)),
            sa.Column('vix_chg_pct',       sa.Numeric(6,3)),
            sa.Column('copper',            sa.Numeric(8,4)),
            sa.Column('copper_prev',       sa.Numeric(8,4)),
            sa.Column('copper_chg_pct',    sa.Numeric(6,3)),
            sa.Column('treasury_10y',      sa.Numeric(6,3)),
            sa.Column('treasury_10y_prev', sa.Numeric(6,3)),
            sa.Column('treasury_10y_chg',  sa.Numeric(6,3)),
            sa.Column('eurusd',            sa.Numeric(8,4)),
            sa.Column('eurusd_prev',       sa.Numeric(8,4)),
            sa.Column('eurusd_chg_pct',    sa.Numeric(6,3)),
            sa.Column('eem',               sa.Numeric(8,2)),
            sa.Column('eem_prev',          sa.Numeric(8,2)),
            sa.Column('eem_chg_pct',       sa.Numeric(6,3)),
            sa.Column('epu',               sa.Numeric(8,2)),
            sa.Column('epu_prev',          sa.Numeric(8,2)),
            sa.Column('epu_chg_pct',       sa.Numeric(6,3)),
            sa.Column('usdjpy',            sa.Numeric(8,3)),
            sa.Column('usdjpy_prev',       sa.Numeric(8,3)),
            sa.Column('usdjpy_chg_pct',    sa.Numeric(6,3)),
            sa.Column('btc',               sa.Numeric(12,2)),
            sa.Column('btc_prev',          sa.Numeric(12,2)),
            sa.Column('btc_chg_pct',       sa.Numeric(6,3)),
        )
        op.create_index('idx_market_snap_time', 'market_snapshots', ['captured_at'])

    # ── macro_indicators ──────────────────────────────────────────────────────
    if not _table_exists(conn, 'macro_indicators'):
        op.create_table(
            'macro_indicators',
            sa.Column('id',          sa.Integer,       primary_key=True),
            sa.Column('key',         sa.String(50),    unique=True, nullable=False),
            sa.Column('label',       sa.String(100)),
            sa.Column('value',       sa.Numeric(12,4)),
            sa.Column('prev_value',  sa.Numeric(12,4)),
            sa.Column('unit',        sa.String(20)),
            sa.Column('period',      sa.String(30)),
            sa.Column('source',      sa.String(50)),
            sa.Column('direction',   sa.String(10)),
            sa.Column('updated_at',  sa.DateTime),
            sa.Column('notes',       sa.String(200)),
        )

    # ── market_news ───────────────────────────────────────────────────────────
    if not _table_exists(conn, 'market_news'):
        op.create_table(
            'market_news',
            sa.Column('id',              sa.Integer,      primary_key=True),
            sa.Column('fetched_at',      sa.DateTime,     nullable=False),
            sa.Column('source',          sa.String(80)),
            sa.Column('source_country',  sa.String(2)),
            sa.Column('title',           sa.String(300),  nullable=False),
            sa.Column('summary',         sa.Text),
            sa.Column('url',             sa.String(500)),
            sa.Column('published_at',    sa.DateTime),
            sa.Column('impact_level',    sa.String(10),   server_default='low'),
            sa.Column('direction',       sa.String(20),   server_default='neutral'),
            sa.Column('sentiment_score', sa.Numeric(4,2), server_default='0'),
            sa.Column('url_hash',        sa.String(32),   unique=True),
        )
        op.create_index('idx_news_fetched', 'market_news', ['fetched_at'])
        op.create_index('idx_news_impact',  'market_news', ['impact_level'])

    # ── market_signals ────────────────────────────────────────────────────────
    if not _table_exists(conn, 'market_signals'):
        op.create_table(
            'market_signals',
            sa.Column('id',           sa.Integer,  primary_key=True),
            sa.Column('generated_at', sa.DateTime, nullable=False),
            sa.Column('signal_type',  sa.String(20), nullable=False),
            sa.Column('confidence',   sa.Integer,  server_default='0'),
            sa.Column('title',        sa.String(200)),
            sa.Column('reasoning',    sa.Text),
            sa.Column('triggered_by', sa.Text),
        )

    # ── economic_events ───────────────────────────────────────────────────────
    if not _table_exists(conn, 'economic_events'):
        op.create_table(
            'economic_events',
            sa.Column('id',          sa.Integer,    primary_key=True),
            sa.Column('event_key',   sa.String(32), unique=True, nullable=False),
            sa.Column('event_date',  sa.DateTime,   nullable=False),
            sa.Column('country',     sa.String(10)),
            sa.Column('flag',        sa.String(10)),
            sa.Column('event_name',  sa.String(250)),
            sa.Column('impact',      sa.String(10)),
            sa.Column('actual',      sa.String(30)),
            sa.Column('forecast',    sa.String(30)),
            sa.Column('previous',    sa.String(30)),
            sa.Column('source',      sa.String(50),  server_default='ForexFactory'),
            sa.Column('fetched_at',  sa.DateTime),
        )
        op.create_index('idx_events_date', 'economic_events', ['event_date'])

    # ── daily_analyses ────────────────────────────────────────────────────────
    if not _table_exists(conn, 'daily_analyses'):
        op.create_table(
            'daily_analyses',
            sa.Column('id',                   sa.Integer,  primary_key=True),
            sa.Column('analysis_date',        sa.Date,     nullable=False),
            sa.Column('generated_at',         sa.DateTime, nullable=False),
            sa.Column('trend',                sa.String(10), nullable=False),
            sa.Column('confidence',           sa.Integer,  server_default='0'),
            sa.Column('title',                sa.String(300)),
            sa.Column('summary',              sa.Text),
            sa.Column('key_factors',          sa.Text),
            sa.Column('news_analyzed',        sa.Integer,  server_default='0'),
            sa.Column('bullish_signals',      sa.Integer,  server_default='0'),
            sa.Column('bearish_signals',      sa.Integer,  server_default='0'),
            sa.Column('net_score',            sa.Integer,  server_default='0'),
            sa.Column('is_extraordinary',     sa.Boolean,  server_default=sa.text('false')),
            sa.Column('extraordinary_reason', sa.String(300)),
            sa.Column('is_active',            sa.Boolean,  server_default=sa.text('true')),
        )
        op.create_index('idx_daily_analysis_date', 'daily_analyses', ['analysis_date'])


def downgrade():
    op.drop_table('daily_analyses')
    op.drop_table('economic_events')
    op.drop_table('market_signals')
    op.drop_table('market_news')
    op.drop_table('macro_indicators')
    op.drop_table('market_snapshots')
    op.drop_table('fx_change_events')
    op.drop_table('fx_rate_current')
    op.drop_table('fx_rate_history')
    op.drop_table('fx_competitors')
    op.drop_table('sanctions_entries')

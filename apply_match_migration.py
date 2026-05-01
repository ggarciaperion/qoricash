"""
Script de migración directa para accounting_matches profit split.
Ejecutar una sola vez en Render: python3 apply_match_migration.py
"""
from app import create_app
from app.extensions import db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('accounting_matches')]

    added = []
    with db.engine.begin() as conn:
        if 'buy_base_rate' not in columns:
            conn.execute(text('ALTER TABLE accounting_matches ADD COLUMN buy_base_rate NUMERIC(10,4)'))
            added.append('buy_base_rate')
        if 'sell_base_rate' not in columns:
            conn.execute(text('ALTER TABLE accounting_matches ADD COLUMN sell_base_rate NUMERIC(10,4)'))
            added.append('sell_base_rate')
        if 'trader_buy_profit_pen' not in columns:
            conn.execute(text('ALTER TABLE accounting_matches ADD COLUMN trader_buy_profit_pen NUMERIC(15,2)'))
            added.append('trader_buy_profit_pen')
        if 'trader_sell_profit_pen' not in columns:
            conn.execute(text('ALTER TABLE accounting_matches ADD COLUMN trader_sell_profit_pen NUMERIC(15,2)'))
            added.append('trader_sell_profit_pen')
        if 'house_profit_pen' not in columns:
            conn.execute(text('ALTER TABLE accounting_matches ADD COLUMN house_profit_pen NUMERIC(15,2)'))
            added.append('house_profit_pen')
        if 'match_type' not in columns:
            conn.execute(text("ALTER TABLE accounting_matches ADD COLUMN match_type VARCHAR(20) DEFAULT 'client_to_client'"))
            added.append('match_type')

    if added:
        print(f'Columnas agregadas: {", ".join(added)}')
    else:
        print('Todas las columnas ya existían.')

    # Stamp alembic
    from flask_migrate import stamp
    stamp(revision='m1a2t3c4h5p6')
    print('Migración m1a2t3c4h5p6 aplicada correctamente.')

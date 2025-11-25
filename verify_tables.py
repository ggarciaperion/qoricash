"""
Script para verificar que las tablas trader_goals y trader_daily_profits existen
"""
import os
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///qoricash.db'

from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)

    print("\n=== VERIFICACIÓN DE TABLAS ===\n")

    # Verificar trader_goals
    if 'trader_goals' in inspector.get_table_names():
        print("[OK] Tabla 'trader_goals' existe")
        columns = [col['name'] for col in inspector.get_columns('trader_goals')]
        print(f"  Columnas: {columns}")
    else:
        print("[ERROR] Tabla 'trader_goals' NO existe")

    print()

    # Verificar trader_daily_profits
    if 'trader_daily_profits' in inspector.get_table_names():
        print("[OK] Tabla 'trader_daily_profits' existe")
        columns = [col['name'] for col in inspector.get_columns('trader_daily_profits')]
        print(f"  Columnas: {columns}")
    else:
        print("[ERROR] Tabla 'trader_daily_profits' NO existe")

    print("\n=== TODAS LAS TABLAS ===")
    print(inspector.get_table_names())

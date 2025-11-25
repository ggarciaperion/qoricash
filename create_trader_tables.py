"""
Script para crear las tablas trader_goals y trader_daily_profits
Ejecutar: python create_trader_tables.py
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Si no hay DATABASE_URL, usar SQLite
if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///qoricash.db'
    print("Usando SQLite local: qoricash.db")

from app import create_app
from app.extensions import db
from sqlalchemy import text, inspect

app = create_app()

def create_trader_tables():
    with app.app_context():
        print("\nCreando tablas trader_goals y trader_daily_profits...")
        print(f"URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'No configurada')}\n")

        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        print(f"Tablas existentes: {existing_tables}\n")

        # Crear tabla trader_goals
        if 'trader_goals' in existing_tables:
            print("[INFO] Tabla 'trader_goals' ya existe")
        else:
            try:
                sql = """
                CREATE TABLE trader_goals (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
                    year INTEGER NOT NULL,
                    goal_amount_pen NUMERIC(15, 2) NOT NULL DEFAULT 0 CHECK (goal_amount_pen >= 0),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER REFERENCES users(id),
                    CONSTRAINT uq_trader_month_year UNIQUE (user_id, month, year)
                );
                """
                db.session.execute(text(sql))

                # Crear índices
                db.session.execute(text("CREATE INDEX idx_trader_goals_user_id ON trader_goals(user_id);"))
                db.session.execute(text("CREATE INDEX idx_trader_goals_month_year ON trader_goals(month, year);"))

                db.session.commit()
                print("[OK] Tabla 'trader_goals' creada correctamente")
            except Exception as e:
                db.session.rollback()
                print(f"[ERROR] Error al crear 'trader_goals': {e}")

        # Crear tabla trader_daily_profits
        if 'trader_daily_profits' in existing_tables:
            print("[INFO] Tabla 'trader_daily_profits' ya existe")
        else:
            try:
                sql = """
                CREATE TABLE trader_daily_profits (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    profit_date DATE NOT NULL,
                    profit_amount_pen NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER REFERENCES users(id),
                    CONSTRAINT uq_trader_profit_date UNIQUE (user_id, profit_date)
                );
                """
                db.session.execute(text(sql))

                # Crear índices
                db.session.execute(text("CREATE INDEX idx_trader_daily_profits_user_id ON trader_daily_profits(user_id);"))
                db.session.execute(text("CREATE INDEX idx_trader_daily_profits_date ON trader_daily_profits(profit_date);"))

                db.session.commit()
                print("[OK] Tabla 'trader_daily_profits' creada correctamente")
            except Exception as e:
                db.session.rollback()
                print(f"[ERROR] Error al crear 'trader_daily_profits': {e}")

        print("\n[OK] Proceso de creación de tablas completado")
        print("\nReinicia el servidor para aplicar los cambios.")

if __name__ == '__main__':
    create_trader_tables()

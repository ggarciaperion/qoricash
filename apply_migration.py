"""
Script one-shot: aplica las columnas y tabla fixed_assets directamente via SQLAlchemy.
Ejecutar en Render: python3 apply_migration.py
Se puede borrar después.
"""
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        with conn.begin():
            # 1. Columnas nuevas en expense_records
            conn.execute(text("""
                ALTER TABLE expense_records
                ADD COLUMN IF NOT EXISTS base_pen NUMERIC(18,2),
                ADD COLUMN IF NOT EXISTS igv_pen NUMERIC(18,2),
                ADD COLUMN IF NOT EXISTS credito_fiscal BOOLEAN DEFAULT false,
                ADD COLUMN IF NOT EXISTS expense_type VARCHAR(20) DEFAULT 'servicio'
            """))
            print("expense_records: columnas OK")

            # 2. Tabla fixed_assets
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS fixed_assets (
                    id SERIAL PRIMARY KEY,
                    asset_code VARCHAR(20) UNIQUE NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    category VARCHAR(30) NOT NULL,
                    account_code VARCHAR(10) NOT NULL,
                    deprec_account VARCHAR(10) NOT NULL,
                    acquisition_date DATE NOT NULL,
                    cost_pen NUMERIC(18,2) NOT NULL,
                    residual_value NUMERIC(18,2) DEFAULT 0,
                    useful_life_months INTEGER NOT NULL,
                    monthly_depreciation NUMERIC(18,4) NOT NULL,
                    months_depreciated INTEGER DEFAULT 0,
                    accumulated_depreciation NUMERIC(18,2) DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'activo',
                    baja_date DATE,
                    baja_notes TEXT,
                    expense_record_id INTEGER REFERENCES expense_records(id),
                    created_by INTEGER REFERENCES users(id),
                    created_at TIMESTAMP
                )
            """))
            print("fixed_assets: tabla OK")

    print("Migracion aplicada correctamente.")

"""
Aplica la migración de nuevos campos en accounting_periods directamente
con SQLAlchemy (sin necesidad de correr flask db upgrade).

Seguro de ejecutar múltiples veces (verifica existencia de columnas antes).

Ejecutar en Render shell: python3 run_migracion_period.py
"""
from app import create_app
from app.extensions import db

app = create_app()

COLUMNS_TO_ADD = [
    ('tc_sbs_cierre', 'NUMERIC(10,4)'),
    ('reopened_at',   'TIMESTAMP'),
    ('reopened_by',   'INTEGER'),
    ('reopen_reason', 'VARCHAR(500)'),
]

with app.app_context():
    engine = db.engine

    with engine.connect() as conn:
        # Detectar columnas existentes
        from sqlalchemy import text, inspect as sa_inspect
        inspector = sa_inspect(engine)
        existing_cols = {c['name'] for c in inspector.get_columns('accounting_periods')}
        print(f'Columnas actuales en accounting_periods: {sorted(existing_cols)}')

        added = []
        for col_name, col_type in COLUMNS_TO_ADD:
            if col_name not in existing_cols:
                sql = text(f'ALTER TABLE accounting_periods ADD COLUMN {col_name} {col_type}')
                conn.execute(sql)
                conn.commit()
                added.append(col_name)
                print(f'  ✓ Columna añadida: {col_name} {col_type}')
            else:
                print(f'  – {col_name}: ya existe, omitida')

        print()
        if added:
            print(f'Migración completada. Columnas añadidas: {added}')
        else:
            print('Nada que migrar — todas las columnas ya existían.')

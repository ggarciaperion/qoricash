"""
Agrega la columna bank_account_code a expense_records.

Permite registrar gastos bancarios (ITF, comisiones, mantenimiento) con cargo
directo a la cuenta bancaria PCGE (104x) en lugar de crear cuenta por pagar.

Ejecutar en Render shell: python3 agregar_bank_account_code_gasto.py
"""
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    from sqlalchemy import text, inspect as sa_inspect

    inspector = sa_inspect(db.engine)
    cols = {c['name'] for c in inspector.get_columns('expense_records')}

    if 'bank_account_code' in cols:
        print('Columna bank_account_code ya existe en expense_records. Nada que hacer.')
    else:
        with db.engine.connect() as conn:
            conn.execute(text(
                'ALTER TABLE expense_records ADD COLUMN bank_account_code VARCHAR(10)'
            ))
            conn.commit()
        print('Columna bank_account_code agregada a expense_records.')

    print()
    print('Desde ahora, al registrar un gasto bancario (ITF, comision, mantenimiento)')
    print('se puede seleccionar el banco que cargó el gasto.')
    print('El asiento generado sera: DEBE 6xxx / HABER 104x (cargo directo al banco).')
    print('Esto hace que el Libro Caja y Bancos refleje correctamente estos debitos.')

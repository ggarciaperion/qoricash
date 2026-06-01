"""
Crea la tabla bank_balance_history y, opcionalmente, siembra el snapshot
actual de BankBalance para que el Libro Caja y Bancos tenga saldo inicial
desde el día de hoy.

Seguro de ejecutar múltiples veces (verifica existencia de la tabla primero).

Ejecutar en Render shell: python3 crear_tabla_balance_history.py
"""
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    from sqlalchemy import text, inspect as sa_inspect
    from app.utils.formatters import now_peru

    engine = db.engine
    inspector = sa_inspect(engine)
    existing_tables = inspector.get_table_names()

    # ── 1. Crear tabla si no existe ───────────────────────────────────────────
    if 'bank_balance_history' in existing_tables:
        print('Tabla bank_balance_history ya existe.')
    else:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE bank_balance_history (
                    id                  SERIAL PRIMARY KEY,
                    snapshot_date       DATE        NOT NULL,
                    bank_name           VARCHAR(100) NOT NULL,
                    balance_usd         NUMERIC(15,2) NOT NULL DEFAULT 0,
                    balance_pen         NUMERIC(15,2) NOT NULL DEFAULT 0,
                    initial_balance_usd NUMERIC(15,2) NOT NULL DEFAULT 0,
                    initial_balance_pen NUMERIC(15,2) NOT NULL DEFAULT 0,
                    updated_by          INTEGER REFERENCES users(id),
                    updated_at          TIMESTAMP,
                    CONSTRAINT uq_bbh_date_bank UNIQUE (snapshot_date, bank_name)
                )
            """))
            conn.execute(text(
                'CREATE INDEX ix_bbh_snapshot_date ON bank_balance_history (snapshot_date)'
            ))
            conn.execute(text(
                'CREATE INDEX ix_bbh_bank_name ON bank_balance_history (bank_name)'
            ))
            conn.commit()
        print('Tabla bank_balance_history creada con indices.')

    # ── 2. Sembrar snapshot del dia desde BankBalance actual ──────────────────
    from app.models.bank_balance import BankBalance
    from app.models.bank_balance_history import BankBalanceHistory

    today = now_peru().date()
    banks = BankBalance.query.all()

    if not banks:
        print('No hay registros en BankBalance. Nada que sembrar.')
    else:
        sembrados = 0
        omitidos  = 0
        for b in banks:
            existing = BankBalanceHistory.query.filter_by(
                snapshot_date=today, bank_name=b.bank_name
            ).first()
            if existing:
                omitidos += 1
            else:
                db.session.add(BankBalanceHistory(
                    snapshot_date       = today,
                    bank_name           = b.bank_name,
                    balance_usd         = float(b.balance_usd or 0),
                    balance_pen         = float(b.balance_pen or 0),
                    initial_balance_usd = float(b.initial_balance_usd or 0),
                    initial_balance_pen = float(b.initial_balance_pen or 0),
                    updated_by          = b.updated_by,
                    updated_at          = now_peru(),
                ))
                sembrados += 1

        db.session.commit()
        print(f'Snapshots sembrados hoy ({today}): {sembrados} nuevos, {omitidos} ya existian.')

    print()
    print('Desde ahora, cada actualizacion en el modulo Posicion')
    print('guardara un snapshot diario que alimentara el Libro Caja y Bancos.')

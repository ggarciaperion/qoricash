"""
Registra el ingreso operativo de mayo 2026 por diferencia de cambio (spread).
S/1,518.04 = ganancia acumulada por amarre de operaciones (dashboard mayo).

El spread está físicamente en las cuentas bancarias (1041 BCP PEN).
Este asiento lo separa y lo reconoce explícitamente como ingreso en P&L.

Ejecutar en Render shell: python3 registrar_ingreso_mayo.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal
from datetime import date

app = create_app()

SPREAD_MAYO = Decimal('1518.04')

with app.app_context():
    from app.models.accounting_account import AccountingAccount
    from app.models.accounting_period import AccountingPeriod
    from app.services.accounting.journal_service import JournalService
    from app.models.user import User

    master = User.query.filter_by(role='Master').first()
    if not master:
        print('ERROR: No se encontro usuario Master.')
        exit(1)

    # Asegurar que exista la cuenta de ingreso
    if not AccountingAccount.query.filter_by(code='7591').first():
        db.session.add(AccountingAccount(
            code='7591',
            name='Ingresos por diferencia de cambio – operaciones',
            type='ingreso',
            nature='acreedora',
            currency='PEN',
            parent_code='75',
        ))
        db.session.commit()
        print('Cuenta 7591 creada.')

    # Reabrir mayo temporalmente
    periodo = AccountingPeriod.query.filter_by(year=2026, month=5).first()
    if not periodo:
        print('ERROR: No existe periodo mayo 2026.')
        exit(1)

    status_original = periodo.status
    if status_original == 'cerrado':
        periodo.status = 'abierto'
        db.session.commit()
        print('Periodo mayo reabierto.')

    entry = JournalService.create_entry(
        entry_type='manual',
        description='Ingreso por spread FX mayo 2026 — ganancia acumulada por amarre de operaciones',
        lines=[
            {
                'account_code': '1041',
                'description': 'BCP PEN — reconocimiento spread operativo mayo',
                'debe': SPREAD_MAYO,
                'haber': Decimal('0'),
                'currency': 'PEN',
            },
            {
                'account_code': '7591',
                'description': 'Ingresos diferencia de cambio — spread operativo mayo',
                'debe': Decimal('0'),
                'haber': SPREAD_MAYO,
                'currency': 'PEN',
            },
        ],
        source_type='manual',
        entry_date=date(2026, 5, 31),
        created_by=master.id,
    )

    if entry:
        print('Asiento creado: {} | DEBE={} HABER={}'.format(
            entry.entry_number, entry.total_debe, entry.total_haber
        ))
    else:
        print('ERROR al crear asiento.')
        if status_original == 'cerrado':
            periodo.status = 'cerrado'
            db.session.commit()
        exit(1)

    # Volver a cerrar
    if status_original == 'cerrado':
        periodo.status = 'cerrado'
        db.session.commit()
        print('Periodo mayo cerrado nuevamente.')

    print('\nEstado de Resultados mayo ahora deberia mostrar:')
    print('  Ingresos: S/{}'.format(SPREAD_MAYO))

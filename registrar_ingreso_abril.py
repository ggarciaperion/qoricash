"""
Registra el ingreso operativo de abril 2026 por diferencia de cambio (spread).

Calcula el spread acumulado real sumando profit_pen de todos los amarres activos
de operaciones completadas en abril 2026 — la misma fuente que usa el dashboard.

Ejecutar en Render shell: python3 registrar_ingreso_abril.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal
from datetime import date

app = create_app()

with app.app_context():
    from app.models.accounting_account import AccountingAccount
    from app.models.accounting_period import AccountingPeriod
    from app.models.accounting_match import AccountingMatch
    from app.models.journal_entry import JournalEntry
    from app.models.operation import Operation
    from app.services.accounting.journal_service import JournalService
    from app.models.user import User
    from sqlalchemy import extract, func

    master = User.query.filter_by(role='Master').first()
    if not master:
        print('ERROR: No se encontro usuario Master.')
        exit(1)

    # ── Verificar que no haya ya un asiento de ingreso manual en abril ────────
    periodo = AccountingPeriod.query.filter_by(year=2026, month=4).first()
    if not periodo:
        print('ERROR: No existe periodo abril 2026.')
        exit(1)

    print(f'Periodo abril 2026: id={periodo.id} status={periodo.status}')

    # Verificar si ya existe un asiento de ingresos FX en abril
    from app.models.journal_entry_line import JournalEntryLine
    existing_income = (
        db.session.query(JournalEntry)
        .join(JournalEntryLine, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .filter(
            JournalEntry.period_id == periodo.id,
            JournalEntryLine.account_code.in_(['7591', '7711', '7761']),
            JournalEntryLine.haber > 0,
            JournalEntry.status == 'activo',
        )
        .first()
    )
    if existing_income:
        print(f'Ya existe asiento de ingreso en abril: {existing_income.entry_number}')
        print('Si deseas registrar otro, comenta este bloque. Abortando.')
        exit(0)

    # ── Calcular spread de abril desde amarres ─────────────────────────────────
    # Operaciones completadas en abril 2026
    ops_abril = db.session.query(Operation.id).filter(
        Operation.status == 'Completada',
        extract('year',  Operation.completed_at) == 2026,
        extract('month', Operation.completed_at) == 4,
    ).subquery()

    # Suma de profit_pen de matches activos de esas operaciones
    total_buy = db.session.query(
        func.sum(AccountingMatch.profit_pen)
    ).filter(
        AccountingMatch.status == 'Activo',
        AccountingMatch.buy_operation_id.in_(ops_abril),
    ).scalar() or Decimal('0')

    total_sell = db.session.query(
        func.sum(AccountingMatch.profit_pen)
    ).filter(
        AccountingMatch.status == 'Activo',
        AccountingMatch.sell_operation_id.in_(ops_abril),
    ).scalar() or Decimal('0')

    # profit_pen se almacena en el lado compra del match; evitar doble conteo
    spread_abril = Decimal(str(total_buy))
    print(f'Spread calculado desde amarres abril (buy-side): S/{spread_abril:.2f}')
    print(f'  (sell-side para referencia: S/{Decimal(str(total_sell)):.2f})')

    if spread_abril <= 0:
        print('El spread de abril es 0 o negativo. Verifica los amarres.')
        print('Amarres activos de abril:')
        matches = (
            db.session.query(AccountingMatch)
            .filter(
                AccountingMatch.status == 'Activo',
                AccountingMatch.buy_operation_id.in_(ops_abril),
            ).all()
        )
        for m in matches:
            print(f'  Match {m.id}: profit_pen={m.profit_pen}')
        exit(1)

    # ── Asegurar que exista cuenta 7591 ───────────────────────────────────────
    if not AccountingAccount.query.filter_by(code='7591').first():
        db.session.add(AccountingAccount(
            code='7591',
            name='Ingresos por diferencia de cambio — operaciones',
            type='ingreso',
            nature='acreedora',
            currency='PEN',
            parent_code='75',
        ))
        db.session.commit()
        print('Cuenta 7591 creada.')

    # ── Reabrir abril temporalmente ───────────────────────────────────────────
    status_original = periodo.status
    if status_original == 'cerrado':
        periodo.status = 'abierto'
        db.session.commit()
        print('Periodo abril reabierto temporalmente.')

    entry = JournalService.create_entry(
        entry_type='manual',
        description='Ingreso por spread FX abril 2026 — ganancia acumulada por amarre de operaciones',
        lines=[
            {
                'account_code': '1041',
                'description':  'BCP PEN — reconocimiento spread operativo abril',
                'debe':  spread_abril,
                'haber': Decimal('0'),
                'currency': 'PEN',
            },
            {
                'account_code': '7591',
                'description':  'Ingresos diferencia de cambio — spread operativo abril',
                'debe':  Decimal('0'),
                'haber': spread_abril,
                'currency': 'PEN',
            },
        ],
        source_type='manual',
        entry_date=date(2026, 4, 30),
        created_by=master.id,
    )

    if entry:
        print(f'Asiento creado: {entry.entry_number} | DEBE={entry.total_debe} HABER={entry.total_haber}')
    else:
        print('ERROR al crear asiento.')
        if status_original == 'cerrado':
            periodo.status = 'cerrado'
            db.session.commit()
        exit(1)

    # ── Volver a cerrar ────────────────────────────────────────────────────────
    if status_original == 'cerrado':
        periodo.status = 'cerrado'
        db.session.commit()
        print('Periodo abril cerrado nuevamente.')

    print()
    print('Estado de Resultados abril ahora deberia mostrar:')
    print(f'  Ingresos 7591: S/{spread_abril:.2f}')

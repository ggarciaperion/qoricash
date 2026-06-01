"""
Dos correcciones en mayo 2026:

1. Renombra cuenta 6391 y agrega cuentas PCGE correctas para gastos operativos.
2. Revierte AS-2026-0113 (ajuste FX fantasma S/9,704.39):
   El servicio calcula gain = (USD_BankBalance × TC) - valor_libro_journal.
   La diferencia no es ganancia real de TC sino brecha por saldos iniciales
   incompletos — igual que el caso de abril que ya fue revertido.

Ejecutar en Render shell: python3 fix_mayo_cuentas_fx.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal
from datetime import date

app = create_app()

with app.app_context():
    from app.models.accounting_account import AccountingAccount
    from app.models.accounting_period import AccountingPeriod
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.services.accounting.journal_service import JournalService
    from app.models.user import User

    master = User.query.filter_by(role='Master').first()
    if not master:
        print('ERROR: No se encontro usuario Master.')
        exit(1)

    # ── 1. Fix de cuentas contables ───────────────────────────────────────────
    print('=' * 60)
    print('1. ACTUALIZACION DE CUENTAS PCGE')
    print('=' * 60)

    # Renombrar 6391 — estaba como "Comisiones bancarias / ITF", ahora genérica
    c6391 = AccountingAccount.query.filter_by(code='6391').first()
    if c6391:
        c6391.name = 'Otros gastos de servicios'
        print('  6391 renombrada -> "Otros gastos de servicios"')
    else:
        db.session.add(AccountingAccount(
            code='6391', name='Otros gastos de servicios',
            type='gasto', nature='deudora', currency='PEN', parent_code='63'
        ))
        print('  6391 creada -> "Otros gastos de servicios"')

    # Cuentas PCGE para futuros gastos operativos
    nuevas = [
        ('6311', 'Arrendamiento de inmuebles',       'gasto', 'deudora', '63'),
        ('6317', 'Servicios de limpieza',             'gasto', 'deudora', '63'),
        ('6321', 'Alimentos y bebidas',               'gasto', 'deudora', '63'),
        ('6363', 'Servicios de comunicaciones',       'gasto', 'deudora', '63'),
        ('6331', 'Otros servicios de terceros',       'gasto', 'deudora', '63'),
    ]
    for code, name, typ, nat, parent in nuevas:
        if not AccountingAccount.query.filter_by(code=code).first():
            db.session.add(AccountingAccount(
                code=code, name=name, type=typ, nature=nat,
                currency='PEN', parent_code=parent
            ))
            print('  {} creada -> "{}"'.format(code, name))
        else:
            print('  {} ya existe'.format(code))

    db.session.commit()

    # ── 2. Revertir ajuste FX mayo AS-2026-0113 ───────────────────────────────
    print('\n' + '=' * 60)
    print('2. REVERSION AJUSTE FX MAYO (AS-2026-0113)')
    print('=' * 60)

    entry_fx = JournalEntry.query.filter_by(entry_number='AS-2026-0113').first()
    if not entry_fx:
        print('  ERROR: No se encontro AS-2026-0113')
        exit(1)

    print('  Asiento: {} | DEBE={} HABER={}'.format(
        entry_fx.entry_number, entry_fx.total_debe, entry_fx.total_haber
    ))

    lineas = JournalEntryLine.query.filter_by(journal_entry_id=entry_fx.id).all()
    for l in lineas:
        print('    {} | DEBE={} HABER={} | {}'.format(
            l.account_code, l.debe, l.haber, l.description[:50]
        ))

    # Reabrir mayo temporalmente
    periodo_mayo = AccountingPeriod.query.filter_by(year=2026, month=5).first()
    if not periodo_mayo:
        print('  ERROR: No existe periodo mayo 2026')
        exit(1)

    status_original = periodo_mayo.status
    if status_original == 'cerrado':
        periodo_mayo.status = 'abierto'
        db.session.commit()
        print('\n  Periodo mayo reabierto temporalmente.')

    # Construir reverso
    lineas_reverso = []
    for l in lineas:
        lineas_reverso.append({
            'account_code': l.account_code,
            'description':  'Reversión {} — ajuste FX fantasma (sin base real)'.format(
                entry_fx.entry_number),
            'debe':  l.haber,
            'haber': l.debe,
            'currency': 'PEN',
        })

    reverso = JournalService.create_entry(
        entry_type='manual',
        description='Reversión {} — ajuste FX mayo sin base de TC real'.format(
            entry_fx.entry_number),
        lines=lineas_reverso,
        source_type='manual',
        entry_date=date(2026, 5, 31),
        created_by=master.id,
    )

    if reverso:
        print('  Reversión creada: {} | DEBE={} HABER={}'.format(
            reverso.entry_number, reverso.total_debe, reverso.total_haber
        ))
    else:
        print('  ERROR al crear reversión.')
        if status_original == 'cerrado':
            periodo_mayo.status = 'cerrado'
            db.session.commit()
        exit(1)

    # Volver a cerrar mayo
    if status_original == 'cerrado':
        periodo_mayo.status = 'cerrado'
        db.session.commit()
        print('  Periodo mayo cerrado nuevamente.')

    print('\n' + '=' * 60)
    print('RESULTADO ESPERADO EN ESTADO DE RESULTADOS MAYO:')
    print('  7761 Ganancia FX         -> S/ 0.00 (eliminada)')
    print('  6391 Otros gastos serv.  -> S/ 1,092 (renombrada, mismos montos)')
    print('  Ingresos mayo            -> operativos reales solamente')
    print('=' * 60)

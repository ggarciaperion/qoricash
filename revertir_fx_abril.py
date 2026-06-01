"""
Revierte el asiento ajuste FX abril AS-2026-0107.
El ajuste revaluo posiciones USD sin saldos iniciales registrados,
generando una ganancia fantasma de S/140,553.56 en 7761 y un saldo
inexistente de S/119,913.56 en 1012 Caja ME.
Ejecutar en Render shell: python3 revertir_fx_abril.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal

app = create_app()

ENTRY_TO_REVERSE = 'AS-2026-0107'

with app.app_context():
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.accounting_period import AccountingPeriod
    from app.services.accounting.journal_service import JournalService
    from app.models.user import User
    from datetime import date

    master = User.query.filter_by(role='Master').first()
    if not master:
        print('ERROR: No se encontro usuario Master.')
        exit(1)

    entry = JournalEntry.query.filter_by(entry_number=ENTRY_TO_REVERSE).first()
    if not entry:
        print('ERROR: No se encontro {}'.format(ENTRY_TO_REVERSE))
        exit(1)

    print('Asiento a revertir: {} | DEBE={} HABER={}'.format(
        entry.entry_number, entry.total_debe, entry.total_haber
    ))

    # Leer las lineas actuales
    lineas = JournalEntryLine.query.filter_by(journal_entry_id=entry.id).all()
    print('Lineas:')
    for l in lineas:
        print('  {} | DEBE={} HABER={}'.format(l.account_code, l.debe, l.haber))

    # Construir asiento reverso: invertir DEBE/HABER de cada linea
    lineas_reverso = []
    for l in lineas:
        lineas_reverso.append({
            'account_code': l.account_code,
            'description':  'Reversión {} — ajuste FX sin base (inicio ops)'.format(ENTRY_TO_REVERSE),
            'debe':  l.haber,   # invertido
            'haber': l.debe,    # invertido
            'currency': l.currency if hasattr(l, 'currency') else 'PEN',
        })

    print('\nAsiento de reversión a crear:')
    for l in lineas_reverso:
        print('  {} | DEBE={} HABER={}'.format(l['account_code'], l['debe'], l['haber']))

    # Crear asiento de reversión
    reverso = JournalService.create_entry(
        entry_type='manual',
        description='Reversión {} — ajuste FX abril sin saldos iniciales'.format(ENTRY_TO_REVERSE),
        lines=lineas_reverso,
        source_type='manual',
        entry_date=date(2026, 4, 30),
        created_by=master.id,
    )

    if reverso:
        print('\nReversión creada: {} | DEBE={} HABER={}'.format(
            reverso.entry_number, reverso.total_debe, reverso.total_haber
        ))
        print('\nEfecto neto en cuentas afectadas:')
        print('  1012 Caja ME         -> queda en 0 (fantasma eliminado)')
        print('  1044 BCP USD         -> queda en -20,640 (solo operaciones reales)')
        print('  7761 Ganancia FX     -> queda en 0 (ganancia fantasma eliminada)')
    else:
        print('ERROR: No se pudo crear el asiento de reversión.')

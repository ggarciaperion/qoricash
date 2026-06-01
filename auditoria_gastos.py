"""
Auditoría de cuentas de gasto sospechosas de duplicación.
Analiza 6391, 6791 (ITF) y 7761 (ganancia FX) en abril y mayo.
Ejecutar en Render shell: python3 auditoria_gastos.py
"""
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.accounting_period import AccountingPeriod

    CUENTAS = ['6391', '6791', '6711', '6591', '7761']

    for año, mes, nombre in [(2026, 4, 'ABRIL'), (2026, 5, 'MAYO')]:
        periodo = AccountingPeriod.query.filter_by(year=año, month=mes).first()
        if not periodo:
            print('No existe periodo {}'.format(nombre))
            continue

        print('\n' + '=' * 70)
        print('PERIODO {} — id={} status={}'.format(nombre, periodo.id, periodo.status))
        print('=' * 70)

        for cuenta in CUENTAS:
            lineas = (
                db.session.query(JournalEntryLine, JournalEntry)
                .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
                .filter(JournalEntry.period_id == periodo.id)
                .filter(JournalEntryLine.account_code == cuenta)
                .order_by(JournalEntry.entry_number)
                .all()
            )
            if not lineas:
                continue

            total = sum(l.debe - l.haber for l, _ in lineas)
            print('\n  Cuenta {} — {} lineas — SALDO: {:.2f}'.format(cuenta, len(lineas), total))
            for l, e in lineas:
                importe = l.debe if l.debe > 0 else -l.haber
                print('    {} | {} | tipo={} | {:.2f} | {}'.format(
                    e.entry_number,
                    e.entry_date,
                    e.entry_type,
                    importe,
                    l.description[:55],
                ))

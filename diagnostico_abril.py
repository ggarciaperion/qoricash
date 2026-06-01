"""
Diagnostico contable abril 2026.
Ejecutar en Render shell: python3 diagnostico_abril.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal

app = create_app()

with app.app_context():
    from app.models.accounting_period import AccountingPeriod
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.accounting_account import AccountingAccount

    # ── 1. Estado del periodo ──────────────────────────────────────────────────
    periodo = AccountingPeriod.query.filter_by(year=2026, month=4).first()
    if not periodo:
        print('ERROR: No existe periodo abril 2026.')
        exit(1)
    print('=' * 60)
    print('PERIODO ABRIL 2026 — status: {}'.format(periodo.status))
    print('=' * 60)

    # ── 2. Resumen de asientos ─────────────────────────────────────────────────
    entries = JournalEntry.query.filter_by(period_id=periodo.id).order_by(JournalEntry.entry_number).all()
    print('\nTOTAL ASIENTOS: {}'.format(len(entries)))

    tipos = {}
    for e in entries:
        tipos[e.entry_type] = tipos.get(e.entry_type, 0) + 1
    for t, n in sorted(tipos.items()):
        print('  {} : {}'.format(t.ljust(20), n))

    # ── 3. Verificar cuadre (DEBE = HABER) por asiento ────────────────────────
    descuadrados = []
    for e in entries:
        diff = abs(e.total_debe - e.total_haber)
        if diff > Decimal('0.02'):
            descuadrados.append((e.entry_number, e.total_debe, e.total_haber, diff))

    print('\nASIENTOS DESCUADRADOS: {}'.format(len(descuadrados)))
    for en, d, h, diff in descuadrados:
        print('  {} | DEBE={} HABER={} | DIFF={}'.format(en, d, h, diff))

    # ── 4. Saldos por cuenta (solo cuentas con movimiento en abril) ───────────
    print('\nSALDOS POR CUENTA (abril):')
    print('{:<8} {:<40} {:>14} {:>14} {:>14}'.format('Cuenta', 'Nombre', 'DEBE', 'HABER', 'SALDO'))
    print('-' * 92)

    from sqlalchemy import func
    lines = (
        db.session.query(
            JournalEntryLine.account_code,
            func.sum(JournalEntryLine.debe).label('total_debe'),
            func.sum(JournalEntryLine.haber).label('total_haber'),
        )
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .filter(JournalEntry.period_id == periodo.id)
        .group_by(JournalEntryLine.account_code)
        .order_by(JournalEntryLine.account_code)
        .all()
    )

    cuentas_banco = ['1041', '1044', '1047', '1048', '1049', '1050']
    cuentas_caja  = ['1011', '1012', '1013']
    alertas = []

    for row in lines:
        code  = row.account_code
        debe  = row.total_debe  or Decimal('0')
        haber = row.total_haber or Decimal('0')
        saldo = debe - haber

        acc = AccountingAccount.query.filter_by(code=code).first()
        nombre = acc.name[:38] if acc else '(sin nombre)'

        # Flag saldos que llaman la atencion
        flag = ''
        if code in cuentas_banco + cuentas_caja:
            if abs(saldo) > Decimal('100000'):
                flag = ' ⚠ IMPORTE ALTO'
            if saldo < Decimal('-1000') and code in cuentas_banco:
                flag = ' ⚠ SALDO NEGATIVO BANCO'

        print('{:<8} {:<40} {:>14.2f} {:>14.2f} {:>14.2f}{}'.format(
            code, nombre, debe, haber, saldo, flag
        ))
        if flag:
            alertas.append((code, nombre, saldo, flag))

    # ── 5. Cuentas bancarias sin movimiento en abril ───────────────────────────
    codigos_con_mv = {row.account_code for row in lines}
    sin_mv = [c for c in cuentas_banco if c not in codigos_con_mv]
    if sin_mv:
        print('\nCUENTAS BANCARIAS SIN MOVIMIENTO EN ABRIL: {}'.format(sin_mv))

    # ── 6. Resumen final ───────────────────────────────────────────────────────
    total_debe_periodo  = sum(e.total_debe  for e in entries)
    total_haber_periodo = sum(e.total_haber for e in entries)
    print('\n' + '=' * 60)
    print('SUMA TOTAL PERIODO')
    print('  DEBE  : {:>14.2f}'.format(total_debe_periodo))
    print('  HABER : {:>14.2f}'.format(total_haber_periodo))
    print('  DIFF  : {:>14.2f}'.format(abs(total_debe_periodo - total_haber_periodo)))
    if abs(total_debe_periodo - total_haber_periodo) <= Decimal('0.05'):
        print('  >> PERIODO CUADRADO OK')
    else:
        print('  >> ATENCION: PERIODO DESCUADRADO')

    if alertas:
        print('\nALERTAS:')
        for code, nombre, saldo, msg in alertas:
            print('  {} {} | saldo={:.2f} {}'.format(code, nombre, saldo, msg))
    else:
        print('\nSin alertas de importes grotescos.')

    print('=' * 60)

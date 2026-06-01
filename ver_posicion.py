"""
Muestra saldos reales de BankBalance (posicion) vs saldos contables abril.
Ejecutar en Render shell: python3 ver_posicion.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal

app = create_app()

with app.app_context():
    from app.models.bank_balance import BankBalance
    from app.config.bank_accounts import QORICASH_ACCOUNTS

    print('=' * 65)
    print('POSICION REAL (BankBalance)')
    print('=' * 65)
    print('{:<30} {:>14} {:>14}'.format('Banco', 'USD', 'PEN'))
    print('-' * 65)

    balances = BankBalance.query.order_by(BankBalance.bank_name).all()
    total_usd = Decimal('0')
    total_pen = Decimal('0')
    for b in balances:
        print('{:<30} {:>14.2f} {:>14.2f}  [ini USD={:.2f} PEN={:.2f}]'.format(
            b.bank_name,
            b.balance_usd,
            b.balance_pen,
            b.initial_balance_usd,
            b.initial_balance_pen,
        ))
        total_usd += b.balance_usd
        total_pen += b.balance_pen

    print('-' * 65)
    print('{:<30} {:>14.2f} {:>14.2f}'.format('TOTAL', total_usd, total_pen))

    print('\n' + '=' * 65)
    print('CUENTAS CONTABLES ABRIL (saldo del periodo)')
    print('=' * 65)

    from sqlalchemy import func
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.journal_entry import JournalEntry
    from app.models.accounting_period import AccountingPeriod
    from app.models.accounting_account import AccountingAccount

    periodo = AccountingPeriod.query.filter_by(year=2026, month=4).first()
    cuentas_bancarias = ['1011', '1012', '1013', '1041', '1044', '1047', '1048', '1049', '1050']

    lines = (
        db.session.query(
            JournalEntryLine.account_code,
            func.sum(JournalEntryLine.debe).label('total_debe'),
            func.sum(JournalEntryLine.haber).label('total_haber'),
        )
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .filter(JournalEntry.period_id == periodo.id)
        .filter(JournalEntryLine.account_code.in_(cuentas_bancarias))
        .group_by(JournalEntryLine.account_code)
        .order_by(JournalEntryLine.account_code)
        .all()
    )

    print('{:<8} {:<30} {:>14}'.format('Cuenta', 'Nombre', 'SALDO'))
    print('-' * 55)
    for row in lines:
        acc = AccountingAccount.query.filter_by(code=row.account_code).first()
        nombre = acc.name[:28] if acc else '(sin nombre)'
        saldo = (row.total_debe or Decimal('0')) - (row.total_haber or Decimal('0'))
        print('{:<8} {:<30} {:>14.2f}'.format(row.account_code, nombre, saldo))

    print('=' * 65)

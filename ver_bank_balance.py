"""
Muestra el estado actual de todos los saldos en BankBalance.
Uso: python3 ver_bank_balance.py
"""
from app import create_app
from app.extensions import db
from app.models.bank_balance import BankBalance

app = create_app()

with app.app_context():
    banks = BankBalance.query.order_by(BankBalance.bank_name).all()

    print()
    print(f"{'='*72}")
    print(f"  ESTADO ACTUAL — BankBalance ({len(banks)} cuentas)")
    print(f"{'='*72}")
    print(f"  {'Cuenta':<40} {'USD actual':>12} {'PEN actual':>12}")
    print(f"  {'USD inicial':>53} {'PEN inicial':>12}")
    print(f"  {'-'*68}")

    for b in banks:
        print(f"  {b.bank_name:<40} {float(b.balance_usd):>12,.2f} {float(b.balance_pen):>12,.2f}")
        print(f"  {'(inicial)':>40} {float(b.initial_balance_usd):>12,.2f} {float(b.initial_balance_pen):>12,.2f}")
        print()

    total_usd = sum(float(b.balance_usd) for b in banks)
    total_pen = sum(float(b.balance_pen) for b in banks)
    print(f"  {'─'*68}")
    print(f"  {'TOTAL':>40} {total_usd:>12,.2f} {total_pen:>12,.2f}")
    print(f"{'='*72}")
    print()

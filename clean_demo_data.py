"""
Script para limpiar todos los datos demo de QoriCash.

Elimina (en orden seguro de FK):
  - accounting_matches
  - accounting_batches
  - invoices
  - audit_logs
  - trader_daily_profits
  - operations
  - client_risk_profiles
  - complaints
  - reward_codes
  - clients

NO toca: users, bank_balances, exchange_rates, risk_levels, compliance_rules, trader_goals

Ejecutar en Render Shell:
  python clean_demo_data.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db


def clean_demo_data():
    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("LIMPIEZA DE DATOS DEMO — QoriCash")
        print("Se conservan: users, bank_balances, exchange_rates, risk_levels,")
        print("              compliance_rules, trader_goals")
        print("=" * 70)

        steps = [
            ("accounting_matches",    "AccountingMatch"),
            ("accounting_batches",    "AccountingBatch"),
            ("invoices",              "Invoice"),
            ("audit_logs",            "AuditLog"),
            ("trader_daily_profits",  "TraderDailyProfit"),
            ("operations",            "Operation"),
            ("client_risk_profiles",  "ClientRiskProfile"),
            ("complaints",            "Complaint"),
            ("reward_codes",          "RewardCode"),
            ("clients",               "Client"),
        ]

        total = 0

        for table, model_name in steps:
            try:
                result = db.session.execute(
                    db.text(f"DELETE FROM {table}")
                )
                count = result.rowcount
                db.session.flush()
                print(f"  ✓  {table:<30} {count} registros eliminados")
                total += count
            except Exception as e:
                db.session.rollback()
                print(f"  ✗  {table:<30} ERROR: {e}")
                raise

        db.session.commit()

        print("=" * 70)
        print(f"✓  Limpieza completada — {total} registros eliminados en total")
        print("=" * 70)


if __name__ == "__main__":
    try:
        clean_demo_data()
    except Exception as e:
        print(f"\n✗ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

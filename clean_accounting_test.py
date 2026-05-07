"""
Script para eliminar registros de test de Amarre y Neteo (accounting_matches / accounting_batches).

Ejecutar desde Render Shell:
  python clean_accounting_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db


def clean_accounting_test():
    app = create_app()

    with app.app_context():
        from app.models import AccountingMatch, AccountingBatch

        matches = AccountingMatch.query.order_by(AccountingMatch.id).all()
        batches = AccountingBatch.query.order_by(AccountingBatch.id).all()

        print("=" * 60)
        print("REGISTROS EN AMARRE Y NETEO (producción)")
        print("=" * 60)

        if not matches and not batches:
            print("  No hay registros. Nada que eliminar.")
            return

        print(f"\n  accounting_matches ({len(matches)} registros):")
        for m in matches:
            buy_op  = m.buy_operation.operation_id  if m.buy_operation  else '?'
            sell_op = m.sell_operation.operation_id if m.sell_operation else '?'
            print(f"    ID={m.id} | {buy_op} <-> {sell_op} | ${m.matched_amount_usd} | {m.created_at}")

        print(f"\n  accounting_batches ({len(batches)} registros):")
        for b in batches:
            print(f"    ID={b.id} | code={b.batch_code} | profit={b.total_profit_pen} | matches={b.num_matches} | {b.created_at}")

        print("\n" + "=" * 60)
        confirm = input("¿Eliminar TODOS estos registros? (escribe SI para confirmar): ").strip().upper()
        if confirm != "SI":
            print("Cancelado.")
            return

        # Primero matches (FK a batches), luego batches
        match_count = AccountingMatch.query.delete()
        batch_count = AccountingBatch.query.delete()
        db.session.commit()

        print(f"\n✓  {match_count} match(es) eliminado(s)")
        print(f"✓  {batch_count} batch(es) eliminado(s)")
        print("Listo.")


if __name__ == "__main__":
    try:
        clean_accounting_test()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

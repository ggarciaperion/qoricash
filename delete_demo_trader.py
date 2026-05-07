"""
Script para eliminar DEFINITIVAMENTE el usuario demo_trader y TODOS sus datos.

Ejecutar desde Render Shell:
  python delete_demo_trader.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db


def delete_demo_trader():
    app = create_app()

    with app.app_context():
        from app.models.user import User
        from app.models.operation import Operation
        from app.models.client import Client
        from app.models import AccountingMatch, AccountingBatch
        from app.models.audit_log import AuditLog
        from app.models.reward_code import RewardCode

        demo = User.query.filter_by(username='demo_trader').first()
        if not demo:
            print("✓  Usuario demo_trader no existe. Nada que hacer.")
            return

        print("=" * 65)
        print(f"ELIMINAR DEMO TRADER — ID={demo.id}  username={demo.username}")
        print("=" * 65)

        ops        = Operation.query.filter_by(user_id=demo.id).all()
        op_ids     = [o.id for o in ops]
        clients    = Client.query.filter_by(created_by=demo.id).all()
        client_ids = [c.id for c in clients]

        matches_buy  = AccountingMatch.query.filter(AccountingMatch.buy_operation_id.in_(op_ids)).all()  if op_ids else []
        matches_sell = AccountingMatch.query.filter(AccountingMatch.sell_operation_id.in_(op_ids)).all() if op_ids else []
        all_match_ids = list({m.id for m in matches_buy + matches_sell})
        batch_ids_affected = list({m.batch_id for m in matches_buy + matches_sell if m.batch_id})

        print(f"\n  Operaciones del demo:         {len(ops)}")
        print(f"  Clientes del demo:            {len(clients)}")
        print(f"  Amarres que referencian demo: {len(all_match_ids)}")
        print(f"  Batches afectados:            {len(batch_ids_affected)}")

        print("\n" + "=" * 65)
        confirm = input("¿Eliminar TODO + el usuario? (escribe SI): ").strip().upper()
        if confirm != "SI":
            print("Cancelado.")
            return

        # 1. Eliminar matches
        if all_match_ids:
            AccountingMatch.query.filter(AccountingMatch.id.in_(all_match_ids)).delete(synchronize_session=False)
            print(f"  ✓  {len(all_match_ids)} amarre(s) eliminado(s)")

        # 2. Batches vacíos
        for bid in batch_ids_affected:
            remaining = AccountingMatch.query.filter_by(batch_id=bid).count()
            if remaining == 0:
                AccountingBatch.query.filter_by(id=bid).delete()
                print(f"  ✓  Batch ID={bid} eliminado")
            else:
                print(f"  ~  Batch ID={bid} conservado ({remaining} matches restantes)")

        # 3. Audit logs
        audit_count = AuditLog.query.filter_by(user_id=demo.id).delete()
        print(f"  ✓  {audit_count} audit_log(s) eliminado(s)")

        # 4. Reward codes
        reward_count = RewardCode.query.filter_by(user_id=demo.id).delete()
        print(f"  ✓  {reward_count} reward_code(s) eliminado(s)")

        # 5. Operaciones del demo
        op_count = Operation.query.filter_by(user_id=demo.id).delete(synchronize_session=False)
        print(f"  ✓  {op_count} operación(es) eliminada(s)")

        # 6. Operaciones de clientes del demo creadas por otros usuarios
        if client_ids:
            extra = Operation.query.filter(
                Operation.client_id.in_(client_ids),
                Operation.user_id != demo.id
            ).delete(synchronize_session=False)
            if extra:
                print(f"  ✓  {extra} operación(es) extra de clientes demo eliminada(s)")

        # 7. Clientes del demo
        client_count = Client.query.filter_by(created_by=demo.id).delete(synchronize_session=False)
        print(f"  ✓  {client_count} cliente(s) eliminado(s)")

        # 8. Usuario
        db.session.delete(demo)
        print(f"  ✓  Usuario demo_trader eliminado")

        db.session.commit()
        print("\n✅ Listo. demo_trader y todos sus datos han sido eliminados.")


if __name__ == "__main__":
    try:
        delete_demo_trader()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        sys.exit(1)

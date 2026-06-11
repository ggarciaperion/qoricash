"""
Script de reparación: re-genera BankMovements para operaciones Completadas
que no tienen movimientos en la tabla bank_movements.

Uso:
  python3 reparar_bank_movements.py              → modo DRY RUN (solo reporta)
  python3 reparar_bank_movements.py --apply      → aplica los cambios

Opera contra la base de datos de producción (DATABASE_URL en env).
"""

import os
import sys

DRY_RUN = '--apply' not in sys.argv

os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
app = create_app()

with app.app_context():
    from app.extensions import db
    from app.models.operation import Operation
    from app.models.bank_movement import BankMovement
    from app.models.bank_balance import BankBalance

    # Operaciones Completadas específicamente reportadas
    TARGET_IDS = ['EXP-551', 'EXP-549']

    # También buscar todas las ops Completadas sin BankMovement asociado
    all_completed = Operation.query.filter_by(status='Completada').all()

    ops_sin_movimiento = []
    for op in all_completed:
        count = BankMovement.query.filter_by(
            source_type='operation',
            operation_id=op.id
        ).count()
        if count == 0:
            ops_sin_movimiento.append(op)

    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Operaciones Completadas sin BankMovement: {len(ops_sin_movimiento)}")
    print()

    for op in ops_sin_movimiento:
        prioridad = '*** ' if op.operation_id in TARGET_IDS else ''
        print(f"{prioridad}  {op.operation_id} — {op.operation_type} "
              f"USD {op.amount_usd} / PEN {op.amount_pen} — {op.completed_at}")
        deps = op.client_deposits or []
        pays = op.client_payments or []
        for d in deps:
            print(f"      depósito: qc_bank={d.get('qc_bank')!r}  "
                  f"cuenta_cargo={d.get('cuenta_cargo')!r}  importe={d.get('importe')}")
        for p in pays:
            print(f"      pago:     qc_bank={p.get('qc_bank')!r}  "
                  f"cuenta_destino={p.get('cuenta_destino')!r}  importe={p.get('importe')}")

    if not DRY_RUN and ops_sin_movimiento:
        print()
        print("Aplicando BankBalance.apply_operation() para cada operación...")
        ok = 0
        fail = 0
        for op in ops_sin_movimiento:
            try:
                BankBalance.apply_operation(op)
                ok += 1
                print(f"  ✓ {op.operation_id}")
            except Exception as e:
                fail += 1
                print(f"  ✗ {op.operation_id}: {e}")
                try:
                    db.session.rollback()
                except Exception:
                    pass
        print()
        print(f"Resultado: {ok} reparadas, {fail} fallidas")
    elif DRY_RUN:
        print()
        print("Modo DRY RUN — usa --apply para aplicar los cambios.")

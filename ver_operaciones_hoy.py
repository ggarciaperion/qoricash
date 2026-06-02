"""
Muestra todas las operaciones de hoy con detalle de bancos.
Uso: python3 ver_operaciones_hoy.py
"""
from app import create_app
from app.extensions import db
from app.models.operation import Operation
from app.models.user import User
from datetime import datetime, time
from app.utils.formatters import now_peru

app = create_app()

with app.app_context():
    hoy = now_peru().date()
    inicio = datetime.combine(hoy, time.min)
    fin    = datetime.combine(hoy, time.max)

    demo_id = User.get_demo_user_id()
    ops = Operation.query.filter(
        Operation.created_at >= inicio,
        Operation.created_at <= fin,
    )
    if demo_id:
        ops = ops.filter(Operation.user_id != demo_id)
    ops = ops.order_by(Operation.created_at).all()

    print()
    print(f"{'='*72}")
    print(f"  OPERACIONES HOY {hoy} — {len(ops)} total")
    print(f"{'='*72}")

    for op in ops:
        creator = db.session.get(User, op.user_id)
        creator_name = creator.username if creator else '?'
        print()
        print(f"  ID: {op.operation_id}  |  Tipo: {op.operation_type}  |  Estado: {op.status}")
        print(f"  Creado por: {creator_name}  |  Hora: {op.created_at.strftime('%H:%M:%S')}")
        print(f"  Monto: USD {op.amount_usd}  |  PEN {op.amount_pen}  |  TC {op.exchange_rate}")

        if op.client_deposits:
            print(f"  Depósitos cliente:")
            for d in op.client_deposits:
                print(f"    qc_bank={d.get('qc_bank','?')}  importe={d.get('importe','?')}  cuenta_cargo={d.get('cuenta_cargo','?')}")

        if op.client_payments:
            print(f"  Pagos a cliente:")
            for p in op.client_payments:
                print(f"    qc_bank={p.get('qc_bank','?')}  importe={p.get('importe','?')}")

        print(f"  source_account: {op.source_account}")
        print(f"  {'─'*60}")

    print()
    completadas = [o for o in ops if o.status == 'Completada']
    pendientes  = [o for o in ops if o.status in ('Pendiente', 'En proceso')]
    print(f"  Completadas: {len(completadas)}  |  Pendientes/En proceso: {len(pendientes)}")
    print(f"{'='*72}")
    print()

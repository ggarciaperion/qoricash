"""
Ajuste contable — Octubre 2026
==============================
Ejecutar en Render shell:  python ajuste_octubre_2026.py

Acciones:
  1. Crear operacion Banco Interbank: Compra 425 USD @ 3.494, 31 Oct, Completada
  2. EXP-1231 (29 Oct, Cancelado)  -> Completada
  3. EXP-1228 (28 Oct, En proceso) -> Cancelado  (SIN notificaciones al cliente)
  4. EXP-1226 (27 Oct)             -> Completada
  5. EXP-1222 (27 Oct)             -> Completada
  6. EXP-1218 (26 Oct)             -> Completada

IMPORTANTE:
  - completed_at de todas las ops -> su fecha original en octubre (no hoy).
  - entry_date del asiento contable = completed_at.date() -> utilidad en octubre.
  - EXP-1228: solo se actualiza el campo status en DB, no se disparan emails ni WA.
"""

from app import create_app
from app.extensions import db
from app.models.operation import Operation
from app.models.client import Client
from app.models.audit_log import AuditLog
from app.utils.formatters import now_peru
from datetime import datetime, date
import pytz

app = create_app()
LIMA = pytz.timezone('America/Lima')


def ts_lima(year, month, day, hour=23, minute=55):
    """Devuelve datetime timezone-aware en hora Lima."""
    return LIMA.localize(datetime(year, month, day, hour, minute, 0))


with app.app_context():

    print("\n" + "=" * 65)
    print("  AJUSTE CONTABLE OCTUBRE 2026")
    print("=" * 65)

    # Obtener admin para auditoria
    from app.models.user import User
    admin = User.query.filter_by(username='admin').first()
    admin_id = admin.id if admin else 1
    print(f"\n[ADMIN] id={admin_id}  username={getattr(admin, 'username', '?')}")

    # ==============================================================
    # 1. CREAR OPERACION — Banco Interbank, Compra, 425 USD, 3.494
    # ==============================================================
    print("\n[1] Creando operacion Banco Interbank...")

    interbank = Client.query.filter(
        Client.razon_social.ilike('%interbank%')
    ).first()

    if not interbank:
        interbank = Client.query.filter(
            Client.razon_social.ilike('%banco internacional%')
        ).first()

    if not interbank:
        print("    AVISO: No encontre cliente con razon_social LIKE '%interbank%'.")
        print("    Clientes RUC disponibles (primeros 20):")
        clientes = Client.query.filter_by(document_type='RUC').order_by(Client.id).limit(20).all()
        for c in clientes:
            print(f"      id={c.id}  {c.razon_social}")
        print("\n    Edita INTERBANK_CLIENT_ID en este script y vuelve a correr.")
        INTERBANK_CLIENT_ID = None
        nueva_op_id = None
    else:
        INTERBANK_CLIENT_ID = interbank.id
        print(f"    OK Cliente encontrado: id={interbank.id}  {interbank.razon_social}")

    if INTERBANK_CLIENT_ID:
        nueva_op_id = Operation.generate_operation_id()
        oct31 = ts_lima(2026, 10, 31)

        nueva_op = Operation(
            operation_id   = nueva_op_id,
            client_id      = INTERBANK_CLIENT_ID,
            user_id        = admin_id,
            operation_type = 'Compra',
            amount_usd     = 425.00,
            exchange_rate  = 3.4940,
            amount_pen     = round(425.00 * 3.4940, 2),
            status         = 'Completada',
            origen         = 'sistema',
            created_at     = oct31,
            completed_at   = oct31,
            notes          = 'Ajuste contable octubre 2026 — operacion Banco Interbank ingresada manualmente',
        )
        db.session.add(nueva_op)
        db.session.flush()

        AuditLog.log_action(
            user_id   = admin_id,
            action    = 'CREATE_OPERATION',
            entity    = 'Operation',
            entity_id = nueva_op.id,
            details   = f'Ajuste Oct2026: {nueva_op_id} Compra $425 @ 3.494 Interbank — completada 31/10',
        )
        print(f"    OK Operacion creada: {nueva_op_id}  PEN={nueva_op.amount_pen}  completed_at=2026-10-31")
    else:
        nueva_op_id = None
        print("    SALTANDO creacion — cliente no encontrado.")

    # ==============================================================
    # Funcion auxiliar — forzar estado directo en DB (sin API, sin notifs)
    # ==============================================================
    def forzar_estado(exp_id, nuevo_estado, completed_date=None, notas=None):
        op = Operation.query.filter_by(operation_id=exp_id).first()
        if not op:
            print(f"    ERROR No encontrada: {exp_id}")
            return
        estado_ant = op.status
        op.status     = nuevo_estado
        op.updated_at = now_peru()
        if nuevo_estado == 'Completada' and completed_date:
            op.completed_at = ts_lima(completed_date.year, completed_date.month, completed_date.day)
        if notas:
            entrada = f"[Ajuste Oct2026 | admin] {notas}"
            op.notes = (op.notes + f"\n\n{entrada}") if op.notes else entrada
        AuditLog.log_action(
            user_id   = admin_id,
            action    = 'UPDATE_OPERATION_STATUS',
            entity    = 'Operation',
            entity_id = op.id,
            details   = f'Ajuste Oct2026: {exp_id} {estado_ant} -> {nuevo_estado}',
            notes     = notas,
        )
        completed_str = op.completed_at.strftime('%Y-%m-%d') if op.completed_at else '—'
        print(f"    OK {exp_id}: {estado_ant} -> {nuevo_estado}  completed_at={completed_str}")

    # ==============================================================
    # 2. EXP-1231: Cancelado -> Completada (29 Oct)
    # ==============================================================
    print("\n[2] EXP-1231: Cancelado -> Completada")
    forzar_estado('EXP-1231', 'Completada',
                  completed_date=date(2026, 10, 29),
                  notas='Revertida cancelacion — completada con fecha original 29/10')

    # ==============================================================
    # 3. EXP-1228: En proceso -> Cancelado (SIN notificaciones)
    # ==============================================================
    print("\n[3] EXP-1228: En proceso -> Cancelado (sin notificaciones al cliente)")
    forzar_estado('EXP-1228', 'Cancelado',
                  notas='Cancelada sin notificar al cliente — ajuste interno')

    # ==============================================================
    # 4. EXP-1226: -> Completada (27 Oct)
    # ==============================================================
    print("\n[4] EXP-1226: -> Completada")
    forzar_estado('EXP-1226', 'Completada',
                  completed_date=date(2026, 10, 27),
                  notas='Ajuste oct2026 — completada con fecha original 27/10')

    # ==============================================================
    # 5. EXP-1222: -> Completada (27 Oct)
    # ==============================================================
    print("\n[5] EXP-1222: -> Completada")
    forzar_estado('EXP-1222', 'Completada',
                  completed_date=date(2026, 10, 27),
                  notas='Ajuste oct2026 — completada con fecha original 27/10')

    # ==============================================================
    # 6. EXP-1218: -> Completada (26 Oct)
    # ==============================================================
    print("\n[6] EXP-1218: -> Completada")
    forzar_estado('EXP-1218', 'Completada',
                  completed_date=date(2026, 10, 26),
                  notas='Ajuste oct2026 — completada con fecha original 26/10')

    # ==============================================================
    # COMMIT UNICO
    # ==============================================================
    print("\n[COMMIT] Guardando todos los cambios...")
    db.session.commit()
    print("[COMMIT] OK Hecho.\n")

    # Verificacion final
    print("=" * 65)
    print("  VERIFICACION FINAL")
    print("=" * 65)
    targets = ['EXP-1231', 'EXP-1228', 'EXP-1226', 'EXP-1222', 'EXP-1218']
    if nueva_op_id:
        targets.insert(0, nueva_op_id)
    for eid in targets:
        op = Operation.query.filter_by(operation_id=eid).first()
        if op:
            cat = op.completed_at.strftime('%Y-%m-%d') if op.completed_at else '—'
            crt = op.created_at.strftime('%Y-%m-%d') if op.created_at else '—'
            print(f"  {op.operation_id:12}  status={op.status:12}  created={crt}  completed_at={cat}")
        else:
            print(f"  {eid:12}  NO ENCONTRADA")

    print()
    print("  PROXIMOS PASOS:")
    print("  1. Contabilidad -> hacer amarre de cada operacion Completada.")
    print("     El asiento usara completed_at como entry_date -> queda en octubre.")
    print("  2. EXP-1231: si ya tenia asiento de cancelacion, anularlo primero")
    print("     antes de hacer el amarre.")
    print("  3. EXP-1228: status=Cancelado, no se genero asiento ni notificacion.")
    print("=" * 65 + "\n")

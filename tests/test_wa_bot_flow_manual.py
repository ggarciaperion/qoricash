#!/usr/bin/env python3
"""
tests/test_wa_bot_flow_manual.py

Guion de prueba — Bot WhatsApp QoriCash (Etapa 3)
==================================================
Recorrido de referencia para ejecutar la prueba de punta a punta
en un entorno conectado al número de WhatsApp de prueba.

NO envía mensajes reales ni escribe en la base de datos de producción.
Para ejecutar el flujo en flask shell, usa el FIXTURE al final del archivo.

PREREQUISITO
------------
  export FLASK_APP=run.py
  export FLASK_ENV=development
  flask shell   # o python -m flask shell

NUMERO DE PRUEBA
----------------
  Usar un número que no exista en producción, p.ej. 51900000001.
  Limpiarlo antes si ya tiene sesión:

    from app.extensions import db
    from app.models.wa_bot_session import WaBotSession
    WaBotSession.query.filter_by(numero='51900000001').delete()
    db.session.commit()

──────────────────────────────────────────────────────────────────────────────
RECORRIDO CORTO (cliente existente con cuenta guardada)
──────────────────────────────────────────────────────────────────────────────

  Interacción 1  CLIENTE:  "Quiero comprar 500 dólares"
                 BOT:      Cotización con TC vigente y botón [Confirmar cotización]

  Interacción 2  CLIENTE:  pulsa "Confirmar cotización"
                 BOT:      Resumen (monto, TC, cuenta destino guardada)
                           y botón [Confirmar cambio] con token UUID

  Interacción 3  CLIENTE:  pulsa "Confirmar cambio"
                 BOT:      Operación creada (EXP-XXXX)
                           + instrucciones de transferencia con cuentas QoriCash

  Interacción 4  CLIENTE:  escribe el código de voucher (ej. "BCP T-123456")
                 BOT:      Confirmación de registro, operación pasa a "En proceso"

  Total: 4 interacciones del cliente.

──────────────────────────────────────────────────────────────────────────────
RECORRIDO CON CUENTA NUEVA (cliente sin cuenta guardada)
──────────────────────────────────────────────────────────────────────────────

  Interacción 1  "Quiero comprar 500 dólares"
                 → cotización + [Confirmar cotización]

  Interacción 2  pulsa "Confirmar cotización"
                 → solicita número de cuenta bancaria destino

  Interacción 3  "BCP 123-456789-0-12"
                 → Resumen con cuenta ingresada + [Confirmar cambio]

  Interacción 4  pulsa "Confirmar cambio"
                 → EXP-XXXX creada + instrucciones

  Interacción 5  "T-123456"
                 → En proceso

  Total: 5 interacciones del cliente.

──────────────────────────────────────────────────────────────────────────────
CASOS DE BORDE A VERIFICAR MANUALMENTE
──────────────────────────────────────────────────────────────────────────────

  A. Botón caducado (doble tap o sesión vieja)
     Mientras el cliente está en 'confirmando_operacion', cambiar el token en DB:

       s = WaBotSession.query.filter_by(numero=TEL).first()
       old_token = s.cotiz_token
       s.cotiz_token = 'token-nuevo'
       db.session.commit()

     Luego enviar el botón con old_token:
       handle_incoming(TEL, f'btn_confirmar_operacion_{old_token}')

     Esperado: el bot re-muestra el resumen con el token actual.
               No se crea una operación.

  B. Inactividad 15 min (scheduler)
       from datetime import timedelta
       from app.utils.formatters import now_peru
       s = WaBotSession.query.filter_by(numero=TEL).first()
       s.updated_at = now_peru() - timedelta(minutes=16)
       db.session.commit()
       from app.services.operation_expiry_service import OperationExpiryService
       OperationExpiryService.expire_inactive_bot_sessions()
     Esperado: sesión reseteada a 'inicio', mensaje de expiración enviado.

  C. bot_pausado=True — scheduler no toca la sesión
       s.bot_pausado = True
       s.updated_at  = now_peru() - timedelta(minutes=20)
       db.session.commit()
       OperationExpiryService.expire_inactive_bot_sessions()
     Esperado: 0 sesiones notificadas, log "[SESSION] … bot pausado".

  D. Operación expirada (timeout 15 min)
       from app.models.operation import Operation
       op = Operation.query.filter_by(status='Pendiente') \\
                    .order_by(Operation.created_at.desc()).first()
       op.created_at = now_peru() - timedelta(minutes=16)
       db.session.commit()
       OperationExpiryService.expire_old_operations()
     Esperado: op.status == 'Cancelado', notificaciones disparadas.

──────────────────────────────────────────────────────────────────────────────
VERIFICACIONES EN BASE DE DATOS
──────────────────────────────────────────────────────────────────────────────

  from app.models.wa_bot_session import WaBotSession
  from app.models.operation import Operation

  s = WaBotSession.query.filter_by(numero=TEL).first()

  # Tras confirmar la operación:
  assert s.estado == 'op_pendiente_pago'
  assert s.cotiz_op_id.startswith('EXP-')
  assert s.cotiz_token is None          # consumido (previene replay)

  # Operación creada:
  op = Operation.query.filter_by(operation_id=s.cotiz_op_id).first()
  assert op is not None
  assert op.status == 'Pendiente'
  assert op.origen in ('whatsapp',)

  # Tras registrar el código:
  op2 = Operation.query.filter_by(operation_id=s.cotiz_op_id).first()
  assert op2.status == 'En proceso'
  codigos = [d.get('codigo') for d in (op2.client_deposits or [])]
  assert 'T-123456' in codigos or any('T-123456' in c for c in codigos if c)

  # Sin duplicados:
  activas = Operation.query.filter_by(client_id=op2.client_id,
                                       status='Pendiente').all()
  assert len(activas) == 0, f'{len(activas)} op Pendiente duplicada(s)'

──────────────────────────────────────────────────────────────────────────────
LIMPIEZA POST-PRUEBA
──────────────────────────────────────────────────────────────────────────────

  # SOLO en entorno de prueba, nunca en producción
  WaBotSession.query.filter_by(numero=TEL).delete()
  for op in Operation.query.filter(Operation.operation_id.like('EXP-%')).all():
      if op.client and '000000' in (op.client.phone or ''):
          op.status = 'Cancelado'
  db.session.commit()
"""

# ── Fixture para flask shell ───────────────────────────────────────────────────
# Pegar este bloque completo en `flask shell` para ejecutar el recorrido corto
# sin interacción manual (cliente existente con cuenta guardada).

FIXTURE_SHELL = '''
from app.services.wa_bot import handle_incoming
from app.extensions import db
from app.models.wa_bot_session import WaBotSession
from app.models.operation import Operation

TEL = '51900000001'

# Limpiar sesión previa
WaBotSession.query.filter_by(numero=TEL).delete()
db.session.commit()
print("Sesión limpiada.")

# 1 — Cotización directa por monto
print("\\n--- Interacción 1: solicitud compra 500 USD ---")
handle_incoming(TEL, "Quiero comprar 500 dólares")

s = WaBotSession.query.filter_by(numero=TEL).first()
print(f"Estado: {s.estado}")

# 2 — Confirmar cotización (botón)
print("\\n--- Interacción 2: confirmar cotización ---")
handle_incoming(TEL, "btn_confirmar_cotizacion")

s = WaBotSession.query.filter_by(numero=TEL).first()
print(f"Estado: {s.estado} | Token: {s.cotiz_token}")

# Si el cliente no tiene cuenta guardada, hay un paso extra de cuenta
if s.estado in ('esperando_num_cuenta', 'esperando_cuenta_destino'):
    print("\\n--- Interacción extra: ingresar cuenta bancaria ---")
    handle_incoming(TEL, "BCP 123-456789-0-12")
    s = WaBotSession.query.filter_by(numero=TEL).first()
    print(f"Estado: {s.estado} | Token: {s.cotiz_token}")

token = s.cotiz_token
assert token, "El bot debe haber generado un token en estado confirmando_operacion"

# 3 — Confirmar operación (botón con token)
print("\\n--- Interacción 3: confirmar operación ---")
handle_incoming(TEL, f"btn_confirmar_operacion_{token}")

s = WaBotSession.query.filter_by(numero=TEL).first()
print(f"Estado: {s.estado} | Op ID: {s.cotiz_op_id} | Token: {s.cotiz_token}")
assert s.estado == 'op_pendiente_pago', f"Esperado op_pendiente_pago, got {s.estado}"
assert s.cotiz_token is None, "Token debe estar consumido"

op = Operation.query.filter_by(operation_id=s.cotiz_op_id).first()
assert op, "Operación no encontrada en DB"
assert op.status == 'Pendiente'
print(f"Operación {op.operation_id} creada — status: {op.status}")

# 4 — Registrar código de transferencia
print("\\n--- Interacción 4: código de voucher ---")
handle_incoming(TEL, "T-123456")

s = WaBotSession.query.filter_by(numero=TEL).first()
op2 = Operation.query.filter_by(operation_id=s.cotiz_op_id).first()
print(f"Estado sesión: {s.estado} | Status op: {op2.status if op2 else 'N/A'}")

print("\\n=== RESULTADO ===")
print(f"  Estado final:   {s.estado}")
print(f"  Status op:      {op2.status if op2 else 'no encontrada'}")
print(f"  Token consumido: {s.cotiz_token is None}")
'''


def print_fixture():
    """Imprime el fixture listo para pegar en flask shell."""
    print(FIXTURE_SHELL)


if __name__ == '__main__':
    import sys
    if '--fixture' in sys.argv:
        print(FIXTURE_SHELL)
    else:
        print(__doc__)

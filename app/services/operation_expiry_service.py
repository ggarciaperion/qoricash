"""
Servicio para expirar operaciones automáticamente
"""
import logging
import os
import requests
from datetime import timedelta
from app.extensions import db
from app.models.operation import Operation
from app.services.notification_service import NotificationService
from app.utils.formatters import now_peru

logger = logging.getLogger(__name__)

# Tiempo límite de producción: 15 minutos
OPERATION_TIMEOUT_MINUTES = 15

# Hora de cierre diario (22:00 hora Perú)
END_OF_DAY_HOUR = 22


class OperationExpiryService:
    """Servicio para manejar expiración automática de operaciones"""

    @staticmethod
    def expire_old_operations():
        """
        Buscar y cancelar operaciones pendientes que hayan excedido el tiempo límite

        Returns:
            int: Número de operaciones canceladas
        """
        try:
            # Calcular fecha límite (15 minutos atrás desde ahora)
            cutoff_time = now_peru() - timedelta(minutes=OPERATION_TIMEOUT_MINUTES)

            # PROTECCIÓN: Solo considerar operaciones creadas en las últimas 24 horas
            # Esto evita cancelar operaciones viejas con timestamps en hora de Perú
            protection_cutoff = now_peru() - timedelta(hours=24)

            # Buscar operaciones pendientes creadas antes del cutoff_time
            # pero DESPUÉS del protection_cutoff (últimas 24 horas)
            # IMPORTANTE: Solo cancelar operaciones de canales web, app y plataforma
            # Las operaciones de 'sistema' (creadas por Trader) NO se cancelan automáticamente
            expired_operations = Operation.query.filter(
                Operation.status == 'Pendiente',
                Operation.created_at < cutoff_time,
                Operation.created_at > protection_cutoff,  # Solo últimas 24 horas
                Operation.origen.in_(['web', 'app', 'plataforma'])  # Excluir 'sistema'
            ).all()

            if not expired_operations:
                return 0

            expired_count = 0

            for operation in expired_operations:
                try:
                    # LOG: Información detallada de la operación que se va a cancelar
                    logger.info(f"🔍 EXPIRANDO: {operation.operation_id} | Origen: {operation.origen} | Creada: {operation.created_at} | Cutoff: {cutoff_time}")

                    # Cambiar estado a Cancelado (como solicitado por el usuario)
                    operation.status = 'Cancelado'
                    operation.updated_at = now_peru()

                    # Agregar motivo de cancelación en notas
                    cancellation_reason = "Tiempo límite de carga de comprobante expirado"
                    if operation.notes:
                        operation.notes = f"{operation.notes}\n\n[SISTEMA] {cancellation_reason}"
                    else:
                        operation.notes = f"[SISTEMA] {cancellation_reason}"

                    # Guardar en base de datos
                    db.session.commit()

                    logger.info(f"⏱️ Operación {operation.operation_id} cancelada automáticamente por tiempo límite expirado (creada: {operation.created_at})")

                    # Enviar notificación Socket.IO al cliente (app móvil)
                    try:
                        NotificationService.notify_operation_expired(operation)
                        logger.info(f"📡 Notificación Socket.IO enviada para operación {operation.operation_id}")
                    except Exception as notif_error:
                        logger.error(f"❌ Error enviando notificación Socket.IO: {str(notif_error)}")

                    # Enviar correo electrónico al cliente
                    try:
                        from app.services.email_service import EmailService
                        success, message = EmailService.send_operation_expired_email(operation)
                        if success:
                            logger.info(f"📧 Email de cancelación enviado para operación {operation.operation_id}")
                        else:
                            logger.warning(f"⚠️ No se pudo enviar email para operación {operation.operation_id}: {message}")
                    except Exception as email_error:
                        logger.error(f"❌ Error enviando email de expiración: {str(email_error)}")

                    # Enviar Push Notification (Expo) al cliente
                    try:
                        from app.services.push_notification_service import PushNotificationService
                        if operation.client and operation.client.push_notification_token:
                            push_result = PushNotificationService.send_operation_expired_push(operation.client)
                            if push_result.get('success'):
                                logger.info(f"📲 Push notification enviada para operación {operation.operation_id}")
                            else:
                                logger.warning(f"⚠️ No se pudo enviar push: {push_result.get('error')}")
                        else:
                            logger.info(f"ℹ️ Cliente sin token push registrado para operación {operation.operation_id}")
                    except Exception as push_error:
                        logger.error(f"❌ Error enviando push notification: {str(push_error)}")

                    # Notificar al cliente vía WhatsApp
                    try:
                        from app.services.wa_bot import wa_notify_client_buttons
                        titular = operation.client.full_name if operation.client else operation.operation_id
                        wa_notify_client_buttons(
                            operation.client,
                            f'⏱️ Tu operación *{operation.operation_id}* a nombre de *{titular}* fue cancelada automáticamente '
                            f'porque no se registró la transferencia dentro del plazo de *15 minutos*.\n\n'
                            f'Puedes iniciar una nueva cotización cuando lo desees o hablar con un asesor.',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                    except Exception as wa_err:
                        logger.warning(f"[EXPIRY] Error WA para {operation.operation_id}: {wa_err}")

                    expired_count += 1

                except Exception as op_error:
                    logger.error(f"Error expirando operación {operation.operation_id}: {str(op_error)}")
                    db.session.rollback()
                    continue

            if expired_count > 0:
                logger.info(f"✅ {expired_count} operaciones canceladas automáticamente por tiempo límite expirado")

            return expired_count

        except Exception as e:
            logger.error(f"Error en expire_old_operations: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return 0

    @staticmethod
    def cancel_end_of_day_operations():
        """
        Cancela TODAS las operaciones Pendiente o En proceso a las 10pm hora Peru.
        Se llama desde el scheduler cuando la hora actual es >= 22:00 y < 22:02
        para asegurar que solo se ejecuta una vez por dia.

        Returns:
            int: Numero de operaciones canceladas
        """
        try:
            now = now_peru()

            # Solo actuar entre 22:00:00 y 22:01:59 (ventana de 2 minutos)
            if not (now.hour == END_OF_DAY_HOUR and now.minute < 2):
                return 0

            pending_ops = Operation.query.filter(
                Operation.status.in_(['Pendiente', 'En proceso'])
            ).all()

            if not pending_ops:
                logger.info("[EOD] No hay operaciones Pendiente/En proceso para cancelar.")
                return 0

            cancelled_count = 0
            motivo = "[SISTEMA] Cierre automatico diario 10pm - operacion no completada"

            for operation in pending_ops:
                try:
                    operation.status = 'Cancelado'
                    operation.cancellation_reason = motivo
                    operation.updated_at = now_peru()
                    db.session.commit()

                    logger.info(f"[EOD] Operacion {operation.operation_id} cancelada automaticamente a las 10pm")

                    try:
                        NotificationService.notify_operation_canceled(operation, motivo)
                    except Exception as notif_error:
                        logger.error(f"[EOD] Error notificando {operation.operation_id}: {notif_error}")

                    # Notificar al cliente vía WhatsApp
                    try:
                        from app.services.wa_bot import wa_notify_client_buttons
                        titular = operation.client.full_name if operation.client else operation.operation_id
                        wa_notify_client_buttons(
                            operation.client,
                            f'🌙 Tu operación *{operation.operation_id}* a nombre de *{titular}* fue cancelada automáticamente '
                            f'por cierre de operaciones del día (10:00 PM).\n\n'
                            f'Puedes iniciar una nueva cotización mañana o hablar con un asesor.',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                    except Exception as wa_err:
                        logger.warning(f"[EOD] Error WA para {operation.operation_id}: {wa_err}")

                    cancelled_count += 1

                except Exception as op_error:
                    logger.error(f"[EOD] Error cancelando {operation.operation_id}: {op_error}")
                    db.session.rollback()
                    continue

            if cancelled_count > 0:
                logger.info(f"[EOD] {cancelled_count} operaciones canceladas por cierre diario 10pm")

            return cancelled_count

        except Exception as e:
            logger.error(f"Error en cancel_end_of_day_operations: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return 0

    @staticmethod
    def expire_inactive_bot_sessions():
        """
        Envía mensaje de cierre de sesión por inactividad (15 min) en DOS casos:

        Caso A — sesión activa (estado != 'inicio'):
            updated_at < ahora - 15 min → resetear + notificar.

        Caso B — sesión en 'inicio' con mensaje saliente sin respuesta:
            El bot envió algo (cancelación de operación, etc.) hace > 15 min y el
            cliente no ha respondido. Se detecta via WaMessage: el mensaje saliente
            más reciente para ese número es posterior a session.updated_at y fue
            enviado hace > 15 min sin ningún entrante posterior.
            → tocar updated_at (previene re-disparo) + notificar.

        Returns:
            int: Número de sesiones notificadas
        """
        try:
            from app.models.wa_bot_session import WaBotSession
            from app.models.wa_message import WaMessage
            from sqlalchemy import text as sa_text

            now = now_peru()
            cutoff = now - timedelta(minutes=15)

            # Helper: verifica si el número WA tiene una operación En proceso
            from app.models.client import Client as _Client
            from app.models.operation import Operation as _Operation
            import re as _re

            def _tiene_op_en_proceso(numero_wa):
                """Retorna True si el cliente tiene una operación actualmente En proceso."""
                try:
                    digits = _re.sub(r'\D', '', numero_wa)
                    local = digits[-9:] if len(digits) >= 9 else digits
                    if not local:
                        return False
                    client = _Client.query.filter(_Client.phone.ilike(f'%{local}%')).first()
                    if not client:
                        return False
                    return _Operation.query.filter(
                        _Operation.client_id == client.id,
                        _Operation.status == 'En proceso'
                    ).first() is not None
                except Exception:
                    return False

            # ── Caso A: sesiones con flujo activo inactivas > 15 min ──────────
            active_inactive = WaBotSession.query.filter(
                WaBotSession.estado != 'inicio',
                WaBotSession.updated_at < cutoff,
            ).all()

            sessions_to_notify = []

            for s in active_inactive:
                # No expirar si el cliente tiene una operación En proceso —
                # el operador puede tardar más de 15 min en depositar los fondos.
                if _tiene_op_en_proceso(s.numero):
                    logger.info(f"[SESSION] {s.numero} — op En proceso activa, no expirar sesión.")
                    continue
                s.estado        = 'inicio'
                s.cotiz_op      = ''
                s.cotiz_importe = 0.0
                s.cotiz_tc      = 0.0
                s.cotiz_doc     = ''
                s.cotiz_email   = ''
                s.cotiz_op_id   = ''
                s.cotiz_cuenta  = ''
                s.updated_at    = now
                sessions_to_notify.append(s.numero)

            # ── Caso B: sesiones en 'inicio' donde bot envió algo y cliente no respondió ─
            # Busca sesiones donde exista un WaMessage saliente:
            #   - posterior a session.updated_at (fue enviado DESPUÉS del último cambio de estado)
            #   - anterior a cutoff (hace > 15 min)
            #   - sin WaMessage entrante posterior a ese saliente
            inicio_sessions = WaBotSession.query.filter(
                WaBotSession.estado == 'inicio',
            ).all()

            for s in inicio_sessions:
                if s.numero in sessions_to_notify:
                    continue
                # No enviar mensaje de sesión expirada si hay op En proceso
                if _tiene_op_en_proceso(s.numero):
                    logger.info(f"[SESSION] {s.numero} — op En proceso activa, no enviar cierre de sesión.")
                    continue
                try:
                    # Último mensaje saliente para este número posterior a updated_at
                    last_out = (WaMessage.query
                                .filter(
                                    WaMessage.numero == s.numero,
                                    WaMessage.direccion == 'saliente',
                                    WaMessage.created_at > s.updated_at,
                                    WaMessage.created_at < cutoff,
                                )
                                .order_by(WaMessage.created_at.desc())
                                .first())
                    if not last_out:
                        continue
                    # Verificar que no hay entrante posterior a ese saliente
                    has_reply = WaMessage.query.filter(
                        WaMessage.numero == s.numero,
                        WaMessage.direccion == 'entrante',
                        WaMessage.created_at > last_out.created_at,
                    ).first()
                    if has_reply:
                        continue
                    # Califica: tocar updated_at para prevenir re-disparo
                    s.updated_at = now
                    sessions_to_notify.append(s.numero)
                except Exception as e_b:
                    logger.error(f"[SESSION] Error caso B para {s.numero}: {e_b}")

            if not sessions_to_notify:
                return 0

            try:
                db.session.commit()
                logger.info(f"[SESSION] {len(sessions_to_notify)} sesiones marcadas para notificación")
            except Exception as commit_err:
                logger.error(f"[SESSION] Error en commit: {commit_err}")
                db.session.rollback()
                return 0

            # ── Enviar mensaje de cierre de sesión ────────────────────────────
            wa_url   = f"https://graph.facebook.com/v19.0/{os.environ.get('WA_PHONE_NUMBER_ID','1118979324636599')}/messages"
            wa_token = os.environ.get('WA_ACCESS_TOKEN', '')
            headers  = {'Authorization': f'Bearer {wa_token}', 'Content-Type': 'application/json'}
            cuerpo   = ('⏰ Tu sesión ha expirado por inactividad.\n\n'
                        'Cuando desees volver a operar, escríbenos y comenzamos de nuevo.')

            closed_count = 0
            for numero in sessions_to_notify:
                try:
                    # Enviar con botón "Hablar con asesor" (interactive)
                    payload = {
                        'messaging_product': 'whatsapp',
                        'to': numero.lstrip('+'),
                        'type': 'interactive',
                        'interactive': {
                            'type': 'button',
                            'body': {'text': cuerpo},
                            'action': {
                                'buttons': [
                                    {'type': 'reply', 'reply': {'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}}
                                ]
                            }
                        }
                    }
                    requests.post(wa_url, json=payload, headers=headers, timeout=10)
                    logger.info(f"[SESSION] Sesión expirada, WA enviado: {numero}")
                    closed_count += 1
                except Exception as wa_err:
                    logger.warning(f"[SESSION] WA no enviado a {numero}: {wa_err}")
                    closed_count += 1  # la sesión SÍ fue reseteada aunque falle el WA

            if closed_count > 0:
                logger.info(f"[SESSION] {closed_count} sesiones bot cerradas por inactividad")

            return closed_count

        except Exception as e:
            logger.error(f"Error en expire_inactive_bot_sessions: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return 0

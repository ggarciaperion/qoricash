"""
Servicio para expirar operaciones automáticamente
"""
import logging
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
                        from app.services.wa_bot import wa_notify_client
                        titular = operation.client.full_name if operation.client else operation.operation_id
                        wa_notify_client(
                            operation.client,
                            f'⏱️ Tu operación *{operation.operation_id}* a nombre de *{titular}* fue cancelada automáticamente '
                            f'porque no se registró la transferencia dentro del plazo de *15 minutos*.\n\n'
                            f'Puedes iniciar una nueva cotización cuando lo desees.'
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
                        from app.services.wa_bot import wa_notify_client
                        titular = operation.client.full_name if operation.client else operation.operation_id
                        wa_notify_client(
                            operation.client,
                            f'🌙 Tu operación *{operation.operation_id}* a nombre de *{titular}* fue cancelada automáticamente '
                            f'por cierre de operaciones del día (10:00 PM).\n\n'
                            f'Puedes iniciar una nueva cotización mañana.'
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
        Cierra sesiones de WhatsApp bot con más de 20 minutos de inactividad.
        Envía mensaje de sesión cerrada y resetea el estado a 'inicio'.

        Returns:
            int: Número de sesiones cerradas
        """
        try:
            from app.models.wa_bot_session import WaBotSession
            from app.services.wa_bot import send_text as _wa_send

            cutoff = now_peru() - timedelta(minutes=20)

            inactive_sessions = WaBotSession.query.filter(
                WaBotSession.estado != 'inicio',
                WaBotSession.updated_at < cutoff,
            ).all()

            if not inactive_sessions:
                return 0

            closed_count = 0
            for session in inactive_sessions:
                try:
                    # Notificar al cliente
                    _wa_send(
                        session.numero,
                        '🔒 Tu sesión ha sido cerrada por inactividad.\n\n'
                        'Cuando desees volver a operar, escríbenos y te atenderemos de inmediato.'
                    )

                    # Resetear estado y datos en curso
                    session.estado       = 'inicio'
                    session.cotiz_op     = ''
                    session.cotiz_importe = 0.0
                    session.cotiz_tc     = 0.0
                    session.cotiz_doc    = ''
                    session.cotiz_email  = ''
                    session.cotiz_op_id  = ''
                    session.cotiz_cuenta = ''
                    db.session.commit()

                    logger.info(f"[SESSION] Sesión cerrada por inactividad: {session.numero}")
                    closed_count += 1

                except Exception as sess_err:
                    logger.error(f"[SESSION] Error cerrando sesión {session.numero}: {sess_err}")
                    db.session.rollback()
                    continue

            if closed_count > 0:
                logger.info(f"[SESSION] {closed_count} sesiones bot cerradas por inactividad")

            return closed_count

        except Exception as e:
            logger.error(f"Error en expire_inactive_bot_sessions: {str(e)}")
            db.session.rollback()
            return 0

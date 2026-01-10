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
# TEMPORAL: Configurado a 1 minuto para pruebas
OPERATION_TIMEOUT_MINUTES = 1


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

            # Buscar operaciones pendientes creadas antes del cutoff_time
            expired_operations = Operation.query.filter(
                Operation.status == 'Pendiente',
                Operation.created_at < cutoff_time
            ).all()

            if not expired_operations:
                return 0

            expired_count = 0

            for operation in expired_operations:
                try:
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

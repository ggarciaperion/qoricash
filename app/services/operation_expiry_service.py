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

OPERATION_TIMEOUT_MINUTES = 15


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

                    # Enviar notificación Socket.IO al cliente
                    try:
                        NotificationService.notify_operation_expired(operation)
                        logger.info(f"📡 Notificación de expiración enviada para operación {operation.operation_id}")
                    except Exception as notif_error:
                        logger.error(f"Error enviando notificación de expiración: {str(notif_error)}")

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

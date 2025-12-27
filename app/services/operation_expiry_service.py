"""
Servicio para expirar operaciones automáticamente
"""
import logging
from datetime import datetime, timedelta
from app.extensions import db
from app.models.operation import Operation
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

OPERATION_TIMEOUT_MINUTES = 15


class OperationExpiryService:
    """Servicio para manejar expiración automática de operaciones"""

    @staticmethod
    def expire_old_operations():
        """
        Buscar y expirar operaciones pendientes que hayan excedido el tiempo límite

        Returns:
            int: Número de operaciones expiradas
        """
        try:
            # Calcular fecha límite (15 minutos atrás desde ahora)
            cutoff_time = datetime.utcnow() - timedelta(minutes=OPERATION_TIMEOUT_MINUTES)

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
                    # Cambiar estado a Expirada
                    operation.status = 'Expirada'
                    operation.updated_at = datetime.utcnow()

                    # Guardar en base de datos
                    db.session.commit()

                    logger.info(f"⏱️ Operación {operation.operation_id} expirada automáticamente (creada: {operation.created_at})")

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
                logger.info(f"✅ {expired_count} operaciones expiradas automáticamente")

            return expired_count

        except Exception as e:
            logger.error(f"Error en expire_old_operations: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return 0

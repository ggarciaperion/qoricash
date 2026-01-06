"""
Servicio de tareas programadas para QoriCash Trading V2
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.extensions import db, socketio
from app.models.operation import Operation
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Constante para el tiempo límite de operaciones (15 minutos)
OPERATION_TIMEOUT_MINUTES = 15


class SchedulerService:
    """Servicio para gestionar tareas programadas en segundo plano"""

    def __init__(self):
        self.scheduler = None

    def init_app(self, app):
        """
        Inicializar el scheduler con la aplicación Flask

        Args:
            app: Instancia de Flask app
        """
        self.app = app
        self.scheduler = BackgroundScheduler()

        # Registrar tareas programadas
        self.register_jobs()

        # Iniciar el scheduler
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ Scheduler iniciado exitosamente")

    def register_jobs(self):
        """Registrar todas las tareas programadas"""
        # Verificar operaciones expiradas cada 2 minutos
        self.scheduler.add_job(
            func=self._cancel_expired_operations,
            trigger='interval',
            minutes=2,
            id='cancel_expired_operations',
            name='Cancelar operaciones expiradas',
            replace_existing=True
        )
        logger.info("📅 Tarea programada: Cancelar operaciones expiradas (cada 2 minutos)")

    def _cancel_expired_operations(self):
        """
        Cancelar automáticamente operaciones que han excedido el tiempo límite
        sin haber subido comprobante de pago
        """
        try:
            with self.app.app_context():
                # Calcular la fecha límite (ahora - 15 minutos)
                expiration_time = datetime.utcnow() - timedelta(minutes=OPERATION_TIMEOUT_MINUTES)

                logger.info(f"🔍 [SCHEDULER] Buscando operaciones expiradas antes de: {expiration_time}")

                # Buscar operaciones pendientes o en proceso que:
                # 1. No tienen comprobante de pago
                # 2. Fueron creadas hace más de 15 minutos
                expired_operations = Operation.query.filter(
                    Operation.status.in_(['Pendiente', 'En proceso']),
                    Operation.payment_proof_url.is_(None),
                    Operation.created_at <= expiration_time
                ).all()

                if not expired_operations:
                    logger.info("✅ [SCHEDULER] No se encontraron operaciones expiradas")
                    return

                logger.info(f"⚠️ [SCHEDULER] Se encontraron {len(expired_operations)} operaciones expiradas")

                for operation in expired_operations:
                    try:
                        logger.info(f"❌ [SCHEDULER] Cancelando operación {operation.operation_id}")
                        logger.info(f"   - Cliente: {operation.client_id}")
                        logger.info(f"   - Creada: {operation.created_at}")
                        logger.info(f"   - Estado anterior: {operation.status}")
                        logger.info(f"   - Comprobante: {operation.payment_proof_url}")

                        # Cambiar estado a Cancelado
                        operation.status = 'Cancelado'
                        operation.notes = (operation.notes or '') + f"\n[Sistema] Operación cancelada automáticamente por expiración de tiempo límite ({OPERATION_TIMEOUT_MINUTES} min). Fecha: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                        operation.updated_at = datetime.utcnow()

                        db.session.commit()

                        logger.info(f"✅ [SCHEDULER] Operación {operation.operation_id} cancelada exitosamente")

                        # Enviar notificación al cliente via Socket.IO
                        self._notify_client_expiration(operation)

                    except Exception as e:
                        logger.error(f"❌ [SCHEDULER] Error al cancelar operación {operation.operation_id}: {e}")
                        logger.exception(e)
                        db.session.rollback()
                        continue

                logger.info(f"✅ [SCHEDULER] Proceso de cancelación de operaciones expiradas completado")

        except Exception as e:
            logger.error(f"❌ [SCHEDULER] Error en tarea de cancelación de operaciones expiradas: {e}")
            logger.exception(e)

    def _notify_client_expiration(self, operation):
        """
        Enviar notificación Socket.IO al cliente sobre la expiración de su operación

        Args:
            operation: Instancia de Operation que ha expirado
        """
        try:
            # Obtener información del cliente
            client = operation.client
            if not client:
                logger.warning(f"⚠️ [SCHEDULER] No se pudo obtener cliente para operación {operation.operation_id}")
                return

            # Preparar datos de la notificación
            notification_data = {
                'type': 'operation_expired',
                'operation_id': operation.operation_id,
                'client_id': operation.client_id,
                'client_dni': client.dni,
                'title': '⏱️ Operación Expirada',
                'message': f'La operación {operation.operation_id} ha sido cancelada por tiempo límite. Puedes crear una nueva operación.',
                'amount_usd': float(operation.amount_usd),
                'operation_type': operation.operation_type,
                'timestamp': datetime.utcnow().isoformat()
            }

            # Enviar notificación al room del cliente
            room = f'client_{client.dni}'
            logger.info(f"📡 [SCHEDULER] Enviando notificación de expiración al room: {room}")
            logger.info(f"📦 [SCHEDULER] Datos: {notification_data}")

            socketio.emit('operation_expired', notification_data, namespace='/', room=room)

            logger.info(f"✅ [SCHEDULER] Notificación de expiración enviada al cliente {client.dni}")

        except Exception as e:
            logger.error(f"❌ [SCHEDULER] Error enviando notificación de expiración: {e}")
            logger.exception(e)

    def shutdown(self):
        """Detener el scheduler"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("🛑 Scheduler detenido")


# Instancia global del scheduler
scheduler_service = SchedulerService()

"""
Servicio de Scheduler para tareas en segundo plano

Ejecuta tareas periódicas usando APScheduler
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

logger = logging.getLogger(__name__)


class SchedulerService:
    """Servicio para manejar tareas programadas en segundo plano"""

    def __init__(self):
        self.scheduler = None
        self.app = None

    def init_app(self, app):
        """
        Inicializar el scheduler con la aplicación Flask

        Args:
            app: Instancia de Flask app
        """
        self.app = app
        self.scheduler = BackgroundScheduler()

        # Registrar tareas
        self._register_jobs()

        # Iniciar scheduler
        try:
            self.scheduler.start()
            logger.info('✅ Scheduler iniciado correctamente')
        except Exception as e:
            logger.error(f'❌ Error iniciando scheduler: {str(e)}')

    def _register_jobs(self):
        """Registrar todas las tareas programadas"""

        # Tarea 1: Cancelar operaciones expiradas (cada 1 minuto)
        from app.services.operation_expiry_service import OperationExpiryService

        self.scheduler.add_job(
            func=self._expire_operations_job,
            trigger=IntervalTrigger(minutes=1),
            id='expire_operations',
            name='Cancelar operaciones con tiempo límite expirado',
            replace_existing=True
        )
        logger.info('📅 Job registrado: Cancelar operaciones expiradas (cada 1 minuto)')

    def _expire_operations_job(self):
        """Job para cancelar operaciones expiradas"""
        try:
            with self.app.app_context():
                from app.services.operation_expiry_service import OperationExpiryService
                expired_count = OperationExpiryService.expire_old_operations()
                if expired_count > 0:
                    logger.info(f'🔄 Job completado: {expired_count} operaciones canceladas')
        except Exception as e:
            logger.error(f'❌ Error en job de expiración: {str(e)}')
            import traceback
            logger.error(traceback.format_exc())

    def shutdown(self):
        """Detener el scheduler"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info('🛑 Scheduler detenido')


# Instancia global del scheduler
scheduler_service = SchedulerService()

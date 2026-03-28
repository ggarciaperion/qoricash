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

        # Tarea 2: Monitoreo de tipos de cambio de la competencia (cada 5 minutos)
        self.scheduler.add_job(
            func=self._fx_monitor_job,
            trigger=IntervalTrigger(minutes=5),
            id='fx_monitor_scrape',
            name='Scraping tipos de cambio competencia',
            replace_existing=True
        )
        logger.info('📅 Job registrado: FX Monitor scraping (cada 5 minutos)')

        # Tarea 3: Módulo Mercado — precios y señales (cada 5 minutos)
        self.scheduler.add_job(
            func=self._market_job,
            trigger=IntervalTrigger(minutes=5),
            id='market_prices',
            name='Actualización precios de mercado (yfinance)',
            replace_existing=True
        )
        logger.info('📅 Job registrado: Mercado — precios (cada 5 minutos)')

        # Tarea 4: Módulo Mercado — noticias RSS (cada 15 minutos)
        self.scheduler.add_job(
            func=self._market_news_job,
            trigger=IntervalTrigger(minutes=15),
            id='market_news',
            name='Recolección de noticias financieras (RSS)',
            replace_existing=True
        )
        logger.info('📅 Job registrado: Mercado — noticias RSS (cada 15 minutos)')

        # Tarea 5: Módulo Mercado — indicadores macro (cada 6 horas)
        self.scheduler.add_job(
            func=self._market_macro_job,
            trigger=IntervalTrigger(hours=6),
            id='market_macro',
            name='Indicadores macroeconómicos (BLS, BCRP)',
            replace_existing=True
        )
        logger.info('📅 Job registrado: Mercado — macro (cada 6 horas)')

    def _market_job(self):
        """Job para obtener precios de mercado y generar señales"""
        try:
            with self.app.app_context():
                from app.services.market.market_service import MarketService
                result = MarketService.run_price_cycle()
                logger.info(f'📊 Mercado precios: {result}')
        except Exception as e:
            logger.error(f'❌ Error en Market job: {str(e)}')
            import traceback
            logger.error(traceback.format_exc())

    def _market_news_job(self):
        """Job para recolectar noticias financieras via RSS"""
        try:
            with self.app.app_context():
                from app.services.market.market_service import MarketService
                result = MarketService.run_news_cycle()
                logger.info(f'📰 Mercado noticias: {result}')
        except Exception as e:
            logger.error(f'❌ Error en Market News job: {str(e)}')
            import traceback
            logger.error(traceback.format_exc())

    def _market_macro_job(self):
        """Job para indicadores macroeconómicos (BLS, BCRP, FRED)"""
        try:
            with self.app.app_context():
                from app.services.market.market_service import MarketService
                result = MarketService.run_macro_cycle()
                logger.info(f'📊 Macro: {result}')
        except Exception as e:
            logger.error(f'❌ Error en Macro job: {str(e)}')
            import traceback
            logger.error(traceback.format_exc())

    def _fx_monitor_job(self):
        """Job para scrapear tipos de cambio de la competencia"""
        try:
            with self.app.app_context():
                from app.services.fx_monitor.monitor_service import FXMonitorService
                result = FXMonitorService.run_scrape_cycle()
                logger.info(f'💱 FX Monitor: {result}')
        except Exception as e:
            logger.error(f'❌ Error en FX Monitor job: {str(e)}')
            import traceback
            logger.error(traceback.format_exc())

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

"""
Factory de la aplicación Flask para QoriCash Trading V2

Este archivo crea y configura la aplicación Flask usando el patrón Factory.
"""
# IMPORTANTE: Monkey patch de eventlet DEBE ir PRIMERO, antes de cualquier otra importación
import eventlet

# CRITICAL: Desactivar DNS monkey patching para permitir Cloudinary/S3
# Parchear solo lo necesario para Socket.IO
eventlet.monkey_patch(
    os=True,
    select=True,
    socket=True,
    thread=True,
    time=True
)

import logging
import os
from flask import Flask
from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, socketio, limiter, mail, cors
from app.services.scheduler_service import scheduler_service


def create_app(config_name=None):
    """
    Factory para crear la aplicación Flask

    Args:
        config_name: Nombre de la configuración ('development', 'production', 'testing')

    Returns:
        Flask app instance
    """
    app = Flask(__name__)

    # Cargar configuración
    if config_name:
        from app.config import config
        app.config.from_object(config[config_name])
    else:
        app.config.from_object(get_config())

    # Inicializar extensiones
    initialize_extensions(app)

    # Registrar blueprints
    register_blueprints(app)

    # Configurar logging
    configure_logging(app)

    # Registrar error handlers
    register_error_handlers(app)

    # Configurar Shell context (para flask shell)
    register_shell_context(app)

    # Inicializar scheduler de tareas en segundo plano (operaciones)
    scheduler_service.init_app(app)

    # Inicializar schedulers del módulo Mercado y FX Monitor
    start_market_schedulers(app)

    return app


def initialize_extensions(flask_app):
    """Inicializar extensiones de Flask"""
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)
    socketio.init_app(flask_app)
    mail.init_app(flask_app)

    # CORS - Permitir solicitudes desde el frontend web
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://qoricash.vercel.app",
        "https://www.qoricash.pe",
        "https://qoricash.pe",
        "https://qoricash-web.onrender.com"
    ]
    cors.init_app(
        flask_app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )

    if flask_app.config['RATELIMIT_ENABLED']:
        limiter.init_app(flask_app)

    # Configurar user_loader para Flask-Login
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Importar eventos de Socket.IO
    with flask_app.app_context():
        import app.socketio_events

    # Registrar filtros personalizados de Jinja2
    register_template_filters(flask_app)


def register_blueprints(app):
    """Registrar blueprints de la aplicación"""
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.users import users_bp
    from app.routes.clients import clients_bp
    from app.routes.operations import operations_bp
    from app.routes.position import position_bp
    from app.routes.platform import platform_bp
    from app.routes.legal import legal_bp
    from app.routes.referrals import referrals_bp
    from app.routes.fx_monitor import fx_monitor_bp
    from app.routes.market import market_bp
    from app.routes.compliance import compliance_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(clients_bp, url_prefix='/clients')
    app.register_blueprint(operations_bp, url_prefix='/operations')
    app.register_blueprint(position_bp, url_prefix='/position')
    app.register_blueprint(platform_bp)   # Sin prefijo, las rutas ya tienen /api/client y /api/platform
    app.register_blueprint(legal_bp)      # Rutas legales: /legal/terms, /legal/privacy
    app.register_blueprint(referrals_bp)  # Sistema de referidos
    app.register_blueprint(fx_monitor_bp) # Monitor de competencia TC
    app.register_blueprint(market_bp)     # Módulo Mercado
    app.register_blueprint(compliance_bp, url_prefix='/compliance')  # Módulo KYC/Compliance


def configure_logging(app):
    """Configurar logging de la aplicación"""
    if not app.debug and not app.testing:
        logging.basicConfig(
            level=getattr(logging, app.config['LOG_LEVEL']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))


def register_error_handlers(app):
    """Registrar manejadores de errores"""
    from flask import jsonify

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify({'success': False, 'error': 'Acceso denegado'}), 403


def register_template_filters(flask_app):
    """Registrar filtros personalizados de Jinja2"""

    def format_currency_filter(value, decimals=2):
        try:
            num = float(value)
            return f"{num:,.{decimals}f}"
        except (ValueError, TypeError):
            return "0.00"

    flask_app.jinja_env.filters['format_currency'] = format_currency_filter


def register_shell_context(app):
    """Registrar contexto para flask shell"""
    @app.shell_context_processor
    def make_shell_context():
        from app.models.user import User
        from app.models.client import Client
        from app.models.operation import Operation
        return {'db': db, 'User': User, 'Client': Client, 'Operation': Operation}


def start_market_schedulers(app):
    """Iniciar greenlets para jobs del módulo Mercado (precios, noticias, macro, fx_monitor)"""

    def _run_every(interval_sec, job_name, fn):
        def loop():
            logging.info(f"[MARKET] ✅ {job_name} iniciado (cada {interval_sec//60} min)")
            eventlet.sleep(30)  # pequeño delay al arrancar
            while True:
                try:
                    with app.app_context():
                        fn()
                except Exception as e:
                    import traceback
                    logging.error(f"[MARKET] ❌ {job_name}: {e}\n{traceback.format_exc()}")
                eventlet.sleep(interval_sec)
        eventlet.spawn(loop)

    def _prices():
        from app.services.market.market_service import MarketService
        r = MarketService.run_price_cycle()
        logging.info(f"[MARKET] Precios: {r}")

    def _news():
        from app.services.market.market_service import MarketService
        r = MarketService.run_news_cycle()
        logging.info(f"[MARKET] Noticias: {r}")

    def _macro():
        from app.services.market.market_service import MarketService
        r = MarketService.run_macro_cycle()
        logging.info(f"[MARKET] Macro: {r}")

    def _fx_monitor():
        from app.services.fx_monitor.monitor_service import FXMonitorService
        r = FXMonitorService.run_scrape_cycle()
        logging.info(f"[MARKET] FX Monitor: {r}")

    def _calendar():
        from app.services.market.market_service import MarketService
        r = MarketService.run_calendar_cycle()
        logging.info(f"[MARKET] Calendario: {r}")

    _run_every(5  * 60,   'Precios de mercado',   _prices)
    _run_every(15 * 60,   'Noticias RSS',          _news)
    _run_every(6  * 3600, 'Indicadores macro',     _macro)
    _run_every(5  * 60,   'FX Monitor scraping',   _fx_monitor)
    _run_every(24 * 3600, 'Calendario económico',  _calendar)

    # Análisis diario a las 8:30 AM Lima, lunes a viernes
    def _daily_analysis_at_time():
        from datetime import datetime, timezone, timedelta
        _LIMA = timezone(timedelta(hours=-5))

        def _next_830(now_lima):
            target = now_lima.replace(hour=8, minute=30, second=0, microsecond=0)
            if now_lima >= target:
                target += timedelta(days=1)
            while target.weekday() >= 5:
                target += timedelta(days=1)
            return target

        def loop():
            logging.info("[MARKET] ✅ Scheduler análisis diario 8:30 AM Lima iniciado")
            while True:
                now = datetime.now(_LIMA)
                next_run = _next_830(now)
                wait_secs = (next_run - now).total_seconds()
                logging.info(
                    f"[MARKET] Próximo análisis en "
                    f"{int(wait_secs//3600)}h {int((wait_secs%3600)//60)}m "
                    f"({next_run.strftime('%Y-%m-%d %H:%M')} Lima)"
                )
                eventlet.sleep(wait_secs)
                try:
                    with app.app_context():
                        from app.services.market.market_service import MarketService
                        r = MarketService.run_daily_analysis_cycle()
                        logging.info(f"[MARKET] Análisis base 8:30 AM: {r}")
                except Exception as e:
                    import traceback
                    logging.error(f"[MARKET] ❌ Análisis diario: {e}\n{traceback.format_exc()}")

        eventlet.spawn(loop)

    _daily_analysis_at_time()

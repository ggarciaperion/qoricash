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

# Scheduler global para expiración de operaciones
_scheduler_greenlet = None


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

    # Inicializar scheduler de expiración de operaciones usando eventlet
    # IMPORTANTE: Usar eventlet en lugar de APScheduler para compatibilidad con SocketIO
    start_operation_expiry_scheduler(app)

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
    # Incluye localhost para desarrollo y dominios de producción
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://qoricash.vercel.app",
        "https://www.qoricash.pe",
        "https://qoricash.pe"
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

    # Configurar headers de seguridad
    configure_security_headers(flask_app)


def register_blueprints(app):
    """Registrar blueprints de la aplicación"""
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.users import users_bp
    from app.routes.clients import clients_bp
    from app.routes.operations import operations_bp
    from app.routes.position import position_bp
    from app.routes.platform import platform_bp
    from app.routes.platform_api import platform_api_bp
    from app.routes.client_auth import client_auth_bp
    from app.routes.web_api import web_api_bp
    from app.routes.legal import legal_bp
    from app.routes.referrals import referrals_bp
    from app.routes.compliance import compliance_bp
    from app.routes.complaints import complaints_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(clients_bp, url_prefix='/clients')
    app.register_blueprint(operations_bp, url_prefix='/operations')
    app.register_blueprint(position_bp, url_prefix='/position')
    app.register_blueprint(platform_bp)  # Sin prefijo, las rutas ya tienen /api/platform
    app.register_blueprint(platform_api_bp)  # API pública plataforma: /api/platform/*
    app.register_blueprint(client_auth_bp)  # Autenticación de clientes: /api/client/* (web + móvil)
    app.register_blueprint(web_api_bp)  # API Web QoriCash: /api/web/*
    app.register_blueprint(legal_bp)  # Rutas legales: /legal/terms, /legal/privacy
    app.register_blueprint(referrals_bp)  # Sistema de referidos
    app.register_blueprint(compliance_bp, url_prefix='/compliance')  # Módulo de compliance
    app.register_blueprint(complaints_bp, url_prefix='/complaints')  # Módulo de reclamos


def configure_logging(app):
    """Configurar logging de la aplicación"""
    if not app.debug and not app.testing:
        # Configurar logging para producción
        logging.basicConfig(
            level=getattr(logging, app.config['LOG_LEVEL']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Logger de la app
        app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))


def register_error_handlers(app):
    """Registrar manejadores de errores"""
    from flask import jsonify

    @app.errorhandler(404)
    def not_found_error(error):
        # Siempre retornar JSON para APIs
        return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        # Siempre retornar JSON para APIs
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        # Siempre retornar JSON para APIs
        return jsonify({'success': False, 'error': 'Acceso denegado'}), 403


def configure_security_headers(flask_app):
    """
    Configurar headers de seguridad HTTP para proteger contra ataques comunes
    """
    @flask_app.after_request
    def add_security_headers(response):
        # Prevenir clickjacking
        response.headers['X-Frame-Options'] = 'DENY'

        # Prevenir MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Habilitar protección XSS del navegador
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Forzar HTTPS en producción (HSTS)
        if not flask_app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Content Security Policy - SOLO para rutas de API web/cliente
        # No aplicar CSP al sistema administrativo para no romper estilos de CDN
        from flask import request
        if request.path.startswith('/api/'):
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.socket.io https://vercel.live; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https: blob:; "
                "connect-src 'self' https://app.qoricash.pe wss://app.qoricash.pe https://qoricash.vercel.app https://vitals.vercel-insights.com; "
                "frame-ancestors 'none';"
            )

        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy (antes Feature-Policy)
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response


def register_template_filters(flask_app):
    """Registrar filtros personalizados de Jinja2"""

    def format_currency_filter(value, decimals=2):
        """
        Formatea un número como moneda con separador de miles (coma)
        Ejemplo: 1000000.50 -> 1,000,000.50
        """
        try:
            num = float(value)
            formatted = f"{num:,.{decimals}f}"
            return formatted
        except (ValueError, TypeError):
            return "0.00"

    # Registrar el filtro en el entorno de Jinja2
    flask_app.jinja_env.filters['format_currency'] = format_currency_filter


def register_shell_context(app):
    """Registrar contexto para flask shell"""
    @app.shell_context_processor
    def make_shell_context():
        from app.models.user import User
        from app.models.client import Client
        from app.models.operation import Operation
        return {
            'db': db,
            'User': User,
            'Client': Client,
            'Operation': Operation
        }


def start_operation_expiry_scheduler(app):
    """
    Iniciar scheduler de expiración de operaciones usando eventlet
    Se ejecuta en un greenlet separado cada 60 segundos

    IMPORTANTE: Solo se inicia UNA vez globalmente, incluso si gunicorn
    tiene múltiples workers. Usamos una variable global para evitar duplicados.
    """
    global _scheduler_greenlet

    # Solo iniciar si no está ya corriendo
    if _scheduler_greenlet is not None:
        logging.info("[SCHEDULER] Ya existe un scheduler en ejecución, no se inicia otro")
        return

    def scheduler_loop():
        """Loop infinito que expira operaciones cada 60 segundos"""
        import time
        logging.info("[SCHEDULER] ✅ Scheduler de expiración de operaciones iniciado")

        while True:
            try:
                with app.app_context():
                    from app.services.operation_expiry_service import OperationExpiryService
                    expired_count = OperationExpiryService.expire_old_operations()
                    if expired_count > 0:
                        logging.info(f"[SCHEDULER] ⏱️ {expired_count} operaciones canceladas automáticamente")
            except Exception as e:
                logging.error(f"[SCHEDULER] ❌ Error en scheduler de expiración: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())

            # Esperar 60 segundos antes de la próxima verificación
            eventlet.sleep(60)

    # Iniciar el scheduler en un greenlet separado
    _scheduler_greenlet = eventlet.spawn(scheduler_loop)
    logging.info("[SCHEDULER] 🚀 Greenlet de scheduler spawneado")

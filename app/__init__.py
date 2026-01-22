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

    # Inicializar scheduler de tareas en segundo plano
    scheduler_service.init_app(app)

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
    cors.init_app(
        flask_app,
        resources={r"/api/*": {"origins": ["http://localhost:3000", "http://localhost:3001", "https://qoricash.vercel.app"]}},
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
    from app.routes.platform_api import platform_api_bp
    from app.routes.client_auth import client_auth_bp
    from app.routes.web_api import web_api_bp
    from app.routes.legal import legal_bp
    from app.routes.referrals import referrals_bp
    from app.routes.compliance import compliance_bp

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

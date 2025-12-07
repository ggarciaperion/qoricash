"""
Factory de la aplicación Flask para QoriCash Trading V2

Este archivo crea y configura la aplicación Flask usando el patrón Factory.
"""
import logging


def create_app(config_name=None):
    """
    Factory para crear la aplicación Flask

    Args:
        config_name: Nombre de la configuración ('development', 'production', 'testing')

    Returns:
        Flask app instance
    """
    # Imports dentro de la función para evitar ejecución antes del monkey patch
    from flask import Flask
    from app.config import get_config

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
    
    return app


def initialize_extensions(flask_app):
    """Inicializar extensiones de Flask"""
    # Import aquí para evitar ejecución antes del monkey patch
    from app.extensions import db, migrate, login_manager, csrf, socketio, limiter, mail

    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)
    socketio.init_app(flask_app, cors_allowed_origins="*", async_mode='eventlet')
    mail.init_app(flask_app)

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
    from app.routes.compliance import compliance_bp
    from app.routes.platform_api import platform_api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(clients_bp, url_prefix='/clients')
    app.register_blueprint(operations_bp, url_prefix='/operations')
    app.register_blueprint(position_bp, url_prefix='/position')
    app.register_blueprint(compliance_bp, url_prefix='/compliance')
    app.register_blueprint(platform_api_bp)  # API Platform (ya tiene url_prefix='/api/platform')


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
    from app.extensions import db

    @app.errorhandler(404)
    def not_found_error(error):
        # Siempre retornar JSON para APIs
        return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        try:
            db.session.rollback()
        except:
            pass  # Si falla el rollback, continuar
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
    from app.extensions import db

    @app.shell_context_processor
    def make_shell_context():
        from app.models.user import User
        from app.models.client import Client
        from app.models.operation import Operation
        from app.models.compliance import (
            RiskLevel, ClientRiskProfile, ComplianceRule,
            ComplianceAlert, RestrictiveListCheck, TransactionMonitoring,
            ComplianceDocument, ComplianceAudit
        )
        return {
            'db': db,
            'User': User,
            'Client': Client,
            'Operation': Operation,
            'RiskLevel': RiskLevel,
            'ClientRiskProfile': ClientRiskProfile,
            'ComplianceRule': ComplianceRule,
            'ComplianceAlert': ComplianceAlert,
            'RestrictiveListCheck': RestrictiveListCheck,
            'TransactionMonitoring': TransactionMonitoring,
            'ComplianceDocument': ComplianceDocument,
            'ComplianceAudit': ComplianceAudit
        }


# Exportar socketio para que run.py pueda importarlo
# Import lazy para evitar ejecución antes del monkey patch
socketio = None


def _get_socketio():
    """Obtener instancia de socketio de forma lazy"""
    global socketio
    if socketio is None:
        from app.extensions import socketio as _socketio
        socketio = _socketio
    return socketio


# Permitir import directo de socketio
def __getattr__(name):
    if name == 'socketio':
        return _get_socketio()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

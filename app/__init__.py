"""
Factory de la aplicación Flask para QoriCash Trading V2

Este archivo crea y configura la aplicación Flask usando el patrón Factory.
"""
import logging
from flask import Flask
from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, socketio, limiter
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


def initialize_extensions(app):
    """Inicializar extensiones de Flask"""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app)
    
    if app.config['RATELIMIT_ENABLED']:
        limiter.init_app(app)
    
    # Configurar user_loader para Flask-Login
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))


def register_blueprints(app):
    """Registrar blueprints de la aplicación"""
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.users import users_bp
    from app.routes.clients import clients_bp
    from app.routes.operations import operations_bp
    from app.routes.platform import platform_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(clients_bp, url_prefix='/clients')
    app.register_blueprint(operations_bp, url_prefix='/operations')
    app.register_blueprint(platform_bp)  # Sin prefijo, las rutas ya tienen /api/client


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
    from flask import render_template, jsonify
    
    @app.errorhandler(404)
    def not_found_error(error):
        if request_wants_json():
            return jsonify({'error': 'Recurso no encontrado'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request_wants_json():
            return jsonify({'error': 'Error interno del servidor'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        if request_wants_json():
            return jsonify({'error': 'Acceso denegado'}), 403
        return render_template('errors/403.html'), 403


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


def request_wants_json():
    """Verificar si la petición espera JSON"""
    from flask import request
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
           request.accept_mimetypes[best] > request.accept_mimetypes['text/html']

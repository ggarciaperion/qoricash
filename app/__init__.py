"""
Factory de la aplicación Flask para QoriCash Trading V2

Este archivo crea y configura la aplicación Flask usando el patrón Factory.
Última actualización: 2026-01-16 - Force reload scheduler with 15min timeout
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

    # Inicializar scheduler de tareas en segundo plano
    initialize_scheduler(app)

    return app


def initialize_extensions(flask_app):
    """Inicializar extensiones de Flask"""
    # Import aquí para evitar ejecución antes del monkey patch
    from app.extensions import db, migrate, login_manager, csrf, socketio, limiter, mail, cors

    # Inicializar CORS primero - permitir requests desde localhost para desarrollo
    cors.init_app(flask_app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:3000",  # Página web QoriCash
                "http://localhost:3001",  # Página web QoriCash (puerto alternativo)
                "http://localhost:8081",  # App móvil Expo
                "http://localhost:8082",  # App móvil Expo (alternativo)
                "http://localhost:19006",  # App móvil Expo (web)
                "https://app.qoricash.pe",  # App móvil en producción
                "https://qoricash-web.vercel.app",  # Página web QoriCash en Vercel
                "https://www.qoricash.pe",  # Dominio principal de QoriCash
                "https://qoricash.pe"  # Dominio principal de QoriCash (sin www)
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })

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

    # Aplicar correcciones de esquema de base de datos (CRÍTICO)
    with flask_app.app_context():
        try:
            from app.utils.database_fixes import apply_all_fixes
            apply_all_fixes(db)
        except Exception as e:
            flask_app.logger.error(f"Error aplicando correcciones de BD: {str(e)}")

    # Registrar filtros personalizados de Jinja2
    register_template_filters(flask_app)


def register_blueprints(app):
    """Registrar blueprints de la aplicación"""
    from flask import send_from_directory
    import os

    # Ruta para servir favicon.ico
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )

    # Importar y registrar blueprints con manejo de errores
    try:
        from app.routes.auth import auth_bp
        app.register_blueprint(auth_bp)
        app.logger.info('✅ Blueprint auth_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando auth_bp: {str(e)}')

    try:
        from app.routes.dashboard import dashboard_bp
        app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
        app.logger.info('✅ Blueprint dashboard_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando dashboard_bp: {str(e)}')

    try:
        from app.routes.users import users_bp
        app.register_blueprint(users_bp, url_prefix='/users')
        app.logger.info('✅ Blueprint users_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando users_bp: {str(e)}')

    try:
        from app.routes.clients import clients_bp
        app.register_blueprint(clients_bp, url_prefix='/clients')
        app.logger.info('✅ Blueprint clients_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando clients_bp: {str(e)}')

    try:
        from app.routes.operations import operations_bp
        app.register_blueprint(operations_bp, url_prefix='/operations')
        app.logger.info('✅ Blueprint operations_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando operations_bp: {str(e)}')

    try:
        from app.routes.position import position_bp
        app.register_blueprint(position_bp, url_prefix='/position')
        app.logger.info('✅ Blueprint position_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando position_bp: {str(e)}')

    try:
        from app.routes.compliance import compliance_bp
        app.register_blueprint(compliance_bp, url_prefix='/compliance')
        app.logger.info('✅ Blueprint compliance_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando compliance_bp: {str(e)}')

    try:
        from app.routes.platform_api import platform_api_bp
        app.register_blueprint(platform_api_bp)
        app.logger.info('✅ Blueprint platform_api_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando platform_api_bp: {str(e)}')

    try:
        from app.routes.platform import platform_bp
        app.register_blueprint(platform_bp)
        app.logger.info('✅ Blueprint platform_bp registrado (endpoints: /api/client/register, /api/web/add-bank-account)')
    except Exception as e:
        app.logger.error(f'❌ Error registrando platform_bp: {str(e)}')

    try:
        from app.routes.client_auth import client_auth_bp
        app.register_blueprint(client_auth_bp)
        app.logger.info('✅ Blueprint client_auth_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando client_auth_bp: {str(e)}')

    try:
        from app.routes.web_api import web_api_bp
        app.register_blueprint(web_api_bp)
        app.logger.info('✅ Blueprint web_api_bp registrado exitosamente')
    except Exception as e:
        app.logger.error(f'❌ ERROR CRÍTICO registrando web_api_bp: {str(e)}')
        import traceback
        app.logger.error(traceback.format_exc())

    try:
        from app.routes.legal import legal_bp
        app.register_blueprint(legal_bp)
        app.logger.info('✅ Blueprint legal_bp registrado')
    except Exception as e:
        app.logger.error(f'❌ Error registrando legal_bp: {str(e)}')

    try:
        from app.routes.referrals import referrals_bp
        app.register_blueprint(referrals_bp)
        app.logger.info('✅ Blueprint referrals_bp registrado (Sistema de referidos)')
    except Exception as e:
        app.logger.error(f'❌ Error registrando referrals_bp: {str(e)}')


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
    from flask import jsonify, session, request
    from flask_login import current_user
    from app.extensions import db
    from datetime import datetime, timedelta

    @app.before_request
    def check_session_timeout():
        """Verificar timeout de sesión en cada petición"""
        # Solo verificar para usuarios autenticados
        if current_user.is_authenticated:
            # Obtener última actividad de la sesión
            last_activity = session.get('last_activity')

            if last_activity:
                # Obtener tiempo actual en UTC sin timezone (naive)
                now = datetime.utcnow()

                # Convertir last_activity a datetime naive si es necesario
                if isinstance(last_activity, str):
                    last_activity = datetime.fromisoformat(last_activity)

                # Si last_activity tiene timezone, removerlo para comparación
                if hasattr(last_activity, 'tzinfo') and last_activity.tzinfo is not None:
                    last_activity = last_activity.replace(tzinfo=None)

                # Verificar si han pasado más de 10 minutos
                timeout_limit = timedelta(minutes=10)
                if now - last_activity > timeout_limit:
                    # Limpiar sesión por timeout
                    session.clear()
                    return jsonify({
                        'success': False,
                        'error': 'Su sesión expiró',
                        'redirect': '/login'
                    }), 401

            # Actualizar última actividad (siempre como naive datetime)
            session['last_activity'] = datetime.utcnow()
            session.modified = True

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


def initialize_scheduler(app):
    """Inicializar scheduler de tareas en segundo plano"""
    from app.services.scheduler_service import scheduler_service

    # Inicializar scheduler solo en modo producción o desarrollo (no en tests)
    if not app.testing:
        scheduler_service.init_app(app)
        app.logger.info('🕐 Scheduler de tareas en segundo plano inicializado con fix de timezone UTC')


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

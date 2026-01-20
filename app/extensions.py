"""
Extensiones de Flask para QoriCash Trading V2

Todas las extensiones se inicializan aquí y se configuran en __init__.py
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_cors import CORS

# Database
db = SQLAlchemy()
migrate = Migrate()

# Authentication
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página'
login_manager.login_message_category = 'warning'

# Security
csrf = CSRFProtect()

# Rate Limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# WebSocket (Real-time)
# Configuración optimizada para evitar errores "Bad file descriptor"
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='eventlet',  # DEBE ser 'eventlet' cuando gunicorn usa worker_class='eventlet'
    logger=True,  # Habilitar logging para capturar errores
    engineio_logger=False,  # Mantener deshabilitado para evitar spam
    ping_timeout=120,  # Aumentado a 2 minutos para conexiones lentas
    ping_interval=25,
    # Configuración adicional para manejo robusto de conexiones
    cors_credentials=True,
    always_connect=True,  # Permitir reconexiones automáticas
    manage_session=False  # Evita problemas con sesiones Flask en eventlet
)

# Email
mail = Mail()

# CORS - Cross-Origin Resource Sharing
cors = CORS()

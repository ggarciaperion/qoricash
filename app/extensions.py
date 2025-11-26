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
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='eventlet',  # DEBE ser 'eventlet' cuando gunicorn usa worker_class='eventlet'
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25
)

# Email
mail = Mail()

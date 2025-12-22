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
login_manager.session_protection = 'strong'  # Protección fuerte: invalida sesión si cambia IP/User-Agent
login_manager.refresh_view = 'auth.login'
login_manager.needs_refresh_message = 'Para proteger tu cuenta, por favor vuelve a iniciar sesión'
login_manager.needs_refresh_message_category = 'info'

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
    async_mode='eventlet',
    logger=False,
    engineio_logger=False
)

# Email
mail = Mail()

# CORS - Allow cross-origin requests from mobile app
cors = CORS()

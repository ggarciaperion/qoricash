"""
Configuración de la aplicación QoriCash Trading V2
"""
import os
from datetime import timedelta

class Config:
    """Configuración base"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Set True for SQL debugging

    # Pool de conexiones - Prevenir "SSL SYSCALL error: EOF detected"
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,                    # Máximo 5 conexiones en el pool
        'pool_recycle': 280,               # Reciclar conexiones cada 280 segundos (antes del timeout de 300s de Render)
        'pool_pre_ping': True,             # Verificar conexión antes de usar (auto-reconectar si está cerrada)
        'max_overflow': 2,                 # Máximo 2 conexiones extra si se necesitan
        'pool_timeout': 30,                # Timeout de 30s para obtener una conexión del pool
        'connect_args': {
            'connect_timeout': 10,         # Timeout de 10s para conectar a la DB
            'keepalives': 1,               # Habilitar TCP keepalives
            'keepalives_idle': 30,         # Enviar keepalive cada 30s
            'keepalives_interval': 10,     # Intervalo entre keepalives
            'keepalives_count': 5          # Intentos de keepalive antes de considerar conexión muerta
        }
    }
    
    # Session
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 43200))  # 12 hours
    )
    
    # File Upload (Cloudinary)
    CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max file size
    
    # Rate Limiting
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'True') == 'True'
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Timezone
    TIMEZONE = os.environ.get('TIMEZONE', 'America/Lima')
    
    # SocketIO
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE')
    
    # CSRF
    WTF_CSRF_TIME_LIMIT = None  # No expiration
    WTF_CSRF_SSL_STRICT = False  # Allow HTTPS in production

    # Email Configuration (Principal - para nuevas operaciones)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')

    # Email de confirmación (para operaciones completadas)
    MAIL_CONFIRMATION_USERNAME = os.environ.get('MAIL_CONFIRMATION_USERNAME')
    MAIL_CONFIRMATION_PASSWORD = os.environ.get('MAIL_CONFIRMATION_PASSWORD')
    MAIL_CONFIRMATION_SENDER = os.environ.get('MAIL_CONFIRMATION_SENDER')

    MAIL_MAX_EMAILS = None
    MAIL_ASCII_ATTACHMENTS = False


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_ECHO = True  # Show SQL queries


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Configuración para tests"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Diccionario de configuraciones
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Obtener configuración según el entorno"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])

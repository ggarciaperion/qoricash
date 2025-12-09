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
    # Render puede usar DATABASE_URL o RENDER_EXTERNAL_URL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or os.environ.get('RENDER_DATABASE_URL')

    # Debug: Imprimir estado de DATABASE_URL (solo en inicio)
    if not SQLALCHEMY_DATABASE_URI:
        print("[CONFIG ERROR] DATABASE_URL no encontrada en variables de entorno")
        print(f"[CONFIG] Variables disponibles: {[k for k in os.environ.keys() if 'DATABASE' in k or 'POSTGRES' in k]}")
    else:
        print(f"[CONFIG] DATABASE_URL encontrada: {SQLALCHEMY_DATABASE_URI[:20]}...")

    # Convertir postgres:// a postgresql:// (Render usa postgres:// pero SQLAlchemy 2.x requiere postgresql://)
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
        print("[CONFIG] DATABASE_URL convertida de postgres:// a postgresql://")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Set True for SQL debugging
    
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

    # Database optimizations for eventlet
    # Eventlet requires special pool configuration to avoid lock issues
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 10,
        'pool_timeout': 30,
        # This is critical for eventlet compatibility
        'connect_args': {'options': '-c statement_timeout=300000'}
    }

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True

    # Performance
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year for static files


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
    # Detectar automáticamente producción si estamos en Render
    env = os.environ.get('FLASK_ENV')

    # Si no está configurado FLASK_ENV, detectar automáticamente
    if not env:
        # Si estamos en Render (tiene RENDER o DATABASE_URL en env), usar producción
        if os.environ.get('RENDER') or os.environ.get('DATABASE_URL'):
            env = 'production'
            print("[CONFIG] Entorno detectado automáticamente: production (Render)")
        else:
            env = 'development'
            print("[CONFIG] Entorno detectado automáticamente: development")
    else:
        print(f"[CONFIG] Entorno configurado: {env}")

    return config.get(env, config['default'])

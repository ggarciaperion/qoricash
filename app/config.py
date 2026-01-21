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
    # Render puede usar DATABASE_URL. Convertir postgres:// a postgresql://
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Set True for SQL debugging
    
    # Session Security
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Timeout de inactividad del servidor: 10 minutos (backend)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=10)
    # Sesión NO permanente: se cierra al cerrar navegador (cookie de sesión)
    SESSION_PERMANENT = False
    # Cookie de sesión temporal: se borra al cerrar el navegador
    SESSION_COOKIE_NAME = 'session'
    SESSION_REFRESH_EACH_REQUEST = True  # Refrescar sesión en cada petición
    
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

    # Email Configuration (Unified)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')
    MAIL_MAX_EMAILS = None
    MAIL_ASCII_ATTACHMENTS = False

    # Email Configuration - Completed Operations (Optional)
    # Si no se configuran, se usarán las credenciales regulares (MAIL_*) como fallback
    MAIL_CONFIRMATION_USERNAME = os.environ.get('MAIL_CONFIRMATION_USERNAME')
    MAIL_CONFIRMATION_PASSWORD = os.environ.get('MAIL_CONFIRMATION_PASSWORD')
    MAIL_CONFIRMATION_SENDER = os.environ.get('MAIL_CONFIRMATION_SENDER')

    # NubeFact API Configuration
    NUBEFACT_API_URL = os.environ.get('NUBEFACT_API_URL', 'https://api.nubefact.com/api/v1')
    NUBEFACT_TOKEN = os.environ.get('NUBEFACT_TOKEN')
    NUBEFACT_RUC = os.environ.get('NUBEFACT_RUC', '20615113698')
    NUBEFACT_ENABLED = os.environ.get('NUBEFACT_ENABLED', 'False') == 'True'

    # Company Information (Emisor)
    COMPANY_RUC = os.environ.get('COMPANY_RUC', '20615113698')
    COMPANY_NAME = os.environ.get('COMPANY_NAME', 'QORICASH SAC')
    COMPANY_ADDRESS = os.environ.get('COMPANY_ADDRESS', 'AV. BRASIL NRO. 2790 INT. 504')
    COMPANY_DISTRICT = os.environ.get('COMPANY_DISTRICT', 'PUEBLO LIBRE')
    COMPANY_PROVINCE = os.environ.get('COMPANY_PROVINCE', 'LIMA')
    COMPANY_DEPARTMENT = os.environ.get('COMPANY_DEPARTMENT', 'LIMA')


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
        'pool_recycle': 1800,  # Reciclar conexiones cada 30 min (reducido de 1 hora)
        'pool_pre_ping': True,  # Verificar conexiones antes de usarlas
        'max_overflow': 5,  # Reducido overflow para evitar exceso de conexiones
        'pool_timeout': 30,
        'pool_reset_on_return': 'rollback',  # Limpiar transacciones al devolver conexión
        # This is critical for eventlet compatibility
        'connect_args': {
            'options': '-c statement_timeout=120000',  # Timeout de 2 min (reducido de 5)
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
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
    env = os.environ.get('FLASK_ENV', 'production')
    return config.get(env, config['default'])

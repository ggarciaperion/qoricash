"""
Configuración de Gunicorn para producción en Render
Optimizado para Flask-SocketIO con eventlet
"""
import os
import logging

# Bind
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Workers - 1 worker con eventlet para Socket.IO (512MB RAM plan Starter)
workers = 1
worker_class = 'eventlet'
worker_connections = 1000
threads = 1

# Timeouts - AUMENTADOS para evitar worker timeout
timeout = 300  # 5 minutos (antes 180s)
graceful_timeout = 120  # 2 minutos (antes 90s)
keepalive = 5

# Memory limits - AUMENTADO para reducir reinicios frecuentes
max_requests = 1000  # Antes 250 - causaba reinicios cada 250 requests
max_requests_jitter = 50  # Antes 25

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'warning'  # Cambiado de 'info' a 'warning' para reducir spam
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Configurar filtro para suprimir errores conocidos de Socket.IO
class SocketIOErrorFilter(logging.Filter):
    """Filtro para suprimir errores conocidos de Socket.IO que son benignos"""
    def filter(self, record):
        # Suprimir errores "Bad file descriptor" que son comunes en desconexiones abruptas
        if 'Bad file descriptor' in str(record.getMessage()):
            return False
        # Suprimir errores de socket shutdown esperados
        if 'socket shutdown error' in str(record.getMessage()):
            return False
        return True

# Aplicar filtro al logger de gunicorn
logging.getLogger('gunicorn.error').addFilter(SocketIOErrorFilter())

# Preload
preload_app = False

# Worker temp directory
worker_tmp_dir = '/dev/shm'

print(f"✓ Gunicorn configurado: {workers} workers, timeout {timeout}s, loglevel {loglevel}")

# Hook: Ejecutar cuando cada worker arranca (más confiable que on_starting con eventlet)
def post_worker_init(worker):
    """
    Hook que se ejecuta cuando cada worker termina de inicializarse.
    OPTIMIZADO: Solo verifica conectividad, no crea tablas ni usuarios en cada reinicio.
    """
    print(f"🔧 Worker {worker.pid} inicializado")

    try:
        # Importar aquí para evitar problemas de importación circular
        from app import create_app
        from app.extensions import db

        app = create_app()

        with app.app_context():
            # Solo verificar conectividad con una query simple
            db.session.execute(db.text('SELECT 1'))
            print("✓ Conexión DB verificada")

    except Exception as e:
        print(f"❌ Error verificando DB: {e}")
        # No hacer traceback para no llenar logs

def worker_abort(worker):
    """Hook cuando un worker es abortado - limpiar recursos"""
    print(f"⚠️  Worker {worker.pid} siendo abortado")

def on_exit(server):
    """Hook cuando el servidor se apaga - limpiar recursos"""
    print("🔴 Servidor Gunicorn apagándose")

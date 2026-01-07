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

# Timeouts - AUMENTADOS TEMPORALMENTE mientras se aplican índices
timeout = 600  # 10 minutos - temporal hasta que se apliquen índices
graceful_timeout = 180  # 3 minutos
keepalive = 5

# Memory limits - AUMENTADO para reducir reinicios frecuentes
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'warning'  # Reduce spam en logs
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

print(f"✓ Gunicorn configurado: {workers} workers (eventlet), timeout {timeout}s, loglevel {loglevel}")
print(f"⚠️  NOTA: Timeout alto temporal - aplicar índices de BD para mejorar performance")

# Hook: Ejecutar cuando cada worker arranca
def post_worker_init(worker):
    """Hook que se ejecuta cuando cada worker termina de inicializarse"""
    print(f"🔧 Worker {worker.pid} inicializado (eventlet)")

    try:
        from app import create_app
        from app.extensions import db

        app = create_app()

        with app.app_context():
            # Solo verificar conectividad
            db.session.execute(db.text('SELECT 1'))
            print("✓ Conexión DB verificada")

    except Exception as e:
        print(f"❌ Error verificando DB: {e}")

def worker_abort(worker):
    """Hook cuando un worker es abortado"""
    print(f"⚠️  Worker {worker.pid} abortado (probablemente por timeout)")

def on_exit(server):
    """Hook cuando el servidor se apaga"""
    print("🔴 Servidor Gunicorn apagándose")

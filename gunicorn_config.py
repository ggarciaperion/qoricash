"""
Configuración de Gunicorn para producción en Render
Optimizado para QoriCash Trading
"""
# CRÍTICO: Monkey patch de eventlet DEBE ser lo primero
# Esto debe ejecutarse ANTES de cualquier otro import
import eventlet
eventlet.monkey_patch()

import os
import multiprocessing

# Bind
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Workers - Optimizado para Render con eventlet
workers = int(os.environ.get('WEB_CONCURRENCY', 1))
worker_class = 'eventlet'  # Para WebSocket/SocketIO - no usar threads con eventlet
worker_connections = 1000

# Timeouts - Extendidos para operaciones largas
timeout = 300  # 5 minutos
graceful_timeout = 120
keepalive = 5

# Memory limits - Prevenir memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Preload - DISABLED para eventlet (causa lock issues con Flask sessions)
preload_app = False

# Worker temp directory
worker_tmp_dir = '/dev/shm'

# Process naming
proc_name = 'qoricash_trading'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (si se usa certificado propio)
keyfile = None
certfile = None

print(f"[GUNICORN] Configurado: {workers} workers ({worker_class}), timeout {timeout}s")
print(f"[GUNICORN] Conexiones por worker: {worker_connections}")

# Hooks para inicialización de workers
def post_fork(server, worker):
    """
    Hook ejecutado después de que un worker es forked.
    Asegura que eventlet y psycopg2 estén correctamente inicializados en cada worker.
    """
    print(f"[WORKER {worker.pid}] Inicializando con eventlet monkey patch")

    # El monkey patch ya se ejecutó arriba, pero reforzamos para el worker
    import eventlet
    eventlet.monkey_patch()

    # Configurar psycopg2 para trabajar con eventlet usando psycogreen
    try:
        from psycogreen.eventlet import patch_psycopg
        patch_psycopg()
        print(f"[WORKER {worker.pid}] psycopg2 patched con psycogreen")
    except ImportError:
        print(f"[WORKER {worker.pid}] WARNING: psycogreen no disponible")

    print(f"[WORKER {worker.pid}] Listo para recibir requests")

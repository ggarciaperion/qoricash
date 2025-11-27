"""
Configuración de Gunicorn para producción en Render
Optimizado para QoriCash Trading
"""
import os
import multiprocessing

# Bind
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Workers - Optimizado para Render
workers = int(os.environ.get('WEB_CONCURRENCY', 4))
worker_class = 'eventlet'  # Mejor para WebSocket/SocketIO
worker_connections = 1000
threads = 2

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

# Preload
preload_app = True  # Mejor para producción

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
print(f"[GUNICORN] Threads por worker: {threads}")

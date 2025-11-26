"""
Configuración de Gunicorn para producción en Render
"""
import os

# Bind
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Workers - 2 workers con eventlet para Socket.IO (optimizado para plan pagado)
workers = 2
worker_class = 'eventlet'

# Timeouts
timeout = 60
graceful_timeout = 30
keepalive = 2

# Memory limits (optimizado para plan Starter)
max_requests = 500
max_requests_jitter = 50

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Preload
preload_app = False

# Worker temp directory
worker_tmp_dir = '/dev/shm'

print(f"✓ Gunicorn configurado: {workers} workers, timeout {timeout}s")

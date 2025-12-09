"""
Entry point para QoriCash Trading V2

Desarrollo: python run.py
Producción: gunicorn -c gunicorn_config.py run:app
"""
# CRÍTICO: Monkey patch de eventlet DEBE ser lo primero
# Esto debe ejecutarse antes de cualquier import de threading, SQLAlchemy, etc.
import eventlet
eventlet.monkey_patch()

# Configurar psycopg2 para eventlet INMEDIATAMENTE después del monkey patch
try:
    from psycogreen.eventlet import patch_psycopg
    patch_psycopg()
    print("[RUN.PY] psycopg2 patched con psycogreen")
except ImportError:
    print("[RUN.PY] WARNING: psycogreen no disponible")

import os
from dotenv import load_dotenv

# Cargar variables de entorno (después de monkey patch)
load_dotenv()

# Ahora sí importar la app (para que config.py ya tenga las variables disponibles)
from app import create_app, socketio

# Crear aplicación (usado por gunicorn)
app = create_app()

# Healthcheck endpoint - SIN rate limiting, optimizado para respuesta rápida
from app.extensions import limiter
from flask import jsonify
import time

@app.route('/health')
@limiter.exempt
def health_check():
    """
    Endpoint para health checks de Render
    Responde inmediatamente sin consultas a BD
    """
    return jsonify({
        'status': 'healthy',
        'service': 'qoricash-trading',
        'timestamp': time.time()
    }), 200, {'Cache-Control': 'no-cache, no-store, must-revalidate'}

if __name__ == '__main__':
    # Solo para desarrollo local
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True
    )

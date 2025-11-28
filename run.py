"""
Entry point para QoriCash Trading V2

Desarrollo: python run.py
Producción: gunicorn -c gunicorn_config.py run:app
"""
# CRÍTICO: Monkey patch de eventlet DEBE ser lo primero
# Esto debe ejecutarse antes de cualquier import de threading, SQLAlchemy, etc.
import eventlet
eventlet.monkey_patch()

import os
from dotenv import load_dotenv

# Cargar variables de entorno (después de monkey patch)
load_dotenv()

# Ahora sí importar la app (para que config.py ya tenga las variables disponibles)
from app import create_app, socketio

# Crear aplicación (usado por gunicorn)
app = create_app()

# Healthcheck endpoint
@app.route('/health')
def health_check():
    """Endpoint para verificar que el servicio está vivo"""
    return {'status': 'healthy', 'service': 'qoricash-trading'}, 200

if __name__ == '__main__':
    # Solo para desarrollo local
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True
    )

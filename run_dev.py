"""
Entry point para desarrollo local en macOS.
Evita el conflicto eventlet + cloudinary en Python 3.9 / macOS.

Uso: python3 run_dev.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Forzar modo desarrollo sin eventlet
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('DEBUG', 'true')

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[DEV] QoriCash corriendo en http://localhost:{port}")
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=True,
        allow_unsafe_werkzeug=True,
        use_reloader=False,
    )

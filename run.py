"""
Entry point para desarrollo de QoriCash Trading V2

Ejecutar con: python run.py
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno PRIMERO (antes de importar app)
load_dotenv()

# Ahora sí importar la app (para que config.py ya tenga las variables disponibles)
from app import create_app, socketio

# Crear aplicación
app = create_app()

if __name__ == '__main__':
    # Ejecutar con SocketIO
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEBUG']
    )

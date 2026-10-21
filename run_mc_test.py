"""
run_mc_test.py — Servidor de prueba Mission Control v2
DB aislada: qoricash_mc_test (PostgreSQL local, datos ficticios)
NO conecta a producción.
"""
import os
from dotenv import load_dotenv

# 1. Cargar .env base
load_dotenv()

# 2. Sobrescribir DATABASE_URL con la DB de prueba aislada
DB_USER = os.environ.get('USER', 'gianpierre')
os.environ['DATABASE_URL']  = f'postgresql://{DB_USER}@localhost/qoricash_mc_test'
os.environ['FLASK_ENV']     = 'development'
os.environ['DEBUG']         = 'true'
os.environ['PORT']          = '5001'
os.environ['EVENTLET_HUB']  = 'poll'   # evita bug kqueue en macOS/Python 3.9

for _k in ('REDIS_URL', 'CLOUDINARY_URL'):
    os.environ.pop(_k, None)

from app import create_app
from app.extensions import socketio

app = create_app()

print()
print("=" * 60)
print("  MISSION CONTROL v2 — DEMO LOCAL (DATOS FICTICIOS)")
print(f"  DB:   postgresql://{DB_USER}@localhost/qoricash_mc_test")
print("  ENV:  development  (EVENTLET_HUB=poll, no producción)")
print("  URL:  http://localhost:5001/agentes/mission-control")
print("=" * 60)

if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=5001,
        debug=True,
        allow_unsafe_werkzeug=True,
        use_reloader=False,
    )

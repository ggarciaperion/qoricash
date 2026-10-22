"""
run_mc_test.py — Servidor de prueba Mission Control v2
DB aislada: qoricash_mc_test (PostgreSQL local, datos ficticios)
NO conecta a producción.
"""
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.environ.get('USER', 'gianpierre')
os.environ['DATABASE_URL']  = f'postgresql://{DB_USER}@localhost/qoricash_mc_test'
os.environ['FLASK_ENV']     = 'development'
os.environ['DEBUG']         = 'true'
os.environ['PORT']          = '5001'
os.environ['EVENTLET_HUB']  = 'poll'

for _k in ('REDIS_URL', 'CLOUDINARY_URL'):
    os.environ.pop(_k, None)

from app import create_app
from app.extensions import socketio, login_manager

app = create_app()

# --- Bypass de autenticación para localhost ---
from flask import request as _req
from app.models.user import User

# 1. request_loader: autentica desde IP sin sesión
@login_manager.request_loader
def load_user_from_request(request):
    if request.remote_addr in ('127.0.0.1', '::1'):
        return User.query.filter_by(username='mc_test').first()
    return None

# 2. Reemplazar enforce_single_session para que salte en localhost
_fns = app.before_request_funcs.setdefault(None, [])
_orig_enforce = next((f for f in _fns if f.__name__ == 'enforce_single_session'), None)

if _orig_enforce:
    def _enforce_patched():
        if _req.remote_addr in ('127.0.0.1', '::1'):
            return None   # sin validación de token en demo local
        return _orig_enforce()
    _enforce_patched.__name__ = 'enforce_single_session'
    idx = _fns.index(_orig_enforce)
    _fns[idx] = _enforce_patched

print()
print("=" * 60)
print("  MISSION CONTROL v2 — DEMO LOCAL (DATOS FICTICIOS)")
print(f"  DB:   postgresql://{DB_USER}@localhost/qoricash_mc_test")
print("  URL:  http://localhost:5001/agentes/mission-control")
print("  AUTH: sin login (bypass en localhost)")
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

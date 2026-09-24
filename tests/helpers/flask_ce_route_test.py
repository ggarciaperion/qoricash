#!/usr/bin/env python3
"""
Subprocess helper: prueba la ruta HTTP PUT /clients/api/update/<id>
con un cliente CE real en Flask test client.

Uso:
    python3 flask_ce_route_test.py <db_url>

Proceso:
1. Crea Flask app con la DB de prueba (SQLite in-memory o PG).
2. Crea tablas, usuario Master y cliente CE.
3. Invoca la ruta con test client autenticado.
4. Verifica respuesta y datos persistidos.
5. Imprime resultado JSON.
"""
import sys, os, json

DB_URL = sys.argv[1] if len(sys.argv) > 1 else 'sqlite:///:memory:'

os.environ['DATABASE_URL'] = DB_URL
os.environ.setdefault('SECRET_KEY', 'test-secret-p5')
os.environ.setdefault('WTF_CSRF_SECRET_KEY', 'test-csrf-p5')
os.environ.setdefault('ANTHROPIC_API_KEY', '')
os.environ.setdefault('CLOUDINARY_URL', '')
os.environ.setdefault('MAIL_USERNAME', '')
os.environ.setdefault('MAIL_PASSWORD', '')

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, '..', '..'))

# Pre-mock cloudinary ANTES de importar app para evitar el crash:
# app/__init__.py → eventlet.monkey_patch() → cloudinary.__init__ → platform.platform()
# → subprocess.check_output → eventlet kqueue hub → TypeError en macOS.
from unittest.mock import MagicMock as _MagicMock
for _cld_mod in ('cloudinary', 'cloudinary.uploader', 'cloudinary.api',
                 'cloudinary.exceptions', 'cloudinary.utils'):
    sys.modules.setdefault(_cld_mod, _MagicMock())

try:
    from app import create_app
    from app.extensions import db

    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
    app.config['WTF_CSRF_ENABLED']        = False
    app.config['TESTING']                 = True
    app.config['LOGIN_DISABLED']          = False  # queremos probar auth
    # Deshabilitar rate limiting en tests
    app.config['RATELIMIT_ENABLED']       = False

    with app.app_context():
        db.create_all()

        # Crear usuario Master para autenticación
        from app.models.user import User
        master = User(
            username='test_master_p5',
            email='master_p5@test.com',
            role='Master',
            dni='00000000',
            status='Activo',
        )
        # macOS Python 3.9 + LibreSSL no soporta scrypt (werkzeug default).
        # Usar pbkdf2:sha256 que sí está disponible.
        from werkzeug.security import generate_password_hash as _gph
        master.password_hash = _gph('TestPass123!', method='pbkdf2:sha256')
        db.session.add(master)
        db.session.flush()

        # Crear cliente CE con apellidos NULL y DNI con cero inicial
        from app.models.client import Client
        ce_client = Client(
            document_type='CE',
            dni='012345678',
            nombres='MARIA',
            apellido_paterno=None,
            apellido_materno=None,
            email='maria_ce_p5@test.com',
            phone='999000111',
            status='Activo',
            created_by=master.id,
        )
        db.session.add(ce_client)
        db.session.commit()

        client_id = ce_client.id
        master_id = master.id   # Guardar antes de que el contexto cierre la sesión

    # Probar ruta con test client
    with app.test_client() as tc:
        # Login
        with tc.session_transaction() as sess:
            sess['_user_id'] = str(master_id)
            sess['_fresh']   = True

        # PUT a la ruta de actualización
        resp = tc.put(
            f'/clients/api/update/{client_id}',
            json={
                'nombres':          'MARIA ELENA',
                'apellido_paterno': '',
                'apellido_materno': '',
            },
            content_type='application/json',
        )

        resp_data = json.loads(resp.data.decode())
        status_code = resp.status_code

    # Verificar datos persistidos
    with app.app_context():
        from app.models.client import Client
        updated = Client.query.get(client_id)
        apellido_paterno_db = updated.apellido_paterno
        apellido_materno_db = updated.apellido_materno
        nombres_db          = updated.nombres
        dni_db              = updated.dni

    print(json.dumps({
        'ok':               status_code == 200 and resp_data.get('success'),
        'status_code':      status_code,
        'success':          resp_data.get('success'),
        'message':          resp_data.get('message', ''),
        'apellido_paterno': apellido_paterno_db,
        'apellido_materno': apellido_materno_db,
        'nombres':          nombres_db,
        'dni':              dni_db,
    }))

except Exception as exc:
    import traceback
    print(json.dumps({'ok': False, 'error': str(exc), 'trace': traceback.format_exc()}))
    sys.exit(1)

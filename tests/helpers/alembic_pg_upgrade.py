#!/usr/bin/env python3
"""
Subprocess helper: corre alembic upgrade real dentro del contexto Flask.

Uso:
    python3 alembic_pg_upgrade.py <db_url> [start_revision]

Fases:
1. Crea Flask app con la DB de prueba.
2. Hace alembic upgrade hasta start_revision (para establecer el estado previo).
3. Inserta una fila preexistente en wa_messages.
4. Continúa upgrade hasta head.
5. Verifica columnas y datos, imprime resultado JSON.

Requiere que la DB exista y esté vacía (sin tablas de alembic).
"""
import sys, os, json

DB_URL         = sys.argv[1]
START_REVISION = sys.argv[2] if len(sys.argv) > 2 else 'e3t4a5p6a3b4'

# Configurar entorno mínimo para Flask
os.environ['DATABASE_URL'] = DB_URL
os.environ.setdefault('SECRET_KEY', 'test-secret-p4')
os.environ.setdefault('WTF_CSRF_SECRET_KEY', 'test-csrf-p4')
os.environ.setdefault('ANTHROPIC_API_KEY', '')
os.environ.setdefault('CLOUDINARY_URL', '')
os.environ.setdefault('TWILIO_ACCOUNT_SID', '')
os.environ.setdefault('TWILIO_AUTH_TOKEN', '')
os.environ.setdefault('TWILIO_PHONE_NUMBER', '')

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
    # Importaciones mínimas — NO se usa create_app porque registra blueprints,
    # schedulers y threads que abren conexiones PG y bloquean el DDL de alembic.
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from flask_migrate import Migrate
    from alembic.config import Config
    from alembic import command as alembic_cmd
    import psycopg2

    # App mínima: solo SQLAlchemy + Flask-Migrate, sin blueprints ni background tasks.
    # env.py de alembic solo necesita current_app.extensions['migrate'].db.
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
    app.config['SQLALCHEMY_ECHO']         = False
    app.config['SECRET_KEY']              = 'test-p4'

    _db = SQLAlchemy()
    _db.init_app(app)
    Migrate(app, _db)

    MIGRATIONS_DIR = os.path.join(BASE, '..', '..', 'migrations')
    INI_FILE       = os.path.join(MIGRATIONS_DIR, 'alembic.ini')

    # Fase 1: Crear baseline coherente con {w1a2b3o4t5s6, e3t4a5p6a3b4}.
    # El grafo histórico tiene múltiples raíces con FK cross-branch que impiden
    # un 'alembic upgrade' limpio desde cero. Se establece el baseline con
    # psycopg2 + stamp manual (solo para las revisiones YA APLICADAS, no para
    # las que se van a probar).
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # Tablas mínimas que necesitan las migraciones probadas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wa_bot_sessions (
            id    SERIAL PRIMARY KEY,
            phone VARCHAR(20) NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wa_messages (
            id         SERIAL PRIMARY KEY,
            media_id   VARCHAR(200),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    # Tabla de control de versiones de alembic
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(32) NOT NULL,
            CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
        )
    """)
    # Marcar el estado PREVIO: solo e3t4a5p6a3b4.
    # w1a2b3o4t5s6 es ANCESTOR de e3t4a5p6a3b4 (via f1n2a3l4m5e6),
    # por lo que no puede coexistir con él en alembic_version.
    # Con solo e3t4a5p6a3b4 stampeado, 'alembic upgrade head' detecta que
    # la rama hermana s1e2s3i4o5n6→d1o2c3s4t5r6 (nacida de w1a2b3o4t5s6)
    # no está aplicada y la ejecuta antes de la fusión 34bb9704ef8c.
    cur.execute("DELETE FROM alembic_version")
    cur.execute("INSERT INTO alembic_version VALUES ('e3t4a5p6a3b4')")

    # Fase 2: insertar fila preexistente en wa_messages (sin media_local_path)
    cur.execute(
        "INSERT INTO wa_messages (media_id, created_at) VALUES (%s, NOW())",
        ('MEDIA_OLD_PG',)
    )
    cur.close()
    conn.close()

    # Fase 3: alembic upgrade head — aplica SOLO las migraciones probadas:
    #   s1e2s3i4o5n6 (ADD session_started_at a wa_bot_sessions)
    #   d1o2c3s4t5r6 (ADD media_local_path a wa_messages)
    #   34bb9704ef8c (merge, no-op)
    # Esto es real alembic via Flask context en PostgreSQL.
    with app.app_context():
        cfg = Config(INI_FILE)
        cfg.set_main_option('script_location', MIGRATIONS_DIR)
        alembic_cmd.upgrade(cfg, 'head')

    # Fase 4: verificar resultado fuera del app_context
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='wa_bot_sessions' AND column_name='session_started_at'
    """)
    has_session_started_at = cur.fetchone() is not None

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='wa_messages' AND column_name='media_local_path'
    """)
    has_media_local_path = cur.fetchone() is not None

    cur.execute(
        "SELECT media_id, media_local_path FROM wa_messages WHERE media_id=%s",
        ('MEDIA_OLD_PG',)
    )
    row = cur.fetchone()
    data_preserved = row is not None
    data_media_id  = row[0] if row else None
    data_mlp       = row[1] if row else None

    cur.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
    versions = [r[0] for r in cur.fetchall()]
    conn.close()

    print(json.dumps({
        'ok':                      has_session_started_at and has_media_local_path and data_preserved,
        'session_started_at':      has_session_started_at,
        'media_local_path':        has_media_local_path,
        'data_preserved':          data_preserved,
        'media_id_value':          data_media_id,
        'media_local_path_value':  data_mlp,
        'alembic_versions':        versions,
        'head_reached':            '34bb9704ef8c' in versions,
    }))

except Exception as exc:
    import traceback
    print(json.dumps({'ok': False, 'error': str(exc), 'trace': traceback.format_exc()}))
    sys.exit(1)

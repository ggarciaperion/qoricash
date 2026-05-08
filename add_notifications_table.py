"""
Migración manual: crear tabla notifications.
Ejecutar en producción (Render) una vez.

Uso:
    python3 add_notifications_table.py
"""
import os
import sys

# Forzar no-eventlet para poder ejecutar localmente
os.environ.setdefault('FLASK_ENV', 'production')

# Conectar directo a la BD
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: Define DATABASE_URL en el entorno")
    sys.exit(1)

# Adaptar URL postgres:// → postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL)

SQL = """
CREATE TABLE IF NOT EXISTS notifications (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(200) NOT NULL,
    message     VARCHAR(500) NOT NULL,
    notif_type  VARCHAR(30) NOT NULL DEFAULT 'info',
    category    VARCHAR(50) NOT NULL DEFAULT 'general',
    link        VARCHAR(300),
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    read_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_notifications_user_id    ON notifications(user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_is_read    ON notifications(is_read);
CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications(created_at);
"""

with engine.connect() as conn:
    conn.execute(text(SQL))
    conn.commit()
    print("✅ Tabla notifications creada / ya existía")

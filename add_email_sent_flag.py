"""
Migración: agregar columna new_operation_email_sent a la tabla operations.
Ejecutar en Render Shell: python add_email_sent_flag.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        # Verificar si ya existe
        result = conn.execute(db.text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='operations' AND column_name='new_operation_email_sent'
        """))
        if result.fetchone():
            print('Columna new_operation_email_sent ya existe.')
        else:
            conn.execute(db.text("""
                ALTER TABLE operations
                ADD COLUMN new_operation_email_sent BOOLEAN NOT NULL DEFAULT FALSE
            """))
            conn.commit()
            print('Columna new_operation_email_sent agregada correctamente.')

"""
Migración: crear tabla audit_reports
Ejecutar en Render Shell: python3 migrations_audit_report.py
"""
import os
os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    from sqlalchemy import text, inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    if 'audit_reports' in tables:
        print('✅ La tabla audit_reports ya existe — nada que hacer.')
    else:
        print('🔧 Creando tabla audit_reports...')
        from app.models.audit_report import AuditReport
        db.create_all()
        print('✅ Tabla audit_reports creada correctamente.')

    # Verificar columnas
    if 'audit_reports' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('audit_reports')]
        print(f'Columnas: {", ".join(cols)}')

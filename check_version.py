"""Verificar versión actual de Alembic en la base de datos"""
from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    result = db.session.execute(db.text('SELECT version_num FROM alembic_version')).fetchall()
    print('📌 Versión actual de Alembic en la base de datos:')
    for row in result:
        print(f'   {row[0]}')

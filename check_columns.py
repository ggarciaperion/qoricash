"""Verificar si las columnas password existen en la tabla clients"""
from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    columns = inspector.get_columns('clients')

    password_exists = any(col['name'] == 'password' for col in columns)
    requires_change_exists = any(col['name'] == 'requires_password_change' for col in columns)

    print(f'✓ Columna password existe: {password_exists}')
    print(f'✓ Columna requires_password_change existe: {requires_change_exists}')

    if password_exists and requires_change_exists:
        print('\n✅ Ambas columnas están creadas correctamente')
    else:
        print('\n❌ Faltan columnas en la base de datos')

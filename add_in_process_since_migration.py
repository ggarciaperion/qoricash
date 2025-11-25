"""
Script para crear migración del campo in_process_since en la tabla operations
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from flask_migrate import migrate as flask_migrate, upgrade
import sqlalchemy as sa

def create_migration():
    """Crear migración para agregar el campo in_process_since"""
    app = create_app()

    with app.app_context():
        # Crear la migración
        migration_message = "add_in_process_since_to_operations"

        print(f"Creando migración: {migration_message}")

        # Usar Flask-Migrate para generar la migración automáticamente
        from flask_migrate import Migrate, init, migrate as generate_migration, upgrade

        # Generar migración
        os.system(f'cd "{os.path.dirname(__file__)}" && flask db migrate -m "{migration_message}"')

        print("\n✅ Migración creada exitosamente")
        print("Para aplicar la migración, ejecuta: flask db upgrade")

if __name__ == '__main__':
    create_migration()

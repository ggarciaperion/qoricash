"""
Script para ejecutar migraciones de base de datos
Uso: python migrate_db.py
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno PRIMERO
load_dotenv()

# Importar eventlet y hacer monkey patch ANTES de cualquier otra cosa
import eventlet
eventlet.monkey_patch(
    os=True,
    select=True,
    socket=True,
    thread=True,
    time=True
)

# Ahora sí importar Flask y Alembic
from flask_migrate import upgrade
from app import create_app

def run_migrations():
    """Ejecutar migraciones de base de datos"""
    print("🔄 Iniciando migraciones de base de datos...")

    # Crear aplicación
    app = create_app()

    # Ejecutar migraciones dentro del contexto de la aplicación
    with app.app_context():
        try:
            upgrade()
            print("✅ Migraciones completadas exitosamente")
        except Exception as e:
            print(f"❌ Error al ejecutar migraciones: {str(e)}")
            raise

if __name__ == '__main__':
    run_migrations()

"""
Script para aplicar la migración del campo in_process_since
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from sqlalchemy import text

def apply_migration():
    """Aplicar migración manualmente"""
    app = create_app()

    with app.app_context():
        try:
            print("Aplicando migración: Agregar campo 'in_process_since' a la tabla 'operations'...")

            # Verificar si la columna ya existe
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('operations')]

            if 'in_process_since' in columns:
                print("⚠️  El campo 'in_process_since' ya existe en la tabla 'operations'")
                return

            # Agregar la columna
            with db.engine.connect() as conn:
                # Para SQLite
                if 'sqlite' in str(db.engine.url):
                    conn.execute(text('ALTER TABLE operations ADD COLUMN in_process_since DATETIME'))
                    conn.commit()
                # Para PostgreSQL
                else:
                    conn.execute(text('ALTER TABLE operations ADD COLUMN in_process_since TIMESTAMP'))
                    conn.commit()

            print("✅ Campo 'in_process_since' agregado exitosamente a la tabla 'operations'")
            print("\n📝 Ahora puedes:")
            print("   1. Reiniciar el servidor Flask")
            print("   2. Las operaciones que se envíen a 'En proceso' registrarán automáticamente la hora")

        except Exception as e:
            print(f"❌ Error al aplicar migración: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    apply_migration()

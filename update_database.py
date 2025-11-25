"""
Script para actualizar la base de datos con los nuevos campos de Operation
Ejecutar: python update_database.py
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Si no hay DATABASE_URL, usar SQLite
if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///qoricash.db'
    print("Usando SQLite local: qoricash.db")

from app import create_app
from app.extensions import db
from sqlalchemy import text, inspect

app = create_app()

def update_database():
    with app.app_context():
        print("\nActualizando base de datos...")
        print(f"URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'No configurada')}\n")

        # Lista de columnas a agregar a la tabla operations
        columns_to_add = [
            ("client_deposits_json", "TEXT"),
            ("client_payments_json", "TEXT"),
            ("operator_proofs_json", "TEXT"),
            ("modification_logs_json", "TEXT"),
            ("operator_comments", "TEXT"),
        ]

        # Obtener inspector para verificar columnas existentes
        inspector = inspect(db.engine)

        try:
            existing_columns = [col['name'] for col in inspector.get_columns('operations')]
            print(f"Columnas existentes en 'operations': {existing_columns}\n")
        except Exception as e:
            print(f"Error al inspeccionar tabla: {e}")
            existing_columns = []

        for column_name, column_type in columns_to_add:
            if column_name in existing_columns:
                print(f"  [INFO] Columna '{column_name}' ya existe")
                continue

            try:
                db.session.execute(text(f"ALTER TABLE operations ADD COLUMN {column_name} {column_type}"))
                db.session.commit()
                print(f"  [OK] Columna '{column_name}' agregada correctamente")
            except Exception as e:
                db.session.rollback()
                error_msg = str(e).lower()
                if 'duplicate' in error_msg or 'already exists' in error_msg:
                    print(f"  [INFO] Columna '{column_name}' ya existe")
                else:
                    print(f"  [ERROR] Error al agregar '{column_name}': {e}")

        print("\n[OK] Proceso de actualizacion completado")
        print("\nReinicia el servidor para aplicar los cambios.")

if __name__ == '__main__':
    update_database()

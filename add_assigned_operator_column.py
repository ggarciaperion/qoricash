"""
Script para agregar el campo assigned_operator_id a la tabla operations en PostgreSQL
"""
import os
import sys

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 no esta instalado")
    print("Instala con: pip install psycopg2-binary")
    sys.exit(1)

# Obtener URL de la base de datos
database_url = os.environ.get('DATABASE_URL')

if not database_url:
    print("ERROR: DATABASE_URL no esta configurada en .env")
    sys.exit(1)

print("Conectando a la base de datos PostgreSQL...")
print("URL:", database_url[:50] + "...")

try:
    # Conectar a PostgreSQL
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Verificar si la columna ya existe
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='operations' AND column_name='assigned_operator_id'
    """)

    if cursor.fetchone():
        print("AVISO: El campo 'assigned_operator_id' ya existe en la tabla 'operations'")
    else:
        # Agregar la columna con foreign key
        cursor.execute("""
            ALTER TABLE operations
            ADD COLUMN assigned_operator_id INTEGER
            REFERENCES users(id)
        """)

        # Agregar índice para mejorar el rendimiento
        cursor.execute("""
            CREATE INDEX idx_operations_assigned_operator
            ON operations(assigned_operator_id)
        """)

        conn.commit()
        print("EXITO: Campo 'assigned_operator_id' agregado exitosamente a la tabla 'operations'")
        print("EXITO: Indice creado en 'assigned_operator_id'")

    # Verificar que se agrego correctamente
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='operations'
    """)
    columns = [row[0] for row in cursor.fetchall()]

    print("\nColumnas en la tabla 'operations':", len(columns))
    if 'assigned_operator_id' in columns:
        print("CONFIRMADO: 'assigned_operator_id' esta presente")

    cursor.close()
    conn.close()

    print("\nMigracion completada exitosamente")
    print("\nProximos pasos:")
    print("   1. Reinicia el servidor Flask")
    print("   2. Las operaciones que se envien a 'En proceso' se asignaran automaticamente a un operador")

except psycopg2.Error as e:
    print("ERROR de PostgreSQL:", e)
except Exception as e:
    print("ERROR:", e)
    import traceback
    traceback.print_exc()

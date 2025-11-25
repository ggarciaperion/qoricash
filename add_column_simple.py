"""
Script directo para agregar el campo in_process_since a la tabla operations
"""
import sqlite3
import os

# Ruta a la base de datos
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'qoricash.db')

# Verificar si existe la base de datos
if not os.path.exists(db_path):
    # Buscar en otras ubicaciones posibles
    possible_paths = [
        os.path.join(os.path.dirname(__file__), 'qoricash.db'),
        os.path.join(os.path.dirname(__file__), 'app', 'qoricash.db'),
        os.path.join(os.path.dirname(__file__), 'instance', 'app.db'),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    else:
        print("ERROR: No se encontro la base de datos en:", db_path)
        print("\nBuscando archivos .db en el proyecto...")
        for root, dirs, files in os.walk(os.path.dirname(__file__)):
            for file in files:
                if file.endswith('.db'):
                    found_path = os.path.join(root, file)
                    print("   Encontrado:", found_path)

        db_path = input("\nIngresa la ruta completa de la base de datos: ").strip()

print("Usando base de datos:", db_path)

try:
    # Conectar a la base de datos
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Verificar si la columna ya existe
    cursor.execute("PRAGMA table_info(operations)")
    columns = [column[1] for column in cursor.fetchall()]

    if 'in_process_since' in columns:
        print("AVISO: El campo 'in_process_since' ya existe en la tabla 'operations'")
    else:
        # Agregar la columna
        cursor.execute("ALTER TABLE operations ADD COLUMN in_process_since DATETIME")
        conn.commit()
        print("EXITO: Campo 'in_process_since' agregado exitosamente a la tabla 'operations'")

    # Verificar que se agrego correctamente
    cursor.execute("PRAGMA table_info(operations)")
    columns = [column[1] for column in cursor.fetchall()]

    print("\nColumnas en la tabla 'operations':", len(columns))
    if 'in_process_since' in columns:
        print("CONFIRMADO: 'in_process_since' esta presente")

    conn.close()

    print("\nMigracion completada exitosamente")
    print("\nProximos pasos:")
    print("   1. Reinicia el servidor Flask")
    print("   2. Las operaciones que se envien a 'En proceso' registraran automaticamente la hora")

except sqlite3.Error as e:
    print("ERROR de SQLite:", e)
except Exception as e:
    print("ERROR:", e)
    import traceback
    traceback.print_exc()

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
        print(f"❌ No se encontró la base de datos en: {db_path}")
        print("\nBuscando archivos .db en el proyecto...")
        for root, dirs, files in os.walk(os.path.dirname(__file__)):
            for file in files:
                if file.endswith('.db'):
                    found_path = os.path.join(root, file)
                    print(f"   Encontrado: {found_path}")

        db_path = input("\nIngresa la ruta completa de la base de datos: ").strip()

print(f"📂 Usando base de datos: {db_path}")

try:
    # Conectar a la base de datos
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Verificar si la columna ya existe
    cursor.execute("PRAGMA table_info(operations)")
    columns = [column[1] for column in cursor.fetchall()]

    if 'in_process_since' in columns:
        print("⚠️  El campo 'in_process_since' ya existe en la tabla 'operations'")
    else:
        # Agregar la columna
        cursor.execute("ALTER TABLE operations ADD COLUMN in_process_since DATETIME")
        conn.commit()
        print("✅ Campo 'in_process_since' agregado exitosamente a la tabla 'operations'")

    # Verificar que se agregó correctamente
    cursor.execute("PRAGMA table_info(operations)")
    columns = [column[1] for column in cursor.fetchall()]

    print(f"\n📋 Columnas en la tabla 'operations': {len(columns)}")
    if 'in_process_since' in columns:
        print("✓ Confirmado: 'in_process_since' está presente")

    conn.close()

    print("\n✅ Migración completada exitosamente")
    print("\n📝 Próximos pasos:")
    print("   1. Reinicia el servidor Flask")
    print("   2. Las operaciones que se envíen a 'En proceso' registrarán automáticamente la hora")

except sqlite3.Error as e:
    print(f"❌ Error de SQLite: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

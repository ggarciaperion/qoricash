"""
Script para hacer nullable el campo user_id en la tabla operations

Este script aplica la migración directamente usando SQL:
ALTER TABLE operations ALTER COLUMN user_id DROP NOT NULL;

Uso:
    python scripts/fix_operation_user_id.py
"""
import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.config import Config

def main():
    print("=" * 60)
    print("SCRIPT: Hacer nullable operations.user_id")
    print("=" * 60)

    # Obtener DATABASE_URL
    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        print("❌ ERROR: No se pudo obtener DATABASE_URL")
        print("Asegúrate de tener configurada la variable SQLALCHEMY_DATABASE_URI")
        sys.exit(1)

    print(f"📡 Conectando a la base de datos...")

    try:
        # Crear engine
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Verificar estado actual
            print("\n1️⃣ Verificando estado actual de la columna user_id...")
            result = conn.execute(text("""
                SELECT column_name, is_nullable, data_type
                FROM information_schema.columns
                WHERE table_name = 'operations'
                AND column_name = 'user_id'
            """))

            row = result.fetchone()
            if not row:
                print("❌ ERROR: No se encontró la columna user_id en la tabla operations")
                sys.exit(1)

            column_name, is_nullable, data_type = row
            print(f"   - Columna: {column_name}")
            print(f"   - Tipo: {data_type}")
            print(f"   - Nullable: {is_nullable}")

            if is_nullable == 'YES':
                print("\n✅ La columna user_id YA es nullable. No se requiere cambio.")
                print("\n🔍 Verificando datos existentes con user_id NULL...")
                result = conn.execute(text("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN user_id IS NULL THEN 1 ELSE 0 END) as nulls
                    FROM operations
                """))
                row = result.fetchone()
                print(f"   - Total operaciones: {row[0]}")
                print(f"   - Operaciones con user_id NULL: {row[1]}")
                return

            print("\n2️⃣ La columna NO es nullable. Aplicando migración...")

            # Aplicar migración
            conn.execute(text("""
                ALTER TABLE operations ALTER COLUMN user_id DROP NOT NULL
            """))
            conn.commit()

            print("✅ Migración aplicada exitosamente!")

            # Verificar cambio
            print("\n3️⃣ Verificando cambio...")
            result = conn.execute(text("""
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_name = 'operations'
                AND column_name = 'user_id'
            """))

            row = result.fetchone()
            is_nullable_after = row[0]

            if is_nullable_after == 'YES':
                print(f"✅ CONFIRMADO: user_id ahora es nullable ({is_nullable_after})")
                print("\n" + "=" * 60)
                print("✅ MIGRACIÓN COMPLETADA CON ÉXITO")
                print("=" * 60)
                print("\nAhora los clientes del app móvil pueden crear operaciones.")
                print("user_id será NULL para operaciones creadas desde el app.")
            else:
                print(f"❌ ERROR: user_id sigue siendo NOT NULL ({is_nullable_after})")
                sys.exit(1)

    except Exception as e:
        print(f"\n❌ ERROR al aplicar migración:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

"""
Script para aplicar manualmente los cambios de rol Plataforma y campo origen
Ejecutar este script en Render Shell si la migración automática falla

Uso:
    python apply_plataforma_changes.py
"""
import os
import sys

# Asegurar que estamos en el directorio correcto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from sqlalchemy import text

def apply_changes():
    """Aplicar cambios de Plataforma manualmente"""

    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("APLICANDO CAMBIOS DE ROL PLATAFORMA Y CAMPO ORIGEN")
        print("=" * 60)

        try:
            # 1. Verificar conexión a la base de datos
            print("\n1. Verificando conexión a la base de datos...")
            result = db.session.execute(text("SELECT 1"))
            print("   ✓ Conexión exitosa")

            # 2. Actualizar constraint de roles para incluir 'Plataforma'
            print("\n2. Actualizando constraint de roles de usuarios...")
            try:
                # Intentar eliminar el constraint antiguo
                db.session.execute(text("""
                    ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role
                """))
                print("   ✓ Constraint antiguo eliminado")
            except Exception as e:
                print(f"   ⚠ No se pudo eliminar constraint antiguo: {e}")

            try:
                # Crear nuevo constraint con Plataforma
                db.session.execute(text("""
                    ALTER TABLE users ADD CONSTRAINT check_user_role
                    CHECK (role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma'))
                """))
                print("   ✓ Nuevo constraint creado con rol 'Plataforma'")
            except Exception as e:
                print(f"   ⚠ Error al crear constraint: {e}")

            # 3. Verificar si la columna 'origen' ya existe
            print("\n3. Verificando columna 'origen' en tabla operations...")
            check_column = db.session.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='operations' AND column_name='origen'
            """)).fetchone()

            if check_column:
                print("   ✓ La columna 'origen' ya existe")
            else:
                # 4. Agregar columna 'origen' a la tabla operations
                print("\n4. Agregando columna 'origen' a tabla operations...")
                db.session.execute(text("""
                    ALTER TABLE operations
                    ADD COLUMN origen VARCHAR(20) NOT NULL DEFAULT 'sistema'
                """))
                print("   ✓ Columna 'origen' agregada")

                # 5. Crear índice para el campo origen
                print("\n5. Creando índice para campo 'origen'...")
                try:
                    db.session.execute(text("""
                        CREATE INDEX ix_operations_origen ON operations (origen)
                    """))
                    print("   ✓ Índice ix_operations_origen creado")
                except Exception as e:
                    print(f"   ⚠ Error al crear índice (puede ya existir): {e}")

                # 6. Crear constraint para validar valores de origen
                print("\n6. Creando constraint para campo 'origen'...")
                try:
                    db.session.execute(text("""
                        ALTER TABLE operations
                        ADD CONSTRAINT check_operation_origen
                        CHECK (origen IN ('plataforma', 'sistema'))
                    """))
                    print("   ✓ Constraint check_operation_origen creado")
                except Exception as e:
                    print(f"   ⚠ Error al crear constraint (puede ya existir): {e}")

            # 7. Commit de todos los cambios
            print("\n7. Guardando cambios en la base de datos...")
            db.session.commit()
            print("   ✓ Cambios guardados exitosamente")

            # 8. Verificar cambios
            print("\n8. Verificando cambios aplicados...")

            # Verificar columna origen
            check = db.session.execute(text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name='operations' AND column_name='origen'
            """)).fetchone()

            if check:
                print(f"   ✓ Columna 'origen': {check[1]} (default: {check[2]})")

            # Verificar constraint de roles
            check_constraint = db.session.execute(text("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name = 'check_user_role'
            """)).fetchone()

            if check_constraint and 'Plataforma' in str(check_constraint[1]):
                print(f"   ✓ Constraint de roles incluye 'Plataforma'")

            print("\n" + "=" * 60)
            print("✅ CAMBIOS APLICADOS EXITOSAMENTE")
            print("=" * 60)
            print("\nPróximos pasos:")
            print("1. Crear usuario con rol 'Plataforma' para la web pública")
            print("2. Los endpoints de API Platform están disponibles en /api/platform/*")
            print("3. Las operaciones ahora tienen campo 'origen' (sistema/plataforma)")

            return True

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            print("\nRevertiendo cambios...")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   SCRIPT DE APLICACIÓN MANUAL - ROL PLATAFORMA           ║")
    print("║   QoriCash Trading System                                 ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("\n")

    success = apply_changes()

    if success:
        print("\n✅ Script ejecutado exitosamente\n")
        sys.exit(0)
    else:
        print("\n❌ Script falló. Revisa los errores arriba.\n")
        sys.exit(1)

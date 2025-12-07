"""
Script para verificar el estado de la base de datos y las migraciones
Útil para diagnosticar problemas de deployment

Uso:
    python verify_database.py
"""
import os
import sys

# Asegurar que estamos en el directorio correcto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from sqlalchemy import text

def verify_database():
    """Verificar estado de la base de datos"""

    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("VERIFICACIÓN DE BASE DE DATOS - QoriCash Trading")
        print("=" * 70)

        try:
            # 1. Verificar conexión
            print("\n1. CONEXIÓN A LA BASE DE DATOS")
            print("-" * 70)
            result = db.session.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"   ✓ Conexión exitosa")
            print(f"   PostgreSQL: {version[:50]}...")

            # 2. Verificar tabla users
            print("\n2. TABLA USERS")
            print("-" * 70)

            # Columnas de users
            columns = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'users'
                ORDER BY ordinal_position
            """)).fetchall()

            if columns:
                print(f"   ✓ Tabla 'users' existe ({len(columns)} columnas)")
                for col in columns:
                    print(f"     - {col[0]:25s} {col[1]:20s} {'NULL' if col[2]=='YES' else 'NOT NULL'}")
            else:
                print("   ❌ Tabla 'users' no existe")

            # Constraint de roles
            role_constraint = db.session.execute(text("""
                SELECT check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name = 'check_user_role'
            """)).fetchone()

            if role_constraint:
                print(f"\n   Constraint check_user_role:")
                print(f"     {role_constraint[0]}")
                if 'Plataforma' in role_constraint[0]:
                    print("     ✓ Incluye rol 'Plataforma'")
                else:
                    print("     ⚠ NO incluye rol 'Plataforma'")
            else:
                print("   ⚠ No se encontró constraint check_user_role")

            # Contar usuarios por rol
            roles = db.session.execute(text("""
                SELECT role, COUNT(*) as count
                FROM users
                GROUP BY role
                ORDER BY count DESC
            """)).fetchall()

            if roles:
                print(f"\n   Usuarios por rol:")
                for role in roles:
                    print(f"     - {role[0]:20s} {role[1]:3d} usuario(s)")

            # 3. Verificar tabla operations
            print("\n3. TABLA OPERATIONS")
            print("-" * 70)

            # Verificar si existe columna 'origen'
            origen_column = db.session.execute(text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name='operations' AND column_name='origen'
            """)).fetchone()

            if origen_column:
                print(f"   ✓ Columna 'origen' existe")
                print(f"     Tipo: {origen_column[1]}")
                print(f"     Default: {origen_column[2]}")
            else:
                print("   ❌ Columna 'origen' NO existe")

            # Verificar índice de origen
            origen_index = db.session.execute(text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'operations' AND indexname = 'ix_operations_origen'
            """)).fetchone()

            if origen_index:
                print(f"   ✓ Índice ix_operations_origen existe")
            else:
                print("   ⚠ Índice ix_operations_origen NO existe")

            # Constraint de origen
            origen_constraint = db.session.execute(text("""
                SELECT check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name = 'check_operation_origen'
            """)).fetchone()

            if origen_constraint:
                print(f"   ✓ Constraint check_operation_origen existe")
                print(f"     {origen_constraint[0]}")
            else:
                print("   ⚠ Constraint check_operation_origen NO existe")

            # Contar operaciones
            total_ops = db.session.execute(text("""
                SELECT COUNT(*) FROM operations
            """)).scalar()
            print(f"\n   Total de operaciones: {total_ops}")

            # Si existe la columna origen, contar por origen
            if origen_column:
                ops_por_origen = db.session.execute(text("""
                    SELECT origen, COUNT(*) as count
                    FROM operations
                    GROUP BY origen
                    ORDER BY count DESC
                """)).fetchall()

                if ops_por_origen:
                    print(f"\n   Operaciones por origen:")
                    for origen in ops_por_origen:
                        print(f"     - {origen[0]:20s} {origen[1]:5d} operación(es)")

            # 4. Verificar migraciones
            print("\n4. MIGRACIONES DE ALEMBIC")
            print("-" * 70)

            try:
                current_rev = db.session.execute(text("""
                    SELECT version_num FROM alembic_version
                """)).fetchone()

                if current_rev:
                    print(f"   ✓ Revisión actual: {current_rev[0]}")
                else:
                    print("   ⚠ No se encontró versión de migración")
            except Exception as e:
                print(f"   ❌ Error al obtener versión: {e}")

            # 5. Verificar tablas principales
            print("\n5. TABLAS PRINCIPALES")
            print("-" * 70)

            tables = ['users', 'clients', 'operations', 'audit_logs', 'client_risk_profiles']
            for table in tables:
                count = db.session.execute(text(f"""
                    SELECT COUNT(*) FROM {table}
                """)).scalar()
                print(f"   {table:30s} {count:6d} registro(s)")

            # 6. Resumen
            print("\n" + "=" * 70)
            print("RESUMEN DE VERIFICACIÓN")
            print("=" * 70)

            issues = []

            if not role_constraint or 'Plataforma' not in role_constraint[0]:
                issues.append("⚠ Rol 'Plataforma' no está en constraint de users")

            if not origen_column:
                issues.append("❌ Columna 'origen' no existe en operations")

            if not origen_constraint:
                issues.append("⚠ Constraint de origen no existe en operations")

            if issues:
                print("\n⚠️  PROBLEMAS ENCONTRADOS:")
                for issue in issues:
                    print(f"   {issue}")
                print(f"\n💡 Solución: Ejecuta 'python apply_plataforma_changes.py'")
            else:
                print("\n✅ Base de datos configurada correctamente")
                print("   Todos los cambios de Plataforma están aplicados")

            return True

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   VERIFICACIÓN DE BASE DE DATOS                           ║")
    print("║   QoriCash Trading System                                 ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("\n")

    success = verify_database()

    if success:
        print("\n✅ Verificación completada\n")
        sys.exit(0)
    else:
        print("\n❌ Verificación falló\n")
        sys.exit(1)

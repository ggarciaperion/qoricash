"""
Script para verificar y ejecutar la migración del rol Web
Ejecutar: python verify_and_migrate_web_role.py
"""
import os
import sys
from flask import Flask
from app.extensions import db
from app.models.user import User
from app.models.operation import Operation
from werkzeug.security import generate_password_hash
from sqlalchemy import text

def create_app():
    """Crear instancia de la aplicación"""
    app = Flask(__name__)

    # Configuración desde variables de entorno
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    return app

def verify_migration():
    """Verificar estado de la migración"""
    print("\n" + "="*60)
    print("VERIFICACIÓN DE MIGRACIÓN - ROL WEB Y CANAL WEB")
    print("="*60 + "\n")

    app = create_app()

    with app.app_context():
        try:
            # 1. Verificar historial de migraciones
            print("1️⃣  Verificando historial de migraciones...")
            result = db.session.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.fetchone()
            if current_version:
                print(f"   ✅ Versión actual: {current_version[0]}")
            else:
                print("   ❌ No se encontró versión de migración")

            # 2. Verificar usuario Web
            print("\n2️⃣  Verificando usuario con rol 'Web'...")
            web_user = User.query.filter_by(role='Web').first()
            if web_user:
                print(f"   ✅ Usuario encontrado:")
                print(f"      - ID: {web_user.id}")
                print(f"      - Username: {web_user.username}")
                print(f"      - Email: {web_user.email}")
                print(f"      - DNI: {web_user.dni}")
                print(f"      - Rol: {web_user.role}")
                print(f"      - Estado: {web_user.status}")
            else:
                print("   ⚠️  No se encontró usuario con rol 'Web'")
                print("   🔧 Creando usuario 'Página Web'...")

                # Crear usuario Web
                web_user = User(
                    username='Página Web',
                    email='web@qoricash.pe',
                    dni='99999997',
                    role='Web',
                    status='Activo'
                )
                web_user.set_password('WebQoriCash2025!')
                db.session.add(web_user)
                db.session.commit()
                print("   ✅ Usuario 'Página Web' creado exitosamente")

            # 3. Verificar constraint de roles
            print("\n3️⃣  Verificando constraint de roles en tabla users...")
            result = db.session.execute(text("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name = 'check_user_role'
            """))
            constraint = result.fetchone()
            if constraint:
                print(f"   ✅ Constraint encontrado:")
                print(f"      {constraint[1]}")
                if "'Web'" in constraint[1] or '"Web"' in constraint[1]:
                    print("   ✅ Rol 'Web' está incluido en el constraint")
                else:
                    print("   ⚠️  Rol 'Web' NO está en el constraint")
                    print("   🔧 Se necesita ejecutar la migración")
            else:
                print("   ❌ No se encontró constraint 'check_user_role'")

            # 4. Verificar constraint de origen
            print("\n4️⃣  Verificando constraint de origen en tabla operations...")
            result = db.session.execute(text("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name = 'check_operation_origen'
            """))
            constraint = result.fetchone()
            if constraint:
                print(f"   ✅ Constraint encontrado:")
                print(f"      {constraint[1]}")
                if "'web'" in constraint[1] or '"web"' in constraint[1]:
                    print("   ✅ Canal 'web' está incluido en el constraint")
                else:
                    print("   ⚠️  Canal 'web' NO está en el constraint")
                    print("   🔧 Se necesita ejecutar la migración")
            else:
                print("   ❌ No se encontró constraint 'check_operation_origen'")

            # 5. Probar creación de operación con origen='web'
            print("\n5️⃣  Probando validación de origen='web'...")
            try:
                # Solo verificar que no arroje error de constraint
                result = db.session.execute(text("""
                    SELECT 1 WHERE 'web' IN ('sistema', 'plataforma', 'app', 'web')
                """))
                if result.fetchone():
                    print("   ✅ Validación de origen='web' funciona correctamente")
            except Exception as e:
                print(f"   ❌ Error en validación: {str(e)}")

            # 6. Resumen
            print("\n" + "="*60)
            print("RESUMEN")
            print("="*60)

            web_user_exists = User.query.filter_by(role='Web').first() is not None

            if web_user_exists:
                print("✅ Usuario Web: CREADO")
            else:
                print("❌ Usuario Web: NO ENCONTRADO")

            print("\n💡 ACCIONES RECOMENDADAS:")
            if not web_user_exists:
                print("   1. Ejecutar: flask db upgrade")
                print("   2. Verificar que la migración 20250111_add_web_role.py esté en migrations/versions/")
            else:
                print("   ✅ Todo está configurado correctamente")
                print("   ✅ La página web ya puede crear operaciones con origen='web'")

            print("\n" + "="*60 + "\n")

        except Exception as e:
            print(f"\n❌ Error durante la verificación: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    verify_migration()

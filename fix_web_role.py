"""
Script para aplicar el rol Web manualmente
Ejecutar: python fix_web_role.py
"""
import os
from sqlalchemy import create_engine, text

def apply_web_role():
    print("\n" + "="*60)
    print("APLICANDO ROL WEB Y CANAL WEB")
    print("="*60 + "\n")

    # Obtener URL de base de datos
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: No se encontró DATABASE_URL")
        return

    try:
        # Crear conexión
        engine = create_engine(database_url)

        with engine.begin() as conn:
            print("1️⃣  Actualizando constraint de roles...")

            # Eliminar constraint antiguo
            conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role"))

            # Crear nuevo constraint
            conn.execute(text("""
                ALTER TABLE users ADD CONSTRAINT check_user_role
                CHECK (role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma', 'App', 'Web'))
            """))
            print("   ✅ Constraint de roles actualizado")

            print("\n2️⃣  Actualizando constraint de origen...")

            # Eliminar constraint antiguo
            conn.execute(text("ALTER TABLE operations DROP CONSTRAINT IF EXISTS check_operation_origen"))

            # Crear nuevo constraint
            conn.execute(text("""
                ALTER TABLE operations ADD CONSTRAINT check_operation_origen
                CHECK (origen IN ('sistema', 'plataforma', 'app', 'web'))
            """))
            print("   ✅ Constraint de origen actualizado")

            print("\n3️⃣  Creando usuario 'Página Web'...")

            # Verificar si ya existe
            result = conn.execute(text("SELECT id FROM users WHERE email = 'web@qoricash.pe'"))
            existing = result.fetchone()

            if existing:
                print(f"   ⚠️  Usuario ya existe (ID: {existing[0]})")
            else:
                # Crear usuario
                conn.execute(text("""
                    INSERT INTO users (username, email, password_hash, dni, role, status, created_at, updated_at)
                    VALUES (
                        'Página Web',
                        'web@qoricash.pe',
                        'scrypt:32768:8:1$jRiO7CCyq6Q2WGuq$67eebac4cb6ef08f293a8f301ec061aa39124cfed01e89116ae3e0f5e2991ccda937f18a3454a2ec52f9aa85deb6468172d87b274e10a0b0691cd4d6ec5cfe21',
                        '99999997',
                        'Web',
                        'Activo',
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                """))
                print("   ✅ Usuario 'Página Web' creado")

            print("\n4️⃣  Verificando resultado...")

            # Verificar usuario
            result = conn.execute(text("""
                SELECT id, username, email, dni, role, status
                FROM users
                WHERE role = 'Web'
            """))
            user = result.fetchone()

            if user:
                print("\n" + "="*60)
                print("✅ ÉXITO - Usuario Web Creado")
                print("="*60)
                print(f"ID: {user[0]}")
                print(f"Username: {user[1]}")
                print(f"Email: {user[2]}")
                print(f"DNI: {user[3]}")
                print(f"Rol: {user[4]}")
                print(f"Estado: {user[5]}")
                print("\n✅ La página web ahora puede crear operaciones con origen='web'")
            else:
                print("❌ No se pudo verificar el usuario")

        print("\n" + "="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    apply_web_role()

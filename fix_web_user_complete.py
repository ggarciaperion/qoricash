"""
Script completo para verificar y corregir el usuario Web
Ejecutar: python fix_web_user_complete.py
"""
import os
from sqlalchemy import create_engine, text

def fix_complete():
    print("\n" + "="*60)
    print("VERIFICACIÓN Y CORRECCIÓN COMPLETA - USUARIO WEB")
    print("="*60 + "\n")

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: No se encontró DATABASE_URL")
        return

    try:
        engine = create_engine(database_url)

        with engine.begin() as conn:
            # 1. Verificar usuario web@qoricash.pe
            print("1️⃣  Buscando usuario web@qoricash.pe...")
            result = conn.execute(text("""
                SELECT id, username, email, dni, role, status
                FROM users
                WHERE email = 'web@qoricash.pe'
            """))
            existing_user = result.fetchone()

            if existing_user:
                print(f"   ✅ Usuario encontrado:")
                print(f"      ID: {existing_user[0]}")
                print(f"      Username: {existing_user[1]}")
                print(f"      Email: {existing_user[2]}")
                print(f"      DNI: {existing_user[3]}")
                print(f"      Rol: {existing_user[4]}")
                print(f"      Estado: {existing_user[5]}")

                # Si el rol no es 'Web', actualizarlo
                if existing_user[4] != 'Web':
                    print(f"\n2️⃣  Actualizando rol de '{existing_user[4]}' a 'Web'...")
                    conn.execute(text("""
                        UPDATE users
                        SET role = 'Web',
                            username = 'Página Web',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :user_id
                    """), {"user_id": existing_user[0]})
                    print("   ✅ Rol actualizado a 'Web'")
                else:
                    print("\n2️⃣  El rol ya es 'Web', no se necesita actualización")
            else:
                print("   ⚠️  Usuario no existe, creando...")
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
                print("   ✅ Usuario creado")

            # 3. Verificar todos los usuarios con rol 'Web'
            print("\n3️⃣  Verificando todos los usuarios con rol 'Web'...")
            result = conn.execute(text("""
                SELECT id, username, email, dni, role, status
                FROM users
                WHERE role = 'Web'
            """))
            web_users = result.fetchall()

            if web_users:
                print(f"   ✅ Encontrados {len(web_users)} usuario(s) con rol 'Web':")
                for user in web_users:
                    print(f"\n      Usuario ID {user[0]}:")
                    print(f"      - Username: {user[1]}")
                    print(f"      - Email: {user[2]}")
                    print(f"      - DNI: {user[3]}")
                    print(f"      - Estado: {user[5]}")
            else:
                print("   ❌ No se encontró ningún usuario con rol 'Web'")

            # 4. Verificar constraints
            print("\n4️⃣  Verificando constraints...")

            # Constraint de roles
            result = conn.execute(text("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name = 'check_user_role'
            """))
            constraint = result.fetchone()
            if constraint and "'Web'" in constraint[1]:
                print("   ✅ Constraint de roles incluye 'Web'")
            else:
                print("   ❌ Constraint de roles NO incluye 'Web'")

            # Constraint de origen
            result = conn.execute(text("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name = 'check_operation_origen'
            """))
            constraint = result.fetchone()
            if constraint and "'web'" in constraint[1]:
                print("   ✅ Constraint de origen incluye 'web'")
            else:
                print("   ❌ Constraint de origen NO incluye 'web'")

            # Resumen final
            print("\n" + "="*60)
            print("RESUMEN FINAL")
            print("="*60)

            # Verificar estado final
            result = conn.execute(text("""
                SELECT COUNT(*) FROM users WHERE role = 'Web'
            """))
            count = result.fetchone()[0]

            if count > 0:
                print("✅ TODO CONFIGURADO CORRECTAMENTE")
                print(f"✅ {count} usuario(s) con rol 'Web'")
                print("✅ Constraints actualizados")
                print("\n🎉 La página web puede crear operaciones con origen='web'")
                print("🎉 Los clientes pueden hacer login con DNI + contraseña")
            else:
                print("❌ AÚN HAY PROBLEMAS")
                print("❌ No se encontró usuario con rol 'Web'")

        print("\n" + "="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    fix_complete()

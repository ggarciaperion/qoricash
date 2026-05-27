"""
Elimina el usuario allisoncookmz@gmail.com / dni 06631846 de la BD
para permitir volver a registrarlo.

Uso (en Render Shell):
    python3 delete_user_allison.py
"""
import os, sys

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: Define DATABASE_URL en el entorno")
    sys.exit(1)

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL)

TARGET_EMAIL = 'allisoncookmz@gmail.com'
TARGET_DNI   = '06631846'

with engine.begin() as conn:

    # Buscar el usuario (activo o inactivo, email original u obfuscado)
    row = conn.execute(text("""
        SELECT id, username, email, dni, status
        FROM users
        WHERE email = :email
           OR email LIKE '%' || :email
           OR dni   = :dni
           OR dni   LIKE '%' || :dni
        LIMIT 5
    """), {'email': TARGET_EMAIL, 'dni': TARGET_DNI}).fetchall()

    if not row:
        print("No se encontró ningún usuario con ese email o DNI.")
        sys.exit(0)

    print("Usuarios encontrados:")
    for r in row:
        print(f"  id={r.id} | username={r.username} | email={r.email} | dni={r.dni} | status={r.status}")

    # Verificar si tienen operaciones asociadas
    ids = [r.id for r in row]
    for uid in ids:
        ops = conn.execute(text(
            "SELECT COUNT(*) as c FROM operations WHERE user_id = :uid"
        ), {'uid': uid}).scalar()
        print(f"  -> user_id={uid} tiene {ops} operaciones asociadas")

        if ops == 0:
            # Sin operaciones: eliminar completamente
            conn.execute(text("DELETE FROM audit_logs WHERE user_id = :uid"), {'uid': uid})
            conn.execute(text("DELETE FROM users WHERE id = :uid"), {'uid': uid})
            print(f"  ✅ Usuario id={uid} eliminado completamente.")
        else:
            # Con operaciones: obfuscar con timestamp para liberar el email/dni
            import time
            ts = int(time.time())
            conn.execute(text("""
                UPDATE users
                SET email    = 'del_' || :ts || '_' || id || '@deleted.invalid',
                    username = 'deleted_' || :ts || '_' || id,
                    dni      = 'D' || :ts || '_' || id
                WHERE id = :uid
            """), {'uid': uid, 'ts': ts})
            print(f"  ✅ Usuario id={uid} tiene operaciones — credenciales obfuscadas para liberar email/dni.")

print("\n✅ Listo. Ahora puedes registrar allisoncookmz@gmail.com nuevamente.")

"""Add App role and rename platform user

Revision ID: 20250108_add_app_role
Revises:
Create Date: 2025-01-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250108_add_app_role'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    1. Eliminar constraint anterior de roles
    2. Agregar rol 'App' al constraint
    3. Renombrar usuario plataforma@qoricash.pe a app@qoricash.pe
    4. Cambiar username de 'plataforma' a 'App Móvil'
    5. Cambiar rol de 'Plataforma' a 'App'
    """

    # 1. Eliminar constraint anterior
    op.drop_constraint('check_user_role', 'users', type_='check')

    # 2. Crear nuevo constraint con rol 'App'
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma', 'App')"
    )

    # 3. Actualizar usuario plataforma@qoricash.pe (si existe)
    connection = op.get_bind()

    # Verificar si existe el usuario
    result = connection.execute(
        sa.text("SELECT id FROM users WHERE email = 'plataforma@qoricash.pe' LIMIT 1")
    ).fetchone()

    if result:
        user_id = result[0]

        # Actualizar email, username y rol
        connection.execute(
            sa.text("""
                UPDATE users
                SET email = 'app@qoricash.pe',
                    username = 'App Móvil',
                    role = 'App'
                WHERE id = :user_id
            """),
            {"user_id": user_id}
        )

        print(f"✅ Usuario actualizado: plataforma@qoricash.pe -> app@qoricash.pe (Rol: App)")
    else:
        print("ℹ️ No se encontró usuario plataforma@qoricash.pe para actualizar")

    # 4. Crear usuario 'Web Externa' para canales externos (si no existe)
    result_web = connection.execute(
        sa.text("SELECT id FROM users WHERE email = 'web@qoricash.pe' LIMIT 1")
    ).fetchone()

    if not result_web:
        # Crear usuario Web Externa
        from werkzeug.security import generate_password_hash

        password_hash = generate_password_hash('WebExterna2025!')

        connection.execute(
            sa.text("""
                INSERT INTO users (username, email, password_hash, dni, role, status, created_at, updated_at)
                VALUES (:username, :email, :password_hash, :dni, :role, :status, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "username": "Web Externa",
                "email": "web@qoricash.pe",
                "password_hash": password_hash,
                "dni": "99999998",  # DNI ficticio para usuario de sistema
                "role": "Plataforma",
                "status": "Activo"
            }
        )
        print("✅ Usuario 'Web Externa' creado para canales externos (web, teléfono, WhatsApp)")
    else:
        print("ℹ️ Usuario 'Web Externa' ya existe")


def downgrade():
    """
    Revertir cambios:
    1. Restaurar usuario app@qoricash.pe a plataforma@qoricash.pe
    2. Eliminar rol 'App' del constraint
    """

    # 1. Restaurar usuario (si existe)
    connection = op.get_bind()

    result = connection.execute(
        sa.text("SELECT id FROM users WHERE email = 'app@qoricash.pe' LIMIT 1")
    ).fetchone()

    if result:
        user_id = result[0]

        connection.execute(
            sa.text("""
                UPDATE users
                SET email = 'plataforma@qoricash.pe',
                    username = 'plataforma',
                    role = 'Plataforma'
                WHERE id = :user_id
            """),
            {"user_id": user_id}
        )

    # 2. Restaurar constraint sin rol 'App'
    op.drop_constraint('check_user_role', 'users', type_='check')
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma')"
    )

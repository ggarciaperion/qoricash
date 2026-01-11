"""Add Web role and web channel

Revision ID: 20250111_add_web_role
Revises:
Create Date: 2025-01-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250111_add_web_role'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    1. Actualizar constraint de roles para incluir 'Web'
    2. Actualizar constraint de origen para incluir 'web'
    3. Renombrar usuario existente 'Web Externa' (Plataforma) a rol 'Web'
    """

    # 1. Actualizar constraint de roles en tabla users
    op.drop_constraint('check_user_role', 'users', type_='check')
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma', 'App', 'Web')"
    )

    # 2. Actualizar constraint de origen en tabla operations
    op.drop_constraint('check_operation_origen', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('sistema', 'plataforma', 'app', 'web')"
    )

    # 3. Actualizar usuario 'Web Externa' si existe
    connection = op.get_bind()

    # Verificar si existe el usuario web@qoricash.pe
    result = connection.execute(
        sa.text("SELECT id FROM users WHERE email = 'web@qoricash.pe' LIMIT 1")
    ).fetchone()

    if result:
        user_id = result[0]

        # Actualizar rol de Plataforma a Web
        connection.execute(
            sa.text("""
                UPDATE users
                SET role = 'Web',
                    username = 'Página Web'
                WHERE id = :user_id
            """),
            {"user_id": user_id}
        )

        print(f"✅ Usuario actualizado: web@qoricash.pe -> Rol: Web")
    else:
        # Crear usuario 'Página Web' si no existe
        from werkzeug.security import generate_password_hash

        password_hash = generate_password_hash('WebQoriCash2025!')

        connection.execute(
            sa.text("""
                INSERT INTO users (username, email, password_hash, dni, role, status, created_at, updated_at)
                VALUES (:username, :email, :password_hash, :dni, :role, :status, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "username": "Página Web",
                "email": "web@qoricash.pe",
                "password_hash": password_hash,
                "dni": "99999997",  # DNI ficticio para usuario de sistema
                "role": "Web",
                "status": "Activo"
            }
        )
        print("✅ Usuario 'Página Web' creado para operaciones desde la web")


def downgrade():
    """
    Revertir cambios:
    1. Restaurar usuario web a rol Plataforma
    2. Eliminar 'Web' del constraint de roles
    3. Eliminar 'web' del constraint de origen
    """

    # 1. Restaurar usuario (si existe)
    connection = op.get_bind()

    result = connection.execute(
        sa.text("SELECT id FROM users WHERE email = 'web@qoricash.pe' LIMIT 1")
    ).fetchone()

    if result:
        user_id = result[0]

        connection.execute(
            sa.text("""
                UPDATE users
                SET role = 'Plataforma',
                    username = 'Web Externa'
                WHERE id = :user_id
            """),
            {"user_id": user_id}
        )

    # 2. Restaurar constraint de roles sin 'Web'
    op.drop_constraint('check_user_role', 'users', type_='check')
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma', 'App')"
    )

    # 3. Restaurar constraint de origen sin 'web'
    op.drop_constraint('check_operation_origen', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('sistema', 'plataforma', 'app')"
    )

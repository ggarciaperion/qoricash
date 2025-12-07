"""
Script para crear usuario con rol Plataforma
Este usuario será utilizado por la página web pública para registrar clientes y operaciones

Uso:
    python create_plataforma_user.py
"""
import os
import sys

# Asegurar que estamos en el directorio correcto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models.user import User
from app.extensions import db
from getpass import getpass

def create_plataforma_user():
    """Crear usuario con rol Plataforma"""

    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("CREAR USUARIO PLATAFORMA PARA WEB PÚBLICA")
        print("=" * 60)

        # Verificar si ya existe un usuario Plataforma
        existing = User.query.filter_by(role='Plataforma').first()
        if existing:
            print(f"\n⚠️  Ya existe un usuario Plataforma: {existing.username}")
            respuesta = input("¿Deseas crear otro usuario Plataforma? (s/n): ")
            if respuesta.lower() != 's':
                print("Operación cancelada.")
                return False

        print("\nIngresa los datos para el nuevo usuario Plataforma:\n")

        # Solicitar datos
        username = input("Username (ej: plataforma_web): ").strip()
        if not username:
            print("❌ El username es requerido")
            return False

        # Verificar si el username ya existe
        if User.query.filter_by(username=username).first():
            print(f"❌ Ya existe un usuario con username '{username}'")
            return False

        email = input("Email (ej: plataforma@qoricash.com): ").strip()
        if not email:
            print("❌ El email es requerido")
            return False

        # Verificar si el email ya existe
        if User.query.filter_by(email=email).first():
            print(f"❌ Ya existe un usuario con email '{email}'")
            return False

        dni = input("DNI (8 dígitos, ej: 00000001): ").strip()
        if not dni or len(dni) != 8:
            print("❌ El DNI debe tener 8 dígitos")
            return False

        # Verificar si el DNI ya existe
        if User.query.filter_by(dni=dni).first():
            print(f"❌ Ya existe un usuario con DNI '{dni}'")
            return False

        # Solicitar contraseña
        print("\n⚠️  La contraseña debe ser segura (mínimo 8 caracteres)")
        password = getpass("Contraseña: ")
        password_confirm = getpass("Confirmar contraseña: ")

        if password != password_confirm:
            print("❌ Las contraseñas no coinciden")
            return False

        if len(password) < 8:
            print("❌ La contraseña debe tener al menos 8 caracteres")
            return False

        # Crear usuario
        print("\n" + "-" * 60)
        print("Creando usuario con los siguientes datos:")
        print(f"  Username: {username}")
        print(f"  Email: {email}")
        print(f"  DNI: {dni}")
        print(f"  Rol: Plataforma")
        print(f"  Estado: Activo")
        print("-" * 60)

        confirmacion = input("\n¿Confirmas la creación del usuario? (s/n): ")
        if confirmacion.lower() != 's':
            print("Operación cancelada.")
            return False

        try:
            user = User(
                username=username,
                email=email,
                dni=dni,
                role='Plataforma',
                status='Activo'
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            print("\n" + "=" * 60)
            print("✅ USUARIO PLATAFORMA CREADO EXITOSAMENTE")
            print("=" * 60)
            print(f"\nID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Rol: {user.role}")
            print(f"Estado: {user.status}")
            print("\n📌 Este usuario puede:")
            print("  • Registrar clientes desde la web pública")
            print("  • Crear operaciones con origen='plataforma'")
            print("  • Acceder a endpoints /api/platform/*")
            print("\n⚠️  IMPORTANTE: Guarda estas credenciales de forma segura")
            print(f"   Username: {user.username}")
            print(f"   Password: [la que ingresaste]")

            return True

        except Exception as e:
            print(f"\n❌ ERROR al crear usuario: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   CREAR USUARIO PLATAFORMA                                ║")
    print("║   QoriCash Trading System                                 ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("\n")

    success = create_plataforma_user()

    if success:
        print("\n✅ Usuario creado exitosamente\n")
        sys.exit(0)
    else:
        print("\n❌ No se pudo crear el usuario\n")
        sys.exit(1)

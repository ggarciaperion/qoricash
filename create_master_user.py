#!/usr/bin/env python
"""
Script para crear usuario Master en producción
Ejecutar desde Render Shell: python create_master_user.py
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.user import User

def create_master_user():
    """Crear usuario Master"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("CREAR USUARIO MASTER - QoriCash Trading")
        print("=" * 60)

        # Solicitar datos
        print("\nIngrese los datos del usuario Master:\n")

        username = input("Username: ").strip()
        if not username:
            print("❌ Error: El username es requerido")
            return

        email = input("Email: ").strip()
        if not email:
            print("❌ Error: El email es requerido")
            return

        password = input("Password: ").strip()
        if not password:
            print("❌ Error: El password es requerido")
            return

        dni = input("DNI (opcional, presiona Enter para omitir): ").strip()
        if not dni:
            dni = None

        # Verificar si ya existe
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            print(f"\n❌ Error: Ya existe un usuario con ese username o email")
            print(f"   Username existente: {existing_user.username}")
            print(f"   Email existente: {existing_user.email}")
            return

        # Crear usuario
        try:
            user = User(
                username=username,
                email=email,
                dni=dni,
                role='Master',
                status='Activo'
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            print("\n" + "=" * 60)
            print("✅ USUARIO MASTER CREADO EXITOSAMENTE")
            print("=" * 60)
            print(f"\nID:       {user.id}")
            print(f"Username: {user.username}")
            print(f"Email:    {user.email}")
            print(f"DNI:      {user.dni or 'N/A'}")
            print(f"Role:     {user.role}")
            print(f"Status:   {user.status}")
            print(f"\nAhora puedes iniciar sesión en: https://tu-app.onrender.com")
            print("=" * 60)

        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error al crear usuario: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    create_master_user()

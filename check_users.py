#!/usr/bin/env python
"""
Script para listar todos los usuarios en la base de datos
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

# Monkey patch de eventlet PRIMERO
import eventlet
eventlet.monkey_patch()

from app import create_app
from app.models.user import User

def list_users():
    """Listar todos los usuarios"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("USUARIOS EN LA BASE DE DATOS")
        print("=" * 80)

        users = User.query.all()

        if not users:
            print("\n❌ No hay usuarios en la base de datos")
            print("\nEjecuta create_master_quick.py para crear el usuario Master")
            return

        print(f"\nTotal de usuarios: {len(users)}\n")

        for user in users:
            print("-" * 80)
            print(f"ID:       {user.id}")
            print(f"Username: {user.username}")
            print(f"Email:    {user.email}")
            print(f"DNI:      {user.dni or 'N/A'}")
            print(f"Role:     {user.role}")
            print(f"Status:   {user.status}")
            print(f"Created:  {user.created_at}")
            print(f"Last Login: {user.last_login or 'Nunca'}")

        print("=" * 80)

if __name__ == '__main__':
    list_users()

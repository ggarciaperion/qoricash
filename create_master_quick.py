#!/usr/bin/env python
"""
Script RÁPIDO para crear usuario Master en producción
Sin input interactivo - Ejecutar: python create_master_quick.py
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.user import User

# ========================================
# CONFIGURAR AQUÍ LOS DATOS DEL USUARIO
# ========================================
USERNAME = "admin"
EMAIL = "admin@qoricash.com"
PASSWORD = "Qoricash2024!"  # CAMBIAR DESPUÉS DEL PRIMER LOGIN
DNI = None  # Opcional
# ========================================

def create_master_user():
    """Crear usuario Master"""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("CREAR USUARIO MASTER - QoriCash Trading")
        print("=" * 60)

        # Verificar si ya existe
        existing_user = User.query.filter(
            (User.username == USERNAME) | (User.email == EMAIL)
        ).first()

        if existing_user:
            print(f"\n⚠️  Usuario ya existe:")
            print(f"   ID:       {existing_user.id}")
            print(f"   Username: {existing_user.username}")
            print(f"   Email:    {existing_user.email}")
            print(f"   Role:     {existing_user.role}")
            print(f"   Status:   {existing_user.status}")
            print("\n¿Deseas actualizar la contraseña? (y/n): ", end='')

            try:
                response = input().strip().lower()
                if response == 'y':
                    existing_user.set_password(PASSWORD)
                    db.session.commit()
                    print("✅ Contraseña actualizada exitosamente")
                else:
                    print("❌ No se realizaron cambios")
            except:
                print("\n❌ No se realizaron cambios")
            return

        # Crear usuario nuevo
        try:
            user = User(
                username=USERNAME,
                email=EMAIL,
                dni=DNI,
                role='Master',
                status='Activo'
            )
            user.set_password(PASSWORD)

            db.session.add(user)
            db.session.commit()

            print("\n" + "=" * 60)
            print("✅ USUARIO MASTER CREADO EXITOSAMENTE")
            print("=" * 60)
            print(f"\nCredenciales de Acceso:")
            print(f"URL:      https://tu-app.onrender.com")
            print(f"Username: {user.username}")
            print(f"Email:    {user.email}")
            print(f"Password: {PASSWORD}")
            print(f"\nDatos del Usuario:")
            print(f"ID:       {user.id}")
            print(f"DNI:      {user.dni or 'N/A'}")
            print(f"Role:     {user.role}")
            print(f"Status:   {user.status}")
            print("\n⚠️  IMPORTANTE: Cambia la contraseña después del primer login")
            print("=" * 60)

        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error al crear usuario: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    create_master_user()

#!/usr/bin/env python
"""
Script para resetear contraseña del usuario Master en producción
Ejecutar en Render Shell: python reset_master_password.py
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

# Monkey patch de eventlet PRIMERO
import eventlet
eventlet.monkey_patch()

from app import create_app
from app.extensions import db
from app.models.user import User

# ========================================
# CONFIGURAR CREDENCIALES DEL MASTER
# ========================================
NEW_USERNAME = "admin"
NEW_EMAIL = "admin@qoricash.com"
NEW_PASSWORD = "Qoricash2024!"
NEW_DNI = "00000000"
# ========================================

def reset_or_create_master():
    """Resetear o crear usuario Master"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("RESETEAR/CREAR USUARIO MASTER - QoriCash Trading")
        print("=" * 80)

        # Listar todos los usuarios actuales
        all_users = User.query.all()
        print(f"\n📋 Usuarios actuales en la base de datos: {len(all_users)}")

        for user in all_users:
            print(f"   - ID: {user.id} | Username: {user.username} | Email: {user.email} | Role: {user.role} | Status: {user.status}")

        # Buscar usuario Master existente
        master_user = User.query.filter_by(role='Master').first()

        if master_user:
            print(f"\n✅ Usuario Master encontrado:")
            print(f"   ID:       {master_user.id}")
            print(f"   Username: {master_user.username}")
            print(f"   Email:    {master_user.email}")
            print(f"   Status:   {master_user.status}")

            # Actualizar credenciales
            print(f"\n🔄 Actualizando credenciales...")
            master_user.username = NEW_USERNAME
            master_user.email = NEW_EMAIL
            master_user.dni = NEW_DNI
            master_user.status = 'Activo'
            master_user.set_password(NEW_PASSWORD)

            db.session.commit()
            print("✅ Credenciales actualizadas exitosamente!")

        else:
            # Crear nuevo usuario Master
            print(f"\n⚠️  No se encontró usuario Master. Creando nuevo...")

            # Verificar si existe usuario con mismo username o email
            existing = User.query.filter(
                (User.username == NEW_USERNAME) | (User.email == NEW_EMAIL)
            ).first()

            if existing:
                print(f"\n🔄 Usuario existente encontrado (convirtiendo a Master):")
                print(f"   Username: {existing.username}")
                print(f"   Email:    {existing.email}")
                existing.role = 'Master'
                existing.status = 'Activo'
                existing.set_password(NEW_PASSWORD)
                master_user = existing
            else:
                # Crear completamente nuevo
                master_user = User(
                    username=NEW_USERNAME,
                    email=NEW_EMAIL,
                    dni=NEW_DNI,
                    role='Master',
                    status='Activo'
                )
                master_user.set_password(NEW_PASSWORD)
                db.session.add(master_user)

            db.session.commit()
            print("✅ Usuario Master creado exitosamente!")

        # Mostrar credenciales finales
        print("\n" + "=" * 80)
        print("🎉 CREDENCIALES DE ACCESO")
        print("=" * 80)
        print(f"\n🌐 URL:      {os.environ.get('RENDER_EXTERNAL_URL', 'https://qoricash-trading-u673.onrender.com')}/login")
        print(f"👤 Username: {master_user.username}")
        print(f"📧 Email:    {master_user.email}")
        print(f"🔑 Password: {NEW_PASSWORD}")
        print(f"\n📋 Detalles:")
        print(f"   ID:     {master_user.id}")
        print(f"   DNI:    {master_user.dni or 'N/A'}")
        print(f"   Role:   {master_user.role}")
        print(f"   Status: {master_user.status}")
        print("\n⚠️  IMPORTANTE: Cambia la contraseña después del primer login")
        print("=" * 80)

if __name__ == '__main__':
    try:
        reset_or_create_master()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

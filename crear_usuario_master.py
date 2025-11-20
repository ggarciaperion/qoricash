"""
Script para crear o resetear usuario Master
QoriCash Trading V2
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models.user import User
from app.utils.formatters import now_peru

print("=" * 60)
print("CREACION/RESETEO DE USUARIO MASTER")
print("=" * 60)

app = create_app()

with app.app_context():
    # Verificar si ya existe un usuario admin
    existing = User.query.filter_by(username='admin').first()

    if existing:
        print(f"\n[!] Usuario 'admin' ya existe")
        print(f"   Email: {existing.email}")
        print(f"   DNI: {existing.dni}")
        print(f"   Rol: {existing.role}")
        print(f"   Estado: {existing.status}")

        respuesta = input("\nDeseas resetear la contrasena? (s/n): ").strip().lower()

        if respuesta == 's':
            # Resetear contraseña
            existing.set_password('admin123')
            existing.status = 'Activo'  # Asegurar que esté activo
            db.session.commit()

            print("\n[OK] Contrasena reseteada exitosamente")
            print("=" * 60)
            print("CREDENCIALES DE ACCESO:")
            print("=" * 60)
            print(f"Username: admin")
            print(f"Password: admin123")
            print(f"URL: http://localhost:5000/login")
            print("=" * 60)
            print("[!] IMPORTANTE: Cambia esta contrasena despues del login")
            print("=" * 60)
        else:
            print("\n[X] Operacion cancelada")
    else:
        # Crear nuevo usuario Master
        print("\n[...] Creando nuevo usuario Master...")

        admin = User(
            username='admin',
            email='admin@qoricash.com',
            dni='12345678',
            role='Master',
            status='Activo',
            created_at=now_peru()
        )
        admin.set_password('admin123')

        db.session.add(admin)
        db.session.commit()

        print("\n[OK] Usuario Master creado exitosamente")
        print("=" * 60)
        print("CREDENCIALES DE ACCESO:")
        print("=" * 60)
        print(f"Username: admin")
        print(f"Password: admin123")
        print(f"Email: admin@qoricash.com")
        print(f"DNI: 12345678")
        print(f"Rol: Master")
        print(f"URL: http://localhost:5000/login")
        print("=" * 60)
        print("[!] IMPORTANTE: Cambia esta contrasena despues del login")
        print("=" * 60)

    # Listar todos los usuarios Master existentes
    print("\nUSUARIOS MASTER EN EL SISTEMA:")
    print("-" * 60)
    masters = User.query.filter_by(role='Master').all()
    if masters:
        for master in masters:
            status_icon = "[OK]" if master.status == 'Activo' else "[X]"
            print(f"{status_icon} {master.username} | {master.email} | {master.status}")
    else:
        print("No hay usuarios Master registrados")
    print("-" * 60)

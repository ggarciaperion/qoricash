"""
Script para actualizar clientes existentes con datos faltantes
QoriCash Trading V2

Este script:
1. Asigna created_by a clientes que no tienen usuario asignado
2. Asigna created_at a clientes sin fecha
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models.client import Client
from app.models.user import User
from datetime import datetime
from app.utils.formatters import now_peru

print("=" * 60)
print("ACTUALIZACION DE CLIENTES EXISTENTES")
print("=" * 60)

app = create_app()

with app.app_context():
    # Obtener todos los clientes
    all_clients = Client.query.all()
    print(f"\nTotal de clientes en la base de datos: {len(all_clients)}")

    # Buscar el usuario Master o el primer usuario disponible
    master_user = User.query.filter_by(role='Master').first()
    if not master_user:
        master_user = User.query.first()

    if not master_user:
        print("\n[ERROR] No hay usuarios en el sistema.")
        print("Por favor, crea primero un usuario Master ejecutando:")
        print("  python crear_usuario_master.py")
        sys.exit(1)

    print(f"\nUsuario de referencia para asignacion: {master_user.username} ({master_user.role})")

    # Contadores
    clientes_sin_created_by = 0
    clientes_sin_created_at = 0
    clientes_actualizados = 0

    print("\nAnalizando clientes...")
    print("-" * 60)

    for client in all_clients:
        actualizado = False

        # Verificar created_by
        if not client.created_by:
            client.created_by = master_user.id
            clientes_sin_created_by += 1
            actualizado = True
            print(f"[+] Cliente #{client.id} ({client.full_name or client.dni}): asignando created_by")

        # Verificar created_at
        if not client.created_at:
            client.created_at = now_peru()
            clientes_sin_created_at += 1
            actualizado = True
            print(f"[+] Cliente #{client.id} ({client.full_name or client.dni}): asignando created_at")

        if actualizado:
            clientes_actualizados += 1

    # Guardar cambios
    if clientes_actualizados > 0:
        try:
            db.session.commit()
            print("-" * 60)
            print(f"\n[OK] {clientes_actualizados} clientes actualizados exitosamente")
            print(f"     - Clientes sin created_by: {clientes_sin_created_by}")
            print(f"     - Clientes sin created_at: {clientes_sin_created_at}")
        except Exception as e:
            db.session.rollback()
            print(f"\n[ERROR] Error al guardar cambios: {e}")
            sys.exit(1)
    else:
        print("\n[OK] Todos los clientes ya tienen los datos completos")

    # Mostrar resumen final
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)

    clientes_con_creator = Client.query.filter(Client.created_by.isnot(None)).count()
    clientes_con_fecha = Client.query.filter(Client.created_at.isnot(None)).count()

    print(f"Total de clientes: {len(all_clients)}")
    print(f"Clientes con created_by: {clientes_con_creator}")
    print(f"Clientes con created_at: {clientes_con_fecha}")

    if clientes_con_creator == len(all_clients) and clientes_con_fecha == len(all_clients):
        print("\n[OK] Todos los clientes tienen datos completos!")
        print("     Ahora la tabla mostrara correctamente:")
        print("     - Columna 'Usuario' (para Master/Operador)")
        print("     - Columna 'Fecha Registro' (para todos)")
    else:
        print("\n[!] Algunos clientes aun tienen datos incompletos")
        print("    Ejecuta este script nuevamente")

    print("=" * 60)

    # Mostrar algunos ejemplos
    print("\nEJEMPLOS DE CLIENTES (primeros 5):")
    print("-" * 60)
    ejemplos = Client.query.limit(5).all()
    for client in ejemplos:
        creator_name = client.creator.username if client.creator else "N/A"
        fecha = client.created_at.strftime('%d/%m/%Y %H:%M') if client.created_at else "N/A"
        print(f"ID: {client.id} | {client.full_name or client.dni}")
        print(f"  -> Registrado por: {creator_name}")
        print(f"  -> Fecha: {fecha}")
        print()

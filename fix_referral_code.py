"""
Script para actualizar cliente que usó código de referido antes del fix
Este script marca al cliente con DNI 73733737 como que ya usó el código 3NEFUG
"""
import sys
import os

# Agregar el directorio raíz al path para importar la app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.client import Client

def fix_referral_code():
    """Actualizar cliente que ya usó código de referido"""
    app = create_app()

    with app.app_context():
        # Buscar el cliente con DNI 73733737
        client = Client.query.filter_by(dni='73733737').first()

        if not client:
            print("❌ Cliente con DNI 73733737 no encontrado")
            return

        print(f"✅ Cliente encontrado: {client.full_name} (DNI: {client.dni})")
        print(f"   Estado actual - used_referral_code: {client.used_referral_code}")
        print(f"   Estado actual - referred_by: {client.referred_by}")

        # Buscar el dueño del código 3NEFUG
        referrer = Client.query.filter_by(referral_code='3NEFUG').first()

        if not referrer:
            print("❌ No se encontró el dueño del código 3NEFUG")
            return

        print(f"✅ Dueño del código encontrado: {referrer.full_name} (Código: {referrer.referral_code})")

        # Actualizar el cliente
        client.used_referral_code = '3NEFUG'
        client.referred_by = referrer.id

        # Guardar cambios
        db.session.commit()

        print(f"\n✅ Cliente actualizado exitosamente!")
        print(f"   used_referral_code: {client.used_referral_code}")
        print(f"   referred_by: {client.referred_by} ({referrer.full_name})")
        print(f"\n🔒 Ahora el cliente NO podrá usar otro código de referido")

if __name__ == '__main__':
    fix_referral_code()

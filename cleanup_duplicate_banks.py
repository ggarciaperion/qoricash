"""
Script para eliminar bancos duplicados/fantasma de la base de datos

Este script elimina los bancos genéricos sin número de cuenta que no deberían existir.
Solo deben existir bancos con el formato: "BANCO MONEDA (número_cuenta)"

Bancos a eliminar:
- BCP (sin número de cuenta) - tiene $5,000 que causan el descuadre
- BBVA (sin número de cuenta)
- INTERBANK (sin número de cuenta)
- SCOTIABANK (sin número de cuenta)
- PICHINCHA (sin número de cuenta)
- BANBIF (sin número de cuenta)
"""

import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.bank_balance import BankBalance

def cleanup_duplicate_banks():
    """Eliminar bancos duplicados/fantasma"""

    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("LIMPIEZA DE BANCOS DUPLICADOS/FANTASMA")
        print("=" * 80)

        # Lista de bancos genéricos a eliminar (sin número de cuenta)
        banks_to_delete = [
            'BCP',
            'BBVA',
            'INTERBANK',
            'SCOTIABANK',
            'PICHINCHA',
            'BANBIF'
        ]

        print("\nBuscando bancos fantasma...")
        print("-" * 80)

        deleted_count = 0

        for bank_name in banks_to_delete:
            bank = BankBalance.query.filter_by(bank_name=bank_name).first()

            if bank:
                print(f"\n❌ Encontrado banco fantasma: {bank_name}")
                print(f"   Saldos: USD ${float(bank.balance_usd)}, PEN S/{float(bank.balance_pen)}")
                print(f"   Saldos iniciales: USD ${float(bank.initial_balance_usd)}, PEN S/{float(bank.initial_balance_pen)}")
                print(f"   ID: {bank.id}")

                # Eliminar
                db.session.delete(bank)
                deleted_count += 1
                print(f"   ✓ Eliminado")
            else:
                print(f"✓ {bank_name}: No encontrado (OK)")

        # Mostrar bancos que quedarán
        print("\n" + "=" * 80)
        print("BANCOS QUE QUEDARÁN EN LA BASE DE DATOS:")
        print("-" * 80)

        # Commit temporal para ver los resultados
        db.session.commit()

        remaining_banks = BankBalance.query.all()

        if remaining_banks:
            for bank in remaining_banks:
                print(f"✓ {bank.bank_name}")
                print(f"  Inicial: USD ${float(bank.initial_balance_usd)}, PEN S/{float(bank.initial_balance_pen)}")
                print(f"  Actual: USD ${float(bank.balance_usd)}, PEN S/{float(bank.balance_pen)}")
                print()
        else:
            print("⚠️  No quedan bancos en la base de datos")

        print("=" * 80)
        print(f"\n✓ Limpieza completada exitosamente")
        print(f"  Bancos eliminados: {deleted_count}")
        print(f"  Bancos restantes: {len(remaining_banks)}")
        print("=" * 80)

if __name__ == '__main__':
    try:
        cleanup_duplicate_banks()
        print("\n✓ Script ejecutado exitosamente")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

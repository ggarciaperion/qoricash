"""
Script para eliminar bancos fantasma que no están en el desplegable oficial

Según el modal "Agregar Cuenta Bancaria a Reconciliación", SOLO deben existir
estos 8 bancos en la base de datos:

USD:
1. BCP USD (654321)
2. INTERBANK USD (456789)
3. BANBIF USD (369852)
4. PICHINCHA USD (159796)

PEN:
1. BCP PEN (123456)
2. INTERBANK PEN (987654)
3. BANBIF PEN (741852)
4. PICHINCHA PEN (753951)

Este script eliminará todos los demás bancos, incluyendo:
- BCP (sin número de cuenta) - $5,000 que causa el descuadre
- BBVA, INTERBANK genérico, SCOTIABANK, PICHINCHA genérico, BANBIF genérico
"""

import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.bank_balance import BankBalance

def fix_bank_reconciliation():
    """Eliminar todos los bancos que no estén en la lista oficial del desplegable"""

    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("LIMPIEZA DE BANCOS FANTASMA - RECONCILIACIÓN BANCARIA")
        print("=" * 80)

        # Lista OFICIAL de bancos permitidos (según el desplegable del modal)
        allowed_banks = [
            'BCP USD (654321)',
            'INTERBANK USD (456789)',
            'BANBIF USD (369852)',
            'PICHINCHA USD (159796)',
            'BCP PEN (123456)',
            'INTERBANK PEN (987654)',
            'BANBIF PEN (741852)',
            'PICHINCHA PEN (753951)'
        ]

        # Obtener todos los bancos actuales
        all_banks = BankBalance.query.all()

        print(f"\nTotal de bancos en la base de datos: {len(all_banks)}")
        print("\n" + "-" * 80)
        print("ANÁLISIS DE BANCOS:")
        print("-" * 80)

        banks_to_delete = []
        banks_to_keep = []

        for bank in all_banks:
            if bank.bank_name in allowed_banks:
                banks_to_keep.append(bank)
                print(f"✓ MANTENER: {bank.bank_name}")
                print(f"  Inicial: USD ${float(bank.initial_balance_usd)}, PEN S/{float(bank.initial_balance_pen)}")
                print(f"  Actual: USD ${float(bank.balance_usd)}, PEN S/{float(bank.balance_pen)}")
            else:
                banks_to_delete.append(bank)
                print(f"❌ ELIMINAR: {bank.bank_name}")
                print(f"   Saldos: USD ${float(bank.balance_usd)}, PEN S/{float(bank.balance_pen)}")
                print(f"   Saldos iniciales: USD ${float(bank.initial_balance_usd)}, PEN S/{float(bank.initial_balance_pen)}")
                print(f"   ID: {bank.id}")

        # Confirmar eliminación
        print("\n" + "=" * 80)
        print(f"Se eliminarán {len(banks_to_delete)} banco(s) fantasma:")
        print("=" * 80)

        total_usd_deleted = 0
        total_pen_deleted = 0

        for bank in banks_to_delete:
            print(f"- {bank.bank_name} (ID: {bank.id})")
            total_usd_deleted += float(bank.initial_balance_usd or 0)
            total_pen_deleted += float(bank.initial_balance_pen or 0)
            db.session.delete(bank)

        # Commit de eliminaciones
        db.session.commit()

        print(f"\n✓ Saldos iniciales eliminados: USD ${total_usd_deleted}, PEN S/{total_pen_deleted}")
        print(f"✓ {len(banks_to_delete)} banco(s) eliminado(s) exitosamente")

        # Mostrar resumen final
        print("\n" + "=" * 80)
        print("BANCOS RESTANTES EN LA BASE DE DATOS:")
        print("=" * 80)

        remaining_banks = BankBalance.query.all()
        total_initial_usd = 0
        total_initial_pen = 0

        for bank in remaining_banks:
            print(f"\n✓ {bank.bank_name}")
            print(f"  Inicial: USD ${float(bank.initial_balance_usd)}, PEN S/{float(bank.initial_balance_pen)}")
            print(f"  Actual: USD ${float(bank.balance_usd)}, PEN S/{float(bank.balance_pen)}")
            total_initial_usd += float(bank.initial_balance_usd or 0)
            total_initial_pen += float(bank.initial_balance_pen or 0)

        print("\n" + "=" * 80)
        print(f"TOTAL SALDOS INICIALES:")
        print(f"  USD: ${total_initial_usd}")
        print(f"  PEN: S/{total_initial_pen}")
        print("=" * 80)
        print(f"\n✓ Limpieza completada exitosamente")
        print(f"  Bancos totales: {len(remaining_banks)}")
        print("=" * 80)

if __name__ == '__main__':
    try:
        fix_bank_reconciliation()
        print("\n✓ Script ejecutado exitosamente")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

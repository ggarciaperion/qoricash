"""
Script para cambiar forzosamente el estado de la operación EXP-1010 a Cancelado
"""
import sys
import os

# Agregar el directorio raíz al path para importar app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.operation import Operation
from app.utils.timezone import now_peru

def fix_operation_exp_1010():
    """Cambiar estado de EXP-1010 de Pendiente a Cancelado"""

    app = create_app()

    with app.app_context():
        # Buscar la operación EXP-1010
        operation = Operation.query.filter_by(operation_id='EXP-1010').first()

        if not operation:
            print("❌ ERROR: No se encontró la operación EXP-1010")
            return False

        print(f"📋 Operación encontrada:")
        print(f"   ID: {operation.id}")
        print(f"   Código: {operation.operation_id}")
        print(f"   Estado actual: {operation.status}")
        print(f"   Cliente: {operation.client.full_name if operation.client else 'N/A'}")
        print(f"   Monto USD: ${operation.amount_usd}")
        print(f"   Monto PEN: S/{operation.amount_pen}")
        print(f"   Creada: {operation.created_at}")
        print(f"   Origen: {operation.origen if hasattr(operation, 'origen') else 'N/A'}")

        if operation.status != 'Pendiente':
            print(f"\n⚠️ ADVERTENCIA: La operación no está en estado 'Pendiente'")
            print(f"   Estado actual: {operation.status}")
            respuesta = input("¿Deseas continuar de todas formas? (s/n): ")
            if respuesta.lower() != 's':
                print("❌ Operación cancelada por el usuario")
                return False

        # Cambiar estado a Cancelado
        estado_anterior = operation.status
        operation.status = 'Cancelado'
        operation.updated_at = now_peru()

        try:
            db.session.commit()
            print(f"\n✅ ÉXITO: Estado de la operación {operation.operation_id} cambiado")
            print(f"   Estado anterior: {estado_anterior}")
            print(f"   Estado nuevo: {operation.status}")
            print(f"   Actualizado: {operation.updated_at}")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERROR al actualizar la operación: {str(e)}")
            return False

if __name__ == '__main__':
    fix_operation_exp_1010()

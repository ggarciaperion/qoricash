"""
Script para cambiar el estado de una operación específica
Uso: python scripts/fix_operation_status.py <operation_id> <nuevo_estado>
Ejemplo: python scripts/fix_operation_status.py EXP-1010 Cancelado
"""
import sys
import os

# Agregar el directorio raíz al path para importar app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.operation import Operation
from app.utils.timezone import now_peru

def fix_operation_status(operation_id, new_status):
    """Cambiar estado de una operación específica"""

    app = create_app()

    with app.app_context():
        # Buscar la operación
        operation = Operation.query.filter_by(operation_id=operation_id).first()

        if not operation:
            print(f"❌ ERROR: No se encontró la operación {operation_id}")
            return False

        print(f"📋 Operación encontrada:")
        print(f"   ID: {operation.id}")
        print(f"   Código: {operation.operation_id}")
        print(f"   Estado actual: {operation.status}")
        print(f"   Cliente: {operation.client.full_name if operation.client else 'N/A'}")
        print(f"   Monto USD: ${operation.amount_usd}")
        print(f"   Monto PEN: S/{operation.amount_pen}")
        print(f"   Creada: {operation.created_at}")

        # Cambiar estado
        estado_anterior = operation.status
        operation.status = new_status
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
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python scripts/fix_operation_status.py <operation_id> <nuevo_estado>")
        print("Ejemplo: python scripts/fix_operation_status.py EXP-1010 Cancelado")
        print("\nEstados válidos: Pendiente, En proceso, Completada, Cancelado, Expirada")
        sys.exit(1)

    operation_id = sys.argv[1]
    new_status = sys.argv[2]

    # Validar estado
    valid_statuses = ['Pendiente', 'En proceso', 'Completada', 'Cancelado', 'Expirada']
    if new_status not in valid_statuses:
        print(f"❌ ERROR: Estado inválido '{new_status}'")
        print(f"Estados válidos: {', '.join(valid_statuses)}")
        sys.exit(1)

    fix_operation_status(operation_id, new_status)

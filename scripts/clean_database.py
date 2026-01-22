"""
Script de Limpieza de Base de Datos - QoriCash Trading V2

Este script elimina TODOS los clientes y operaciones del sistema,
incluyendo todos los datos relacionados (compliance, facturas, etc.).

ADVERTENCIA: Esta acción es IRREVERSIBLE
Los usuarios del sistema (Traders, Operadores, Master) NO se eliminan

Uso:
    python scripts/clean_database.py

Autor: Claude Code
Fecha: 2026-01-22
"""

import os
import sys
from pathlib import Path

# Configurar encoding UTF-8 para Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
env_path = root_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"⚠️  ADVERTENCIA: No se encontró archivo .env en {root_dir}")
    print("Asegúrate de tener configuradas las variables de entorno necesarias")
    print()

# Monkey patch DEBE ser lo primero (requerido para Eventlet)
import eventlet
eventlet.monkey_patch()

from app import create_app, db
from app.models.client import Client
from app.models.operation import Operation
from app.models.invoice import Invoice
from app.models.reward_code import RewardCode
from app.models.compliance import (
    ClientRiskProfile,
    ComplianceAlert,
    ComplianceDocument,
    RestrictiveListCheck,
    TransactionMonitoring,
    ComplianceAudit
)
from app.models.audit_log import AuditLog
from datetime import datetime


def print_header():
    """Imprimir encabezado del script"""
    print("=" * 80)
    print(" " * 20 + "LIMPIEZA DE BASE DE DATOS")
    print(" " * 15 + "QoriCash Trading V2 - Clean Database Script")
    print("=" * 80)
    print()
    print("⚠️  ADVERTENCIA: Este script eliminará TODOS los clientes y operaciones")
    print("⚠️  Esta acción es IRREVERSIBLE")
    print()
    print("✅ Los usuarios del sistema (Master, Traders, Operadores) NO se eliminan")
    print()
    print("=" * 80)
    print()


def count_records():
    """Contar registros antes de la limpieza"""
    print("📊 Conteo de registros actuales:")
    print("-" * 80)

    counts = {
        'Clientes': Client.query.count(),
        'Operaciones': Operation.query.count(),
        'Facturas': Invoice.query.count(),
        'Códigos de Recompensa': RewardCode.query.count(),
        'Perfiles de Riesgo': ClientRiskProfile.query.count(),
        'Alertas de Compliance': ComplianceAlert.query.count(),
        'Documentos de Compliance': ComplianceDocument.query.count(),
        'Verificaciones de Listas': RestrictiveListCheck.query.count(),
        'Monitoreo de Transacciones': TransactionMonitoring.query.count(),
        'Auditoría de Compliance': ComplianceAudit.query.count(),
        'Registros de Auditoría': AuditLog.query.count(),
    }

    total = 0
    for table, count in counts.items():
        print(f"  • {table:<35} : {count:>8,} registros")
        total += count

    print("-" * 80)
    print(f"  TOTAL DE REGISTROS A ELIMINAR       : {total:>8,}")
    print()

    return counts


def confirm_deletion():
    """Solicitar confirmación del usuario"""
    print("⚠️  CONFIRMACIÓN REQUERIDA")
    print("-" * 80)
    print()
    print("Para continuar, escribe exactamente: ELIMINAR TODO")
    print()

    confirmation = input("Confirmación: ").strip()

    if confirmation != "ELIMINAR TODO":
        print()
        print("❌ Confirmación incorrecta. Operación cancelada.")
        return False

    print()
    print("✅ Confirmación recibida. Iniciando limpieza...")
    print()
    return True


def clean_database():
    """Ejecutar limpieza de base de datos"""

    try:
        print("🗑️  Iniciando proceso de limpieza...")
        print("-" * 80)
        print()

        deleted_counts = {}

        # Orden de eliminación (respetando foreign keys)

        # 1. Compliance Documents (depende de alerts, operations, clients)
        print("  [1/11] Eliminando Documentos de Compliance...")
        count = ComplianceDocument.query.delete()
        deleted_counts['ComplianceDocument'] = count
        print(f"          ✓ {count} documentos eliminados")

        # 2. Compliance Alerts (depende de clients, operations)
        print("  [2/11] Eliminando Alertas de Compliance...")
        count = ComplianceAlert.query.delete()
        deleted_counts['ComplianceAlert'] = count
        print(f"          ✓ {count} alertas eliminadas")

        # 3. Transaction Monitoring (depende de operations, clients)
        print("  [3/11] Eliminando Monitoreo de Transacciones...")
        count = TransactionMonitoring.query.delete()
        deleted_counts['TransactionMonitoring'] = count
        print(f"          ✓ {count} registros eliminados")

        # 4. Restrictive List Checks (depende de clients)
        print("  [4/11] Eliminando Verificaciones de Listas Restrictivas...")
        count = RestrictiveListCheck.query.delete()
        deleted_counts['RestrictiveListCheck'] = count
        print(f"          ✓ {count} verificaciones eliminadas")

        # 5. Client Risk Profiles (depende de clients)
        print("  [5/11] Eliminando Perfiles de Riesgo de Clientes...")
        count = ClientRiskProfile.query.delete()
        deleted_counts['ClientRiskProfile'] = count
        print(f"          ✓ {count} perfiles eliminados")

        # 6. Reward Codes (depende de clients, operations)
        print("  [6/11] Eliminando Códigos de Recompensa...")
        count = RewardCode.query.delete()
        deleted_counts['RewardCode'] = count
        print(f"          ✓ {count} códigos eliminados")

        # 7. Invoices (depende de operations, clients)
        print("  [7/11] Eliminando Facturas Electrónicas...")
        count = Invoice.query.delete()
        deleted_counts['Invoice'] = count
        print(f"          ✓ {count} facturas eliminadas")

        # 8. Operations (depende de clients)
        print("  [8/11] Eliminando Operaciones...")
        count = Operation.query.delete()
        deleted_counts['Operation'] = count
        print(f"          ✓ {count} operaciones eliminadas")

        # 9. Clients (tabla principal)
        print("  [9/11] Eliminando Clientes...")
        count = Client.query.delete()
        deleted_counts['Client'] = count
        print(f"          ✓ {count} clientes eliminados")

        # 10. Compliance Audit (relacionado con entidades eliminadas)
        print("  [10/11] Limpiando Auditoría de Compliance...")
        # Eliminar auditorías relacionadas con clientes y operaciones
        count = ComplianceAudit.query.filter(
            db.or_(
                ComplianceAudit.entity_type == 'Client',
                ComplianceAudit.entity_type == 'Operation'
            )
        ).delete()
        deleted_counts['ComplianceAudit'] = count
        print(f"           ✓ {count} registros de auditoría eliminados")

        # 11. Audit Logs (relacionado con entidades eliminadas)
        print("  [11/11] Limpiando Registros de Auditoría...")
        # Eliminar logs relacionados con clientes y operaciones
        count = AuditLog.query.filter(
            db.or_(
                AuditLog.entity == 'Client',
                AuditLog.entity == 'Operation'
            )
        ).delete()
        deleted_counts['AuditLog'] = count
        print(f"           ✓ {count} registros de auditoría eliminados")

        print()
        print("-" * 80)

        # Confirmar cambios
        db.session.commit()

        print()
        print("✅ LIMPIEZA COMPLETADA EXITOSAMENTE")
        print("=" * 80)
        print()
        print("📊 Resumen de eliminación:")
        print("-" * 80)

        total_deleted = 0
        for model, count in deleted_counts.items():
            print(f"  • {model:<35} : {count:>8,} eliminados")
            total_deleted += count

        print("-" * 80)
        print(f"  TOTAL DE REGISTROS ELIMINADOS       : {total_deleted:>8,}")
        print()

        return True

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ ERROR DURANTE LA LIMPIEZA")
        print("=" * 80)
        print()
        print(f"Error: {str(e)}")
        print()
        print("🔄 Realizando rollback...")
        db.session.rollback()
        print("✓ Rollback completado. No se realizaron cambios en la base de datos.")
        print()

        import traceback
        print("Stack trace completo:")
        print(traceback.format_exc())

        return False


def verify_users_intact():
    """Verificar que los usuarios del sistema no fueron afectados"""
    from app.models.user import User

    print("🔍 Verificando integridad de usuarios del sistema...")
    print("-" * 80)

    users = User.query.all()
    print(f"  ✓ Total de usuarios en el sistema: {len(users)}")

    for user in users:
        print(f"    • {user.username} ({user.role}) - {user.status}")

    print()


def main():
    """Función principal"""

    # Crear aplicación Flask
    app = create_app()

    with app.app_context():
        print_header()

        # Contar registros antes
        count_records()

        # Solicitar confirmación
        if not confirm_deletion():
            sys.exit(0)

        # Ejecutar limpieza
        success = clean_database()

        if success:
            # Verificar usuarios
            verify_users_intact()

            print("=" * 80)
            print()
            print("✅ Base de datos limpiada exitosamente")
            print()
            print("El sistema está listo para realizar pruebas integrales.")
            print()
            print("Próximos pasos recomendados:")
            print("  1. Crear clientes de prueba desde cada canal (app, web, sistema)")
            print("  2. Crear operaciones de prueba")
            print("  3. Verificar flujos completos (registro, operaciones, compliance)")
            print("  4. Validar correos automáticos")
            print("  5. Validar facturación electrónica (NubeFact)")
            print()
            print("=" * 80)

            sys.exit(0)
        else:
            print("=" * 80)
            print("❌ La limpieza no se completó correctamente")
            print("=" * 80)
            sys.exit(1)


if __name__ == '__main__':
    main()

"""
Script de Limpieza de Base de Datos (SQL Directo) - QoriCash Trading V2

Este script elimina TODOS los clientes y operaciones usando SQL directo,
evitando problemas con migraciones pendientes.

ADVERTENCIA: Esta acción es IRREVERSIBLE
Los usuarios del sistema (Traders, Operadores, Master) NO se eliminan

Uso:
    python scripts/clean_database_sql.py

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
    print(f"ADVERTENCIA: No se encontró archivo .env en {root_dir}")
    print("Asegúrate de tener configuradas las variables de entorno necesarias")
    print()

import psycopg2
from datetime import datetime


def get_database_connection():
    """Obtener conexión a PostgreSQL"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL no está configurada en las variables de entorno")

    # Convertir postgres:// a postgresql:// si es necesario
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    return psycopg2.connect(database_url)


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


def count_records(conn):
    """Contar registros antes de la limpieza"""
    print("📊 Conteo de registros actuales:")
    print("-" * 80)

    cursor = conn.cursor()
    tables = [
        ('clients', 'Clientes'),
        ('operations', 'Operaciones'),
        ('invoices', 'Facturas'),
        ('reward_codes', 'Códigos de Recompensa'),
        ('client_risk_profiles', 'Perfiles de Riesgo'),
        ('compliance_alerts', 'Alertas de Compliance'),
        ('compliance_documents', 'Documentos de Compliance'),
        ('restrictive_list_checks', 'Verificaciones de Listas'),
        ('transaction_monitoring', 'Monitoreo de Transacciones'),
    ]

    counts = {}
    total = 0

    for table_name, display_name in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            counts[display_name] = count
            print(f"  • {display_name:<35} : {count:>8,} registros")
            total += count
        except Exception as e:
            conn.rollback()  # Rollback para continuar con la siguiente consulta
            counts[display_name] = 0
            print(f"  • {display_name:<35} : {'N/A':>8} (tabla no existe)")

    # Audit logs relacionados
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM audit_logs
            WHERE entity IN ('Client', 'Operation')
        """)
        audit_count = cursor.fetchone()[0]
        counts['Registros de Auditoría'] = audit_count
        print(f"  • {'Registros de Auditoría':<35} : {audit_count:>8,} registros")
        total += audit_count
    except Exception as e:
        conn.rollback()
        counts['Registros de Auditoría'] = 0
        print(f"  • {'Registros de Auditoría':<35} : {'N/A':>8} (tabla no existe)")

    # Compliance audit
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM compliance_audit
            WHERE entity_type IN ('Client', 'Operation')
        """)
        comp_audit_count = cursor.fetchone()[0]
        counts['Auditoría de Compliance'] = comp_audit_count
        print(f"  • {'Auditoría de Compliance':<35} : {comp_audit_count:>8,} registros")
        total += comp_audit_count
    except Exception as e:
        conn.rollback()
        counts['Auditoría de Compliance'] = 0
        print(f"  • {'Auditoría de Compliance':<35} : {'N/A':>8} (tabla no existe)")

    print("-" * 80)
    print(f"  TOTAL DE REGISTROS A ELIMINAR       : {total:>8,}")
    print()

    cursor.close()
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


def clean_database(conn):
    """Ejecutar limpieza de base de datos usando SQL directo"""

    try:
        print("🗑️  Iniciando proceso de limpieza...")
        print("-" * 80)
        print()

        cursor = conn.cursor()
        deleted_counts = {}

        # Orden de eliminación (respetando foreign keys)

        # 1. Compliance Documents
        print("  [1/11] Eliminando Documentos de Compliance...")
        try:
            cursor.execute("DELETE FROM compliance_documents")
            count = cursor.rowcount
            deleted_counts['ComplianceDocument'] = count
            print(f"          ✓ {count} documentos eliminados")
        except Exception as e:
            conn.rollback()
            print(f"          ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['ComplianceDocument'] = 0

        # 2. Compliance Alerts
        print("  [2/11] Eliminando Alertas de Compliance...")
        try:
            cursor.execute("DELETE FROM compliance_alerts")
            count = cursor.rowcount
            deleted_counts['ComplianceAlert'] = count
            print(f"          ✓ {count} alertas eliminadas")
        except Exception as e:
            conn.rollback()
            print(f"          ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['ComplianceAlert'] = 0

        # 3. Transaction Monitoring
        print("  [3/11] Eliminando Monitoreo de Transacciones...")
        try:
            cursor.execute("DELETE FROM transaction_monitoring")
            count = cursor.rowcount
            deleted_counts['TransactionMonitoring'] = count
            print(f"          ✓ {count} registros eliminados")
        except Exception as e:
            conn.rollback()
            print(f"          ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['TransactionMonitoring'] = 0

        # 4. Restrictive List Checks
        print("  [4/11] Eliminando Verificaciones de Listas Restrictivas...")
        try:
            cursor.execute("DELETE FROM restrictive_list_checks")
            count = cursor.rowcount
            deleted_counts['RestrictiveListCheck'] = count
            print(f"          ✓ {count} verificaciones eliminadas")
        except Exception as e:
            conn.rollback()
            print(f"          ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['RestrictiveListCheck'] = 0

        # 5. Client Risk Profiles
        print("  [5/11] Eliminando Perfiles de Riesgo de Clientes...")
        try:
            cursor.execute("DELETE FROM client_risk_profiles")
            count = cursor.rowcount
            deleted_counts['ClientRiskProfile'] = count
            print(f"          ✓ {count} perfiles eliminados")
        except Exception as e:
            conn.rollback()
            print(f"          ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['ClientRiskProfile'] = 0

        # 6. Reward Codes
        print("  [6/11] Eliminando Códigos de Recompensa...")
        try:
            cursor.execute("DELETE FROM reward_codes")
            count = cursor.rowcount
            deleted_counts['RewardCode'] = count
            print(f"          ✓ {count} códigos eliminados")
        except Exception as e:
            conn.rollback()
            print(f"          ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['RewardCode'] = 0

        # 7. Invoices
        print("  [7/11] Eliminando Facturas Electrónicas...")
        try:
            cursor.execute("DELETE FROM invoices")
            count = cursor.rowcount
            deleted_counts['Invoice'] = count
            print(f"          ✓ {count} facturas eliminadas")
        except Exception as e:
            conn.rollback()
            print(f"          ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['Invoice'] = 0

        # 8. Operations
        print("  [8/11] Eliminando Operaciones...")
        cursor.execute("DELETE FROM operations")
        count = cursor.rowcount
        deleted_counts['Operation'] = count
        print(f"          ✓ {count} operaciones eliminadas")

        # 9. Clients
        print("  [9/11] Eliminando Clientes...")
        cursor.execute("DELETE FROM clients")
        count = cursor.rowcount
        deleted_counts['Client'] = count
        print(f"          ✓ {count} clientes eliminados")

        # 10. Compliance Audit
        print("  [10/11] Limpiando Auditoría de Compliance...")
        try:
            cursor.execute("""
                DELETE FROM compliance_audit
                WHERE entity_type IN ('Client', 'Operation')
            """)
            count = cursor.rowcount
            deleted_counts['ComplianceAudit'] = count
            print(f"           ✓ {count} registros de auditoría eliminados")
        except Exception as e:
            conn.rollback()
            print(f"           ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['ComplianceAudit'] = 0

        # 11. Audit Logs
        print("  [11/11] Limpiando Registros de Auditoría...")
        try:
            cursor.execute("""
                DELETE FROM audit_logs
                WHERE entity IN ('Client', 'Operation')
            """)
            count = cursor.rowcount
            deleted_counts['AuditLog'] = count
            print(f"           ✓ {count} registros de auditoría eliminados")
        except Exception as e:
            conn.rollback()
            print(f"           ⚠️ Error (puede que no exista tabla): {str(e)[:50]}")
            deleted_counts['AuditLog'] = 0

        print()
        print("-" * 80)

        # Confirmar cambios
        conn.commit()
        cursor.close()

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
        conn.rollback()
        print("✓ Rollback completado. No se realizaron cambios en la base de datos.")
        print()

        import traceback
        print("Stack trace completo:")
        print(traceback.format_exc())

        return False


def verify_users_intact(conn):
    """Verificar que los usuarios del sistema no fueron afectados"""
    print("🔍 Verificando integridad de usuarios del sistema...")
    print("-" * 80)

    cursor = conn.cursor()
    cursor.execute("SELECT username, role, status FROM users ORDER BY id")
    users = cursor.fetchall()

    print(f"  ✓ Total de usuarios en el sistema: {len(users)}")

    for username, role, status in users:
        print(f"    • {username} ({role}) - {status}")

    cursor.close()
    print()


def main():
    """Función principal"""

    try:
        print_header()

        # Conectar a base de datos
        conn = get_database_connection()
        print("✓ Conexión a base de datos establecida")
        print()

        # Contar registros antes
        count_records(conn)

        # Solicitar confirmación
        if not confirm_deletion():
            conn.close()
            sys.exit(0)

        # Ejecutar limpieza
        success = clean_database(conn)

        if success:
            # Verificar usuarios
            verify_users_intact(conn)

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

            conn.close()
            sys.exit(0)
        else:
            print("=" * 80)
            print("❌ La limpieza no se completó correctamente")
            print("=" * 80)
            conn.close()
            sys.exit(1)

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ ERROR FATAL")
        print("=" * 80)
        print()
        print(f"Error: {str(e)}")
        print()

        import traceback
        print("Stack trace completo:")
        print(traceback.format_exc())

        sys.exit(1)


if __name__ == '__main__':
    main()

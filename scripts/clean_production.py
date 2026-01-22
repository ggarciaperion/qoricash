"""
Script de Limpieza para Producción (Render Shell)

Este script elimina TODOS los clientes y operaciones de PRODUCCIÓN.
Diseñado para ejecutarse directamente en Render Shell.

ADVERTENCIA: Esta acción es IRREVERSIBLE
Los usuarios del sistema NO se eliminan

Uso en Render Shell:
    python scripts/clean_production.py

Autor: Claude Code
Fecha: 2026-01-22
"""

import os
import sys

# Verificar que estamos en producción
if os.environ.get('FLASK_ENV') != 'production':
    print("ERROR: Este script solo debe ejecutarse en producción")
    print(f"FLASK_ENV actual: {os.environ.get('FLASK_ENV')}")
    sys.exit(1)

import psycopg2


def get_database_connection():
    """Obtener conexión a PostgreSQL"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL no configurada")

    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    return psycopg2.connect(database_url)


def clean_database():
    """Ejecutar limpieza de base de datos"""

    print("=" * 80)
    print("LIMPIEZA DE BASE DE DATOS - PRODUCCION")
    print("=" * 80)
    print()

    conn = get_database_connection()
    cursor = conn.cursor()

    try:
        # Contar antes
        print("Contando registros...")
        cursor.execute("SELECT COUNT(*) FROM clients")
        clients_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM operations")
        operations_count = cursor.fetchone()[0]

        print(f"  Clientes: {clients_count}")
        print(f"  Operaciones: {operations_count}")
        print()

        # Limpiar
        print("Iniciando limpieza...")

        # 1. Compliance documents
        try:
            cursor.execute("DELETE FROM compliance_documents")
            print(f"  [1/11] Compliance documents: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [1/11] Compliance documents: N/A")

        # 2. Compliance alerts
        try:
            cursor.execute("DELETE FROM compliance_alerts")
            print(f"  [2/11] Compliance alerts: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [2/11] Compliance alerts: N/A")

        # 3. Transaction monitoring
        try:
            cursor.execute("DELETE FROM transaction_monitoring")
            print(f"  [3/11] Transaction monitoring: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [3/11] Transaction monitoring: N/A")

        # 4. Restrictive list checks
        try:
            cursor.execute("DELETE FROM restrictive_list_checks")
            print(f"  [4/11] Restrictive list checks: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [4/11] Restrictive list checks: N/A")

        # 5. Client risk profiles
        try:
            cursor.execute("DELETE FROM client_risk_profiles")
            print(f"  [5/11] Client risk profiles: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [5/11] Client risk profiles: N/A")

        # 6. Reward codes
        try:
            cursor.execute("DELETE FROM reward_codes")
            print(f"  [6/11] Reward codes: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [6/11] Reward codes: N/A")

        # 7. Invoices
        try:
            cursor.execute("DELETE FROM invoices")
            print(f"  [7/11] Invoices: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [7/11] Invoices: N/A")

        # 8. Operations
        cursor.execute("DELETE FROM operations")
        ops_deleted = cursor.rowcount
        print(f"  [8/11] Operations: {ops_deleted} eliminados")

        # 9. Clients
        cursor.execute("DELETE FROM clients")
        clients_deleted = cursor.rowcount
        print(f"  [9/11] Clients: {clients_deleted} eliminados")

        # 10. Compliance audit
        try:
            cursor.execute("DELETE FROM compliance_audit WHERE entity_type IN ('Client', 'Operation')")
            print(f"  [10/11] Compliance audit: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [10/11] Compliance audit: N/A")

        # 11. Audit logs
        try:
            cursor.execute("DELETE FROM audit_logs WHERE entity IN ('Client', 'Operation')")
            print(f"  [11/11] Audit logs: {cursor.rowcount} eliminados")
        except:
            conn.rollback()
            print(f"  [11/11] Audit logs: N/A")

        # Commit
        conn.commit()

        print()
        print("=" * 80)
        print("LIMPIEZA COMPLETADA")
        print("=" * 80)
        print(f"  Total clientes eliminados: {clients_deleted}")
        print(f"  Total operaciones eliminadas: {ops_deleted}")
        print()

        # Verificar usuarios
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
        print(f"  Usuarios del sistema preservados: {users_count}")
        print()

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        conn.rollback()
        print()
        print("ERROR:", str(e))
        import traceback
        traceback.print_exc()
        cursor.close()
        conn.close()
        return False


if __name__ == '__main__':
    success = clean_database()
    sys.exit(0 if success else 1)

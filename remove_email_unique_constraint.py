#!/usr/bin/env python3
"""
Script para eliminar el constraint UNIQUE del campo email en la tabla clients.
Ejecutar en el shell de Render después del deploy.

Uso:
    python remove_email_unique_constraint.py
"""

import os
import sys
import psycopg2
from psycopg2 import sql

def main():
    # Obtener DATABASE_URL del entorno
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("❌ ERROR: Variable de entorno DATABASE_URL no encontrada")
        sys.exit(1)

    # Render usa postgres://, pero psycopg2 requiere postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print("🔗 Conectando a la base de datos...")

    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        print("✅ Conexión establecida\n")

        # Paso 1: Buscar el nombre del constraint UNIQUE en el campo email
        print("🔍 Buscando constraint UNIQUE en el campo 'email' de la tabla 'clients'...")

        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'clients'
            AND constraint_type = 'UNIQUE'
            AND constraint_name LIKE '%email%';
        """)

        result = cursor.fetchone()

        if result:
            constraint_name = result[0]
            print(f"✅ Constraint encontrado: {constraint_name}\n")

            # Paso 2: Eliminar el constraint
            print(f"🗑️  Eliminando constraint '{constraint_name}'...")

            cursor.execute(sql.SQL(
                "ALTER TABLE clients DROP CONSTRAINT IF EXISTS {}"
            ).format(sql.Identifier(constraint_name)))

            conn.commit()

            print(f"✅ Constraint '{constraint_name}' eliminado exitosamente!\n")

        else:
            # Intentar con nombre genérico por si acaso
            print("⚠️  No se encontró constraint con 'email' en el nombre.")
            print("🔄 Intentando eliminar con nombre genérico 'clients_email_key'...")

            cursor.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS clients_email_key;")
            conn.commit()

            print("✅ Comando ejecutado (si el constraint existía, fue eliminado)\n")

        # Paso 3: Verificar que se eliminó
        print("🔍 Verificando estado actual de la tabla 'clients'...")

        cursor.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'clients';
        """)

        constraints = cursor.fetchall()

        print("\n📋 Constraints actuales en la tabla 'clients':")
        for constraint in constraints:
            print(f"   - {constraint[0]} ({constraint[1]})")

        # Verificar específicamente si existe UNIQUE en email
        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'clients'
            AND constraint_type = 'UNIQUE'
            AND constraint_name LIKE '%email%';
        """)

        if cursor.fetchone():
            print("\n❌ ADVERTENCIA: Aún existe un constraint UNIQUE en el campo email")
        else:
            print("\n✅ ÉXITO: No hay constraint UNIQUE en el campo email")
            print("✅ Ahora se pueden registrar múltiples clientes con el mismo email")

        # Cerrar conexión
        cursor.close()
        conn.close()

        print("\n🎉 Script completado exitosamente!")

    except psycopg2.Error as e:
        print(f"\n❌ ERROR de base de datos: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

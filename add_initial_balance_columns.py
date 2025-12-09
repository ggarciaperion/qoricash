#!/usr/bin/env python
"""
Script para agregar columnas initial_balance_usd e initial_balance_pen
Ejecutar en el shell de Render con: python add_initial_balance_columns.py
"""

from app import create_app
from app.extensions import db
from sqlalchemy import text

def migrate():
    print("🚀 Iniciando migración: agregar columnas initial_balance...")

    app = create_app()

    with app.app_context():
        try:
            # Verificar si las columnas ya existen
            print("📊 Verificando si las columnas existen...")

            with db.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'bank_balances'
                    AND column_name IN ('initial_balance_usd', 'initial_balance_pen')
                """))

                existing_columns = [row[0] for row in result]
                print(f"   Columnas existentes: {existing_columns}")

                if 'initial_balance_usd' in existing_columns and 'initial_balance_pen' in existing_columns:
                    print("✅ Las columnas ya existen. No se necesita migración.")
                    return

                # Agregar columna initial_balance_usd si no existe
                if 'initial_balance_usd' not in existing_columns:
                    print("🔧 Agregando columna initial_balance_usd...")
                    conn.execute(text("""
                        ALTER TABLE bank_balances
                        ADD COLUMN initial_balance_usd NUMERIC(15, 2) NOT NULL DEFAULT 0
                    """))
                    print("   ✓ Columna initial_balance_usd agregada")

                # Agregar columna initial_balance_pen si no existe
                if 'initial_balance_pen' not in existing_columns:
                    print("🔧 Agregando columna initial_balance_pen...")
                    conn.execute(text("""
                        ALTER TABLE bank_balances
                        ADD COLUMN initial_balance_pen NUMERIC(15, 2) NOT NULL DEFAULT 0
                    """))
                    print("   ✓ Columna initial_balance_pen agregada")

                conn.commit()

                # Verificar que se aplicaron
                print("✔️  Verificando cambios...")
                result = conn.execute(text("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'bank_balances'
                    AND column_name IN ('initial_balance_usd', 'initial_balance_pen')
                    ORDER BY column_name
                """))

                print("\n   Columnas agregadas:")
                for row in result:
                    print(f"   - {row[0]}: {row[1]} (default: {row[2]})")

                print("\n✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
                print("   Las columnas initial_balance_usd e initial_balance_pen han sido agregadas.")

        except Exception as e:
            print(f"\n❌ ERROR durante la migración: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    migrate()

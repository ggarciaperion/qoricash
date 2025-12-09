#!/usr/bin/env python
"""
Script para migrar el campo bank_name de 50 a 100 caracteres
Ejecutar en el shell de Render con: python migrate_bank_name.py
"""

from app import create_app
from app.extensions import db
from sqlalchemy import text

def migrate():
    print("🚀 Iniciando migración de bank_name...")

    app = create_app()

    with app.app_context():
        try:
            # Verificar tamaño actual
            print("📊 Verificando tamaño actual del campo bank_name...")
            result = db.engine.execute(text("""
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'bank_balances'
                AND column_name = 'bank_name'
            """))

            current_size = result.fetchone()
            if current_size:
                print(f"   Tamaño actual: {current_size[0]} caracteres")

                if current_size[0] >= 100:
                    print("✅ El campo ya tiene 100 caracteres o más. No se necesita migración.")
                    return

            # Ejecutar la migración
            print("🔧 Ejecutando ALTER TABLE...")
            db.engine.execute(text("""
                ALTER TABLE bank_balances
                ALTER COLUMN bank_name TYPE VARCHAR(100)
            """))

            # Verificar que se aplicó
            print("✔️  Verificando cambio...")
            result = db.engine.execute(text("""
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'bank_balances'
                AND column_name = 'bank_name'
            """))

            new_size = result.fetchone()
            if new_size and new_size[0] == 100:
                print(f"✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
                print(f"   Nuevo tamaño: {new_size[0]} caracteres")
            else:
                print(f"⚠️  Advertencia: Tamaño después de migración: {new_size[0] if new_size else 'No encontrado'}")

        except Exception as e:
            print(f"❌ ERROR durante la migración: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    migrate()

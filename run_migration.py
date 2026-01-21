"""
Script para ejecutar migración de beneficios por referidos
Agrega columnas: referral_pips_earned, referral_pips_available, referral_completed_uses
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db

def run_migration():
    """Ejecutar migración para agregar columnas de beneficios por referidos"""
    app = create_app()

    with app.app_context():
        print("🔧 Iniciando migración de beneficios por referidos...")

        try:
            # Verificar si las columnas ya existen
            result = db.session.execute(db.text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'clients'
                AND column_name IN ('referral_pips_earned', 'referral_pips_available', 'referral_completed_uses')
            """))
            existing_columns = [row[0] for row in result]

            if len(existing_columns) == 3:
                print("✅ Las columnas ya existen. No es necesario migrar.")
                return

            print(f"📊 Columnas existentes: {existing_columns}")
            print("📝 Agregando columnas faltantes...")

            # Agregar columnas si no existen
            if 'referral_pips_earned' not in existing_columns:
                db.session.execute(db.text(
                    "ALTER TABLE clients ADD COLUMN referral_pips_earned FLOAT DEFAULT 0.0"
                ))
                print("✅ Agregada columna: referral_pips_earned")

            if 'referral_pips_available' not in existing_columns:
                db.session.execute(db.text(
                    "ALTER TABLE clients ADD COLUMN referral_pips_available FLOAT DEFAULT 0.0"
                ))
                print("✅ Agregada columna: referral_pips_available")

            if 'referral_completed_uses' not in existing_columns:
                db.session.execute(db.text(
                    "ALTER TABLE clients ADD COLUMN referral_completed_uses INTEGER DEFAULT 0"
                ))
                print("✅ Agregada columna: referral_completed_uses")

            # Actualizar valores NULL a defaults
            db.session.execute(db.text("""
                UPDATE clients
                SET referral_pips_earned = 0.0
                WHERE referral_pips_earned IS NULL
            """))
            db.session.execute(db.text("""
                UPDATE clients
                SET referral_pips_available = 0.0
                WHERE referral_pips_available IS NULL
            """))
            db.session.execute(db.text("""
                UPDATE clients
                SET referral_completed_uses = 0
                WHERE referral_completed_uses IS NULL
            """))

            # Commit cambios
            db.session.commit()

            print("✅ Migración completada exitosamente!")
            print("📊 Todas las columnas han sido agregadas y valores inicializados.")

        except Exception as e:
            print(f"❌ Error durante la migración: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    run_migration()

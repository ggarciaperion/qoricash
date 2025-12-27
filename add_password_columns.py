"""
Script para agregar columnas de autenticación a la tabla clients
Ejecutar desde Render Shell: python add_password_columns.py
"""
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        try:
            print("🔍 Verificando columnas existentes...")

            # Verificar si las columnas ya existen
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='clients' AND column_name IN ('password_hash', 'requires_password_change')
            """))
            existing_columns = [row[0] for row in result]

            print(f"Columnas encontradas: {existing_columns}")

            # Agregar password_hash si no existe
            if 'password_hash' not in existing_columns:
                print("\n📝 Agregando columna password_hash...")
                conn.execute(text("ALTER TABLE clients ADD COLUMN password_hash VARCHAR(200)"))
                conn.commit()
                print("✅ Columna password_hash agregada exitosamente")
            else:
                print("\n⚠️  Columna password_hash ya existe - omitiendo")

            # Agregar requires_password_change si no existe
            if 'requires_password_change' not in existing_columns:
                print("\n📝 Agregando columna requires_password_change...")
                conn.execute(text("ALTER TABLE clients ADD COLUMN requires_password_change BOOLEAN DEFAULT true"))
                conn.commit()
                print("✅ Columna requires_password_change agregada exitosamente")
            else:
                print("\n⚠️  Columna requires_password_change ya existe - omitiendo")

            print("\n" + "="*60)
            print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
            print("="*60)
            print("\n📊 Verificando estructura final de la tabla clients...")

            # Verificar las columnas finales
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name='clients' AND column_name IN ('password_hash', 'requires_password_change')
                ORDER BY column_name
            """))

            print("\nColumnas de autenticación en tabla clients:")
            for row in result:
                print(f"  - {row[0]}: {row[1]} (nullable: {row[2]})")

            print("\n🎉 El sistema de autenticación está listo para usar")

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            conn.rollback()
            raise

"""
Script para agregar columnas base_rate y pips a la tabla operations
Ejecutar desde Render Shell: python add_base_rate_pips.py
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
                WHERE table_name='operations' AND column_name IN ('base_rate', 'pips')
            """))
            existing_columns = [row[0] for row in result]

            print(f"Columnas encontradas: {existing_columns}")

            # Agregar base_rate si no existe
            if 'base_rate' not in existing_columns:
                print("\n📝 Agregando columna base_rate...")
                conn.execute(text("ALTER TABLE operations ADD COLUMN base_rate NUMERIC(10, 4)"))
                conn.commit()
                print("✅ Columna base_rate agregada exitosamente")
            else:
                print("\n⚠️  Columna base_rate ya existe - omitiendo")

            # Agregar pips si no existe
            if 'pips' not in existing_columns:
                print("\n📝 Agregando columna pips...")
                conn.execute(text("ALTER TABLE operations ADD COLUMN pips NUMERIC(8, 1)"))
                conn.commit()
                print("✅ Columna pips agregada exitosamente")
            else:
                print("\n⚠️  Columna pips ya existe - omitiendo")

            print("\n" + "="*60)
            print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
            print("="*60)
            print("\n📊 Verificando estructura final de la tabla operations...")

            # Verificar las columnas finales
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name='operations' AND column_name IN ('base_rate', 'pips')
                ORDER BY column_name
            """))

            print("\nColumnas de base/pips en tabla operations:")
            for row in result:
                print(f"  - {row[0]}: {row[1]} (nullable: {row[2]})")

            print("\n🎉 Los campos Base y Pips están listos para usar")

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            conn.rollback()
            raise

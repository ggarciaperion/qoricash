"""
Script para crear tabla exchange_rates en producción
Ejecutar desde Render Shell: python create_exchange_rates_db.py
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Importar después de cargar .env
from app import create_app
from app.extensions import db
from app.models.exchange_rate import ExchangeRate
from app.models.user import User

def create_exchange_rates_table():
    """Crear tabla exchange_rates y poblar con valores iniciales"""
    app = create_app()

    with app.app_context():
        try:
            # Crear todas las tablas (solo creará las que no existen)
            print("📋 Creando tabla exchange_rates...")
            db.create_all()
            print("✅ Tabla creada exitosamente")

            # Verificar si ya existen registros
            existing = ExchangeRate.query.first()
            if existing:
                print(f"⚠️  Ya existe un registro de tipos de cambio: Compra={existing.buy_rate}, Venta={existing.sell_rate}")
                return

            # Buscar usuario Master para el registro inicial
            master_user = User.query.filter_by(role='Master').first()

            if not master_user:
                print("⚠️  No se encontró usuario Master, usando primer usuario...")
                master_user = User.query.first()

            if not master_user:
                print("❌ No hay usuarios en la base de datos. Cree un usuario primero.")
                return

            # Crear registro inicial con tipos de cambio por defecto
            print(f"📝 Creando registro inicial con usuario: {master_user.username}")
            initial_rate = ExchangeRate(
                buy_rate=3.7500,
                sell_rate=3.7700,
                updated_by=master_user.id
            )

            db.session.add(initial_rate)
            db.session.commit()

            print(f"✅ Registro inicial creado exitosamente:")
            print(f"   - Compra: S/ {initial_rate.buy_rate}")
            print(f"   - Venta: S/ {initial_rate.sell_rate}")
            print(f"   - Actualizado por: {master_user.username}")
            print(f"   - Fecha: {initial_rate.updated_at}")

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    create_exchange_rates_table()

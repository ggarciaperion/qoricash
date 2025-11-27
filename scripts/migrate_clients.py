"""
Script de migración para actualizar tabla clients
Ejecutar con: python scripts/migrate_clients.py
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.client import Client
from sqlalchemy import text

def migrate_clients():
    """Migrar tabla clients con nuevos campos"""
    
    app = create_app()
    
    with app.app_context():
        print("🔄 Iniciando migración de tabla clients...")
        
        try:
            # Verificar si las columnas ya existen
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('clients')]
            
            print(f"📋 Columnas existentes: {len(existing_columns)}")
            
            # Lista de nuevas columnas a agregar
            new_columns = {
                'document_type': "VARCHAR(10) DEFAULT 'DNI' NOT NULL",
                'apellido_paterno': "VARCHAR(100)",
                'apellido_materno': "VARCHAR(100)",
                'nombres': "VARCHAR(100)",
                'razon_social': "VARCHAR(200)",
                'persona_contacto': "VARCHAR(200)",
                'dni_representante_front_url': "VARCHAR(500)",
                'dni_representante_back_url': "VARCHAR(500)",
                'ficha_ruc_url': "VARCHAR(500)",
                'direccion': "VARCHAR(300)",
                'distrito': "VARCHAR(100)",
                'provincia': "VARCHAR(100)",
                'departamento': "VARCHAR(100)",
                'origen': "VARCHAR(20)",
                'account_type': "VARCHAR(20)",
                'currency': "VARCHAR(10)",
                'bank_account_number': "VARCHAR(100)",
                'created_by': "INTEGER REFERENCES users(id)"
            }
            
            # Agregar nuevas columnas si no existen
            for column_name, column_def in new_columns.items():
                if column_name not in existing_columns:
                    try:
                        sql = f"ALTER TABLE clients ADD COLUMN {column_name} {column_def}"
                        db.session.execute(text(sql))
                        print(f"✅ Columna '{column_name}' agregada")
                    except Exception as e:
                        print(f"⚠️  Error al agregar '{column_name}': {str(e)}")
            
            db.session.commit()
            
            # Migrar datos existentes
            print("\n🔄 Migrando datos existentes...")
            
            clients = Client.query.all()
            for client in clients:
                # Si tiene 'name', dividirlo en apellidos y nombres
                if hasattr(client, 'name') and client.name and not client.nombres:
                    parts = client.name.strip().split()
                    if len(parts) >= 3:
                        client.apellido_paterno = parts[0]
                        client.apellido_materno = parts[1]
                        client.nombres = ' '.join(parts[2:])
                    elif len(parts) == 2:
                        client.apellido_paterno = parts[0]
                        client.nombres = parts[1]
                    else:
                        client.nombres = client.name
                
                # Validar longitud de DNI para asignar tipo
                if not client.document_type:
                    if len(client.dni) == 8:
                        client.document_type = 'DNI'
                    elif len(client.dni) == 11:
                        client.document_type = 'RUC'
                        client.razon_social = client.full_name if hasattr(client, 'full_name') else 'Sin razón social'
                    else:
                        client.document_type = 'CE'
                
                # Cambiar estado por defecto a Inactivo si no está especificado
                if client.status == 'Activo':
                    pass  # Mantener activos
                else:
                    client.status = 'Inactivo'
            
            db.session.commit()
            print(f"✅ {len(clients)} clientes migrados")
            
            # Agregar constraints
            print("\n🔒 Agregando constraints...")
            
            try:
                # Check constraint para document_type
                db.session.execute(text("""
                    ALTER TABLE clients 
                    DROP CONSTRAINT IF EXISTS check_document_type;
                """))
                db.session.execute(text("""
                    ALTER TABLE clients 
                    ADD CONSTRAINT check_document_type 
                    CHECK (document_type IN ('DNI', 'CE', 'RUC'));
                """))
                print("✅ Constraint check_document_type agregado")
            except Exception as e:
                print(f"⚠️  Error al agregar constraint: {str(e)}")
            
            db.session.commit()
            
            # Intentar eliminar columna 'name' antigua si existe
            try:
                if 'name' in existing_columns:
                    db.session.execute(text("ALTER TABLE clients DROP COLUMN IF EXISTS name"))
                    db.session.commit()
                    print("✅ Columna 'name' antigua eliminada")
            except Exception as e:
                print(f"⚠️  No se pudo eliminar columna 'name': {str(e)}")
            
            print("\n✅ ¡Migración completada exitosamente!")
            print("\n📊 Resumen:")
            print(f"   - Total clientes: {Client.query.count()}")
            print(f"   - Clientes activos: {Client.query.filter_by(status='Activo').count()}")
            print(f"   - Clientes inactivos: {Client.query.filter_by(status='Inactivo').count()}")
            print(f"   - DNI: {Client.query.filter_by(document_type='DNI').count()}")
            print(f"   - CE: {Client.query.filter_by(document_type='CE').count()}")
            print(f"   - RUC: {Client.query.filter_by(document_type='RUC').count()}")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error durante la migración: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        return True


if __name__ == '__main__':
    print("=" * 60)
    print("MIGRACIÓN DE TABLA CLIENTS - QORICASH TRADING V2")
    print("=" * 60)
    print()
    
    success = migrate_clients()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ MIGRACIÓN COMPLETADA CON ÉXITO")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ MIGRACIÓN FALLÓ - Revisar errores arriba")
        print("=" * 60)
        sys.exit(1)

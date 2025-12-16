#!/usr/bin/env python
"""
Script para crear la tabla invoices manualmente
Ejecutar: python create_invoices_table.py
"""
from run import app
from app.extensions import db
from sqlalchemy import text

def create_invoices_table():
    """Crear tabla invoices manualmente"""
    with app.app_context():
        try:
            print("=" * 60)
            print("CREANDO TABLA INVOICES")
            print("=" * 60)

            # SQL para crear la tabla
            create_table_sql = text("""
            CREATE TABLE invoices (
                id SERIAL PRIMARY KEY,
                operation_id INTEGER NOT NULL REFERENCES operations(id),
                client_id INTEGER NOT NULL REFERENCES clients(id),
                invoice_type VARCHAR(20) NOT NULL,
                serie VARCHAR(10),
                numero VARCHAR(20),
                invoice_number VARCHAR(50),
                emisor_ruc VARCHAR(11) NOT NULL,
                emisor_razon_social VARCHAR(200) NOT NULL,
                emisor_direccion VARCHAR(300),
                cliente_tipo_documento VARCHAR(10),
                cliente_numero_documento VARCHAR(20) NOT NULL,
                cliente_denominacion VARCHAR(200) NOT NULL,
                cliente_direccion VARCHAR(300),
                cliente_email VARCHAR(120),
                descripcion TEXT,
                monto_total NUMERIC(15, 2) NOT NULL,
                moneda VARCHAR(10) DEFAULT 'PEN',
                gravada NUMERIC(15, 2) DEFAULT 0,
                exonerada NUMERIC(15, 2) DEFAULT 0,
                igv NUMERIC(15, 2) DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'Pendiente',
                nubefact_response TEXT,
                nubefact_enlace_pdf VARCHAR(500),
                nubefact_enlace_xml VARCHAR(500),
                nubefact_aceptada_por_sunat BOOLEAN DEFAULT false,
                nubefact_sunat_description TEXT,
                nubefact_sunat_note TEXT,
                nubefact_codigo_hash VARCHAR(200),
                error_message TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP,
                sent_at TIMESTAMP,
                accepted_at TIMESTAMP
            );
            """)

            # Crear índices
            create_indexes_sql = [
                text("CREATE INDEX ix_invoices_operation_id ON invoices(operation_id);"),
                text("CREATE INDEX ix_invoices_client_id ON invoices(client_id);"),
                text("CREATE INDEX ix_invoices_invoice_number ON invoices(invoice_number);"),
                text("CREATE INDEX ix_invoices_status ON invoices(status);"),
                text("CREATE INDEX ix_invoices_created_at ON invoices(created_at);")
            ]

            # Actualizar versión de Alembic
            update_alembic_sql = text("""
            UPDATE alembic_version SET version_num = '20251216_invoices';
            """)

            # Ejecutar comandos
            with db.engine.connect() as conn:
                print("\n1. Creando tabla invoices...")
                conn.execute(create_table_sql)
                conn.commit()
                print("   ✓ Tabla creada")

                print("\n2. Creando índices...")
                for idx, index_sql in enumerate(create_indexes_sql, 1):
                    conn.execute(index_sql)
                    print(f"   ✓ Índice {idx}/5 creado")
                conn.commit()

                print("\n3. Actualizando versión de Alembic...")
                conn.execute(update_alembic_sql)
                conn.commit()
                print("   ✓ Versión actualizada")

            print("\n" + "=" * 60)
            print("✅ TABLA INVOICES CREADA EXITOSAMENTE")
            print("=" * 60)
            return True

        except Exception as e:
            print(f"\n❌ Error al crear tabla: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    create_invoices_table()

#!/usr/bin/env python
"""
Script para crear la tabla complaints directamente en PostgreSQL
Uso: python create_complaints_table.py
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no está configurada")
    exit(1)

print("🚀 Creando tabla complaints...")

engine = create_engine(DATABASE_URL)

sql = """
CREATE TABLE IF NOT EXISTS complaints (
    id SERIAL PRIMARY KEY,
    complaint_number VARCHAR(20) UNIQUE NOT NULL,
    document_type VARCHAR(10) NOT NULL CHECK (document_type IN ('DNI', 'CE', 'RUC')),
    document_number VARCHAR(20) NOT NULL,
    full_name VARCHAR(300),
    company_name VARCHAR(300),
    contact_person VARCHAR(300),
    email VARCHAR(120) NOT NULL,
    phone VARCHAR(100) NOT NULL,
    address VARCHAR(500),
    complaint_type VARCHAR(20) NOT NULL DEFAULT 'Reclamo' CHECK (complaint_type IN ('Reclamo', 'Queja')),
    detail TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pendiente' CHECK (status IN ('Pendiente', 'En Revisión', 'Resuelto')),
    response TEXT,
    evidence_image_url TEXT,
    resolution_image_url TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_complaints_complaint_number ON complaints(complaint_number);
CREATE INDEX IF NOT EXISTS ix_complaints_document_number ON complaints(document_number);
CREATE INDEX IF NOT EXISTS ix_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS ix_complaints_created_at ON complaints(created_at);

INSERT INTO alembic_version (version_num) VALUES ('20260126_complaints') ON CONFLICT (version_num) DO NOTHING;
"""

try:
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
        print("✅ Tabla complaints creada exitosamente")
        print("✅ Migración registrada en alembic_version")
except Exception as e:
    print(f"❌ ERROR: {e}")
    exit(1)

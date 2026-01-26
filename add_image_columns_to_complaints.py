#!/usr/bin/env python
"""
Script para agregar columnas de imágenes a la tabla complaints
Uso: python add_image_columns_to_complaints.py
"""
import os
from sqlalchemy import create_engine, text, inspect

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no está configurada")
    exit(1)

print("🚀 Agregando columnas de imágenes a tabla complaints...")

engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

try:
    # Verificar si la tabla existe
    if 'complaints' not in inspector.get_table_names():
        print("❌ ERROR: La tabla complaints no existe. Ejecuta create_complaints_table.py primero.")
        exit(1)

    # Obtener columnas existentes
    existing_columns = [col['name'] for col in inspector.get_columns('complaints')]
    print(f"📋 Columnas existentes: {', '.join(existing_columns)}")

    columns_to_add = []

    if 'evidence_image_url' not in existing_columns:
        columns_to_add.append('evidence_image_url')

    if 'resolution_image_url' not in existing_columns:
        columns_to_add.append('resolution_image_url')

    if not columns_to_add:
        print("✅ Las columnas de imágenes ya existen en la tabla")
        exit(0)

    print(f"➕ Agregando columnas: {', '.join(columns_to_add)}")

    with engine.connect() as conn:
        for column in columns_to_add:
            sql = f"ALTER TABLE complaints ADD COLUMN IF NOT EXISTS {column} TEXT;"
            conn.execute(text(sql))
            print(f"  ✓ Columna {column} agregada")

        conn.commit()

    print("✅ Columnas de imágenes agregadas exitosamente")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

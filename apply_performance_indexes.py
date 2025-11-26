"""
Script para aplicar indices de performance a la base de datos
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL no encontrada")
    exit(1)

# Fix para Heroku/Render
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

print("Conectando a la base de datos...")
engine = create_engine(DATABASE_URL)

# Leer script SQL con codificacion UTF-8
with open('add_performance_indexes.sql', 'r', encoding='utf-8') as f:
    sql_script = f.read()

# Separar por queries
queries = [q.strip() for q in sql_script.split(';') if q.strip() and not q.strip().startswith('SELECT')]

print(f"Aplicando {len(queries)} indices...")

with engine.connect() as conn:
    for i, query in enumerate(queries, 1):
        try:
            conn.execute(text(query))
            conn.commit()
            if 'CREATE INDEX' in query:
                index_name = query.split('idx_')[1].split(' ')[0] if 'idx_' in query else f"index_{i}"
                print(f"  OK [{i}/{len(queries)}] idx_{index_name}")
        except Exception as e:
            error_msg = str(e)
            if 'already exists' in error_msg:
                print(f"  SKIP [{i}/{len(queries)}] Ya existe")
            else:
                print(f"  WARN [{i}/{len(queries)}] {error_msg[:80]}")

print("\nIndices aplicados exitosamente")

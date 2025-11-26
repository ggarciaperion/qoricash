"""
Script para aplicar índices de performance a la base de datos
Ejecutar una sola vez para mejorar velocidad del dashboard
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no encontrada")
    exit(1)

# Fix para Heroku/Render postgresql:// -> postgreschql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

print(f"🔗 Conectando a la base de datos...")
engine = create_engine(DATABASE_URL)

# Leer script SQL
with open('add_performance_indexes.sql', 'r') as f:
    sql_script = f.read()

# Separar por queries (ignorar el SELECT final)
queries = [q.strip() for q in sql_script.split(';') if q.strip() and not q.strip().startswith('SELECT')]

print(f"📋 Aplicando {len(queries)} índices...")

with engine.connect() as conn:
    for i, query in enumerate(queries, 1):
        try:
            conn.execute(text(query))
            conn.commit()
            # Extraer nombre del índice para mostrar
            if 'CREATE INDEX' in query:
                index_name = query.split('idx_')[1].split(' ')[0] if 'idx_' in query else f"index_{i}"
                print(f"  ✅ [{i}/{len(queries)}] idx_{index_name}")
        except Exception as e:
            print(f"  ⚠️  [{i}/{len(queries)}] Error: {str(e)[:100]}")

print("\n✅ Índices aplicados exitosamente")
print("🚀 El dashboard debería ser significativamente más rápido ahora")

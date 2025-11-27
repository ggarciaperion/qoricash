#!/usr/bin/env python
"""
scripts/add_bank_accounts_column.py

Crea la columna bank_accounts_json en la tabla clients si no existe.
Idempotente y minimal: usa SQL directo via SQLAlchemy engine. Ejecutar
con el virtualenv del proyecto activado.
"""
import os
import sys
from sqlalchemy import create_engine, text

# Cargar .env si existe (opcional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

db_url = os.environ.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')
if not db_url:
    sys.stderr.write("ERROR: SQLALCHEMY_DATABASE_URI o DATABASE_URL no definido en el entorno.\n")
    sys.exit(2)

engine = create_engine(db_url)

sql = "ALTER TABLE clients ADD COLUMN IF NOT EXISTS bank_accounts_json TEXT;"

print("Conectando a la BD y ejecutando ALTER TABLE IF NOT EXISTS ...")
with engine.connect() as conn:
    trans = conn.begin()
    try:
        conn.execute(text(sql))
        trans.commit()
        print("✅ Columna bank_accounts_json creada o ya existente.")
    except Exception as e:
        trans.rollback()
        sys.stderr.write(f"ERROR al crear la columna bank_accounts_json: {e}\n")
        sys.exit(3)
"""
Cambia EXP-1068 de 'Cancelado' → 'Completada' directamente en la base de datos.

Uso (en Render Shell):
    python3 completar_exp1068.py
"""
import os, sys

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: Define DATABASE_URL en el entorno")
    sys.exit(1)

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

from sqlalchemy import create_engine, text
from datetime import datetime
import pytz

engine = create_engine(DATABASE_URL)

OPERATION_ID = 'EXP-1068'

def now_peru():
    peru_tz = pytz.timezone('America/Lima')
    return datetime.now(pytz.utc).astimezone(peru_tz).replace(tzinfo=None)

with engine.begin() as conn:
    row = conn.execute(text(
        "SELECT id, operation_id, status, amount_usd, amount_pen FROM operations WHERE operation_id = :oid"
    ), {'oid': OPERATION_ID}).fetchone()

    if not row:
        print(f"ERROR: No se encontro la operacion {OPERATION_ID}")
        sys.exit(1)

    op_db_id = row[0]
    print(f"Operacion encontrada -> id={op_db_id}  codigo={row[1]}  estado={row[2]}  USD={row[3]}  PEN={row[4]}")

    if row[2] == 'Completada':
        print("La operacion ya esta como Completada, no se modifica.")
        sys.exit(0)

    now = now_peru()

    conn.execute(text("""
        UPDATE operations
        SET status       = 'Completada',
            completed_at = :now,
            updated_at   = :now
        WHERE id = :id
    """), {'now': now, 'id': op_db_id})

    print(f"")
    print(f"EXITO: Operacion {OPERATION_ID} marcada como Completada.")
    print(f"   completed_at = {now}")

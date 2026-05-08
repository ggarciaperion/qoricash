"""
Elimina operaciones de prueba en estado Cancelado de hoy
para el cliente Garcia Vilca Gian Pierre Andres.

Uso (en Render Shell):
    python3 delete_test_operations.py
"""
import os, sys
from datetime import date

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: Define DATABASE_URL en el entorno")
    sys.exit(1)

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL)

TODAY = date.today()

FIND_SQL = """
SELECT o.id, o.operation_id, o.status, o.created_at, c.nombres, c.apellido_paterno, c.apellido_materno
FROM operations o
JOIN clients c ON o.client_id = c.id
WHERE DATE(o.created_at AT TIME ZONE 'America/Lima') = :today
  AND o.status = 'Cancelado'
  AND LOWER(c.apellido_paterno) LIKE '%garcia%'
  AND LOWER(c.apellido_materno) LIKE '%vilca%'
ORDER BY o.created_at;
"""

DELETE_SQL = """
DELETE FROM operations
WHERE id IN (
    SELECT o.id
    FROM operations o
    JOIN clients c ON o.client_id = c.id
    WHERE DATE(o.created_at AT TIME ZONE 'America/Lima') = :today
      AND o.status = 'Cancelado'
      AND LOWER(c.apellido_paterno) LIKE '%garcia%'
      AND LOWER(c.apellido_materno) LIKE '%vilca%'
);
"""

with engine.connect() as conn:
    rows = conn.execute(text(FIND_SQL), {'today': TODAY}).fetchall()

    if not rows:
        print("No se encontraron operaciones que coincidan. Nada que eliminar.")
        sys.exit(0)

    print(f"\nOperaciones encontradas ({len(rows)}):")
    print("-" * 70)
    for r in rows:
        print(f"  ID={r[0]}  |  {r[1]}  |  {r[2]}  |  {r[3]}  |  {r[4]} {r[5]} {r[6]}")
    print("-" * 70)

    confirm = input(f"\nEliminar estas {len(rows)} operacion(es)? [s/N]: ").strip().lower()
    if confirm != 's':
        print("Cancelado. No se eliminó nada.")
        sys.exit(0)

    result = conn.execute(text(DELETE_SQL), {'today': TODAY})
    conn.commit()
    print(f"\nEliminadas {result.rowcount} operacion(es). Listo.")

import os
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
conn.autocommit = True
cur = conn.cursor()

cur.execute('ALTER TABLE bank_balances DROP CONSTRAINT IF EXISTS check_balance_usd_positive')
cur.execute('ALTER TABLE bank_balances DROP CONSTRAINT IF EXISTS check_balance_pen_positive')

cur.execute(
    "SELECT constraint_name FROM information_schema.table_constraints "
    "WHERE table_name='bank_balances' AND constraint_type='CHECK'"
)
restantes = cur.fetchall()
conn.close()

if restantes:
    print(f"ADVERTENCIA: constraints restantes: {restantes}")
else:
    print("OK: constraints eliminados. Puedes correr reparar_bank_movements.py --apply")

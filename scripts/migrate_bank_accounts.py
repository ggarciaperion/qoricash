"""
scripts/migrate_bank_accounts.py
Migra cuentas bancarias existentes a la columna bank_accounts_json (JSON string).
Ejecutar con el virtualenv del proyecto activo.
"""
import os
import json
import sys

# cargar .env si existe (opcional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DB = os.environ.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')
if not DB:
    sys.stderr.write("ERROR: define SQLALCHEMY_DATABASE_URI o DATABASE_URL en el entorno.\n")
    sys.exit(2)

# Import app factory y modelos dentro de contexto app
from app import create_app
from app.extensions import db
from app.models.client import Client

def migrate():
    app = create_app()
    with app.app_context():
        count = 0
        clients = Client.query.all()
        for client in clients:
            # Evitar sobreescribir si ya existe valor
            existing = getattr(client, 'bank_accounts_json', None)
            if existing:
                continue
            # Si no hay datos bancarios legacy, saltar
            if not getattr(client, 'bank_name', None) and not getattr(client, 'bank_account_number', None) and not getattr(client, 'bank_account', None):
                continue
            account = {
                'origen': getattr(client, 'origen', '') or getattr(client, 'bank_origin', '') or '',
                'bank_name': getattr(client, 'bank_name', '') or '',
                'account_type': getattr(client, 'account_type', '') or '',
                'currency': getattr(client, 'currency', '') or '',
                # intentar varios nombres posibles del campo de número
                'account_number': getattr(client, 'bank_account_number', None) or getattr(client, 'bank_account', None) or ''
            }
            client.bank_accounts_json = json.dumps([account], ensure_ascii=False)
            count += 1
        db.session.commit()
        print(f"✅ Migrados: {count} clientes (bank_accounts_json poblado)")
    return 0

if __name__ == '__main__':
    sys.exit(migrate())
"""
Fix puntual: resetea rol y password del usuario demo_trader.

Uso en Render Shell:
    python fix_demo_trader_role.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

DEMO_DNI      = '12345678'
DEMO_USERNAME = 'demo_trader'
NEW_PASSWORD  = 'Demo@Trader2026'

def run():
    app = create_app()
    with app.app_context():
        user = User.query.filter(
            (User.username == DEMO_USERNAME) | (User.dni == DEMO_DNI)
        ).first()

        if not user:
            print('ERROR: No se encontró el usuario demo_trader.')
            return

        user.role          = 'Trader'
        user.status        = 'Activo'
        user.username      = DEMO_USERNAME
        user.password_hash = generate_password_hash(NEW_PASSWORD, method='pbkdf2:sha256')
        db.session.commit()

        print('✓ Usuario demo actualizado:')
        print(f'  DNI      : {user.dni}')
        print(f'  Username : {user.username}')
        print(f'  Rol      : {user.role}')
        print(f'  Password : {NEW_PASSWORD}')

if __name__ == '__main__':
    run()

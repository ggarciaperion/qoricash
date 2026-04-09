"""
Seed local — inicializa usuarios necesarios para pruebas con Expo Go.
Solo afecta la BD local (SQLite). No toca producción.

Uso: python3 seed_local.py
"""
import os
os.environ.setdefault('FLASK_ENV', 'development')

# Parchear eventlet antes de todo
import eventlet
eventlet.monkey_patch()

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

def set_password_compat(user, password):
    """Usa pbkdf2:sha256 compatible con Python 3.9 en macOS (sin scrypt)."""
    user.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

app = create_app()

with app.app_context():
    db.create_all()

    usuarios = [
        # Usuario admin/master para el panel web local
        {
            'username': 'admin',
            'email': 'admin@qoricash.pe',
            'dni': '00000001',
            'role': 'Master',
            'status': 'Activo',
            'password': 'admin123',
        },
        # Usuario App Móvil (necesario para registrar clientes desde el app)
        {
            'username': 'app_movil',
            'email': 'app@qoricash.pe',
            'dni': '99999999',
            'role': 'App',
            'status': 'Activo',
            'password': 'app123',
        },
        # Usuario plataforma web
        {
            'username': 'plataforma',
            'email': 'plataforma@qoricash.pe',
            'dni': '99999998',
            'role': 'Web',
            'status': 'Activo',
            'password': 'plataforma123',
        },
    ]

    creados = 0
    for u in usuarios:
        existing = User.query.filter(
            (User.email == u['email']) | (User.username == u['username'])
        ).first()
        if existing:
            print(f'  ✓ Ya existe: {u["username"]} ({u["role"]})')
            continue
        user = User(
            username=u['username'],
            email=u['email'],
            dni=u['dni'],
            role=u['role'],
            status=u['status'],
        )
        set_password_compat(user, u['password'])
        db.session.add(user)
        creados += 1
        print(f'  + Creado: {u["username"]} ({u["role"]}) — pass: {u["password"]}')

    db.session.commit()
    print(f'\n✅ Seed completo — {creados} usuario(s) creado(s)')
    print('\nCredenciales para el panel web local (http://172.20.10.5:5001):')
    print('  Usuario: admin    Contraseña: admin123')
    print('\nEl app móvil ya puede registrar clientes vía Expo Go.')

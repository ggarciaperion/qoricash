"""
Diagnóstico de Web Push — correr en Render Shell:
    python3 debug_push.py
"""
import os, sys
os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("\n=== VAPID Keys ===")
    priv = os.environ.get('VAPID_PRIVATE_KEY', '')
    pub  = os.environ.get('VAPID_PUBLIC_KEY', '')
    sub  = os.environ.get('VAPID_CLAIMS_SUB', '')
    print(f"  VAPID_PRIVATE_KEY : {'✓ configurada (' + str(len(priv)) + ' chars)' if priv else '✗ NO CONFIGURADA'}")
    print(f"  VAPID_PUBLIC_KEY  : {'✓ ' + pub[:30] + '...' if pub else '✗ NO CONFIGURADA'}")
    print(f"  VAPID_CLAIMS_SUB  : {sub or '✗ vacía'}")

    print("\n=== Tabla push_subscriptions ===")
    try:
        rows = db.session.execute(text(
            "SELECT ps.id, u.username, u.role, LEFT(ps.endpoint,50) as ep, ps.created_at "
            "FROM push_subscriptions ps JOIN users u ON u.id = ps.user_id "
            "ORDER BY ps.created_at DESC"
        )).fetchall()
        if rows:
            for r in rows:
                print(f"  id={r.id}  user={r.username}({r.role})  ep={r.ep}...  at={r.created_at}")
        else:
            print("  ✗ Sin suscripciones — el cliente nunca completó el registro")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n=== Exchange Rates actuales ===")
    try:
        r = db.session.execute(text(
            "SELECT buy_rate, sell_rate, updated_at FROM exchange_rates ORDER BY updated_at DESC LIMIT 1"
        )).fetchone()
        if r:
            print(f"  Compra={r.buy_rate}  Venta={r.sell_rate}  at={r.updated_at}")
        else:
            print("  Sin datos")
    except Exception as e:
        print(f"  Error: {e}")

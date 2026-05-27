"""
Prueba de envío real de Web Push — correr en Render Shell:
    python3 test_push_send.py
"""
import os, sys, json, traceback
os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY  = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS_SUB  = os.environ.get('VAPID_CLAIMS_SUB', 'mailto:gerencia@qoricash.pe')

with app.app_context():
    rows = db.session.execute(text(
        "SELECT id, endpoint, p256dh, auth FROM push_subscriptions ORDER BY id DESC"
    )).fetchall()

    if not rows:
        print("✗ No hay suscripciones en la BD")
        sys.exit(1)

    print(f"Intentando enviar a {len(rows)} suscripcion(es)...\n")

    for row in rows:
        sub_info = {
            'endpoint': row.endpoint,
            'keys': {'p256dh': row.p256dh, 'auth': row.auth},
        }
        payload = json.dumps({
            'title': 'QoriCash — Prueba',
            'body': 'Notificación de prueba OK',
            'type': 'info',
            'tag': 'test-push',
        })

        print(f"  Sub id={row.id}  endpoint={row.endpoint[:60]}...")
        try:
            from pywebpush import webpush, WebPushException
            webpush(
                subscription_info=sub_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={'sub': VAPID_CLAIMS_SUB},
                ttl=3600,
            )
            print(f"  ✓ Enviado correctamente")
        except WebPushException as e:
            print(f"  ✗ WebPushException: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"     HTTP status : {e.response.status_code}")
                print(f"     Body        : {e.response.text[:400]}")
        except Exception as e:
            print(f"  ✗ Error inesperado: {type(e).__name__}: {e}")
            traceback.print_exc()
        print()

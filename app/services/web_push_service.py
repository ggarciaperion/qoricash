"""
Servicio de Web Push Notifications — QoriCash
Envía notificaciones push al browser usando el protocolo Web Push (VAPID).
Funciona aunque la pestaña esté cerrada o la pantalla bloqueada.

Variables de entorno necesarias en Render:
  VAPID_PRIVATE_KEY  — clave privada EC en formato PEM
  VAPID_PUBLIC_KEY   — clave pública EC en base64url (sin padding)
  VAPID_CLAIMS_SUB   — "mailto:gerencia@qoricash.pe" (contacto VAPID)

Para generar las claves: python3 generate_vapid_keys.py
"""
import json
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY  = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS_SUB  = os.environ.get('VAPID_CLAIMS_SUB', 'mailto:gerencia@qoricash.pe')


def is_configured() -> bool:
    return bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY)


def get_vapid_public_key() -> str:
    return VAPID_PUBLIC_KEY


def _send_one(sub_info: dict, payload: dict):
    """Envía un push a una suscripción. Lanza WebPushException si falla."""
    from pywebpush import webpush
    webpush(
        subscription_info=sub_info,
        data=json.dumps(payload, ensure_ascii=False),
        vapid_private_key=VAPID_PRIVATE_KEY,
        vapid_claims={'sub': VAPID_CLAIMS_SUB},
        ttl=86400,
    )


def send_to_users(user_ids: List[int], payload: dict) -> int:
    """
    Envía web push a todos los dispositivos suscritos de los usuarios indicados.
    Elimina automáticamente suscripciones caducadas (410 Gone).
    Retorna el número de envíos exitosos.
    """
    if not is_configured() or not user_ids:
        return 0
    try:
        from pywebpush import WebPushException
        from app.models.push_subscription import PushSubscription
        from app.extensions import db

        subs  = PushSubscription.query.filter(PushSubscription.user_id.in_(user_ids)).all()
        sent  = 0
        stale = []
        for sub in subs:
            try:
                _send_one(sub.to_sub_info(), payload)
                sent += 1
            except WebPushException as e:
                if e.response is not None and e.response.status_code in (404, 410):
                    stale.append(sub.id)
                else:
                    logger.warning(f'[WEB-PUSH] sub={sub.id} error: {e}')
            except Exception as e:
                logger.warning(f'[WEB-PUSH] sub={sub.id} unexpected: {e}')

        if stale:
            PushSubscription.query.filter(PushSubscription.id.in_(stale)).delete(synchronize_session=False)
            db.session.commit()
            logger.info(f'[WEB-PUSH] {len(stale)} suscripcion(es) caducada(s) eliminada(s)')

        return sent
    except ImportError:
        logger.warning('[WEB-PUSH] pywebpush no instalado — push deshabilitado')
        return 0
    except Exception as e:
        logger.error(f'[WEB-PUSH] send_to_users error: {e}')
        return 0


def send_to_roles(roles: List[str], payload: dict) -> int:
    """Envía web push a todos los usuarios activos de los roles indicados."""
    if not is_configured():
        return 0
    try:
        from app.models.user import User
        users = User.query.filter(User.role.in_(roles), User.status == 'Activo').all()
        if not users:
            return 0
        return send_to_users([u.id for u in users], payload)
    except Exception as e:
        logger.error(f'[WEB-PUSH] send_to_roles error: {e}')
        return 0

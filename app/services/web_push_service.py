"""
Servicio de Web Push Notifications — QoriCash
Envía notificaciones push al browser usando el protocolo Web Push (VAPID).
Funciona aunque la pestaña esté cerrada o la pantalla bloqueada.

Variables de entorno necesarias en Render:
  VAPID_PRIVATE_KEY  — clave privada EC: raw 32 bytes en base64url (43 chars)
  VAPID_PUBLIC_KEY   — clave pública EC en base64url sin padding (87 chars)
  VAPID_CLAIMS_SUB   — "mailto:gerencia@qoricash.pe" (contacto VAPID)

Para generar las claves: python3 generate_vapid_keys.py
"""
import base64
import json
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS_SUB = os.environ.get('VAPID_CLAIMS_SUB', 'mailto:gerencia@qoricash.pe')

_VAPID_PEM_CACHE: str = ''


def _load_private_key_pem() -> str:
    """
    Carga VAPID_PRIVATE_KEY desde el entorno y devuelve siempre PEM válido.
    Acepta: raw 32-byte base64url, DER base64url (truncado o completo), PEM multilínea.
    Cachea el resultado para no recalcular en cada envío.
    """
    global _VAPID_PEM_CACHE
    if _VAPID_PEM_CACHE:
        return _VAPID_PEM_CACHE

    raw = os.environ.get('VAPID_PRIVATE_KEY', '').strip()
    if not raw:
        return ''

    # PEM con \n literales (Render puede escaparlos)
    if '\\n' in raw:
        _VAPID_PEM_CACHE = raw.replace('\\n', '\n')
        return _VAPID_PEM_CACHE

    # PEM multilínea normal
    if raw.startswith('-----'):
        _VAPID_PEM_CACHE = raw
        return _VAPID_PEM_CACHE

    # Base64url — decodificar tolerando truncación de hasta 3 chars
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption, load_der_private_key
    )

    data = None
    for pad in ('', '=', '==', '==='):
        try:
            candidate = base64.urlsafe_b64decode(raw + pad)
            data = candidate
            break
        except Exception:
            continue

    if data is None:
        logger.error('[WEB-PUSH] VAPID_PRIVATE_KEY no es base64url válido')
        return ''

    try:
        if len(data) == 32:
            # Raw EC scalar (formato preferido — 43 chars en base64url)
            priv_int = int.from_bytes(data, 'big')
            key = ec.derive_private_key(priv_int, ec.SECP256R1(), default_backend())
        else:
            # DER completo
            key = load_der_private_key(data, password=None)

        _VAPID_PEM_CACHE = key.private_bytes(
            Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
        ).decode('utf8')
        return _VAPID_PEM_CACHE
    except Exception as exc:
        logger.error(f'[WEB-PUSH] No se pudo deserializar VAPID private key: {exc}')
        return ''


def is_configured() -> bool:
    return bool(os.environ.get('VAPID_PRIVATE_KEY', '').strip() and VAPID_PUBLIC_KEY)


def get_vapid_public_key() -> str:
    return VAPID_PUBLIC_KEY


def _send_one(sub_info: dict, payload: dict):
    """Envía un push a una suscripción. Lanza WebPushException si falla."""
    from pywebpush import webpush
    pem = _load_private_key_pem()
    if not pem:
        raise ValueError('VAPID private key no cargada')
    webpush(
        subscription_info=sub_info,
        data=json.dumps(payload, ensure_ascii=False),
        vapid_private_key=pem,
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
                code = e.response.status_code if e.response is not None else 0
                if code in (400, 403, 404, 410):
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

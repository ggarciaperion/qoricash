"""
security.py — QoriCash Security Hardening
Centraliza todos los headers de seguridad HTTP y utilidades de protección.
"""
import hmac
import hashlib
import logging
import os
from functools import wraps
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)


def configure_security_headers(app):
    """
    Aplica headers de seguridad HTTP a todas las respuestas.
    Protege contra XSS, clickjacking, MIME sniffing, CSRF y más.
    """
    @app.after_request
    def add_security_headers(response):
        # ── HTTPS estricto (HSTS) ──────────────────────────────────────────
        # Solo en producción — evita downgrade a HTTP
        if not app.debug:
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )

        # ── Clickjacking ────────────────────────────────────────────────────
        response.headers['X-Frame-Options'] = 'DENY'

        # ── MIME sniffing ───────────────────────────────────────────────────
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # ── XSS ─────────────────────────────────────────────────────────────
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # ── Referrer ─────────────────────────────────────────────────────────
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # ── Permissions Policy ───────────────────────────────────────────────
        response.headers['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
        )

        # ── Content Security Policy ──────────────────────────────────────────
        # Ajustado para permitir CDNs usados en templates (Bootstrap, FontAwesome, etc.)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "    https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "    https://code.jquery.com https://cdn.socket.io; "
            "style-src 'self' 'unsafe-inline' "
            "    https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "    https://fonts.googleapis.com; "
            "font-src 'self' data: "
            "    https://fonts.gstatic.com https://cdnjs.cloudflare.com "
            "    https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob: https://res.cloudinary.com; "
            "connect-src 'self' "
            "    wss://app.qoricash.pe https://app.qoricash.pe "
            "    ws://localhost:5000 http://localhost:5000; "
            "media-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers['Content-Security-Policy'] = csp

        # ── Ocultar tecnología ────────────────────────────────────────────────
        response.headers.pop('Server', None)
        response.headers.pop('X-Powered-By', None)

        return response


def safe_compare(a: str, b: str) -> bool:
    """
    Comparación en tiempo constante para evitar timing attacks.
    Usar siempre para comparar secrets, tokens y API keys.
    """
    return hmac.compare_digest(
        a.encode('utf-8') if isinstance(a, str) else a,
        b.encode('utf-8') if isinstance(b, str) else b,
    )


def require_internal_api_key(f):
    """
    Decorador para endpoints internos.
    Usa comparación en tiempo constante (anti-timing attack).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key', '')
        expected = os.environ.get('INTERNAL_API_KEY', '')

        if not expected:
            logger.critical('[Security] INTERNAL_API_KEY no configurada — bloqueando acceso')
            return jsonify({'error': 'Configuración de seguridad no disponible'}), 503

        if not api_key or not safe_compare(api_key, expected):
            logger.warning(f'[Security] API key inválida desde {request.remote_addr} → {request.path}')
            return jsonify({'error': 'No autorizado'}), 401

        return f(*args, **kwargs)
    return decorated


# Mantener compatibilidad con el decorador anterior
api_key_required = require_internal_api_key


# ── Account Lockout ──────────────────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5      # intentos antes de bloquear
LOCKOUT_MINUTES     = 15     # minutos bloqueado


def check_account_lockout(user):
    """
    Verifica si la cuenta está bloqueada por intentos fallidos.
    Retorna (bloqueado: bool, mensaje: str, segundos_restantes: int)
    """
    from app.utils.formatters import now_peru

    locked_until = getattr(user, 'locked_until', None)
    if locked_until and locked_until > now_peru():
        remaining = int((locked_until - now_peru()).total_seconds())
        mins = remaining // 60
        secs = remaining % 60
        return True, f'Cuenta bloqueada. Intente en {mins}m {secs}s', remaining
    return False, '', 0


def register_failed_attempt(user, db):
    """Registra intento fallido y bloquea la cuenta si supera el límite."""
    from app.utils.formatters import now_peru
    from datetime import timedelta

    attempts = getattr(user, 'failed_attempts', 0) or 0
    attempts += 1
    user.failed_attempts = attempts

    if attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = now_peru() + timedelta(minutes=LOCKOUT_MINUTES)
        logger.warning(
            f'[Security] Cuenta {user.username} bloqueada tras {attempts} intentos fallidos'
        )

    db.session.commit()


def reset_failed_attempts(user, db):
    """Resetea contador de intentos fallidos tras login exitoso."""
    if getattr(user, 'failed_attempts', 0) or getattr(user, 'locked_until', None):
        user.failed_attempts = 0
        user.locked_until = None
        db.session.commit()

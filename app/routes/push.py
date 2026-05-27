"""
Blueprint: Web Push — /api/push/*
Gestiona suscripciones VAPID del navegador.
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.push_subscription import PushSubscription

push_bp = Blueprint('push', __name__, url_prefix='/api/push')


@push_bp.route('/vapid-key')
@login_required
def vapid_key():
    from app.services.web_push_service import get_vapid_public_key, is_configured
    if not is_configured():
        return jsonify({'ok': False, 'error': 'VAPID not configured'}), 503
    return jsonify({'ok': True, 'publicKey': get_vapid_public_key()})


@push_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    data     = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint', '').strip()
    keys     = data.get('keys') or {}
    p256dh   = keys.get('p256dh', '').strip()
    auth     = keys.get('auth', '').strip()

    if not endpoint or not p256dh or not auth:
        return jsonify({'ok': False, 'error': 'Faltan campos'}), 400

    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if sub:
        sub.user_id    = current_user.id
        sub.p256dh     = p256dh
        sub.auth       = auth
        sub.user_agent = (request.headers.get('User-Agent') or '')[:250]
    else:
        sub = PushSubscription(
            user_id    = current_user.id,
            endpoint   = endpoint,
            p256dh     = p256dh,
            auth       = auth,
            user_agent = (request.headers.get('User-Agent') or '')[:250],
        )
        db.session.add(sub)

    db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    data     = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint', '')
    if endpoint:
        PushSubscription.query.filter_by(
            endpoint=endpoint, user_id=current_user.id
        ).delete()
        db.session.commit()
    return jsonify({'ok': True})

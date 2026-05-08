"""
API de Notificaciones — QoriCash
Endpoints para historial, badge counter y mark-as-read.
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.notification import Notification

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


@notifications_bp.route('/api/unread_count')
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


@notifications_bp.route('/api/list')
@login_required
def list_notifications():
    limit = min(int(request.args.get('limit', 30)), 100)
    notifs = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify({'notifications': [n.to_dict() for n in notifs]})


@notifications_bp.route('/api/mark_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    n.mark_read()
    db.session.commit()
    return jsonify({'ok': True})


@notifications_bp.route('/api/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({
        'is_read': True
    })
    db.session.commit()
    return jsonify({'ok': True})

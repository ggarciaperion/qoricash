"""
Modelo para suscripciones de Web Push Notifications.
Almacena el endpoint + claves de cifrado del browser por usuario.
"""
from app.extensions import db
from app.utils.formatters import now_peru


class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    endpoint   = db.Column(db.Text, nullable=False, unique=True)
    p256dh     = db.Column(db.Text, nullable=False)
    auth       = db.Column(db.String(100), nullable=False)
    user_agent = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)

    user = db.relationship('User', backref=db.backref('push_subscriptions', lazy='select'))

    def to_sub_info(self):
        return {
            'endpoint': self.endpoint,
            'keys': {'p256dh': self.p256dh, 'auth': self.auth},
        }

    def __repr__(self):
        return f'<PushSubscription user={self.user_id} endpoint={self.endpoint[:40]}>'

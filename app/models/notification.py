"""
Modelo de Notificación persistente para QoriCash.
Permite historial, contador de no leídas y auditoría.
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class Notification(db.Model):
    __tablename__ = 'notifications'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title       = db.Column(db.String(200), nullable=False)
    message     = db.Column(db.String(500), nullable=False)
    notif_type  = db.Column(db.String(30), nullable=False, default='info')  # info|success|warning|danger
    category    = db.Column(db.String(50), nullable=False, default='general')  # operation|client|user|system
    link        = db.Column(db.String(300))          # URL opcional para redirigir al click
    is_read     = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at  = db.Column(db.DateTime, default=now_peru, nullable=False, index=True)
    read_at     = db.Column(db.DateTime)

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))

    def mark_read(self):
        self.is_read = True
        self.read_at = now_peru()

    def to_dict(self):
        return {
            'id':          self.id,
            'title':       self.title,
            'message':     self.message,
            'type':        self.notif_type,
            'category':    self.category,
            'link':        self.link,
            'is_read':     self.is_read,
            'created_at':  self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def create_for_user(cls, user_id, title, message, notif_type='info', category='general', link=None):
        n = cls(
            user_id=user_id,
            title=title,
            message=message,
            notif_type=notif_type,
            category=category,
            link=link,
        )
        db.session.add(n)
        return n

    @classmethod
    def create_for_role(cls, role, title, message, notif_type='info', category='general', link=None):
        """Crea notificaciones para todos los usuarios activos de un rol."""
        from app.models.user import User
        users = User.query.filter_by(role=role, status='Activo').all()
        notifs = []
        for u in users:
            notifs.append(cls.create_for_user(u.id, title, message, notif_type, category, link))
        return notifs

    @classmethod
    def create_for_roles(cls, roles, title, message, notif_type='info', category='general', link=None):
        """Crea notificaciones para múltiples roles."""
        notifs = []
        for role in roles:
            notifs.extend(cls.create_for_role(role, title, message, notif_type, category, link))
        return notifs

    def __repr__(self):
        return f'<Notification {self.id} → user {self.user_id}: {self.title[:30]}>'

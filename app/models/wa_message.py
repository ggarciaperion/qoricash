"""
Modelo WaMessage — Mensajes de WhatsApp CRM
"""
from app.extensions import db
from app.utils.formatters import now_peru


class WaMessage(db.Model):
    __tablename__ = 'wa_messages'

    id        = db.Column(db.Integer, primary_key=True)
    numero    = db.Column(db.String(25),  nullable=False, index=True)
    nombre    = db.Column(db.String(120), default='')
    empresa   = db.Column(db.String(200), default='')
    mensaje   = db.Column(db.Text,        nullable=False)
    direccion = db.Column(db.String(10),  nullable=False)  # 'entrante' | 'saliente'
    wa_id     = db.Column(db.String(120), default='')
    leido     = db.Column(db.Boolean,     default=False)
    created_at = db.Column(db.DateTime,   default=now_peru, nullable=False)

    def to_dict(self):
        return {
            'id':        self.id,
            'numero':    self.numero,
            'nombre':    self.nombre,
            'empresa':   self.empresa,
            'mensaje':   self.mensaje,
            'direccion': self.direccion,
            'leido':     self.leido,
            'created_at': self.created_at.strftime('%d/%m/%Y %H:%M') if self.created_at else '',
        }

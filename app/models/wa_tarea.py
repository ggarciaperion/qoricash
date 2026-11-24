"""
WaTarea — Tareas y recordatorios ligados a un número de WhatsApp.

Independiente de Prospecto y Client: sirve para cualquier número que
esté en la bandeja WA, aunque no tenga match en la base de datos.
"""
from app.extensions import db
from app.utils.formatters import now_peru


class WaTarea(db.Model):
    __tablename__ = 'wa_tareas'

    id            = db.Column(db.Integer, primary_key=True)
    numero        = db.Column(db.String(25), nullable=False, index=True)   # E.164 +51XXXXXXXXX
    descripcion   = db.Column(db.Text,      nullable=False)
    fecha_prog    = db.Column(db.Date,      nullable=True, index=True)     # fecha programada
    completado    = db.Column(db.Boolean,   default=False, nullable=False)
    completado_en = db.Column(db.DateTime,  nullable=True)
    creado_por    = db.Column(db.Integer,   db.ForeignKey('users.id'), nullable=True)
    creado_en     = db.Column(db.DateTime,  default=now_peru, nullable=False)

    usuario = db.relationship('User', foreign_keys=[creado_por])

    def to_dict(self):
        return {
            'id':           self.id,
            'numero':       self.numero,
            'descripcion':  self.descripcion,
            'fecha_prog':   self.fecha_prog.isoformat() if self.fecha_prog else None,
            'completado':   self.completado,
            'completado_en': self.completado_en.strftime('%d/%m/%Y %H:%M') if self.completado_en else None,
            'creado_por':   self.usuario.username if self.usuario else '',
            'creado_en':    self.creado_en.strftime('%d/%m/%Y %H:%M') if self.creado_en else '',
        }

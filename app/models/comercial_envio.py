"""
Registro de envíos de tipo de cambio desde el módulo Comercial.
Permite controlar el límite diario y mostrar el último contacto por cliente.
"""
from datetime import datetime
from app.extensions import db


class ComercialEnvio(db.Model):
    __tablename__ = 'comercial_envios'

    id        = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable=False, index=True)
    sent_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    compra    = db.Column(db.String(10))
    venta     = db.Column(db.String(10))

    client = db.relationship('Client', backref=db.backref('comercial_envios', lazy='dynamic'))
    user   = db.relationship('User',   backref=db.backref('comercial_envios', lazy='dynamic'))

    def __repr__(self):
        return f'<ComercialEnvio client={self.client_id} user={self.user_id} at={self.sent_at}>'

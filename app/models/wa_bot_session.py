"""
WaBotSession — Estado de conversación del bot de WhatsApp
"""
from app.extensions import db
from app.utils.formatters import now_peru


class WaBotSession(db.Model):
    __tablename__ = 'wa_bot_sessions'

    id         = db.Column(db.Integer, primary_key=True)
    numero     = db.Column(db.String(25), nullable=False, unique=True, index=True)
    estado     = db.Column(db.String(50), nullable=False, default='inicio')
    # Datos recopilados durante el onboarding
    tipo       = db.Column(db.String(20), default='')      # 'natural' | 'empresa'
    dni_front  = db.Column(db.String(120), default='')     # media_id de imagen DNI frontal
    dni_back   = db.Column(db.String(120), default='')     # media_id de imagen DNI posterior
    ruc_doc    = db.Column(db.String(120), default='')     # media_id de ficha RUC
    nombre     = db.Column(db.String(120), default='')
    # Cotización en curso
    cotiz_op      = db.Column(db.String(10),  default='')   # 'compra' | 'venta'
    cotiz_importe = db.Column(db.Float,       default=0.0)  # monto en USD
    cotiz_tc      = db.Column(db.Float,       default=0.0)  # TC ofrecido
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru, nullable=False)

    @classmethod
    def get_or_create(cls, numero):
        s = cls.query.filter_by(numero=numero).first()
        if not s:
            s = cls(numero=numero, estado='inicio')
            db.session.add(s)
        return s

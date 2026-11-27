"""
WaProspectoBase — Registro de prospectos sincronizados desde la Fuente de Datos (Google Sheet).

Cada fila = un contacto que ya recibió un email, con teléfono disponible para WA.
Se actualiza diariamente via sync_wa_prospectos.py (script local Mac).
"""
from app.extensions import db
from app.utils.formatters import now_peru


class WaProspectoBase(db.Model):
    __tablename__ = 'wa_prospectos_base'

    id             = db.Column(db.Integer, primary_key=True)
    numero         = db.Column(db.String(15), unique=True, nullable=False, index=True)  # 9 dígitos
    nombre         = db.Column(db.String(200), default='')
    empresa        = db.Column(db.String(300), default='')
    rubro          = db.Column(db.String(100), default='')
    bandeja_email  = db.Column(db.String(20), default='')    # ggarcia / gerencia / info
    fecha_email    = db.Column(db.DateTime, nullable=True)   # Fecha de Envío del email
    wa_validado    = db.Column(db.String(20), default='sin_historial')
    # sin_historial / con_wa / sin_wa / bot_session

    # Sheet fields added 2026-11-24 (source of truth columns)
    ruc            = db.Column(db.String(15),  nullable=True, index=True)  # para cruce con Client.dni
    resultado      = db.Column(db.String(100), nullable=True)  # CLIENTE / INTERESADO / COTIZO / REBOTADO / …
    email          = db.Column(db.String(200), nullable=True)
    cargo          = db.Column(db.String(150), nullable=True)

    fecha_wa       = db.Column(db.DateTime, nullable=True)   # Último envío WA exitoso

    actualizado_en = db.Column(db.DateTime, default=now_peru, onupdate=now_peru, nullable=False)

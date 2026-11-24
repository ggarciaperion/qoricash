"""
WaCampanaProspecto — Registro de campañas WA enviadas a prospectos de la Fuente de Datos.

Independiente del sistema de email (scheduler_lotes) y del chatbot WA (WaBotSession).
Cada fila = un envío WA a un número, con trazabilidad completa de estado.
"""
from app.extensions import db
from app.utils.formatters import now_peru


class WaCampanaProspecto(db.Model):
    __tablename__ = 'wa_campana_prospectos'

    id               = db.Column(db.Integer, primary_key=True)

    # Prospecto origen (puede ser NULL si el número no está en la tabla prospectos)
    prospecto_id     = db.Column(db.Integer, db.ForeignKey('prospectos.id'), nullable=True, index=True)
    numero           = db.Column(db.String(25), nullable=False, index=True)   # E.164 +51XXXXXXXXX
    nombre           = db.Column(db.String(150), default='')
    empresa          = db.Column(db.String(300), default='')

    # Validación WA — resultado del intento de envío
    wa_validado      = db.Column(db.String(20), default='sin_validar')  # sin_validar / con_wa / sin_wa
    fecha_validacion = db.Column(db.DateTime, nullable=True)

    # Campaña
    campana          = db.Column(db.String(100), nullable=False, index=True)  # ej: "Nov2026"
    plantilla        = db.Column(db.String(100), nullable=False)              # nombre plantilla Meta
    compra           = db.Column(db.String(10), default='')
    venta            = db.Column(db.String(10), default='')

    # Resultado del envío
    wa_id            = db.Column(db.String(120), nullable=True, index=True)  # Meta message ID
    estado           = db.Column(db.String(20), default='pendiente', index=True)
    # estados: pendiente / enviado / entregado / leido / fallido / sin_wa
    error_msg        = db.Column(db.Text, nullable=True)

    # Timestamps de ciclo de vida del mensaje
    fecha_envio      = db.Column(db.DateTime, nullable=True)
    fecha_entregado  = db.Column(db.DateTime, nullable=True)
    fecha_leido      = db.Column(db.DateTime, nullable=True)

    # Respuesta del destinatario al template de campaña
    respondio_en     = db.Column(db.DateTime, nullable=True)   # primera respuesta / press botón
    respuesta_btn    = db.Column(db.String(200), nullable=True) # payload/texto del botón presionado

    enviado_por      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    creado_en        = db.Column(db.DateTime, default=now_peru, nullable=False)
    actualizado_en   = db.Column(db.DateTime, default=now_peru, onupdate=now_peru, nullable=False)

    # Relaciones
    prospecto = db.relationship('Prospecto', foreign_keys=[prospecto_id],
                                backref=db.backref('wa_campanas', lazy='dynamic'))
    usuario   = db.relationship('User', foreign_keys=[enviado_por])

    __table_args__ = (
        # Evitar duplicar el mismo número en la misma campaña
        db.UniqueConstraint('numero', 'campana', name='uq_wa_campana_numero'),
    )

    def to_dict(self):
        return {
            'id':               self.id,
            'prospecto_id':     self.prospecto_id,
            'numero':           self.numero,
            'nombre':           self.nombre or '',
            'empresa':          self.empresa or '',
            'wa_validado':      self.wa_validado,
            'campana':          self.campana,
            'plantilla':        self.plantilla,
            'compra':           self.compra or '',
            'venta':            self.venta or '',
            'wa_id':            self.wa_id or '',
            'estado':           self.estado,
            'error_msg':        self.error_msg or '',
            'fecha_envio':      self.fecha_envio.strftime('%d/%m/%Y %H:%M') if self.fecha_envio else '',
            'fecha_entregado':  self.fecha_entregado.strftime('%d/%m/%Y %H:%M') if self.fecha_entregado else '',
            'fecha_leido':      self.fecha_leido.strftime('%d/%m/%Y %H:%M') if self.fecha_leido else '',
            'respondio_en':     self.respondio_en.strftime('%d/%m/%Y %H:%M') if self.respondio_en else '',
            'respuesta_btn':    self.respuesta_btn or '',
            'enviado_por':      self.usuario.username if self.usuario else '',
            'creado_en':        self.creado_en.strftime('%d/%m/%Y %H:%M') if self.creado_en else '',
        }

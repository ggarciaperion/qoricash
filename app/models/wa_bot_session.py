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
    # Registro / verificación de identidad
    cotiz_doc     = db.Column(db.String(20),  default='')   # DNI o RUC ingresado
    cotiz_email   = db.Column(db.String(120), default='')   # email para registro
    cotiz_op_id   = db.Column(db.String(20),  default='')   # operation_id creado (EXP-XXX)
    cotiz_cuenta  = db.Column(db.String(50),  default='')   # cuenta destino del cliente
    cotiz_timestamp = db.Column(db.DateTime, nullable=True)  # timestamp cuando se mostró la cotización
    cotiz_token     = db.Column(db.String(36), nullable=True)  # token UUID corto que identifica la versión de cotización
    # Control de ciclo de sesión: marca el inicio de un nuevo ciclo tras expiración por inactividad.
    # Permite acotar el historial de IA y rechazar botones de ciclos anteriores.
    # NULL = sesión nunca expirada (cliente nuevo o sesión activa sin reset por inactividad).
    # Non-NULL = timestamp del último reset por inactividad (scheduler o in-band).
    session_started_at = db.Column(db.DateTime, nullable=True)
    # Control de atención humana
    bot_pausado    = db.Column(db.Boolean, default=False, nullable=False)
    # Intentos fallidos consecutivos en el estado actual (para ofrecer salida tras N errores)
    cotiz_intentos = db.Column(db.Integer, default=0, nullable=False)
    # ── Rate limiting ──────────────────────────────────────────────────────────
    # rate_resp_sesion   : respuestas del bot en la sesión actual (sin operación creada)
    # rate_resp_periodo  : respuestas del bot en la ventana móvil (ej. 24 h)
    # rate_periodo_inicio: inicio de la ventana móvil actual
    # rate_pausado_hasta : datetime hasta el que el bot está silenciado (NULL = activo)
    # rate_motivo        : 'limite_sesion' | 'limite_periodo' | 'burst' | 'manual'
    # rate_aviso_enviado : True si ya se envió el mensaje de pausa (para no repetirlo)
    rate_resp_sesion    = db.Column(db.Integer,    default=0,     nullable=False)
    rate_resp_periodo   = db.Column(db.Integer,    default=0,     nullable=False)
    rate_periodo_inicio = db.Column(db.DateTime,   nullable=True)
    rate_pausado_hasta  = db.Column(db.DateTime,   nullable=True)
    rate_motivo         = db.Column(db.String(30), nullable=True)
    rate_aviso_enviado  = db.Column(db.Boolean,    default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru, nullable=False)

    @classmethod
    def get_or_create(cls, numero):
        s = cls.query.filter_by(numero=numero).first()
        if not s:
            s = cls(numero=numero, estado='inicio')
            db.session.add(s)
        return s

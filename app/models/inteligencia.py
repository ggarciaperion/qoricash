"""
Modelos del Centro de Inteligencia Comercial — QoriCash
Tablas: email_eventos, oportunidades_comerciales, ejecuciones_motor
"""
from app.extensions import db
from app.utils.formatters import now_peru


class EmailEvento(db.Model):
    """Registro de cada email procesado por los motores automáticos."""
    __tablename__ = "email_eventos"

    id             = db.Column(db.Integer, primary_key=True)
    cuenta         = db.Column(db.String(100), nullable=False, index=True)   # ggarcia | gerencia | info
    mensaje_id     = db.Column(db.String(400), unique=True, index=True)
    remitente      = db.Column(db.String(300))
    asunto         = db.Column(db.String(500))
    tipo           = db.Column(db.String(50), index=True)
    # bounce | auto_reply | oportunidad | no_contactar | email_cambio | marketing | irrelevante
    confianza      = db.Column(db.Float, default=1.0)   # 0.0 – 1.0
    ia_usada       = db.Column(db.Boolean, default=False)
    ia_tokens      = db.Column(db.Integer, default=0)
    accion         = db.Column(db.String(300))          # descripción de lo que se hizo
    email_afectado = db.Column(db.String(200))          # correo que se marcó/actualizó
    email_nuevo    = db.Column(db.String(200))          # en caso de cambio de email
    sheets_tab     = db.Column(db.String(50))           # pestaña donde se actualizó
    crm_updated    = db.Column(db.Boolean, default=False)
    sheets_updated = db.Column(db.Boolean, default=False)
    procesado_en   = db.Column(db.DateTime, default=now_peru, index=True)

    def to_dict(self):
        return {
            "id":            self.id,
            "cuenta":        self.cuenta,
            "remitente":     self.remitente or "",
            "asunto":        self.asunto or "",
            "tipo":          self.tipo or "",
            "confianza":     self.confianza,
            "ia_usada":      self.ia_usada,
            "accion":        self.accion or "",
            "email_afectado": self.email_afectado or "",
            "email_nuevo":   self.email_nuevo or "",
            "sheets_updated": self.sheets_updated,
            "crm_updated":   self.crm_updated,
            "procesado_en":  self.procesado_en.strftime("%d/%m %H:%M") if self.procesado_en else "",
        }


class Oportunidad(db.Model):
    """Oportunidad comercial detectada automáticamente por el Motor Comercial."""
    __tablename__ = "oportunidades_comerciales"

    id                  = db.Column(db.Integer, primary_key=True)
    empresa             = db.Column(db.String(300))
    contacto            = db.Column(db.String(200))
    cargo               = db.Column(db.String(150))
    email               = db.Column(db.String(200), index=True)
    telefono            = db.Column(db.String(100))
    sector              = db.Column(db.String(100))
    prioridad           = db.Column(db.String(20), index=True)  # alta | media | baja
    score               = db.Column(db.Integer, default=0)      # 0-100
    volumen_usd_est     = db.Column(db.Integer, default=0)      # USD mensuales estimados
    necesidad           = db.Column(db.Text)                    # resumen de la necesidad
    recomendacion       = db.Column(db.Text)                    # acción sugerida por IA
    cuerpo_email        = db.Column(db.Text)                    # extracto del email original
    estado              = db.Column(db.String(50), default="nuevo", index=True)
    # nuevo | en_seguimiento | convertido | descartado
    cuenta_origen       = db.Column(db.String(100))
    mensaje_id          = db.Column(db.String(400))
    prospecto_creado_id = db.Column(db.Integer, db.ForeignKey("prospectos.id"), nullable=True)
    wa_alerta_enviada   = db.Column(db.Boolean, default=False)
    detectado_en        = db.Column(db.DateTime, default=now_peru, index=True)
    actualizado_en      = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    prospecto = db.relationship("Prospecto", foreign_keys=[prospecto_creado_id],
                                backref=db.backref("oportunidad_origen", uselist=False))

    @property
    def prioridad_badge(self):
        return {"alta": "danger", "media": "warning", "baja": "secondary"}.get(
            self.prioridad or "baja", "secondary")

    def to_dict(self):
        return {
            "id":           self.id,
            "empresa":      self.empresa or "",
            "contacto":     self.contacto or "",
            "cargo":        self.cargo or "",
            "email":        self.email or "",
            "sector":       self.sector or "",
            "prioridad":    self.prioridad or "baja",
            "score":        self.score,
            "volumen_usd":  self.volumen_usd_est,
            "necesidad":    self.necesidad or "",
            "recomendacion": self.recomendacion or "",
            "estado":       self.estado or "nuevo",
            "detectado_en": self.detectado_en.strftime("%d/%m %H:%M") if self.detectado_en else "",
        }


class EjecucionMotor(db.Model):
    """Log de cada ejecución de los motores automáticos."""
    __tablename__ = "ejecuciones_motor"

    id                  = db.Column(db.Integer, primary_key=True)
    motor               = db.Column(db.String(50), index=True)  # comercial | limpieza | auditoria
    inicio              = db.Column(db.DateTime, default=now_peru)
    fin                 = db.Column(db.DateTime)
    duracion_seg        = db.Column(db.Float)
    correos_analizados  = db.Column(db.Integer, default=0)
    rebotes             = db.Column(db.Integer, default=0)
    oportunidades       = db.Column(db.Integer, default=0)
    actualizaciones     = db.Column(db.Integer, default=0)
    no_contactar        = db.Column(db.Integer, default=0)
    ia_tokens           = db.Column(db.Integer, default=0)
    ia_costo_usd        = db.Column(db.Float, default=0.0)
    errores             = db.Column(db.Integer, default=0)
    estado              = db.Column(db.String(20), default="ok")  # ok | error | parcial
    resumen             = db.Column(db.Text)

    def to_dict(self):
        return {
            "id":                  self.id,
            "motor":               self.motor,
            "inicio":              self.inicio.strftime("%d/%m %H:%M") if self.inicio else "",
            "duracion_seg":        round(self.duracion_seg or 0, 1),
            "correos_analizados":  self.correos_analizados,
            "rebotes":             self.rebotes,
            "oportunidades":       self.oportunidades,
            "actualizaciones":     self.actualizaciones,
            "ia_tokens":           self.ia_tokens,
            "ia_costo_usd":        round(self.ia_costo_usd or 0, 5),
            "estado":              self.estado,
        }

"""
Modelo de Factura Electrónica para QoriCash Trading V2
Integración con NubeFact API
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class Invoice(db.Model):
    """Modelo de Factura/Boleta Electrónica"""

    __tablename__ = 'invoices'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    operation_id = db.Column(db.Integer, db.ForeignKey('operations.id'), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)

    # Tipo de comprobante
    invoice_type = db.Column(
        db.String(20),
        nullable=False
    )  # Factura (01), Boleta (03)

    # Serie y número del comprobante
    serie = db.Column(db.String(10))  # Ej: F001, B001
    numero = db.Column(db.String(20))  # Ej: 00000123

    # Número completo del comprobante (serie-numero)
    invoice_number = db.Column(db.String(50), index=True)  # Ej: F001-00000123

    # Datos del emisor (QoriCash SAC)
    emisor_ruc = db.Column(db.String(11), nullable=False)
    emisor_razon_social = db.Column(db.String(200), nullable=False)
    emisor_direccion = db.Column(db.String(300))

    # Datos del cliente (receptor)
    cliente_tipo_documento = db.Column(db.String(10))  # 1=DNI, 6=RUC, 4=CE
    cliente_numero_documento = db.Column(db.String(20), nullable=False)
    cliente_denominacion = db.Column(db.String(200), nullable=False)
    cliente_direccion = db.Column(db.String(300))
    cliente_email = db.Column(db.String(120))

    # Detalles de la operación
    descripcion = db.Column(db.Text)  # Descripción del servicio
    monto_total = db.Column(db.Numeric(15, 2), nullable=False)
    moneda = db.Column(db.String(10), default='PEN')  # PEN, USD

    # IGV
    gravada = db.Column(db.Numeric(15, 2), default=0)  # Monto gravado
    exonerada = db.Column(db.Numeric(15, 2), default=0)  # Monto exonerado
    igv = db.Column(db.Numeric(15, 2), default=0)  # Monto de IGV

    # Estado de la factura
    status = db.Column(
        db.String(20),
        nullable=False,
        default='Pendiente',
        index=True
    )  # Pendiente, Enviado, Aceptado, Rechazado, Error

    # Respuesta de NubeFact
    nubefact_response = db.Column(db.Text)  # JSON response completo de NubeFact
    nubefact_enlace_pdf = db.Column(db.String(500))  # URL del PDF
    nubefact_enlace_xml = db.Column(db.String(500))  # URL del XML
    nubefact_aceptada_por_sunat = db.Column(db.Boolean, default=False)
    nubefact_sunat_description = db.Column(db.Text)  # Descripción de SUNAT
    nubefact_sunat_note = db.Column(db.Text)  # Nota de SUNAT
    nubefact_codigo_hash = db.Column(db.String(200))  # Hash del comprobante

    # Errores
    error_message = db.Column(db.Text)  # Mensaje de error si falla

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    sent_at = db.Column(db.DateTime)  # Cuándo se envió a NubeFact
    accepted_at = db.Column(db.DateTime)  # Cuándo fue aceptado por SUNAT

    # Relaciones
    operation = db.relationship('Operation', backref='invoices', lazy=True)
    client = db.relationship('Client', backref='invoices', lazy=True)

    def __repr__(self):
        return f'<Invoice {self.invoice_number} - Operation {self.operation_id}>'

    def to_dict(self):
        """Convertir a diccionario para JSON"""
        return {
            'id': self.id,
            'operation_id': self.operation_id,
            'invoice_type': self.invoice_type,
            'invoice_number': self.invoice_number,
            'serie': self.serie,
            'numero': self.numero,
            'cliente_numero_documento': self.cliente_numero_documento,
            'cliente_denominacion': self.cliente_denominacion,
            'monto_total': float(self.monto_total) if self.monto_total else 0,
            'moneda': self.moneda,
            'status': self.status,
            'nubefact_enlace_pdf': self.nubefact_enlace_pdf,
            'nubefact_enlace_xml': self.nubefact_enlace_xml,
            'nubefact_aceptada_por_sunat': self.nubefact_aceptada_por_sunat,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None
        }

"""
Modelos de Compliance para AML/KYC/PLAFT - QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class RiskLevel(db.Model):
    """Niveles de riesgo para clientes y operaciones"""

    __tablename__ = 'risk_levels'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # Bajo, Medio, Alto, Crítico
    description = db.Column(db.Text)
    color = db.Column(db.String(20))  # Para UI: green, yellow, orange, red
    score_min = db.Column(db.Integer)  # Puntaje mínimo
    score_max = db.Column(db.Integer)  # Puntaje máximo
    created_at = db.Column(db.DateTime, default=now_peru)

    def __repr__(self):
        return f'<RiskLevel {self.name}>'


class ClientRiskProfile(db.Model):
    """Perfil de riesgo de cada cliente"""

    __tablename__ = 'client_risk_profiles'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, unique=True)

    # Scoring de riesgo
    risk_level_id = db.Column(db.Integer, db.ForeignKey('risk_levels.id'))
    risk_score = db.Column(db.Integer, default=0)  # 0-100

    # Flags de riesgo
    is_pep = db.Column(db.Boolean, default=False)  # Persona Expuesta Políticamente
    has_legal_issues = db.Column(db.Boolean, default=False)  # Tiene procesos judiciales
    in_restrictive_lists = db.Column(db.Boolean, default=False)  # En listas restrictivas
    high_volume_operations = db.Column(db.Boolean, default=False)  # Alto volumen de operaciones

    # Datos adicionales de PEP (si is_pep = True)
    pep_type = db.Column(db.String(50))  # Directo, Familiar, Asociado Cercano
    pep_position = db.Column(db.String(200))  # Cargo/Posición
    pep_entity = db.Column(db.String(200))  # Entidad/Institución
    pep_designation_date = db.Column(db.Date)  # Fecha de designación
    pep_end_date = db.Column(db.Date)  # Fecha de cese (si ya no es PEP)
    pep_notes = db.Column(db.Text)  # Notas adicionales sobre PEP

    # KYC Status
    kyc_status = db.Column(db.String(50), default='Pendiente')  # Pendiente, En Proceso, Aprobado, Rechazado
    kyc_verified_at = db.Column(db.DateTime)
    kyc_verified_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Middle Office user
    kyc_notes = db.Column(db.Text)

    # Due Diligence
    dd_level = db.Column(db.String(50))  # Básica, Simplificada, Reforzada
    dd_last_review = db.Column(db.DateTime)
    dd_next_review = db.Column(db.DateTime)

    # Scoring factors (almacenado como JSON)
    scoring_details = db.Column(db.Text)  # JSON con detalles del scoring

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    # Relaciones
    client = db.relationship('Client', backref='risk_profile')
    risk_level = db.relationship('RiskLevel', backref='client_profiles')
    verified_by_user = db.relationship('User', foreign_keys=[kyc_verified_by])

    def __repr__(self):
        return f'<ClientRiskProfile client_id={self.client_id} risk_score={self.risk_score}>'


class ComplianceRule(db.Model):
    """Reglas de compliance para detectar actividades sospechosas"""

    __tablename__ = 'compliance_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    rule_type = db.Column(db.String(50), nullable=False)  # AML, KYC, PEP, Volumetric, Behavioral

    # Configuración de la regla (JSON)
    rule_config = db.Column(db.Text, nullable=False)  # JSON con parámetros de la regla

    # Activación
    is_active = db.Column(db.Boolean, default=True)
    severity = db.Column(db.String(20))  # Baja, Media, Alta, Crítica

    # Acciones automáticas
    auto_flag = db.Column(db.Boolean, default=True)  # Marcar automáticamente
    auto_block = db.Column(db.Boolean, default=False)  # Bloquear automáticamente
    requires_review = db.Column(db.Boolean, default=True)  # Requiere revisión manual

    # Metadata
    created_at = db.Column(db.DateTime, default=now_peru)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<ComplianceRule {self.name}>'


class ComplianceAlert(db.Model):
    """Alertas generadas por el motor de compliance"""

    __tablename__ = 'compliance_alerts'

    id = db.Column(db.Integer, primary_key=True)

    # Tipo de alerta
    alert_type = db.Column(db.String(50), nullable=False)  # AML, KYC, PEP, Suspicious, Volume
    severity = db.Column(db.String(20), nullable=False)  # Baja, Media, Alta, Crítica

    # Entidad relacionada
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    operation_id = db.Column(db.Integer, db.ForeignKey('operations.id'))

    # Regla que generó la alerta
    rule_id = db.Column(db.Integer, db.ForeignKey('compliance_rules.id'))

    # Detalles
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    details = db.Column(db.Text)  # JSON con detalles adicionales

    # Estado de la alerta
    status = db.Column(db.String(50), default='Pendiente')  # Pendiente, En Revisión, Resuelta, Falsa Alarma, Escalada

    # Revisión
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_notes = db.Column(db.Text)
    resolution = db.Column(db.String(100))  # Aprobado, Rechazado, Reportado a UIF, etc.

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    # Relaciones
    client = db.relationship('Client', backref='compliance_alerts')
    operation = db.relationship('Operation', backref='compliance_alerts')
    rule = db.relationship('ComplianceRule', backref='alerts')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<ComplianceAlert {self.alert_type} - {self.severity}>'


class RestrictiveListCheck(db.Model):
    """Registro de consultas a listas restrictivas (OFAC, ONU, UIF, etc.)"""

    __tablename__ = 'restrictive_list_checks'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    # Tipo de lista consultada
    list_type = db.Column(db.String(50), nullable=False)  # OFAC, ONU, UIF, PEP, Interpol
    provider = db.Column(db.String(100))  # Inspektor, WorldCheck, Manual

    # Resultado
    result = db.Column(db.String(50), nullable=False)  # Clean, Match, Potential_Match
    match_score = db.Column(db.Integer)  # 0-100
    details = db.Column(db.Text)  # JSON con detalles del match

    # Campos para búsqueda manual
    is_manual = db.Column(db.Boolean, default=False)  # Indica si es búsqueda manual

    # Verificaciones manuales específicas
    pep_checked = db.Column(db.Boolean, default=False)
    pep_result = db.Column(db.String(50))  # Clean, Match
    pep_details = db.Column(db.Text)  # Detalles de coincidencias PEP

    ofac_checked = db.Column(db.Boolean, default=False)
    ofac_result = db.Column(db.String(50))  # Clean, Match
    ofac_details = db.Column(db.Text)

    onu_checked = db.Column(db.Boolean, default=False)
    onu_result = db.Column(db.String(50))  # Clean, Match
    onu_details = db.Column(db.Text)

    uif_checked = db.Column(db.Boolean, default=False)
    uif_result = db.Column(db.String(50))  # Clean, Match
    uif_details = db.Column(db.Text)

    interpol_checked = db.Column(db.Boolean, default=False)
    interpol_result = db.Column(db.String(50))  # Clean, Match
    interpol_details = db.Column(db.Text)

    denuncias_checked = db.Column(db.Boolean, default=False)
    denuncias_result = db.Column(db.String(50))  # Clean, Match
    denuncias_details = db.Column(db.Text)

    otras_listas_checked = db.Column(db.Boolean, default=False)
    otras_listas_result = db.Column(db.String(50))  # Clean, Match
    otras_listas_details = db.Column(db.Text)

    # Observaciones generales
    observations = db.Column(db.Text)  # Observaciones generales del oficial

    # Archivos adjuntos (URLs separadas por comas)
    attachments = db.Column(db.Text)  # URLs de Cloudinary separadas por comas

    # Metadata
    checked_at = db.Column(db.DateTime, default=now_peru)
    checked_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relaciones
    client = db.relationship('Client', backref='restrictive_checks')
    checker = db.relationship('User', foreign_keys=[checked_by])

    def __repr__(self):
        return f'<RestrictiveListCheck client_id={self.client_id} result={self.result}>'


class TransactionMonitoring(db.Model):
    """Monitoreo de transacciones para detectar patrones sospechosos"""

    __tablename__ = 'transaction_monitoring'

    id = db.Column(db.Integer, primary_key=True)
    operation_id = db.Column(db.Integer, db.ForeignKey('operations.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    # Análisis automático
    risk_score = db.Column(db.Integer, default=0)  # 0-100
    flags = db.Column(db.Text)  # JSON array de flags detectados

    # Patrones detectados
    unusual_amount = db.Column(db.Boolean, default=False)  # Monto inusual
    unusual_frequency = db.Column(db.Boolean, default=False)  # Frecuencia inusual
    structuring = db.Column(db.Boolean, default=False)  # Posible estructuración (smurfing)
    rapid_movement = db.Column(db.Boolean, default=False)  # Movimiento rápido de fondos

    # Contexto
    client_avg_amount = db.Column(db.Numeric(15, 2))  # Monto promedio del cliente
    deviation_percentage = db.Column(db.Numeric(10, 2))  # % de desviación del promedio

    # Timestamps
    analyzed_at = db.Column(db.DateTime, default=now_peru)

    # Relaciones
    operation = db.relationship('Operation', backref='monitoring')
    client = db.relationship('Client', backref='transaction_monitoring')

    def __repr__(self):
        return f'<TransactionMonitoring operation_id={self.operation_id} risk_score={self.risk_score}>'


class ComplianceDocument(db.Model):
    """Documentos de compliance (reportes UIF, due diligence, etc.)"""

    __tablename__ = 'compliance_documents'

    id = db.Column(db.Integer, primary_key=True)

    # Tipo de documento
    document_type = db.Column(db.String(100), nullable=False)  # ROS, Due_Diligence, KYC_Report, etc.
    title = db.Column(db.String(200), nullable=False)

    # Entidad relacionada
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    operation_id = db.Column(db.Integer, db.ForeignKey('operations.id'))
    alert_id = db.Column(db.Integer, db.ForeignKey('compliance_alerts.id'))

    # Documento
    file_url = db.Column(db.String(500))  # URL en Cloudinary u otro storage
    file_name = db.Column(db.String(255))
    content = db.Column(db.Text)  # Contenido del reporte (si es texto)

    # Metadata
    status = db.Column(db.String(50), default='Borrador')  # Borrador, Enviado, Archivado
    sent_to_uif = db.Column(db.Boolean, default=False)  # Si fue enviado a UIF
    sent_at = db.Column(db.DateTime)

    # Creación
    created_at = db.Column(db.DateTime, default=now_peru)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relaciones
    client = db.relationship('Client', backref='compliance_documents')
    operation = db.relationship('Operation', backref='compliance_documents')
    alert = db.relationship('ComplianceAlert', backref='documents')
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<ComplianceDocument {self.document_type} - {self.title}>'


class ComplianceAudit(db.Model):
    """Auditoría de acciones de compliance"""

    __tablename__ = 'compliance_audit'

    id = db.Column(db.Integer, primary_key=True)

    # Usuario que realizó la acción
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Tipo de acción
    action_type = db.Column(db.String(100), nullable=False)  # KYC_Review, Alert_Resolution, Rule_Creation, etc.
    entity_type = db.Column(db.String(50))  # Client, Operation, Alert, Rule
    entity_id = db.Column(db.Integer)

    # Detalles
    description = db.Column(db.Text)
    changes = db.Column(db.Text)  # JSON con cambios realizados

    # Metadata
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=now_peru)

    # Relaciones
    user = db.relationship('User', backref='compliance_audits')

    def __repr__(self):
        return f'<ComplianceAudit {self.action_type} by user {self.user_id}>'

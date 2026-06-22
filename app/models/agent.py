"""
Modelos para el Ecosistema de Agentes IA — QoriCash
Tablas: agent_status, agent_logs, agent_alerts, agent_metrics
"""
from app.extensions import db
from app.utils.formatters import now_peru


class AgentStatus(db.Model):
    """Estado en tiempo real de cada agente."""
    __tablename__ = 'agent_status'

    id             = db.Column(db.Integer, primary_key=True)
    agent_id       = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name           = db.Column(db.String(100), nullable=False)
    description    = db.Column(db.String(300))
    icon           = db.Column(db.String(50))        # bootstrap icon class
    color          = db.Column(db.String(20))        # blue | green | purple | amber | red | teal | navy

    # Estado: idle | running | warning | error | stopped | disabled
    status         = db.Column(db.String(20), default='idle', nullable=False, index=True)
    last_run       = db.Column(db.DateTime, nullable=True)
    next_run       = db.Column(db.DateTime, nullable=True)
    run_interval   = db.Column(db.Integer, default=900)  # segundos entre ejecuciones

    # Métricas acumuladas del día
    tasks_today    = db.Column(db.Integer, default=0)
    errors_today   = db.Column(db.Integer, default=0)
    total_tasks    = db.Column(db.Integer, default=0)
    total_errors   = db.Column(db.Integer, default=0)

    # Última ejecución
    last_result    = db.Column(db.Text, nullable=True)   # resumen del último run
    last_error     = db.Column(db.Text, nullable=True)   # último error

    # Control manual
    enabled        = db.Column(db.Boolean, default=True, nullable=False)
    paused_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    paused_at      = db.Column(db.DateTime, nullable=True)

    # Rendimiento (0-100)
    performance    = db.Column(db.Float, default=100.0)

    created_at     = db.Column(db.DateTime, default=now_peru)
    updated_at     = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    pauser = db.relationship('User', foreign_keys=[paused_by])
    logs   = db.relationship('AgentLog', backref='agent', lazy='dynamic',
                             order_by='AgentLog.created_at.desc()')
    alerts = db.relationship('AgentAlert', backref='agent', lazy='dynamic')

    @property
    def status_class(self):
        return {
            'running': 'success',
            'idle':    'secondary',
            'warning': 'warning',
            'error':   'danger',
            'stopped': 'dark',
            'disabled':'light',
        }.get(self.status, 'secondary')

    def to_dict(self):
        return {
            'agent_id':    self.agent_id,
            'name':        self.name,
            'description': self.description or '',
            'icon':        self.icon or 'bi-robot',
            'color':       self.color or 'blue',
            'status':      self.status,
            'enabled':     self.enabled,
            'last_run':    self.last_run.strftime('%d/%m %H:%M') if self.last_run else '—',
            'last_run_iso':self.last_run.isoformat() if self.last_run else None,
            'next_run':    self.next_run.strftime('%d/%m %H:%M') if self.next_run else '—',
            'next_run_iso':self.next_run.isoformat() if self.next_run else None,
            'tasks_today': self.tasks_today,
            'errors_today':self.errors_today,
            'total_tasks': self.total_tasks,
            'total_errors':self.total_errors,
            'last_result': self.last_result or '',
            'last_error':  self.last_error or '',
            'performance': round(self.performance or 100.0, 1),
            'run_interval':self.run_interval,
        }


class AgentLog(db.Model):
    """Log de actividad en tiempo real de todos los agentes."""
    __tablename__ = 'agent_logs'

    id         = db.Column(db.Integer, primary_key=True)
    agent_id   = db.Column(db.String(50), db.ForeignKey('agent_status.agent_id'),
                           nullable=False, index=True)
    level      = db.Column(db.String(10), default='INFO', index=True)
    # INFO | SUCCESS | WARNING | ERROR | DEBUG
    message    = db.Column(db.Text, nullable=False)
    detail     = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=now_peru, index=True)

    def to_dict(self):
        return {
            'id':         self.id,
            'agent_id':   self.agent_id,
            'level':      self.level,
            'message':    self.message,
            'detail':     self.detail or '',
            'created_at': self.created_at.strftime('%H:%M:%S') if self.created_at else '',
            'created_iso':self.created_at.isoformat() if self.created_at else '',
        }


class AgentAlert(db.Model):
    """Alertas generadas por el Supervisor Agent."""
    __tablename__ = 'agent_alerts'

    id          = db.Column(db.Integer, primary_key=True)
    agent_id    = db.Column(db.String(50), db.ForeignKey('agent_status.agent_id'),
                            nullable=True, index=True)
    severity    = db.Column(db.String(20), default='warning', index=True)
    # info | warning | error | critical
    title       = db.Column(db.String(200), nullable=False)
    message     = db.Column(db.Text, nullable=False)
    resolved    = db.Column(db.Boolean, default=False, index=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at  = db.Column(db.DateTime, default=now_peru, index=True)

    resolver = db.relationship('User', foreign_keys=[resolved_by])

    @property
    def severity_class(self):
        return {
            'critical': 'danger',
            'error':    'danger',
            'warning':  'warning',
            'info':     'info',
        }.get(self.severity, 'secondary')

    def to_dict(self):
        return {
            'id':         self.id,
            'agent_id':   self.agent_id or '',
            'severity':   self.severity,
            'title':      self.title,
            'message':    self.message,
            'resolved':   self.resolved,
            'created_at': self.created_at.strftime('%d/%m %H:%M') if self.created_at else '',
            'created_iso':self.created_at.isoformat() if self.created_at else '',
        }


class AgentMetric(db.Model):
    """Métricas diarias por agente para dashboards ejecutivos."""
    __tablename__ = 'agent_metrics'

    id              = db.Column(db.Integer, primary_key=True)
    agent_id        = db.Column(db.String(50), nullable=False, index=True)
    date            = db.Column(db.Date, nullable=False, index=True)

    # Contadores del día
    runs            = db.Column(db.Integer, default=0)
    tasks_completed = db.Column(db.Integer, default=0)
    errors          = db.Column(db.Integer, default=0)

    # Métricas de negocio (cada agente llena los que corresponden)
    prospects_found     = db.Column(db.Integer, default=0)   # Lead Discovery
    prospects_validated = db.Column(db.Integer, default=0)   # Data Quality
    emails_sent         = db.Column(db.Integer, default=0)   # Mail Agent
    emails_analyzed     = db.Column(db.Integer, default=0)   # Email Intelligence
    bounces_detected    = db.Column(db.Integer, default=0)   # Email Intelligence
    opportunities       = db.Column(db.Integer, default=0)   # Email Intelligence
    duplicates_removed  = db.Column(db.Integer, default=0)   # Data Quality
    followups_scheduled = db.Column(db.Integer, default=0)   # Outreach

    created_at      = db.Column(db.DateTime, default=now_peru)

    __table_args__ = (
        db.UniqueConstraint('agent_id', 'date', name='uq_agent_metric_day'),
    )

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

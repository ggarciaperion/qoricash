"""
AuditReport — Resultado de cada ejecución del Agente Contable IA.

Cada ejecución diaria genera un registro con:
  - estado global  : APROBADO | OBSERVADO | CRÍTICO
  - hallazgos JSON : lista de inconsistencias detectadas
  - métricas JSON  : KPIs financieros del día/período
  - acciones JSON  : correcciones automáticas aplicadas

El agente NUNCA modifica datos contables; solo registra hallazgos y genera alertas.
Toda corrección requiere intervención humana (acción sugerida en el hallazgo).
"""
import json
from datetime import date
from app.extensions import db
from app.utils.formatters import now_peru


ESTADO_APROBADO  = 'APROBADO'
ESTADO_OBSERVADO = 'OBSERVADO'
ESTADO_CRITICO   = 'CRÍTICO'

SEVERIDAD_INFO     = 'INFO'
SEVERIDAD_ALERTA   = 'ALERTA'
SEVERIDAD_CRITICO  = 'CRÍTICO'


class AuditReport(db.Model):
    """Reporte de auditoría contable diario generado por el Agente IA."""
    __tablename__ = 'audit_reports'

    id              = db.Column(db.Integer, primary_key=True)
    # Fecha auditada (no la de ejecución — puede diferir si se re-ejecuta)
    audit_date      = db.Column(db.Date, nullable=False, index=True)
    # Período contable auditado (YYYY-MM)
    period_label    = db.Column(db.String(10), nullable=True)
    # APROBADO | OBSERVADO | CRÍTICO
    estado          = db.Column(db.String(20), nullable=False, default=ESTADO_APROBADO)

    # ── Hallazgos ────────────────────────────────────────────────────────────
    # JSON: lista de {modulo, severidad, titulo, detalle, accion_sugerida}
    hallazgos_json  = db.Column(db.Text, default='[]')

    # ── Métricas financieras del día ─────────────────────────────────────────
    # JSON: {ingresos, gastos, utilidad_neta, ir_a_cuenta, saldos_banco, ...}
    metricas_json   = db.Column(db.Text, default='{}')

    # ── Conciliaciones ───────────────────────────────────────────────────────
    # JSON: {banco: {pcge, saldo_journal, saldo_tesoreria, diferencia, ok}}
    conciliacion_json = db.Column(db.Text, default='{}')

    # ── Resumen ejecutivo ────────────────────────────────────────────────────
    ops_sin_asiento         = db.Column(db.Integer, default=0)
    asientos_descuadrados   = db.Column(db.Integer, default=0)
    diferencias_banco       = db.Column(db.Integer, default=0)
    gastos_sin_comprobante  = db.Column(db.Integer, default=0)
    activos_sin_depreciar   = db.Column(db.Integer, default=0)
    total_hallazgos         = db.Column(db.Integer, default=0)
    hallazgos_criticos      = db.Column(db.Integer, default=0)

    # ── Métricas financieras planas (para queries rápidas) ───────────────────
    ingresos_pen            = db.Column(db.Numeric(18, 2), default=0)
    gastos_pen              = db.Column(db.Numeric(18, 2), default=0)
    utilidad_neta_pen       = db.Column(db.Numeric(18, 2), default=0)
    ir_pago_cuenta_pen      = db.Column(db.Numeric(18, 2), default=0)

    # ── Control de ejecución ─────────────────────────────────────────────────
    # manual | cron | api
    trigger             = db.Column(db.String(20), default='cron')
    # Tiempo de ejecución en segundos
    execution_seconds   = db.Column(db.Numeric(8, 2), nullable=True)
    error_message       = db.Column(db.Text, nullable=True)

    executed_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=now_peru, nullable=False)

    executor = db.relationship('User', foreign_keys=[executed_by])

    __table_args__ = (
        db.Index('idx_audit_date_estado', 'audit_date', 'estado'),
    )

    # ── Propiedades ──────────────────────────────────────────────────────────

    @property
    def hallazgos(self) -> list:
        try:
            return json.loads(self.hallazgos_json or '[]')
        except Exception:
            return []

    @hallazgos.setter
    def hallazgos(self, val: list):
        self.hallazgos_json = json.dumps(val, ensure_ascii=False, default=str)

    @property
    def metricas(self) -> dict:
        try:
            return json.loads(self.metricas_json or '{}')
        except Exception:
            return {}

    @metricas.setter
    def metricas(self, val: dict):
        self.metricas_json = json.dumps(val, ensure_ascii=False, default=str)

    @property
    def conciliacion(self) -> dict:
        try:
            return json.loads(self.conciliacion_json or '{}')
        except Exception:
            return {}

    @conciliacion.setter
    def conciliacion(self, val: dict):
        self.conciliacion_json = json.dumps(val, ensure_ascii=False, default=str)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def add_hallazgo(self, modulo: str, severidad: str, titulo: str,
                     detalle: str, accion: str = None):
        """Agrega un hallazgo y actualiza contadores."""
        h = self.hallazgos
        h.append({
            'modulo':           modulo,
            'severidad':        severidad,
            'titulo':           titulo,
            'detalle':          detalle,
            'accion_sugerida':  accion or '',
        })
        self.hallazgos = h
        self.total_hallazgos = len(h)
        self.hallazgos_criticos = sum(
            1 for x in h if x.get('severidad') == SEVERIDAD_CRITICO
        )
        # Actualizar estado global
        if any(x['severidad'] == SEVERIDAD_CRITICO for x in h):
            self.estado = ESTADO_CRITICO
        elif any(x['severidad'] == SEVERIDAD_ALERTA for x in h):
            if self.estado != ESTADO_CRITICO:
                self.estado = ESTADO_OBSERVADO

    def to_dict(self) -> dict:
        return {
            'id':                       self.id,
            'audit_date':               self.audit_date.isoformat() if self.audit_date else None,
            'period_label':             self.period_label,
            'estado':                   self.estado,
            'hallazgos':                self.hallazgos,
            'metricas':                 self.metricas,
            'conciliacion':             self.conciliacion,
            'ops_sin_asiento':          self.ops_sin_asiento,
            'asientos_descuadrados':    self.asientos_descuadrados,
            'diferencias_banco':        self.diferencias_banco,
            'gastos_sin_comprobante':   self.gastos_sin_comprobante,
            'activos_sin_depreciar':    self.activos_sin_depreciar,
            'total_hallazgos':          self.total_hallazgos,
            'hallazgos_criticos':       self.hallazgos_criticos,
            'ingresos_pen':             float(self.ingresos_pen or 0),
            'gastos_pen':               float(self.gastos_pen or 0),
            'utilidad_neta_pen':        float(self.utilidad_neta_pen or 0),
            'ir_pago_cuenta_pen':       float(self.ir_pago_cuenta_pen or 0),
            'trigger':                  self.trigger,
            'execution_seconds':        float(self.execution_seconds or 0),
            'error_message':            self.error_message,
            'created_at':               self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<AuditReport {self.audit_date} [{self.estado}] {self.total_hallazgos} hallazgos>'

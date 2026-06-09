"""
DailyClosure — Cierre Diario de Tesorería
==========================================
Registro del proceso obligatorio de cierre al final de cada día operativo.

Flujo:
  1. El sistema calcula automáticamente saldos esperados por banco/moneda.
  2. El usuario ingresa los saldos reales (del estado de cuenta bancario).
  3. El sistema compara y muestra diferencias.
  4. El usuario confirma el cierre con notas (si hay diferencias, debe explicarlas).
  5. El cierre queda VALIDADO — sin cierre validado no se puede operar al día siguiente.

Estructura de saldos (JSON):
  {
    "BCP": {"USD": 12450.00, "PEN": 34200.00},
    "INTERBANK": {"USD": 8200.00, "PEN": 21000.00},
    "BANBIF": {"USD": 3100.00, "PEN": 9500.00}
  }
"""
import json
from app.extensions import db
from app.utils.formatters import now_peru


class DailyClosure(db.Model):
    __tablename__ = 'daily_closures'

    STATUS_BORRADOR = 'borrador'   # calculado, pendiente de validar
    STATUS_VALIDADO = 'validado'   # aprobado por el responsable

    # ── PK ────────────────────────────────────────────────────────────────
    id           = db.Column(db.Integer, primary_key=True)
    closure_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    status       = db.Column(db.String(20), nullable=False, default='borrador')

    # ── Saldos del sistema (calculados automáticamente) ───────────────────
    system_balances_json    = db.Column(db.Text, default='{}')
    # Saldos reales ingresados manualmente por el responsable
    validated_balances_json = db.Column(db.Text, default='{}')
    # Diferencias: real − sistema (negativo = sistema sobrestimado)
    differences_json        = db.Column(db.Text, default='{}')

    # ── Resumen operativo del día ──────────────────────────────────────────
    operations_completed  = db.Column(db.Integer,       default=0)
    total_volume_usd      = db.Column(db.Numeric(15, 2), default=0)
    total_bought_usd      = db.Column(db.Numeric(15, 2), default=0)  # compras completadas
    total_sold_usd        = db.Column(db.Numeric(15, 2), default=0)  # ventas completadas
    avg_buy_rate          = db.Column(db.Numeric(10, 4), default=0)  # TC promedio compra
    avg_sell_rate         = db.Column(db.Numeric(10, 4), default=0)  # TC promedio venta

    # ── P&L del día ───────────────────────────────────────────────────────
    gross_spread_pen      = db.Column(db.Numeric(15, 2), default=0)  # utilidad bruta (amarres del día)
    expenses_pen          = db.Column(db.Numeric(15, 2), default=0)  # gastos del día
    net_profit_pen        = db.Column(db.Numeric(15, 2), default=0)  # neto = spread - gastos

    # ── Posición pendiente al cierre ──────────────────────────────────────
    pending_operations        = db.Column(db.Integer,       default=0)  # ops sin completar
    unmatched_completed_usd   = db.Column(db.Numeric(15, 2), default=0)  # USD completada sin amarrar
    open_matches              = db.Column(db.Integer,       default=0)  # amarres sin batch cerrado

    # ── Discrepancias ─────────────────────────────────────────────────────
    has_discrepancies    = db.Column(db.Boolean, default=False)
    max_discrepancy_usd  = db.Column(db.Numeric(15, 2), default=0)
    max_discrepancy_pen  = db.Column(db.Numeric(15, 2), default=0)
    discrepancy_reason   = db.Column(db.Text)

    # ── Notas ─────────────────────────────────────────────────────────────
    notes = db.Column(db.Text)

    # ── Saldo Inicial del Día (apertura) ──────────────────────────────────────
    # Se registra una vez al inicio de la jornada. No sobreescribible.
    opening_balance_json   = db.Column(db.Text, default='{}')
    opening_total_usd      = db.Column(db.Numeric(15, 2), default=0)
    opening_total_pen      = db.Column(db.Numeric(15, 2), default=0)
    opening_registered_at  = db.Column(db.DateTime, nullable=True)
    opening_registered_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # ── Saldo Final del Día (cierre de caja) ─────────────────────────────────
    closing_balance_json   = db.Column(db.Text, default='{}')
    closing_total_usd      = db.Column(db.Numeric(15, 2), default=0)
    closing_total_pen      = db.Column(db.Numeric(15, 2), default=0)
    closing_registered_at  = db.Column(db.DateTime, nullable=True)
    closing_registered_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # ── Resultado del día (closing - opening) ─────────────────────────────────
    result_usd    = db.Column(db.Numeric(15, 2), nullable=True)
    result_pen    = db.Column(db.Numeric(15, 2), nullable=True)
    result_label  = db.Column(db.String(20), nullable=True)  # utilidad | perdida | cuadre

    # ── Validación ────────────────────────────────────────────────────────
    validated_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    validated_at  = db.Column(db.DateTime, nullable=True)

    # ── Metadata ──────────────────────────────────────────────────────────
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=now_peru)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    # ── Relaciones ────────────────────────────────────────────────────────
    validator      = db.relationship('User', foreign_keys=[validated_by])
    creator        = db.relationship('User', foreign_keys=[created_by])
    opener         = db.relationship('User', foreign_keys=[opening_registered_by])
    closer         = db.relationship('User', foreign_keys=[closing_registered_by])

    # ── Propiedades de conveniencia ───────────────────────────────────────
    @property
    def opening_balance(self):
        try:
            return json.loads(self.opening_balance_json or '{}')
        except Exception:
            return {}

    @opening_balance.setter
    def opening_balance(self, val):
        self.opening_balance_json = json.dumps(val)

    @property
    def closing_balance(self):
        try:
            return json.loads(self.closing_balance_json or '{}')
        except Exception:
            return {}

    @closing_balance.setter
    def closing_balance(self, val):
        self.closing_balance_json = json.dumps(val)

    @property
    def system_balances(self):
        try:
            return json.loads(self.system_balances_json or '{}')
        except Exception:
            return {}

    @system_balances.setter
    def system_balances(self, val):
        self.system_balances_json = json.dumps(val)

    @property
    def validated_balances(self):
        try:
            return json.loads(self.validated_balances_json or '{}')
        except Exception:
            return {}

    @validated_balances.setter
    def validated_balances(self, val):
        self.validated_balances_json = json.dumps(val)

    @property
    def differences(self):
        try:
            return json.loads(self.differences_json or '{}')
        except Exception:
            return {}

    @differences.setter
    def differences(self, val):
        self.differences_json = json.dumps(val)

    @property
    def is_validated(self):
        return self.status == self.STATUS_VALIDADO

    def compute_result(self):
        """
        Calcula resultado = saldo final - saldo inicial.
        Actualiza result_usd, result_pen, result_label.
        """
        if not self.opening_balance_json or self.opening_balance_json == '{}':
            return None
        if not self.closing_balance_json or self.closing_balance_json == '{}':
            return None

        op_usd = float(self.opening_total_usd or 0)
        op_pen = float(self.opening_total_pen or 0)
        cl_usd = float(self.closing_total_usd or 0)
        cl_pen = float(self.closing_total_pen or 0)

        self.result_usd = round(cl_usd - op_usd, 2)
        self.result_pen = round(cl_pen - op_pen, 2)

        r_pen = float(self.result_pen)
        if abs(r_pen) < 0.01:
            self.result_label = 'cuadre'
        elif r_pen > 0:
            self.result_label = 'utilidad'
        else:
            self.result_label = 'perdida'

        return {
            'result_usd':   float(self.result_usd),
            'result_pen':   float(self.result_pen),
            'result_label': self.result_label,
        }

    def compute_differences(self):
        """
        Calcula diferencias = saldos_reales - saldos_sistema y actualiza
        has_discrepancies, max_discrepancy_usd, max_discrepancy_pen.
        Retorna el dict de diferencias.
        """
        sys_b = self.system_balances
        val_b = self.validated_balances
        diffs = {}
        max_usd = 0.0
        max_pen = 0.0

        for banco in ['BCP', 'INTERBANK', 'BANBIF']:
            diffs[banco] = {}
            for cur in ['USD', 'PEN']:
                sys_val = float((sys_b.get(banco) or {}).get(cur, 0) or 0)
                val_val = float((val_b.get(banco) or {}).get(cur, 0) or 0)
                diff    = round(val_val - sys_val, 2)
                diffs[banco][cur] = diff
                if cur == 'USD':
                    max_usd = max(max_usd, abs(diff))
                else:
                    max_pen = max(max_pen, abs(diff))

        self.differences         = diffs
        self.max_discrepancy_usd = max_usd
        self.max_discrepancy_pen = max_pen
        self.has_discrepancies   = (max_usd > 0.01 or max_pen > 0.01)
        return diffs

    def to_dict(self):
        return {
            'id':                        self.id,
            'closure_date':              self.closure_date.isoformat() if self.closure_date else None,
            'status':                    self.status,
            'is_validated':              self.is_validated,
            'system_balances':           self.system_balances,
            'validated_balances':        self.validated_balances,
            'differences':               self.differences,
            'operations_completed':      self.operations_completed,
            'total_volume_usd':          float(self.total_volume_usd or 0),
            'total_bought_usd':          float(self.total_bought_usd or 0),
            'total_sold_usd':            float(self.total_sold_usd or 0),
            'avg_buy_rate':              float(self.avg_buy_rate or 0),
            'avg_sell_rate':             float(self.avg_sell_rate or 0),
            'gross_spread_pen':          float(self.gross_spread_pen or 0),
            'expenses_pen':              float(self.expenses_pen or 0),
            'net_profit_pen':            float(self.net_profit_pen or 0),
            'pending_operations':        self.pending_operations,
            'unmatched_completed_usd':   float(self.unmatched_completed_usd or 0),
            'open_matches':              self.open_matches,
            'has_discrepancies':         self.has_discrepancies,
            'max_discrepancy_usd':       float(self.max_discrepancy_usd or 0),
            'max_discrepancy_pen':       float(self.max_discrepancy_pen or 0),
            'discrepancy_reason':        self.discrepancy_reason,
            'notes':                     self.notes,
            'validated_by':              self.validator.username if self.validator else None,
            'validated_at':              self.validated_at.isoformat() if self.validated_at else None,
            'created_at':                self.created_at.isoformat() if self.created_at else None,
            # Saldo inicial / final / resultado
            'opening_balance':           self.opening_balance,
            'opening_total_usd':         float(self.opening_total_usd or 0),
            'opening_total_pen':         float(self.opening_total_pen or 0),
            'opening_registered_at':     self.opening_registered_at.isoformat() if self.opening_registered_at else None,
            'opening_registered_by':     self.opener.username if self.opener else None,
            'has_opening':               bool(self.opening_balance_json and self.opening_balance_json != '{}'),
            'closing_balance':           self.closing_balance,
            'closing_total_usd':         float(self.closing_total_usd or 0),
            'closing_total_pen':         float(self.closing_total_pen or 0),
            'closing_registered_at':     self.closing_registered_at.isoformat() if self.closing_registered_at else None,
            'closing_registered_by':     self.closer.username if self.closer else None,
            'has_closing':               bool(self.closing_balance_json and self.closing_balance_json != '{}'),
            'result_usd':                float(self.result_usd) if self.result_usd is not None else None,
            'result_pen':                float(self.result_pen) if self.result_pen is not None else None,
            'result_label':              self.result_label,
        }

    def __repr__(self):
        return f'<DailyClosure {self.closure_date} [{self.status}]>'

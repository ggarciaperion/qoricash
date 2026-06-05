"""
BankMovement — Libro Ledger de Movimientos Bancarios
=====================================================
Registro inmutable de CADA movimiento que afecta los saldos bancarios de QoriCash.
Es la única fuente de verdad para reconstruir saldos desde cero.

Cada operación completada genera 2 registros:
  Compra USD: entrada USD (depósito cliente) + salida PEN (pago QoriCash)
  Venta USD:  entrada PEN (depósito cliente) + salida USD (pago QoriCash)

Tipos de movimiento:
  op_entrada      — ingreso por operación de cambio
  op_salida       — egreso por operación de cambio
  ajuste_entrada  — ajuste manual de conciliación (entrada)
  ajuste_salida   — ajuste manual de conciliación (salida)
  transfer_entrada — transferencia interna entre cuentas propias (entrada)
  transfer_salida  — transferencia interna entre cuentas propias (salida)
  gasto            — egreso por gasto operativo
  saldo_inicial    — apertura de período / saldo inicial registrado
"""
from app.extensions import db
from app.utils.formatters import now_peru


class BankMovement(db.Model):
    __tablename__ = 'bank_movements'

    # ── Tipos de movimiento ────────────────────────────────────────────────
    TYPE_OP_ENTRADA        = 'op_entrada'
    TYPE_OP_SALIDA         = 'op_salida'
    TYPE_AJUSTE_ENTRADA    = 'ajuste_entrada'
    TYPE_AJUSTE_SALIDA     = 'ajuste_salida'
    TYPE_TRANSFER_ENTRADA  = 'transfer_entrada'
    TYPE_TRANSFER_SALIDA   = 'transfer_salida'
    TYPE_GASTO             = 'gasto'
    TYPE_SALDO_INICIAL     = 'saldo_inicial'

    LABELS = {
        'op_entrada':       'Ingreso por operación',
        'op_salida':        'Egreso por operación',
        'ajuste_entrada':   'Ajuste de entrada',
        'ajuste_salida':    'Ajuste de salida',
        'transfer_entrada': 'Transferencia interna (entrada)',
        'transfer_salida':  'Transferencia interna (salida)',
        'gasto':            'Gasto operativo',
        'saldo_inicial':    'Saldo inicial',
    }

    # ── PK ────────────────────────────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)

    # ── Identidad del movimiento ───────────────────────────────────────────
    movement_date = db.Column(db.DateTime, nullable=False, default=now_peru, index=True)
    bank_name     = db.Column(db.String(100), nullable=False, index=True)
    # banco canónico: BCP | INTERBANK | BANBIF (para filtrar/agrupar)
    bank_key      = db.Column(db.String(20),  nullable=False, index=True)
    currency      = db.Column(db.String(3),   nullable=False)   # USD | PEN
    # positivo = entrada, negativo = salida
    amount        = db.Column(db.Numeric(15, 2), nullable=False)
    movement_type = db.Column(db.String(50), nullable=False)

    # ── Origen ────────────────────────────────────────────────────────────
    source_type    = db.Column(db.String(50))     # operation | adjustment | transfer | expense
    source_id      = db.Column(db.Integer)         # ID del registro origen
    operation_id   = db.Column(db.Integer, db.ForeignKey('operations.id'), nullable=True, index=True)

    # ── Descriptores ──────────────────────────────────────────────────────
    description    = db.Column(db.String(500))
    reference_code = db.Column(db.String(100))    # código op, nro transferencia, nro cheque…
    counterpart    = db.Column(db.String(200))     # cliente, proveedor, banco destino

    # ── Saldo corriente DESPUÉS del movimiento ────────────────────────────
    # Se calcula y almacena al crear el registro; permite auditar la evolución
    balance_after  = db.Column(db.Numeric(15, 2))

    # ── Auditoría ─────────────────────────────────────────────────────────
    created_by     = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at     = db.Column(db.DateTime, default=now_peru)
    is_validated   = db.Column(db.Boolean, default=False)
    closure_date   = db.Column(db.Date, index=True)   # fecha del cierre diario asociado

    # ── Relaciones ────────────────────────────────────────────────────────
    operation = db.relationship('Operation', backref='bank_movements', lazy='select')
    creator   = db.relationship('User', foreign_keys=[created_by], lazy='select')

    # ── Índices compuestos ────────────────────────────────────────────────
    __table_args__ = (
        db.Index('ix_bm_bank_currency_date', 'bank_key', 'currency', 'movement_date'),
        db.Index('ix_bm_closure_date',       'closure_date'),
    )

    # ── API ───────────────────────────────────────────────────────────────
    def to_dict(self):
        return {
            'id':             self.id,
            'movement_date':  self.movement_date.isoformat() if self.movement_date else None,
            'bank_name':      self.bank_name,
            'bank_key':       self.bank_key,
            'currency':       self.currency,
            'amount':         float(self.amount),
            'movement_type':  self.movement_type,
            'movement_label': self.LABELS.get(self.movement_type, self.movement_type),
            'source_type':    self.source_type,
            'source_id':      self.source_id,
            'description':    self.description,
            'reference_code': self.reference_code,
            'counterpart':    self.counterpart,
            'balance_after':  float(self.balance_after) if self.balance_after is not None else None,
            'created_at':     self.created_at.isoformat() if self.created_at else None,
            'is_validated':   self.is_validated,
        }

    @staticmethod
    def compute_running_balance(bank_key: str, currency: str, up_to_id: int = None,
                                up_to_date=None) -> float:
        """
        Calcula el saldo acumulado desde el primer movimiento.
        Útil para reconstruir la posición en cualquier punto del tiempo.
        """
        from sqlalchemy import func
        q = BankMovement.query.filter(
            BankMovement.bank_key == bank_key,
            BankMovement.currency == currency,
        )
        if up_to_id:
            q = q.filter(BankMovement.id <= up_to_id)
        if up_to_date:
            q = q.filter(BankMovement.movement_date <= up_to_date)
        result = q.with_entities(func.sum(BankMovement.amount)).scalar()
        return float(result or 0)

    @staticmethod
    def get_movements_for_day(date_val, bank_key=None, currency=None):
        """Movimientos de un día específico, con filtros opcionales."""
        from datetime import datetime, timedelta
        start = datetime.combine(date_val, datetime.min.time())
        end   = start + timedelta(days=1)
        q = BankMovement.query.filter(
            BankMovement.movement_date >= start,
            BankMovement.movement_date <  end,
        )
        if bank_key:
            q = q.filter(BankMovement.bank_key == bank_key)
        if currency:
            q = q.filter(BankMovement.currency == currency)
        return q.order_by(BankMovement.movement_date.asc()).all()

    def __repr__(self):
        sign = '+' if float(self.amount) >= 0 else ''
        return f'<BankMovement {self.bank_key} {self.currency} {sign}{self.amount} [{self.movement_type}]>'

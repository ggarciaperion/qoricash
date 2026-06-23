"""
InternalTransfer — Traslados Internos de Fondos Propios
=======================================================
Registro de movimientos de dinero entre las cuentas bancarias de QoriCash.
Ejemplo: mover USD de BCP a INTERBANK, o PEN de INTERBANK a BANBIF.

Cada traslado genera:
  - 1 BankMovement tipo transfer_salida (cuenta origen)
  - 1 BankMovement tipo transfer_entrada (cuenta destino)
  - 1 JournalEntry con partida doble (+ líneas de comisión/ITF si aplica)
"""
from decimal import Decimal
from app.extensions import db
from app.utils.formatters import now_peru


class InternalTransfer(db.Model):
    __tablename__ = 'internal_transfers'

    # ── PK ───────────────────────────────────────────────────────────────────
    id              = db.Column(db.Integer, primary_key=True)
    transfer_code   = db.Column(db.String(30), unique=True, nullable=False, index=True)
    transfer_date   = db.Column(db.DateTime, nullable=False, default=now_peru, index=True)

    # ── Origen ───────────────────────────────────────────────────────────────
    origin_bank     = db.Column(db.String(20), nullable=False)   # BCP | INTERBANK | BANBIF
    origin_currency = db.Column(db.String(3),  nullable=False)   # USD | PEN
    origin_account  = db.Column(db.String(120), nullable=False)  # "BCP USD (1917357790119)"

    # ── Destino ──────────────────────────────────────────────────────────────
    dest_bank       = db.Column(db.String(20), nullable=False)
    dest_currency   = db.Column(db.String(3),  nullable=False)
    dest_account    = db.Column(db.String(120), nullable=False)

    # ── Montos (en la moneda de la cuenta de origen) ──────────────────────
    amount          = db.Column(db.Numeric(15, 2), nullable=False)  # llega al destino
    commission      = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    itf_amount      = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # ── Descriptores ─────────────────────────────────────────────────────────
    description     = db.Column(db.String(500))
    reference_code  = db.Column(db.String(100))   # nro operación bancaria

    # ── Vínculos contables ────────────────────────────────────────────────────
    journal_entry_id    = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True)
    movement_salida_id  = db.Column(db.Integer, db.ForeignKey('bank_movements.id'), nullable=True)
    movement_entrada_id = db.Column(db.Integer, db.ForeignKey('bank_movements.id'), nullable=True)

    # ── Estado ───────────────────────────────────────────────────────────────
    status          = db.Column(db.String(20), nullable=False, default='activo', index=True)
    # activo | anulado

    # ── Auditoría ─────────────────────────────────────────────────────────────
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=now_peru)
    anulado_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    anulado_at      = db.Column(db.DateTime, nullable=True)
    anulado_reason  = db.Column(db.String(500), nullable=True)

    # ── Relaciones ────────────────────────────────────────────────────────────
    creator         = db.relationship('User', foreign_keys=[created_by])
    anuler          = db.relationship('User', foreign_keys=[anulado_by])
    journal_entry   = db.relationship('JournalEntry', foreign_keys=[journal_entry_id])
    movement_salida = db.relationship('BankMovement', foreign_keys=[movement_salida_id])
    movement_entrada= db.relationship('BankMovement', foreign_keys=[movement_entrada_id])

    @property
    def total_debit(self) -> Decimal:
        """Total que sale de la cuenta de origen."""
        return (self.amount or Decimal('0')) + (self.commission or Decimal('0')) + (self.itf_amount or Decimal('0'))

    @classmethod
    def next_code(cls) -> str:
        """Genera un código secuencial IT-YYYYMMDD-NNNN."""
        from datetime import date
        today_str = date.today().strftime('%Y%m%d')
        prefix = f'IT-{today_str}-'
        last = (cls.query
                .filter(cls.transfer_code.like(f'{prefix}%'))
                .order_by(cls.id.desc())
                .first())
        seq = 1
        if last:
            try:
                seq = int(last.transfer_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                pass
        return f'{prefix}{seq:04d}'

    def to_dict(self) -> dict:
        return {
            'id':               self.id,
            'transfer_code':    self.transfer_code,
            'transfer_date':    self.transfer_date.isoformat() if self.transfer_date else None,
            'origin_bank':      self.origin_bank,
            'origin_currency':  self.origin_currency,
            'origin_account':   self.origin_account,
            'dest_bank':        self.dest_bank,
            'dest_currency':    self.dest_currency,
            'dest_account':     self.dest_account,
            'amount':           float(self.amount),
            'commission':       float(self.commission),
            'itf_amount':       float(self.itf_amount),
            'total_debit':      float(self.total_debit),
            'description':      self.description or '',
            'reference_code':   self.reference_code or '',
            'journal_entry_id': self.journal_entry_id,
            'movement_salida_id':  self.movement_salida_id,
            'movement_entrada_id': self.movement_entrada_id,
            'status':           self.status,
            'created_by':       self.creator.username if self.creator else None,
            'created_at':       self.created_at.isoformat() if self.created_at else None,
            'anulado_reason':   self.anulado_reason or '',
            'anulado_at':       self.anulado_at.isoformat() if self.anulado_at else None,
        }

    def __repr__(self):
        return f'<InternalTransfer {self.transfer_code} {self.origin_account} → {self.dest_account} {self.amount}>'

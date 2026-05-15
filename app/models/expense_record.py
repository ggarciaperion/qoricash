"""
Registro de gastos / egresos.
Cada registro genera automáticamente un asiento en el Libro Diario.

Tipos de gasto (expense_type):
  servicio    → cuenta 6xxx (telecomunicaciones, honorarios, comisiones, etc.)
  activo_fijo → cuenta 33xx (muebles, equipos) — genera también registro en fixed_assets
  suministro  → cuenta 6xxx (útiles de oficina, materiales)
  planilla    → cuenta 62x  (remuneraciones, EsSalud, AFP)
  tributo     → cuenta 64x  (IR pago a cuenta, ITF, etc.)

IGV en gastos (casa de cambio):
  Las casas de cambio están exoneradas de IGV en su actividad principal
  (Art. 2 TUO Ley IGV). En consecuencia, el IGV pagado en compras NO puede
  usarse como crédito fiscal y se activa como COSTO del gasto.
  Si en el futuro se genera IGV deducible (prorrata), activar credito_fiscal=True.
"""
from app.utils.formatters import now_peru
from app.extensions import db


class ExpenseRecord(db.Model):
    __tablename__ = 'expense_records'

    id               = db.Column(db.Integer, primary_key=True)
    period_id        = db.Column(db.Integer, db.ForeignKey('accounting_periods.id'), nullable=False, index=True)
    expense_date     = db.Column(db.Date, nullable=False)
    # Código PCGE de la cuenta de gasto: '6391', '6381', '621', '3361', etc.
    category         = db.Column(db.String(50), nullable=False)
    description      = db.Column(db.Text, nullable=False)
    # amount_pen = total del comprobante (base + IGV si aplica)
    amount_pen       = db.Column(db.Numeric(18, 2), nullable=False)
    # Desglose IGV (Phase 2)
    base_pen         = db.Column(db.Numeric(18, 2), nullable=True)   # importe sin IGV
    igv_pen          = db.Column(db.Numeric(18, 2), nullable=True)   # IGV 18%
    # True si el IGV es recuperable como crédito fiscal (por defecto False para CdC)
    credito_fiscal   = db.Column(db.Boolean, default=False)
    # Clasificación del desembolso
    # servicio | activo_fijo | suministro | planilla | tributo
    expense_type     = db.Column(db.String(20), default='servicio')
    # Si el gasto es en USD, se convierte a PEN
    amount_usd       = db.Column(db.Numeric(18, 2), nullable=True)
    exchange_rate_used = db.Column(db.Numeric(10, 4), nullable=True)
    # factura | boleta | recibo | planilla
    voucher_type     = db.Column(db.String(30), nullable=True)
    voucher_number   = db.Column(db.String(50), nullable=True)
    supplier_ruc     = db.Column(db.String(20), nullable=True)
    supplier_name    = db.Column(db.String(120), nullable=True)
    # URL Cloudinary del comprobante escaneado
    voucher_url      = db.Column(db.Text, nullable=True)
    # Asiento generado automáticamente al guardar
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True, index=True)
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at       = db.Column(db.DateTime, default=now_peru)

    period        = db.relationship('AccountingPeriod', foreign_keys=[period_id])
    journal_entry = db.relationship('JournalEntry', foreign_keys=[journal_entry_id])
    fixed_asset   = db.relationship('FixedAsset', back_populates='expense_record',
                                    uselist=False, lazy='select')

    def __repr__(self):
        return f'<ExpenseRecord {self.expense_date} {self.category} S/{self.amount_pen}>'

    @property
    def igv_efectivo(self):
        """IGV registrado (0 si no se desglosó)."""
        return self.igv_pen or 0

    @property
    def base_efectiva(self):
        """Base imponible (amount_pen si no se desglosó IGV)."""
        if self.base_pen is not None:
            return self.base_pen
        return self.amount_pen

    def to_dict(self):
        return {
            'id': self.id,
            'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'category': self.category,
            'expense_type': self.expense_type or 'servicio',
            'description': self.description,
            'amount_pen': float(self.amount_pen),
            'base_pen': float(self.base_pen) if self.base_pen else None,
            'igv_pen': float(self.igv_pen) if self.igv_pen else None,
            'credito_fiscal': self.credito_fiscal or False,
            'amount_usd': float(self.amount_usd) if self.amount_usd else None,
            'voucher_type': self.voucher_type,
            'voucher_number': self.voucher_number,
            'supplier_name': self.supplier_name,
            'supplier_ruc': self.supplier_ruc,
            'voucher_url': self.voucher_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

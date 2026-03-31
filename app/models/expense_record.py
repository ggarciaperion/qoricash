"""
Registro de gastos / egresos.
Cada registro genera automáticamente un asiento en el Libro Diario.
"""
from datetime import datetime
from app.extensions import db


class ExpenseRecord(db.Model):
    __tablename__ = 'expense_records'

    id               = db.Column(db.Integer, primary_key=True)
    period_id        = db.Column(db.Integer, db.ForeignKey('accounting_periods.id'), nullable=False)
    expense_date     = db.Column(db.Date, nullable=False)
    # Código PCGE de la cuenta de gasto: '6391', '6381', '621', etc.
    category         = db.Column(db.String(50), nullable=False)
    description      = db.Column(db.Text, nullable=False)
    amount_pen       = db.Column(db.Numeric(18, 2), nullable=False)
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
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=True)
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    period        = db.relationship('AccountingPeriod', foreign_keys=[period_id])
    journal_entry = db.relationship('JournalEntry', foreign_keys=[journal_entry_id])

    def __repr__(self):
        return f'<ExpenseRecord {self.expense_date} {self.category} S/{self.amount_pen}>'

    def to_dict(self):
        return {
            'id': self.id,
            'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'category': self.category,
            'description': self.description,
            'amount_pen': float(self.amount_pen),
            'amount_usd': float(self.amount_usd) if self.amount_usd else None,
            'voucher_type': self.voucher_type,
            'voucher_number': self.voucher_number,
            'supplier_name': self.supplier_name,
            'supplier_ruc': self.supplier_ruc,
            'voucher_url': self.voucher_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

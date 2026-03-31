"""
Líneas del Libro Diario (partidas individuales de cada asiento).
"""
from app.extensions import db


class JournalEntryLine(db.Model):
    __tablename__ = 'journal_entry_lines'

    id               = db.Column(db.Integer, primary_key=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False)
    # Código del PCGE: '1041', '7711', etc.
    account_code     = db.Column(db.String(10), nullable=False, index=True)
    description      = db.Column(db.Text, nullable=True)
    debe             = db.Column(db.Numeric(18, 2), default=0)
    haber            = db.Column(db.Numeric(18, 2), default=0)
    # PEN | USD
    currency         = db.Column(db.String(5), default='PEN')
    # Importe original en USD (si aplica), para trazabilidad
    amount_usd       = db.Column(db.Numeric(18, 2), nullable=True)
    # TC utilizado para convertir a PEN
    exchange_rate    = db.Column(db.Numeric(10, 4), nullable=True)
    line_order       = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f'<JournalEntryLine {self.account_code} D:{self.debe} H:{self.haber}>'

    def to_dict(self):
        return {
            'id': self.id,
            'account_code': self.account_code,
            'description': self.description,
            'debe': float(self.debe or 0),
            'haber': float(self.haber or 0),
            'currency': self.currency,
            'amount_usd': float(self.amount_usd) if self.amount_usd else None,
            'exchange_rate': float(self.exchange_rate) if self.exchange_rate else None,
            'line_order': self.line_order,
        }

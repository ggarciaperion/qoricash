"""
Libro Diario — Asientos contables (cabecera).
Cada asiento tiene N líneas (journal_entry_lines) con DEBE y HABER.
La suma de DEBE siempre debe igualar la suma de HABER (partida doble).
"""
from app.extensions import db
from app.utils.formatters import now_peru


class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'

    id             = db.Column(db.Integer, primary_key=True)
    # AS-2026-0001
    entry_number   = db.Column(db.String(20), unique=True, nullable=False)
    period_id      = db.Column(db.Integer, db.ForeignKey('accounting_periods.id'), nullable=False, index=True)
    entry_date     = db.Column(db.Date, nullable=False)
    description    = db.Column(db.Text, nullable=False)   # glosa
    # operacion_completada | calce_netting | gasto | ajuste_tc | pago_cuenta_ir | manual
    entry_type     = db.Column(db.String(30), nullable=False, index=True)
    # operation | match | batch | manual
    source_type    = db.Column(db.String(30), nullable=True)
    source_id      = db.Column(db.Integer, nullable=True)

    total_debe     = db.Column(db.Numeric(18, 2), nullable=False)
    total_haber    = db.Column(db.Numeric(18, 2), nullable=False)
    # activo | anulado
    status         = db.Column(db.String(20), default='activo')

    created_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_at     = db.Column(db.DateTime, default=now_peru)
    annulled_at    = db.Column(db.DateTime, nullable=True)
    annulled_by    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    annulled_reason = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.Index('idx_je_source', 'source_type', 'source_id'),
    )

    # Relaciones
    period  = db.relationship('AccountingPeriod', foreign_keys=[period_id])
    lines   = db.relationship(
        'JournalEntryLine',
        backref='entry',
        lazy='select',
        cascade='all, delete-orphan',
        order_by='JournalEntryLine.line_order',
    )

    def __repr__(self):
        return f'<JournalEntry {self.entry_number} [{self.entry_type}] {self.total_debe}>'

    def to_dict(self):
        return {
            'id': self.id,
            'entry_number': self.entry_number,
            'entry_date': self.entry_date.isoformat() if self.entry_date else None,
            'description': self.description,
            'entry_type': self.entry_type,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'total_debe': float(self.total_debe),
            'total_haber': float(self.total_haber),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'lines': [l.to_dict() for l in self.lines],
        }

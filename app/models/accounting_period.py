"""
Períodos contables mensuales.
Un período cerrado no acepta nuevos asientos.
"""
from app.extensions import db


class AccountingPeriod(db.Model):
    __tablename__ = 'accounting_periods'

    id         = db.Column(db.Integer, primary_key=True)
    year       = db.Column(db.Integer, nullable=False)
    month      = db.Column(db.Integer, nullable=False)       # 1–12
    # abierto | cerrado
    status     = db.Column(db.String(20), default='abierto')
    closed_at  = db.Column(db.DateTime, nullable=True)
    closed_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # TC SBS de cierre (usado para el ajuste FX NIC-21)
    tc_sbs_cierre  = db.Column(db.Numeric(10, 4), nullable=True)

    # Trazabilidad de reaperturas
    reopened_at    = db.Column(db.DateTime, nullable=True)
    reopened_by    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reopen_reason  = db.Column(db.String(500), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='uq_accounting_period_year_month'),
    )

    @property
    def label(self):
        months = ['Ene','Feb','Mar','Abr','May','Jun',
                  'Jul','Ago','Sep','Oct','Nov','Dic']
        return f"{months[self.month - 1]} {self.year}"

    def __repr__(self):
        return f'<AccountingPeriod {self.year}/{self.month:02d} [{self.status}]>'

    def to_dict(self):
        return {
            'id': self.id,
            'year': self.year,
            'month': self.month,
            'label': self.label,
            'status': self.status,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'tc_sbs_cierre': float(self.tc_sbs_cierre) if self.tc_sbs_cierre else None,
            'reopened_at': self.reopened_at.isoformat() if self.reopened_at else None,
        }

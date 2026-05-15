"""
Catálogo de cuentas contables — Plan Contable General Empresarial (PCGE)
Adaptado para QoriCash (Casa de Cambio)
"""
from app.extensions import db
from app.utils.formatters import now_peru


class AccountingAccount(db.Model):
    __tablename__ = 'accounting_accounts'

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(10), unique=True, nullable=False, index=True)
    name        = db.Column(db.String(120), nullable=False)
    # activo | pasivo | patrimonio | ingreso | gasto
    type        = db.Column(db.String(20), nullable=False)
    # deudora | acreedora
    nature      = db.Column(db.String(10), nullable=False)
    # PEN | USD | AMBAS
    currency    = db.Column(db.String(5), default='PEN')
    is_active   = db.Column(db.Boolean, default=True)
    parent_code = db.Column(db.String(10), nullable=True)
    created_at  = db.Column(db.DateTime, default=now_peru)

    def __repr__(self):
        return f'<AccountingAccount {self.code} – {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'type': self.type,
            'nature': self.nature,
            'currency': self.currency,
            'is_active': self.is_active,
            'parent_code': self.parent_code,
        }

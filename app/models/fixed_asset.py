"""
Control de Activos Fijos — QoriCash
====================================
Registra muebles, equipos de cómputo y equipos de oficina adquiridos
por la empresa. Cada activo tiene una vida útil, un método de depreciación
(solo lineal por ahora) y genera un asiento mensual de depreciación.

Cuentas PCGE usadas:
  Costo del activo  : 3351 (Muebles y enseres) | 3361 (Equipos cómputo) | 3362 (Equipos oficina)
  Deprec. acumulada : 3951 / 3961 / 3962  (contra-cuenta del activo)
  Gasto depreciac.  : 6814 (Depreciación de inmuebles, maquinaria y equipo)

Vida útil SII / SUNAT:
  Muebles y enseres       : 10 años (120 meses)
  Equipos de cómputo      :  4 años  (48 meses)
  Equipos de oficina      :  5 años  (60 meses)
"""
from datetime import datetime, date
from decimal import Decimal
from app.extensions import db


# ── Constantes PCGE ────────────────────────────────────────────────────────────
ASSET_CATEGORY_ACCOUNTS = {
    'mueble_enseres':    ('3351', '3951'),   # costo, deprec. acumulada
    'equipo_computo':    ('3361', '3961'),
    'equipo_oficina':    ('3362', '3962'),
    'instalaciones':     ('3321', '3921'),
}

ASSET_DEFAULT_LIFE = {
    'mueble_enseres':  120,   # meses
    'equipo_computo':   48,
    'equipo_oficina':   60,
    'instalaciones':   120,
}


class FixedAsset(db.Model):
    __tablename__ = 'fixed_assets'

    id                = db.Column(db.Integer, primary_key=True)
    # Código correlativo: FA-2026-001
    asset_code        = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name              = db.Column(db.String(200), nullable=False)
    # mueble_enseres | equipo_computo | equipo_oficina | instalaciones
    category          = db.Column(db.String(30), nullable=False)
    # Cuenta PCGE del activo (e.g. '3351')
    account_code      = db.Column(db.String(10), nullable=False)
    # Cuenta depreciación acumulada (e.g. '3951')
    deprec_account    = db.Column(db.String(10), nullable=False)

    acquisition_date  = db.Column(db.Date, nullable=False)
    # Costo de adquisición en PEN (base + IGV si no hay crédito fiscal)
    cost_pen          = db.Column(db.Numeric(18, 2), nullable=False)
    # Valor residual al final de la vida útil (normalmente 0 o 1 sol)
    residual_value    = db.Column(db.Numeric(18, 2), default=Decimal('0'))
    # Vida útil en meses (SUNAT)
    useful_life_months = db.Column(db.Integer, nullable=False)
    # Depreciación mensual calculada: (costo - residual) / vida_util
    monthly_depreciation = db.Column(db.Numeric(18, 4), nullable=False)

    # Control de depreciación
    months_depreciated    = db.Column(db.Integer, default=0)
    accumulated_depreciation = db.Column(db.Numeric(18, 2), default=Decimal('0'))

    # activo | depreciado | baja
    status            = db.Column(db.String(20), default='activo')
    baja_date         = db.Column(db.Date, nullable=True)
    baja_notes        = db.Column(db.Text, nullable=True)

    # Vínculo con el gasto de compra (opcional)
    expense_record_id = db.Column(
        db.Integer,
        db.ForeignKey('expense_records.id'),
        nullable=True,
    )
    created_by        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    expense_record    = db.relationship('ExpenseRecord', back_populates='fixed_asset')

    # ── Propiedades calculadas ─────────────────────────────────────────────────

    @property
    def net_book_value(self) -> Decimal:
        """Valor en libros neto (costo - depreciación acumulada)."""
        return Decimal(str(self.cost_pen)) - Decimal(str(self.accumulated_depreciation or 0))

    @property
    def is_fully_depreciated(self) -> bool:
        return (self.months_depreciated or 0) >= self.useful_life_months

    @property
    def remaining_months(self) -> int:
        return max(0, self.useful_life_months - (self.months_depreciated or 0))

    # ── Métodos ───────────────────────────────────────────────────────────────

    @staticmethod
    def generate_asset_code() -> str:
        year = date.today().year
        last = FixedAsset.query.filter(
            FixedAsset.asset_code.like(f'FA-{year}-%')
        ).order_by(FixedAsset.id.desc()).first()
        if last:
            try:
                num = int(last.asset_code.split('-')[2]) + 1
            except (IndexError, ValueError):
                num = 1
        else:
            num = 1
        return f'FA-{year}-{num:03d}'

    @classmethod
    def from_expense(cls, expense_record, category: str, name: str,
                     useful_life_months: int = None, residual_value: Decimal = None,
                     created_by: int = None) -> 'FixedAsset':
        """
        Crea un FixedAsset a partir de un ExpenseRecord de tipo activo_fijo.
        """
        cost = Decimal(str(expense_record.amount_pen))
        residual = residual_value if residual_value is not None else Decimal('0')
        life = useful_life_months or ASSET_DEFAULT_LIFE.get(category, 60)
        account, deprec_account = ASSET_CATEGORY_ACCOUNTS.get(
            category, ('3362', '3962')
        )
        monthly = ((cost - residual) / life).quantize(Decimal('0.0001'))

        return cls(
            asset_code=cls.generate_asset_code(),
            name=name,
            category=category,
            account_code=account,
            deprec_account=deprec_account,
            acquisition_date=expense_record.expense_date,
            cost_pen=cost,
            residual_value=residual,
            useful_life_months=life,
            monthly_depreciation=monthly,
            months_depreciated=0,
            accumulated_depreciation=Decimal('0'),
            status='activo',
            expense_record_id=expense_record.id,
            created_by=created_by,
        )

    def to_dict(self):
        return {
            'id': self.id,
            'asset_code': self.asset_code,
            'name': self.name,
            'category': self.category,
            'account_code': self.account_code,
            'acquisition_date': self.acquisition_date.isoformat() if self.acquisition_date else None,
            'cost_pen': float(self.cost_pen),
            'residual_value': float(self.residual_value or 0),
            'useful_life_months': self.useful_life_months,
            'monthly_depreciation': float(self.monthly_depreciation),
            'months_depreciated': self.months_depreciated or 0,
            'accumulated_depreciation': float(self.accumulated_depreciation or 0),
            'net_book_value': float(self.net_book_value),
            'remaining_months': self.remaining_months,
            'status': self.status,
        }

    def __repr__(self):
        return f'<FixedAsset {self.asset_code} {self.name} [{self.status}]>'

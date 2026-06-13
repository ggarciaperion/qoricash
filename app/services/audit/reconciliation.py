"""
Motor de Conciliación — Single Source of Truth
================================================
Principio fundamental: el Libro Diario (journal_entry_lines) es la
ÚNICA fuente de verdad. Tesorería (BankBalance, DailyClosure) y cualquier
otro módulo se validan CONTRA el journal, nunca al revés.

Fórmulas validadas:
  Saldo_Journal(cuenta) = Σ(debe) − Σ(haber) de JournalEntryLine para esa cuenta
  Diferencia = Saldo_Tesorería − Saldo_Journal
  Si |Diferencia| > umbral → hallazgo de conciliación

Cuentas auditadas (PCGE ↔ banco):
  1041 BCP PEN | 1044 BCP USD | 1047 Interbank USD | 1048 Interbank PEN
  1049 BanBif PEN | 1050 BanBif USD | 1051 Pichincha PEN | 1052 Pichincha USD
"""
from decimal import Decimal
from app.extensions import db

# Umbral de diferencia aceptable (menor a S/ 1.00 o USD 0.50 se ignora)
UMBRAL_PEN = Decimal('1.00')
UMBRAL_USD = Decimal('0.50')

# Mapeo PCGE → (etiqueta, moneda, banco_key)
CUENTAS_CAJA_BANCO = {
    '1011': ('Caja MN',        'PEN', None),
    '1012': ('Caja ME',        'USD', None),
    '1041': ('BCP PEN',        'PEN', 'BCP'),
    '1044': ('BCP USD',        'USD', 'BCP'),
    '1047': ('Interbank USD',  'USD', 'INTERBANK'),
    '1048': ('Interbank PEN',  'PEN', 'INTERBANK'),
    '1049': ('BanBif PEN',     'PEN', 'BANBIF'),
    '1050': ('BanBif USD',     'USD', 'BANBIF'),
    '1051': ('Pichincha PEN',  'PEN', 'PICHINCHA'),
    '1052': ('Pichincha USD',  'USD', 'PICHINCHA'),
}


def _saldo_journal(account_code: str) -> Decimal:
    """
    Calcula el saldo acumulado de una cuenta desde el Libro Diario.
    Para cuentas USD devuelve el saldo en USD (usando amount_usd).
    Para cuentas PEN devuelve el saldo en PEN.
    Es la fuente única de verdad.
    """
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from sqlalchemy import func

    _, moneda, _ = CUENTAS_CAJA_BANCO.get(account_code, ('', 'PEN', None))
    is_usd = (moneda == 'USD')

    join_cond = JournalEntryLine.journal_entry_id == JournalEntry.id
    base_filter = [
        JournalEntryLine.account_code == account_code,
        JournalEntry.status == 'activo',
    ]

    if is_usd:
        d = db.session.query(func.sum(JournalEntryLine.amount_usd)).join(
            JournalEntry, join_cond
        ).filter(*base_filter, JournalEntryLine.debe > 0).scalar() or Decimal('0')

        h = db.session.query(func.sum(JournalEntryLine.amount_usd)).join(
            JournalEntry, join_cond
        ).filter(*base_filter, JournalEntryLine.haber > 0).scalar() or Decimal('0')
    else:
        row = db.session.query(
            func.sum(JournalEntryLine.debe).label('d'),
            func.sum(JournalEntryLine.haber).label('h'),
        ).join(JournalEntry, join_cond).filter(*base_filter).first()
        d = Decimal(str(row.d or 0))
        h = Decimal(str(row.h or 0))

    return Decimal(str(d)) - Decimal(str(h))


def _saldo_tesoreria(account_code: str) -> Decimal | None:
    """
    Retorna el saldo operativo de Tesorería (BankBalance) para la cuenta dada.
    Retorna None si no existe registro en BankBalance para esa cuenta.
    """
    from app.models.bank_balance import BankBalance

    _, moneda, banco_key = CUENTAS_CAJA_BANCO.get(account_code, ('', 'PEN', None))
    if not banco_key:
        return None

    bb_all = BankBalance.query.all()
    for bb in bb_all:
        bname = bb.bank_name.upper()
        if banco_key in bname and moneda in bname:
            if moneda == 'PEN':
                return Decimal(str(bb.balance_pen or 0))
            else:
                return Decimal(str(bb.balance_usd or 0))
    return None


def run_conciliacion() -> dict:
    """
    Ejecuta la conciliación completa Tesorería vs Libro Diario.

    Retorna dict:
    {
      account_code: {
        'label': str,
        'moneda': str,
        'saldo_journal': Decimal,
        'saldo_tesoreria': Decimal | None,
        'diferencia': Decimal,
        'ok': bool,
        'observacion': str | None,
      }
    }
    """
    resultado = {}

    for code, (label, moneda, banco_key) in CUENTAS_CAJA_BANCO.items():
        saldo_j = _saldo_journal(code)
        saldo_t = _saldo_tesoreria(code)

        if saldo_j == 0 and saldo_t is None:
            continue  # Cuenta sin actividad — omitir

        diferencia = (saldo_t - saldo_j) if saldo_t is not None else None
        umbral = UMBRAL_USD if moneda == 'USD' else UMBRAL_PEN

        if diferencia is None:
            ok = True
            obs = 'Sin registro en Tesorería — no se puede conciliar'
        elif abs(diferencia) <= umbral:
            ok = True
            obs = None
        else:
            ok = False
            obs = (
                f'Tesorería {moneda} {float(saldo_t):,.2f} ≠ '
                f'Diario {moneda} {float(saldo_j):,.2f} '
                f'(Δ {moneda} {float(diferencia):+,.2f})'
            )

        resultado[code] = {
            'label':             label,
            'moneda':            moneda,
            'banco_key':         banco_key,
            'saldo_journal':     saldo_j,
            'saldo_tesoreria':   saldo_t,
            'diferencia':        diferencia,
            'ok':                ok,
            'observacion':       obs,
        }

    return resultado


def run_partida_doble_check(year: int, month: int) -> list:
    """
    Verifica que todos los asientos del período cumplan DEBE == HABER.
    Retorna lista de asientos descuadrados.
    """
    from app.models.journal_entry import JournalEntry
    from sqlalchemy import extract, func

    entradas = JournalEntry.query.filter(
        extract('year',  JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).all()

    descuadrados = []
    for e in entradas:
        diff = abs(Decimal(str(e.total_debe)) - Decimal(str(e.total_haber)))
        if diff > Decimal('0.01'):
            descuadrados.append({
                'entry_number': e.entry_number,
                'entry_date':   e.entry_date.isoformat(),
                'total_debe':   float(e.total_debe),
                'total_haber':  float(e.total_haber),
                'diferencia':   float(diff),
                'description':  e.description[:80],
            })

    return descuadrados

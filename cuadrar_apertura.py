"""
Diagnóstico del Balance General usando fuentes reales.

ACTIVO:
  - Bancos: BankBalance (Posición real, igual que balance_general())
  - Caja:   Libro Diario (1011/1012)
  - Fijos:  modelo FixedAsset

PASIVO + PATRIMONIO: Libro Diario (journal-based)

La "brecha" es informativa — no se crea ningún asiento.
El Balance General ya la muestra como "Diferencia a conciliar".

Uso: python3 cuadrar_apertura.py
"""
from decimal import Decimal
from datetime import date

from app import create_app
from app.extensions import db
from app.models.fixed_asset import FixedAsset

app = create_app()

with app.app_context():
    from sqlalchemy import func
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.bank_balance import BankBalance
    from app.models.exchange_rate import ExchangeRate

    corte = date.today()

    def _saldo(prefix: str, side: str) -> Decimal:
        row = (
            db.session.query(
                func.coalesce(func.sum(JournalEntryLine.debe),  0).label('d'),
                func.coalesce(func.sum(JournalEntryLine.haber), 0).label('h'),
            )
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntryLine.account_code.like(f'{prefix}%'),
                JournalEntry.entry_date <= corte,
                JournalEntry.status == 'activo',
            )
            .one()
        )
        d = Decimal(str(row.d or 0))
        h = Decimal(str(row.h or 0))
        return max(d - h, Decimal('0')) if side == 'deudora' else max(h - d, Decimal('0'))

    def saldo_d(prefix): return _saldo(prefix, 'deudora')
    def saldo_a(prefix): return _saldo(prefix, 'acreedora')

    # ── TC para USD → PEN ────────────────────────────────────────────────────
    rates = ExchangeRate.get_current_rates()
    tc = Decimal(str((rates['compra'] + rates['venta']) / 2))

    # ── ACTIVO — bancos desde Posición ───────────────────────────────────────
    all_banks      = BankBalance.query.all()
    bancos_pen     = sum(Decimal(str(b.balance_pen or 0)) for b in all_banks)
    bancos_usd_raw = sum(Decimal(str(b.balance_usd or 0)) for b in all_banks)
    bancos_usd_pen = bancos_usd_raw * tc

    caja_mn = saldo_d('1011')
    caja_me = saldo_d('1012')
    ctas_cobrar = saldo_d('121')

    fixed_assets  = FixedAsset.query.filter_by(status='activo').all()
    activos_netos = Decimal('0')
    if fixed_assets:
        for fa in fixed_assets:
            activos_netos += fa.net_book_value
    else:
        activos_netos = (
            sum(saldo_d(c) for c in ('3321', '3351', '3361', '3362')) -
            sum(saldo_a(c) for c in ('3921', '3951', '3961', '3962'))
        )

    activo_corriente = caja_mn + caja_me + bancos_pen + bancos_usd_pen + ctas_cobrar
    total_activo     = activo_corriente + activos_netos

    # ── PASIVO ───────────────────────────────────────────────────────────────
    total_pasivo = (
        saldo_a('4211') + saldo_a('4699') + saldo_a('4111') +
        saldo_a('4017') + saldo_a('4031') + saldo_a('4032') + saldo_a('4551')
    )

    # ── PATRIMONIO (journal) ─────────────────────────────────────────────────
    capital        = saldo_a('501') + saldo_a('311')
    utilidades_acc = saldo_a('351') + saldo_a('591')
    perdidas_acc   = saldo_d('592')
    resultado      = (saldo_a('75') + saldo_a('77')) - saldo_d('6')
    total_patrimonio = capital + utilidades_acc - perdidas_acc + resultado

    brecha = total_activo - total_pasivo - total_patrimonio

    print(f"\n{'='*62}")
    print(f"  DIAGNÓSTICO — {corte}  (TC: {tc:.4f})")
    print(f"{'='*62}")
    print(f"  ACTIVO REAL (Posición + Fijos)")
    print(f"    Bancos PEN            : S/ {bancos_pen:>12,.2f}")
    print(f"    Bancos USD {bancos_usd_raw:.2f} × {tc:.4f}: S/ {bancos_usd_pen:>12,.2f}")
    print(f"    Caja M/N (diario)     : S/ {caja_mn:>12,.2f}")
    print(f"    Caja M/E (diario)     : S/ {caja_me:>12,.2f}")
    print(f"    Ctas. por cobrar      : S/ {ctas_cobrar:>12,.2f}")
    print(f"    Activos fijos (neto)  : S/ {activos_netos:>12,.2f}")
    print(f"  {'─'*48}")
    print(f"  TOTAL ACTIVO            : S/ {total_activo:>12,.2f}")
    print(f"")
    print(f"  PASIVO (diario)         : S/ {total_pasivo:>12,.2f}")
    print(f"  PATRIMONIO (diario)     : S/ {total_patrimonio:>12,.2f}")
    print(f"    Capital (501+311)     : S/ {capital:>12,.2f}")
    print(f"    Resultado             : S/ {resultado:>12,.2f}")
    print(f"")
    print(f"  DIFERENCIA a conciliar  : S/ {brecha:>12,.2f}")
    print(f"{'='*62}")
    print()
    if abs(brecha) < Decimal('1'):
        print("✓ Sin diferencia significativa.")
    else:
        print("ℹ  La diferencia representa flujos del diario no reflejados")
        print("   en Posición. Se muestra en el Balance General como")
        print("   'Diferencia a conciliar' — no requiere asiento de ajuste.")

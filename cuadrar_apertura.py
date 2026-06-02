"""
Diagnóstica y corrige el asiento de apertura para que el Balance General cuadre.

Calcula:  brecha = ACTIVO - PASIVO - PATRIMONIO
Si brecha != 0, crea (o actualiza) un asiento de apertura en cuenta 5011
con el importe necesario para llevar la brecha a cero.

Ejecutar en Render shell:  python3 cuadrar_apertura.py [YEAR]
  YEAR opcional; por defecto usa el año actual.
"""
import sys
from decimal import Decimal
from datetime import date
import calendar

from app import create_app
from app.extensions import db
from app.models.fixed_asset import FixedAsset

app = create_app()

with app.app_context():
    from sqlalchemy import text, func, extract
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine

    year = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    _, last_day = calendar.monthrange(year, 12)
    corte = date(year, last_day, 1)   # 1-dic del año para año completo

    # Usamos último día del año en curso como corte si estamos dentro del año
    if date.today().year == year:
        corte = date.today()
    else:
        corte = date(year, 12, 31)

    def _saldo(prefix: str, side: str) -> Decimal:
        """Saldo acumulado de cuentas que empiezan con `prefix` hasta `corte`."""
        lines_q = (
            db.session.query(
                func.coalesce(func.sum(JournalEntryLine.debe), 0).label('d'),
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
        d = Decimal(str(lines_q.d or 0))
        h = Decimal(str(lines_q.h or 0))
        return max(d - h, Decimal('0')) if side == 'deudora' else max(h - d, Decimal('0'))

    def saldo_d(prefix): return _saldo(prefix, 'deudora')
    def saldo_a(prefix): return _saldo(prefix, 'acreedora')

    # ── ACTIVO ──────────────────────────────────────────────────────────────
    caja_mn    = saldo_d('1011')
    caja_me    = saldo_d('1012')
    bancos_pen = sum(saldo_d(c) for c in ('1041', '1048', '1049', '1051'))
    bancos_usd = sum(saldo_d(c) for c in ('1044', '1047', '1050', '1052'))
    ctas_cobrar = saldo_d('121')
    activo_corriente = caja_mn + caja_me + bancos_pen + bancos_usd + ctas_cobrar

    fixed_assets  = FixedAsset.query.filter_by(status='activo').all()
    activos_netos = Decimal('0')
    if fixed_assets:
        for fa in fixed_assets:
            activos_netos += fa.net_book_value
    else:
        costo_af    = sum(saldo_d(c) for c in ('3321', '3351', '3361', '3362'))
        deprec_acum = sum(saldo_a(c) for c in ('3921', '3951', '3961', '3962'))
        activos_netos = costo_af - deprec_acum

    total_activo = activo_corriente + activos_netos

    # ── PASIVO ──────────────────────────────────────────────────────────────
    facturas_pagar = saldo_a('4211')
    otras_ctas_pag = saldo_a('4699')
    sueldos_pagar  = saldo_a('4111')
    ir_pagar       = saldo_a('4017')
    essalud_pagar  = saldo_a('4031')
    afp_pagar      = saldo_a('4032')
    prestamos      = saldo_a('4551')
    total_pasivo   = (facturas_pagar + otras_ctas_pag + sueldos_pagar +
                      ir_pagar + essalud_pagar + afp_pagar + prestamos)

    # ── PATRIMONIO ──────────────────────────────────────────────────────────
    capital        = saldo_a('501') + saldo_a('311')
    utilidades_acc = saldo_a('351') + saldo_a('591')
    perdidas_acc   = saldo_d('592')
    ingresos_ac    = saldo_a('75') + saldo_a('77')
    gastos_ac      = saldo_d('6')
    resultado      = ingresos_ac - gastos_ac
    total_patrimonio = capital + utilidades_acc - perdidas_acc + resultado

    brecha = total_activo - total_pasivo - total_patrimonio

    print(f"\n{'='*60}")
    print(f"  DIAGNÓSTICO BALANCE — corte al {corte}")
    print(f"{'='*60}")
    print(f"  Total Activo      : S/ {total_activo:,.2f}")
    print(f"  Total Pasivo      : S/ {total_pasivo:,.2f}")
    print(f"  Total Patrimonio  : S/ {total_patrimonio:,.2f}")
    print(f"    Capital (501+311): S/ {capital:,.2f}")
    print(f"    Utilidades(351+591): S/ {utilidades_acc:,.2f}")
    print(f"    Resultado         : S/ {resultado:,.2f}")
    print(f"  BRECHA (A-P-PAT)  : S/ {brecha:,.2f}")
    print(f"{'='*60}\n")

    if abs(brecha) < Decimal('0.01'):
        print("✓ Balance cuadrado. No se requiere ajuste.")
        sys.exit(0)

    # Calcular ajuste necesario en 5011
    # Si brecha > 0 → ACTIVO > P+PAT → necesitamos más PASIVO o PATRIMONIO
    #   → asiento: DEBE cuenta puente (p.ej. 1099) / HABER 5011
    #   En realidad: creamos la contrapartida necesaria
    # Estrategia: crear asiento de apertura DEBE <puente> HABER 5011 si brecha > 0
    #             o DEBE 5011 HABER <puente> si brecha < 0

    # La contrapartida del capital es la suma de los activos iniciales ya registrados.
    # El ajuste simplemente iguala con un asiento de apertura adicional en 5011 vs 9999.
    ajuste = abs(brecha)

    if brecha > 0:
        # ACTIVO excede P+PAT → incrementar patrimonio
        debe_code  = '1099'   # Cuenta transitoria / ajuste
        haber_code = '5011'
        desc = f'Ajuste apertura {year}: incremento capital para cuadre (brecha +{brecha:.2f})'
    else:
        # P+PAT excede ACTIVO → reducir patrimonio
        debe_code  = '5011'
        haber_code = '1099'
        desc = f'Ajuste apertura {year}: reducción capital para cuadre (brecha {brecha:.2f})'

    confirm = input(f"\n¿Crear asiento de ajuste S/ {ajuste:.2f} ({debe_code} DEBE / {haber_code} HABER)? [s/N]: ")
    if confirm.strip().lower() != 's':
        print("Abortado.")
        sys.exit(0)

    # Verificar si ya existe un asiento de apertura este año
    existing = JournalEntry.query.filter(
        extract('year', JournalEntry.entry_date) == year,
        JournalEntry.entry_type == 'apertura',
        JournalEntry.status == 'activo',
    ).first()

    if existing:
        entry = existing
        print(f"Actualizando asiento de apertura existente ID={entry.id}")
    else:
        entry = JournalEntry(
            entry_date=date(year, 1, 1),
            description=f'Apertura contable {year}',
            entry_type='apertura',
            status='activo',
        )
        db.session.add(entry)
        db.session.flush()
        print(f"Nuevo asiento de apertura creado ID={entry.id}")

    # Añadir líneas de ajuste
    line_d = JournalEntryLine(
        journal_entry_id=entry.id,
        account_code=debe_code,
        description=desc,
        debe=ajuste,
        haber=Decimal('0'),
        currency='PEN',
    )
    line_h = JournalEntryLine(
        journal_entry_id=entry.id,
        account_code=haber_code,
        description=desc,
        debe=Decimal('0'),
        haber=ajuste,
        currency='PEN',
    )
    db.session.add(line_d)
    db.session.add(line_h)
    db.session.commit()

    print(f"\n✓ Asiento de ajuste registrado exitosamente.")
    print(f"  DEBE  {debe_code} S/ {ajuste:.2f}")
    print(f"  HABER {haber_code} S/ {ajuste:.2f}")
    print(f"\nEjecuta nuevamente para verificar que brecha ≈ 0.00")

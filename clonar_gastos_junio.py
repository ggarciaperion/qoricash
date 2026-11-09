"""
Clona los gastos de junio 2026 → julio, agosto y septiembre 2026.

Uso:
    DATABASE_URL="postgresql://..." python3 clonar_gastos_junio.py

El script:
  1. Lee todos los ExpenseRecord de junio 2026 (incluyendo cuotas de préstamo
     identificadas por category='6711').
  2. Por cada mes destino (julio, agosto, septiembre) crea el período si no
     existe, luego clona cada gasto ajustando la fecha al mismo día del mes
     destino (si el día no existe en ese mes usa el último día del mes).
  3. Genera el asiento contable correspondiente via JournalService, igual que
     lo haría el sistema web.
  4. Al final imprime un resumen y pregunta confirmación antes de commit.
"""

import os
import sys
from decimal import Decimal
from datetime import date
import calendar

# ── Configurar DATABASE_URL desde variable de entorno ──────────────────────
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    # Intentar leer del .env local como fallback (solo sirve para prueba local)
    from dotenv import load_dotenv
    load_dotenv()
    db_url = os.environ.get('DATABASE_URL')

if not db_url:
    print("ERROR: Debes setear DATABASE_URL=<connection_string_render>")
    sys.exit(1)

# Render usa postgres:// — SQLAlchemy necesita postgresql://
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

os.environ['DATABASE_URL'] = db_url

# ── Flask app context ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.expense_record import ExpenseRecord
from app.models.accounting_period import AccountingPeriod
from app.services.accounting.journal_service import JournalService

app = create_app()

MESES_DESTINO = [
    (2026, 7,  'Julio 2026'),
    (2026, 8,  'Agosto 2026'),
    (2026, 9,  'Septiembre 2026'),
]


def ajustar_fecha(dia: int, year: int, month: int) -> date:
    """Retorna date(year, month, dia) ajustando si el día no existe en ese mes."""
    ultimo_dia = calendar.monthrange(year, month)[1]
    return date(year, month, min(dia, ultimo_dia))


def clonar_gasto(original: ExpenseRecord, target_year: int, target_month: int,
                 master_user_id: int, periodo) -> ExpenseRecord:
    """Crea una copia del gasto para el período destino y genera su asiento."""

    nueva_fecha = ajustar_fecha(original.expense_date.day, target_year, target_month)

    nuevo = ExpenseRecord(
        period_id=periodo.id,
        expense_date=nueva_fecha,
        category=original.category,
        description=original.description,
        amount_pen=original.amount_pen,
        base_pen=original.base_pen,
        igv_pen=original.igv_pen,
        credito_fiscal=original.credito_fiscal or False,
        expense_type=original.expense_type or 'servicio',
        amount_usd=original.amount_usd,
        exchange_rate_used=original.exchange_rate_used,
        voucher_type=original.voucher_type,
        voucher_number=original.voucher_number,
        supplier_ruc=original.supplier_ruc,
        supplier_name=original.supplier_name,
        bank_account_code=original.bank_account_code,
        retencion_4ta=original.retencion_4ta or False,
        retencion_4ta_monto=original.retencion_4ta_monto,
        created_by=master_user_id,
    )
    db.session.add(nuevo)
    db.session.flush()

    # ── Reconstruir líneas del asiento (misma lógica que nuevo_gasto) ────────
    account_code   = original.category
    amount_pen     = original.amount_pen
    igv_pen        = original.igv_pen
    base_pen       = original.base_pen
    credito_fiscal = original.credito_fiscal or False
    voucher_type   = (original.voucher_type or '').lower()
    expense_type   = original.expense_type or 'servicio'
    ret_monto      = original.retencion_4ta_monto
    bank_account_code = original.bank_account_code

    _bank_labels = {
        '1011': 'Caja MN', '1012': 'Caja ME',
        '1041': 'BCP PEN', '1044': 'BCP USD',
        '1047': 'Interbank USD', '1048': 'Interbank PEN',
        '1049': 'BanBif PEN', '1050': 'BanBif USD',
    }

    if bank_account_code:
        bank_label = _bank_labels.get(bank_account_code, bank_account_code)
        lines = [
            {'account_code': account_code, 'description': nuevo.description,
             'debe': amount_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': bank_account_code,
             'description': f'Cargo banco {bank_label}: {nuevo.description}',
             'debe': Decimal('0'), 'haber': amount_pen, 'currency': 'PEN'},
        ]
    elif expense_type == 'planilla':
        lines = [
            {'account_code': account_code, 'description': nuevo.description,
             'debe': amount_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '4111', 'description': f'Por pagar planilla: {nuevo.description}',
             'debe': Decimal('0'), 'haber': amount_pen, 'currency': 'PEN'},
        ]
    elif voucher_type == 'factura' and credito_fiscal and igv_pen:
        lines = [
            {'account_code': account_code, 'description': nuevo.description,
             'debe': base_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '4011', 'description': f'IGV compras – {nuevo.description}',
             'debe': igv_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '4211', 'description': f'Factura por pagar: {nuevo.description}',
             'debe': Decimal('0'), 'haber': amount_pen, 'currency': 'PEN'},
        ]
    elif voucher_type == 'factura':
        lines = [
            {'account_code': account_code, 'description': nuevo.description,
             'debe': amount_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '4211', 'description': f'Factura por pagar: {nuevo.description}',
             'debe': Decimal('0'), 'haber': amount_pen, 'currency': 'PEN'},
        ]
    elif original.retencion_4ta and ret_monto:
        neto_pagar = amount_pen - ret_monto
        lines = [
            {'account_code': account_code, 'description': nuevo.description,
             'debe': amount_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '4172',
             'description': f'Retención IR 4ta 8% — {nuevo.description}',
             'debe': Decimal('0'), 'haber': ret_monto, 'currency': 'PEN'},
            {'account_code': '4699',
             'description': f'Honorarios netos por pagar — {nuevo.description}',
             'debe': Decimal('0'), 'haber': neto_pagar, 'currency': 'PEN'},
        ]
    else:
        lines = [
            {'account_code': account_code, 'description': nuevo.description,
             'debe': amount_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '4699', 'description': f'Por pagar: {nuevo.description}',
             'debe': Decimal('0'), 'haber': amount_pen, 'currency': 'PEN'},
        ]

    entry_type = 'activo_fijo' if expense_type == 'activo_fijo' else 'gasto'
    entry = JournalService.create_entry(
        entry_type=entry_type,
        description=f"{'Adq. activo' if entry_type == 'activo_fijo' else 'Gasto'}: {nuevo.description}",
        lines=lines,
        source_type='expense',
        source_id=nuevo.id,
        entry_date=nueva_fecha,
        created_by=master_user_id,
    )
    if entry:
        nuevo.journal_entry_id = entry.id

    return nuevo


def main():
    with app.app_context():
        # ── Leer gastos de junio ────────────────────────────────────────────
        periodo_jun = AccountingPeriod.query.filter_by(year=2026, month=6).first()
        if not periodo_jun:
            print("ERROR: No existe el período Junio 2026 en la BD.")
            sys.exit(1)

        gastos_jun = (ExpenseRecord.query
                      .filter_by(period_id=periodo_jun.id)
                      .order_by(ExpenseRecord.expense_date, ExpenseRecord.id)
                      .all())

        if not gastos_jun:
            print("No se encontraron gastos en Junio 2026.")
            sys.exit(0)

        # Obtener un master_user_id (el primer usuario activo con rol Master)
        from app.models.user import User
        master = User.query.filter_by(role='Master').first()
        if not master:
            master = User.query.first()
        master_user_id = master.id if master else 1

        # ── Mostrar resumen de lo que se va a clonar ───────────────────────
        print(f"\n{'='*65}")
        print(f"  GASTOS DE JUNIO 2026 — {len(gastos_jun)} registros")
        print(f"{'='*65}")
        total_jun = Decimal('0')
        for g in gastos_jun:
            print(f"  {g.expense_date}  {g.category:<8} S/{g.amount_pen:>10,.2f}  {g.description[:45]}")
            total_jun += g.amount_pen
        print(f"{'─'*65}")
        print(f"  TOTAL JUNIO: S/ {total_jun:,.2f}")
        print(f"{'='*65}")

        print(f"\nSe clonarán estos {len(gastos_jun)} gastos para:")
        for (y, m, label) in MESES_DESTINO:
            p = AccountingPeriod.query.filter_by(year=y, month=m).first()
            estado = f"existe ({p.status})" if p else "se CREARÁ"
            print(f"  - {label} (período: {estado})")

        print()
        respuesta = input("¿Confirmar clonación? (escribe 'si' para continuar): ").strip().lower()
        if respuesta != 'si':
            print("Cancelado.")
            sys.exit(0)

        # ── Clonar ─────────────────────────────────────────────────────────
        total_creados = 0
        for (target_year, target_month, label) in MESES_DESTINO:
            # Verificar si ya hay gastos en ese período (evitar duplicados)
            periodo_dest = AccountingPeriod.query.filter_by(year=target_year, month=target_month).first()
            if periodo_dest:
                ya_existen = ExpenseRecord.query.filter_by(period_id=periodo_dest.id).count()
                if ya_existen > 0:
                    print(f"\n⚠️  {label} ya tiene {ya_existen} gastos registrados — omitiendo.")
                    continuar = input(f"   ¿Clonar igual? (si/no): ").strip().lower()
                    if continuar != 'si':
                        print(f"   → {label} omitido.")
                        continue

            # Crear/obtener período destino
            periodo_dest = JournalService.get_or_create_period(
                date(target_year, target_month, 1)
            )
            if periodo_dest.status == 'cerrado':
                print(f"\n⚠️  {label} está CERRADO — no se puede registrar. Omitiendo.")
                continue

            print(f"\nClonando → {label}...")
            creados_mes = 0
            for g in gastos_jun:
                try:
                    clonar_gasto(g, target_year, target_month, master_user_id, periodo_dest)
                    creados_mes += 1
                except Exception as e:
                    print(f"  ERROR en gasto '{g.description[:40]}': {e}")
                    db.session.rollback()
                    raise

            db.session.commit()
            print(f"  ✅ {creados_mes} gastos creados para {label}  (S/ {total_jun:,.2f})")
            total_creados += creados_mes

        print(f"\n{'='*65}")
        print(f"  COMPLETADO — {total_creados} gastos creados en total")
        print(f"  Revisa en: https://app.qoricash.pe/contabilidad/gastos")
        print(f"{'='*65}\n")


if __name__ == '__main__':
    main()

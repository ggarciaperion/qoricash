"""
AUDITORÍA CONTABLE COMPLETA — JUNIO 2026 EN ADELANTE
Ejecutar en Render Shell: python3 auditoria_junio.py

Valida:
  1. Operaciones completadas sin asiento contable
  2. Gastos registrados sin asiento
  3. Diferencias saldos Caja/Bancos (Tesorería vs Libro Diario)
  4. Estado de Ganancias y Pérdidas de junio
  5. Resumen de acciones a tomar
"""
import os
from datetime import date, datetime
from decimal import Decimal

os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
from app.extensions import db

app = create_app()

SEP  = '=' * 72
SEP2 = '-' * 72
DESDE = date(2026, 6, 1)

def fmt(n, decimals=2):
    return f"S/ {float(n):,.{decimals}f}" if n is not None else "S/ 0.00"

def fmt_usd(n):
    return f"$ {float(n):,.2f}" if n is not None else "$ 0.00"

with app.app_context():
    from sqlalchemy import func, extract, text
    from app.models.operation import Operation
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.expense_record import ExpenseRecord
    from app.models.bank_balance import BankBalance
    from app.models.accounting_period import AccountingPeriod
    from app.models.user import User

    demo_id = User.get_demo_user_id()

    print(f"\n{SEP}")
    print(f"  AUDITORÍA CONTABLE QORICASH — DESDE {DESDE.strftime('%d/%m/%Y')}")
    print(f"  Ejecutada: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(SEP)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. OPERACIONES COMPLETADAS SIN ASIENTO
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'1. OPERACIONES COMPLETADAS SIN ASIENTO CONTABLE':^72}")
    print(SEP2)

    # IDs con asiento activo
    ids_con_asiento = {
        r[0] for r in db.session.query(JournalEntry.source_id).filter(
            JournalEntry.source_type == 'operation',
            JournalEntry.status == 'activo',
        ).all() if r[0]
    }

    q = Operation.query.filter(
        Operation.status == 'Completada',
        func.date(Operation.completed_at) >= DESDE,
        ~Operation.id.in_(ids_con_asiento) if ids_con_asiento else True,
    )
    if demo_id:
        q = q.filter(Operation.user_id != demo_id)
    ops_sin_asiento = q.order_by(Operation.completed_at.asc()).all()

    if not ops_sin_asiento:
        print("  ✅  TODAS las operaciones desde el 01/06 tienen asiento contable.")
    else:
        print(f"  ⚠️   {len(ops_sin_asiento)} operación(es) SIN asiento:\n")
        print(f"  {'ID Operación':<20} {'Tipo':<10} {'USD':>12} {'PEN':>12} {'Fecha':<18} {'Cliente'}")
        print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*12} {'-'*18} {'-'*20}")
        for op in ops_sin_asiento:
            client_name = op.client.full_name[:22] if op.client else 'N/A'
            fecha = op.completed_at.strftime('%d/%m/%Y %H:%M') if op.completed_at else '—'
            print(f"  {op.operation_id:<20} {op.operation_type:<10} {fmt_usd(op.amount_usd):>12} {fmt(op.amount_pen):>12} {fecha:<18} {client_name}")

    # Total operaciones completadas desde junio
    total_ops = Operation.query.filter(
        Operation.status == 'Completada',
        func.date(Operation.completed_at) >= DESDE,
    )
    if demo_id:
        total_ops = total_ops.filter(Operation.user_id != demo_id)
    total_ops = total_ops.count()

    print(f"\n  Total operaciones completadas desde {DESDE}: {total_ops}")
    print(f"  Con asiento: {total_ops - len(ops_sin_asiento)}  |  Sin asiento: {len(ops_sin_asiento)}")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. GASTOS REGISTRADOS EN JUNIO
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n\n{'2. GASTOS REGISTRADOS — JUNIO 2026':^72}")
    print(SEP2)

    gastos = ExpenseRecord.query.filter(
        func.date(ExpenseRecord.expense_date) >= DESDE,
    ).order_by(ExpenseRecord.expense_date.asc()).all()

    if not gastos:
        print("  ⚠️  No hay gastos registrados desde el 01/06.")
    else:
        total_gastos = Decimal('0')
        gastos_sin_asiento = []
        print(f"  {'Fecha':<12} {'Tipo':<12} {'Proveedor':<25} {'Comprobante':<12} {'Monto PEN':>12} {'Asiento'}")
        print(f"  {'-'*12} {'-'*12} {'-'*25} {'-'*12} {'-'*12} {'-'*12}")
        for g in gastos:
            asiento = f"AS-{g.journal_entry_id}" if g.journal_entry_id else "⚠️ SIN ASIENTO"
            if not g.journal_entry_id:
                gastos_sin_asiento.append(g)
            proveedor = (g.supplier_name or g.description or '')[:23]
            comprobante = f"{g.voucher_type or '—'} {g.voucher_number or ''}".strip()[:11]
            total_gastos += g.amount_pen
            print(f"  {g.expense_date.strftime('%d/%m/%Y'):<12} {g.category:<12} {proveedor:<25} {comprobante:<12} {fmt(g.amount_pen):>12} {asiento}")

        print(f"\n  TOTAL GASTOS JUNIO: {fmt(total_gastos)}")
        if gastos_sin_asiento:
            print(f"  ⚠️  {len(gastos_sin_asiento)} gasto(s) sin asiento contable vinculado")
        else:
            print(f"  ✅  Todos los gastos tienen asiento contable")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. ASIENTOS DE JUNIO — RESUMEN POR TIPO
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n\n{'3. ASIENTOS JUNIO 2026 — RESUMEN POR TIPO':^72}")
    print(SEP2)

    asientos_resumen = db.session.query(
        JournalEntry.entry_type,
        func.count(JournalEntry.id).label('qty'),
        func.sum(JournalEntry.total_debe).label('total'),
    ).filter(
        extract('year',  JournalEntry.entry_date) == 2026,
        extract('month', JournalEntry.entry_date) == 6,
        JournalEntry.status == 'activo',
    ).group_by(JournalEntry.entry_type).order_by(func.count(JournalEntry.id).desc()).all()

    if not asientos_resumen:
        print("  ⚠️  No hay asientos registrados en junio 2026.")
    else:
        print(f"  {'Tipo de Asiento':<35} {'Cantidad':>10} {'Total DEBE':>15}")
        print(f"  {'-'*35} {'-'*10} {'-'*15}")
        total_asientos = 0
        for r in asientos_resumen:
            total_asientos += r.qty
            print(f"  {r.entry_type:<35} {r.qty:>10} {fmt(r.total):>15}")
        print(f"  {'TOTAL':.<35} {total_asientos:>10}")

    # Asientos anulados en junio
    anulados = JournalEntry.query.filter(
        extract('year',  JournalEntry.entry_date) == 2026,
        extract('month', JournalEntry.entry_date) == 6,
        JournalEntry.status == 'anulado',
    ).count()
    if anulados:
        print(f"\n  ⚠️  Asientos anulados en junio: {anulados}")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. SALDOS CAJA Y BANCOS — TESORERÍA vs LIBRO DIARIO
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n\n{'4. SALDOS CAJA Y BANCOS — TESORERÍA vs LIBRO DIARIO':^72}")
    print(SEP2)

    CUENTAS_BANCO = {
        '1041': ('BCP PEN',      'PEN'),
        '1044': ('BCP USD',      'USD'),
        '1047': ('Interbank USD','USD'),
        '1048': ('Interbank PEN','PEN'),
        '1049': ('BanBif PEN',   'PEN'),
        '1050': ('BanBif USD',   'USD'),
        '1051': ('Pichincha PEN','PEN'),
        '1052': ('Pichincha USD','USD'),
    }

    bb_all = BankBalance.query.all()
    bb_map = {}
    for bb in bb_all:
        name = bb.bank_name.upper()
        bb_map[name] = bb

    print(f"  {'Cuenta PCGE':<14} {'Banco':<18} {'Tesorería':>14} {'Libro Diario':>14} {'Diferencia':>14} {'Estado'}")
    print(f"  {'-'*14} {'-'*18} {'-'*14} {'-'*14} {'-'*14} {'-'*10}")

    diferencias_encontradas = []

    for code, (label, currency) in CUENTAS_BANCO.items():
        # Saldo en Tesorería (BankBalance)
        bb_saldo = Decimal('0')
        for bb in bb_all:
            bname = bb.bank_name.upper()
            banco = label.split()[0].upper()
            if banco in bname and currency in bname:
                bb_saldo = Decimal(str(bb.balance_pen if currency == 'PEN' else bb.balance_usd))
                break

        # Saldo en Libro Diario (suma acumulada cuenta)
        result = db.session.query(
            func.sum(JournalEntryLine.debe).label('d'),
            func.sum(JournalEntryLine.haber).label('h'),
        ).join(
            JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
        ).filter(
            JournalEntryLine.account_code == code,
            JournalEntry.status == 'activo',
        ).first()

        if currency == 'USD':
            result_usd = db.session.query(
                func.sum(JournalEntryLine.amount_usd).label('d'),
            ).join(
                JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
            ).filter(
                JournalEntryLine.account_code == code,
                JournalEntryLine.debe > 0,
                JournalEntry.status == 'activo',
            ).first()
            result_usd_h = db.session.query(
                func.sum(JournalEntryLine.amount_usd).label('h'),
            ).join(
                JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
            ).filter(
                JournalEntryLine.account_code == code,
                JournalEntryLine.haber > 0,
                JournalEntry.status == 'activo',
            ).first()
            libro_saldo = Decimal(str(result_usd.d or 0)) - Decimal(str(result_usd_h.h or 0))
        else:
            libro_saldo = Decimal(str(result.d or 0)) - Decimal(str(result.h or 0))

        diferencia = bb_saldo - libro_saldo
        sym = currency

        if bb_saldo == 0 and libro_saldo == 0:
            continue  # Cuenta sin movimiento, omitir

        estado = "✅ OK" if abs(diferencia) < Decimal('1') else f"⚠️  DIF"
        if abs(diferencia) >= Decimal('1'):
            diferencias_encontradas.append((code, label, currency, bb_saldo, libro_saldo, diferencia))

        ts = f"{sym} {float(bb_saldo):>10,.2f}"
        ls = f"{sym} {float(libro_saldo):>10,.2f}"
        df = f"{sym} {float(diferencia):>+10,.2f}"
        print(f"  {code:<14} {label:<18} {ts:>14} {ls:>14} {df:>14} {estado}")

    if not diferencias_encontradas:
        print(f"\n  ✅  No hay diferencias entre Tesorería y Libro Diario.")
    else:
        print(f"\n  ⚠️  {len(diferencias_encontradas)} cuenta(s) con diferencia > S/1:")
        for code, label, cur, bb, libro, dif in diferencias_encontradas:
            print(f"      {code} {label}: Tesorería {cur} {float(bb):,.2f} — Libro {cur} {float(libro):,.2f} — Dif {cur} {float(dif):+,.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # 5. ESTADO DE GANANCIAS Y PÉRDIDAS — JUNIO 2026
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n\n{'5. ESTADO DE GANANCIAS Y PÉRDIDAS — JUNIO 2026':^72}")
    print(SEP2)

    # Ingresos (cuentas 7xxx)
    ingresos_rows = db.session.query(
        JournalEntryLine.account_code,
        func.sum(JournalEntryLine.haber).label('total'),
    ).join(
        JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        JournalEntryLine.account_code.like('7%'),
        JournalEntryLine.haber > 0,
        extract('year',  JournalEntry.entry_date) == 2026,
        extract('month', JournalEntry.entry_date) == 6,
        JournalEntry.status == 'activo',
    ).group_by(JournalEntryLine.account_code).order_by(JournalEntryLine.account_code).all()

    # Gastos (cuentas 6xxx)
    gastos_rows = db.session.query(
        JournalEntryLine.account_code,
        func.sum(JournalEntryLine.debe).label('td'),
        func.sum(JournalEntryLine.haber).label('th'),
    ).join(
        JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        JournalEntryLine.account_code.like('6%'),
        extract('year',  JournalEntry.entry_date) == 2026,
        extract('month', JournalEntry.entry_date) == 6,
        JournalEntry.status == 'activo',
    ).group_by(JournalEntryLine.account_code).order_by(JournalEntryLine.account_code).all()

    CUENTA_NOMBRES = {
        '7711': 'Diferencia de cambio — ganancia',
        '7761': 'Ganancia diferencia TC (ajuste)',
        '7591': 'Otros ingresos de gestión',
        '7699': 'Ingresos por conciliación',
        '6391': 'Servicios prestados por terceros',
        '6791': 'ITF y tributos',
        '6711': 'Intereses de préstamos',
        '6762': 'Pérdida diferencia TC',
        '6591': 'Otros gastos de gestión',
        '6699': 'Gastos por conciliación',
        '621':  'Remuneraciones',
        '622':  'Otras remuneraciones',
    }

    print(f"\n  INGRESOS")
    total_ingresos = Decimal('0')
    for r in ingresos_rows:
        nombre = CUENTA_NOMBRES.get(r.account_code, f'Cuenta {r.account_code}')
        monto = Decimal(str(r.total or 0))
        total_ingresos += monto
        print(f"    {r.account_code}  {nombre:<38} {fmt(monto):>12}")
    print(f"    {'TOTAL INGRESOS':.<44} {fmt(total_ingresos):>12}")

    print(f"\n  GASTOS")
    total_gastos_er = Decimal('0')
    for r in gastos_rows:
        neto = Decimal(str(r.td or 0)) - Decimal(str(r.th or 0))
        if neto < Decimal('0.01'):
            continue
        nombre = CUENTA_NOMBRES.get(r.account_code, f'Cuenta {r.account_code}')
        total_gastos_er += neto
        print(f"    {r.account_code}  {nombre:<38} {fmt(neto):>12}")
    print(f"    {'TOTAL GASTOS':.<44} {fmt(total_gastos_er):>12}")

    utilidad = total_ingresos - total_gastos_er
    print(f"\n  {'UTILIDAD NETA JUNIO 2026':.<44} {fmt(utilidad):>12}")

    if utilidad > 0:
        ir_pago_cuenta = (utilidad * Decimal('0.01')).quantize(Decimal('0.01'))
        print(f"  {'IR Pago a cuenta (1% Rég. MYPE)':.<44} {fmt(ir_pago_cuenta):>12}")
    else:
        print(f"  ⚠️  Utilidad negativa — no genera IR pago a cuenta")

    # ─────────────────────────────────────────────────────────────────────────
    # 6. PERÍODO CONTABLE JUNIO — ESTADO
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n\n{'6. ESTADO DEL PERÍODO CONTABLE':^72}")
    print(SEP2)

    periodo_jun = AccountingPeriod.query.filter_by(year=2026, month=6).first()
    if not periodo_jun:
        print("  ⚠️  El período Junio 2026 NO existe en la base de datos.")
        print("      → Ir a Contabilidad → Períodos → Crear período Junio 2026")
    else:
        print(f"  Período: {periodo_jun.label}  |  Estado: {periodo_jun.status.upper()}")
        if periodo_jun.status == 'cerrado':
            print(f"  ⚠️  El período está CERRADO. Reabrirlo antes de generar asientos retroactivos.")
        else:
            print(f"  ✅  El período está ABIERTO — se pueden registrar y corregir asientos.")

    # ─────────────────────────────────────────────────────────────────────────
    # 7. RESUMEN DE ACCIONES REQUERIDAS
    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n\n{'7. ACCIONES REQUERIDAS':^72}")
    print(SEP)

    acciones = []

    if ops_sin_asiento:
        acciones.append(f"⚠️  CRÍTICO: {len(ops_sin_asiento)} operación(es) sin asiento → "
                        "Contabilidad → Períodos → Generar Asientos Retroactivos (Junio)")

    if gastos and any(not g.journal_entry_id for g in gastos):
        n = sum(1 for g in gastos if not g.journal_entry_id)
        acciones.append(f"⚠️  {n} gasto(s) sin asiento contable vinculado → revisar en Contabilidad → Gastos")

    if diferencias_encontradas:
        acciones.append(f"⚠️  {len(diferencias_encontradas)} diferencia(s) Tesorería/Libro Diario → "
                        "usar Conciliación Bancaria en Libro Caja")

    if not ingresos_rows:
        acciones.append("⚠️  Sin ingresos registrados en junio → verificar asientos de operaciones")

    if not acciones:
        print("\n  ✅  CONTABILIDAD LIMPIA — no se encontraron diferencias ni faltantes.")
    else:
        for i, a in enumerate(acciones, 1):
            print(f"\n  {i}. {a}")

    print(f"\n{SEP}")
    print(f"  FIN AUDITORÍA — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(SEP)

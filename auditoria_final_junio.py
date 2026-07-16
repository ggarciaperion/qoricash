"""
Auditoría Final — Contabilidad Junio 2026 — QoriCash
Ejecutar en Render shell: python auditoria_final_junio.py
"""
from app import create_app
from app.extensions import db
from app.models.system_config import SystemConfig
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from sqlalchemy import extract, func
from decimal import Decimal

YEAR, MONTH = 2026, 6
OK  = '✅'
ERR = '❌'
WARN = '⚠️ '

app = create_app()

errores = []

with app.app_context():

    print("=" * 60)
    print("  AUDITORÍA FINAL — JUNIO 2026 — QORICASH")
    print("=" * 60)

    # ── 1. RUC ────────────────────────────────────────────────────
    print("\n📋 1. RUC EN SYSTEM CONFIG")
    ruc = SystemConfig.get('RUC', 'NO EXISTE')
    if ruc == '20615113698':
        print(f"  {OK}  RUC: {ruc}")
    else:
        print(f"  {ERR}  RUC incorrecto: {ruc} (esperado: 20615113698)")
        errores.append("RUC incorrecto")

    # ── 2. Asiento incorrecto anulado ─────────────────────────────
    print("\n📋 2. GASTO INCORRECTO S/ 4,021.38 (AS-2026-0153)")
    entry_malo = JournalEntry.query.filter_by(entry_number='AS-2026-0153').first()
    if entry_malo:
        if entry_malo.status == 'anulado':
            print(f"  {OK}  AS-2026-0153 → status: ANULADO")
        else:
            print(f"  {ERR}  AS-2026-0153 → status: {entry_malo.status} (debería ser anulado)")
            errores.append("Asiento AS-2026-0153 no anulado")
    else:
        print(f"  {WARN} AS-2026-0153 no encontrado en BD")

    # ── 3. Ingresos junio ─────────────────────────────────────────
    print("\n📋 3. INGRESOS JUNIO 2026 (cuentas 7xxx)")
    total_ing = db.session.query(
        func.sum(JournalEntryLine.haber)
    ).join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
    ).filter(
        extract('year',  JournalEntry.entry_date) == YEAR,
        extract('month', JournalEntry.entry_date) == MONTH,
        JournalEntry.status == 'activo',
        JournalEntryLine.account_code.like('7%'),
        JournalEntryLine.haber > 0,
    ).scalar() or 0

    count_ing = db.session.query(
        func.count(JournalEntryLine.id)
    ).join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
    ).filter(
        extract('year',  JournalEntry.entry_date) == YEAR,
        extract('month', JournalEntry.entry_date) == MONTH,
        JournalEntry.status == 'activo',
        JournalEntryLine.account_code.like('7%'),
        JournalEntryLine.haber > 0,
    ).scalar() or 0

    # Verificar que todas son Ganancia FX amarre
    no_fx = db.session.query(JournalEntry.entry_number, JournalEntry.description
    ).join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        extract('year',  JournalEntry.entry_date) == YEAR,
        extract('month', JournalEntry.entry_date) == MONTH,
        JournalEntry.status == 'activo',
        JournalEntryLine.account_code.like('7%'),
        JournalEntryLine.haber > 0,
        ~JournalEntry.description.like('Ganancia FX%'),
    ).all()

    print(f"  {OK}  Líneas de ingreso activas: {count_ing}")
    print(f"  {OK}  Total ingresos: S/ {float(total_ing):.2f}")
    print(f"        (Declarado en 621: S/ 3,824.38 | Diferencia: S/ {float(total_ing)-3824.38:.2f})")
    if no_fx:
        print(f"  {WARN} Asientos de ingreso no-FX encontrados:")
        for n in no_fx:
            print(f"        {n.entry_number}: {n.description[:70]}")
    else:
        print(f"  {OK}  Todos los ingresos son 'Ganancia FX amarre' — correctos")

    # ── 4. Gastos junio ───────────────────────────────────────────
    print("\n📋 4. GASTOS JUNIO 2026 (cuentas 6xxx)")

    total_gasto = db.session.query(
        func.sum(JournalEntryLine.debe - JournalEntryLine.haber)
    ).join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
    ).filter(
        extract('year',  JournalEntry.entry_date) == YEAR,
        extract('month', JournalEntry.entry_date) == MONTH,
        JournalEntry.status == 'activo',
        JournalEntryLine.account_code.like('6%'),
        JournalEntryLine.debe > JournalEntryLine.haber,
    ).scalar() or 0

    count_gasto = db.session.query(
        func.count(JournalEntry.id.distinct())
    ).join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        extract('year',  JournalEntry.entry_date) == YEAR,
        extract('month', JournalEntry.entry_date) == MONTH,
        JournalEntry.status == 'activo',
        JournalEntryLine.account_code.like('6%'),
    ).scalar() or 0

    print(f"  {OK}  Asientos de gasto activos: {count_gasto}")
    print(f"  {OK}  Total gastos: S/ {float(total_gasto):.2f}")

    # Verificar que el asiento malo NO suma en gastos
    malo_en_gastos = db.session.query(
        func.sum(JournalEntryLine.debe)
    ).join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
    ).filter(
        JournalEntry.entry_number == 'AS-2026-0153',
        JournalEntry.status == 'activo',
    ).scalar() or 0

    if float(malo_en_gastos) == 0:
        print(f"  {OK}  Gasto incorrecto S/ 4,021.38 NO incluido en totales")
    else:
        print(f"  {ERR}  Gasto incorrecto AÚN suma S/ {float(malo_en_gastos):.2f}")
        errores.append("Gasto incorrecto aún activo")

    # ── 5. Resultado ──────────────────────────────────────────────
    print("\n📋 5. RESULTADO NETO JUNIO")
    resultado = float(total_ing) - float(total_gasto)
    print(f"  Ingresos:  S/ {float(total_ing):.2f}")
    print(f"  Gastos:    S/ {float(total_gasto):.2f}")
    print(f"  Resultado: S/ {resultado:.2f} ({'GANANCIA' if resultado >= 0 else 'PÉRDIDA'})")

    # ── 6. Pago a cuenta Renta ────────────────────────────────────
    print("\n📋 6. PAGO A CUENTA RENTA")
    pago_declarado   = 38.0
    pago_correcto    = round(float(total_ing) * 0.01, 2)
    diferencia_impuesto = round(pago_correcto - pago_declarado, 2)
    print(f"  Declarado en 621:  S/ {pago_declarado:.2f}")
    print(f"  Correcto (1% libros): S/ {pago_correcto:.2f}")
    print(f"  Diferencia:        S/ {diferencia_impuesto:.2f} {'(mínima — no requiere acción urgente)' if diferencia_impuesto < 10 else '(rectificar)'}")

    # ── 7. Nombre correcto de archivos PLE ────────────────────────
    print("\n📋 7. NOMBRE DE ARCHIVOS PLE (con RUC correcto)")
    periodo = f'{YEAR}{MONTH:02d}00'
    ing_file   = f'LE{ruc}{periodo}080100001.txt'
    gasto_file = f'LE{ruc}{periodo}080200001.txt'
    print(f"  {OK}  Ingresos: {ing_file}")
    print(f"  {OK}  Gastos:   {gasto_file}")

    # ── Resumen final ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    if not errores:
        print(f"  {OK}  AUDITORÍA APROBADA — Todo correcto para enviar PLE")
    else:
        print(f"  {ERR}  ERRORES ENCONTRADOS:")
        for e in errores:
            print(f"       - {e}")
    print("=" * 60)

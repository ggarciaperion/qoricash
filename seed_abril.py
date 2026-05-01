"""
seed_abril.py — Datos de prueba Abril 2026
===========================================
Genera operaciones, gastos, amarres y lotes para validar
todos los módulos del sistema contable.

Ejecutar en Render shell:
    python3 seed_abril.py

Para borrar todos los datos de prueba:
    python3 seed_abril.py --delete
"""
import sys
from datetime import datetime, date
from decimal import Decimal

from app import create_app
from app.extensions import db

app = create_app()

# ── Prefijo único para identificar datos de prueba ─────────────────────────
TAG = '[TEST-ABR]'


# ===========================================================================
# BORRAR
# ===========================================================================

def delete_seed():
    with app.app_context():
        from app.models.accounting_match import AccountingMatch
        from app.models.accounting_batch import AccountingBatch
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine
        from app.models.expense_record import ExpenseRecord
        from app.models.operation import Operation
        from app.models.user import User
        from app.models.client import Client
        from app.models.accounting_period import AccountingPeriod
        from app.models.trader_daily_profit import TraderDailyProfit

        print('Borrando datos de prueba Abril 2026...')

        # 1. Anular / borrar amarres de prueba (por operaciones TEST)
        test_ops = Operation.query.filter(Operation.operation_id.like('%-SEED-%')).all()
        test_op_ids = [o.id for o in test_ops]

        if test_op_ids:
            matches = AccountingMatch.query.filter(
                (AccountingMatch.buy_operation_id.in_(test_op_ids)) |
                (AccountingMatch.sell_operation_id.in_(test_op_ids))
            ).all()
            batch_ids = list({m.batch_id for m in matches if m.batch_id})
            for m in matches:
                m.batch_id = None
            db.session.flush()
            for m in matches:
                db.session.delete(m)
            db.session.flush()

            if batch_ids:
                AccountingBatch.query.filter(AccountingBatch.id.in_(batch_ids)).delete(synchronize_session=False)
            db.session.flush()

        # 2. Borrar journal entries de operaciones TEST
        for op in test_ops:
            if op.journal_entry_id:
                je = JournalEntry.query.get(op.journal_entry_id)
                if je:
                    JournalEntryLine.query.filter_by(journal_entry_id=je.id).delete()
                    db.session.delete(je)
        db.session.flush()

        # 3. Borrar journal entries de gastos TEST
        gastos = ExpenseRecord.query.filter(ExpenseRecord.description.like(f'{TAG}%')).all()
        for g in gastos:
            if g.journal_entry_id:
                je = JournalEntry.query.get(g.journal_entry_id)
                if je:
                    JournalEntryLine.query.filter_by(journal_entry_id=je.id).delete()
                    db.session.delete(je)
            db.session.delete(g)
        db.session.flush()

        # 4. Borrar operaciones TEST
        for op in test_ops:
            db.session.delete(op)
        db.session.flush()

        # 5. Borrar TraderDailyProfit de fechas de prueba en abril
        from sqlalchemy import extract
        TraderDailyProfit.query.filter(
            extract('year', TraderDailyProfit.profit_date) == 2026,
            extract('month', TraderDailyProfit.profit_date) == 4,
        ).delete(synchronize_session=False)

        # 6. Borrar usuarios y clientes TEST
        test_users = User.query.filter(User.username.like('test_%')).all()
        test_user_ids = [u.id for u in test_users]
        for u in test_users:
            db.session.delete(u)
        db.session.flush()

        test_clients = Client.query.filter(Client.email.like('%@test-qoricash.pe')).all()
        for c in test_clients:
            db.session.delete(c)

        # 7. Borrar período Abril 2026 si fue creado por seed
        p = AccountingPeriod.query.filter_by(year=2026, month=4).first()
        if p:
            db.session.delete(p)

        db.session.commit()
        print('✅ Todos los datos de prueba de Abril 2026 fueron eliminados.')


# ===========================================================================
# CREAR
# ===========================================================================

def create_seed():
    with app.app_context():
        from app.models.user import User
        from app.models.client import Client
        from app.models.operation import Operation
        from app.models.expense_record import ExpenseRecord
        from app.models.accounting_period import AccountingPeriod
        from app.services.accounting.journal_service import JournalService
        from app.services.accounting_service import AccountingService
        from app.models.accounting_match import AccountingMatch
        from app.models.accounting_batch import AccountingBatch
        from werkzeug.security import generate_password_hash

        print('=== SEED ABRIL 2026 ===\n')

        # ── 0. Período Abril 2026 ───────────────────────────────────────────
        period = AccountingPeriod.query.filter_by(year=2026, month=4).first()
        if not period:
            period = AccountingPeriod(year=2026, month=4, status='abierto')
            db.session.add(period)
            db.session.flush()
            print(f'  Período creado: {period.label}')
        else:
            print(f'  Período existente: {period.label} [{period.status}]')

        # ── 1. Usuarios de prueba ────────────────────────────────────────────
        def get_or_create_user(username, email, dni, role, full_name):
            u = User.query.filter_by(username=username).first()
            if not u:
                first, *last = full_name.split()
                u = User(
                    username=username,
                    email=email,
                    password_hash=generate_password_hash('Test1234!'),
                    dni=dni,
                    role=role,
                    status='Activo',
                )
                db.session.add(u)
                db.session.flush()
                print(f'  Usuario creado: {username} [{role}]')
            return u

        # Buscar master existente
        master = User.query.filter_by(role='Master', status='Activo').first()
        if not master:
            master = get_or_create_user(
                'test_master', 'test_master@test-qoricash.pe',
                '00000001', 'Master', 'Test Master'
            )
        print(f'  Master: {master.username} (id={master.id})')

        trader1 = get_or_create_user(
            'test_trader1', 'test_trader1@test-qoricash.pe',
            '00000002', 'Trader', 'Carlos Prueba Uno'
        )
        trader2 = get_or_create_user(
            'test_trader2', 'test_trader2@test-qoricash.pe',
            '00000003', 'Trader', 'Ana Prueba Dos'
        )

        # ── 2. Clientes de prueba ────────────────────────────────────────────
        def get_or_create_client(dni, nombres, ap, am, email):
            c = Client.query.filter_by(dni=dni).first()
            if not c:
                c = Client(
                    document_type='DNI',
                    dni=dni,
                    nombres=nombres,
                    apellido_paterno=ap,
                    apellido_materno=am,
                    email=email,
                    phone='999000000',
                    status='Activo',
                )
                db.session.add(c)
                db.session.flush()
                print(f'  Cliente creado: {nombres} {ap}')
            return c

        clt1 = get_or_create_client('10000001', 'Luis',     'Gomez',   'Torres',   'clt1@test-qoricash.pe')
        clt2 = get_or_create_client('10000002', 'Maria',    'Quispe',  'Llanos',   'clt2@test-qoricash.pe')
        clt3 = get_or_create_client('10000003', 'Juan',     'Flores',  'Ramos',    'clt3@test-qoricash.pe')
        clt4 = get_or_create_client('10000004', 'Rosa',     'Huanca',  'Vargas',   'clt4@test-qoricash.pe')
        clt5 = get_or_create_client('10000005', 'Pedro',    'Mamani',  'Cruz',     'clt5@test-qoricash.pe')

        # ── 3. Operaciones completadas Abril 2026 ────────────────────────────
        # TC referencial SBS Abril 2026 ≈ 3.85
        # base_rate = precio interno; exchange_rate = precio al cliente
        print('\n--- Creando operaciones ---')
        ops_data = [
            # (op_id, tipo, usd, tc, base, pen, client, trader, fecha)
            ('C-SEED-001', 'Compra', 5000,  3.80, 3.82, clt1, trader1, date(2026, 4,  2)),
            ('C-SEED-002', 'Compra', 3500,  3.79, 3.81, clt2, trader1, date(2026, 4,  5)),
            ('C-SEED-003', 'Compra', 8000,  3.78, 3.80, clt3, trader2, date(2026, 4,  7)),
            ('C-SEED-004', 'Compra', 2000,  3.80, 3.82, clt4, trader2, date(2026, 4, 10)),
            ('C-SEED-005', 'Compra', 10000, 3.77, 3.79, clt1, trader1, date(2026, 4, 15)),  # self-match
            ('C-SEED-006', 'Compra', 1500,  3.81, 3.83, clt5, trader1, date(2026, 4, 20)),
            ('V-SEED-001', 'Venta',  4000,  3.88, 3.86, clt2, trader1, date(2026, 4,  3)),
            ('V-SEED-002', 'Venta',  7000,  3.87, 3.85, clt3, trader2, date(2026, 4,  8)),
            ('V-SEED-003', 'Venta',  10000, 3.86, 3.84, clt4, trader1, date(2026, 4, 16)),  # self-match
            ('V-SEED-004', 'Venta',  3000,  3.89, 3.87, clt5, trader2, date(2026, 4, 22)),
        ]

        created_ops = {}
        for (op_id, tipo, usd, tc, base, client, trader, fech) in ops_data:
            # Saltar si ya existe
            if Operation.query.filter_by(operation_id=op_id).first():
                print(f'  [ya existe] {op_id}')
                created_ops[op_id] = Operation.query.filter_by(operation_id=op_id).first()
                continue

            pen = Decimal(str(usd)) * Decimal(str(tc))
            op = Operation(
                operation_id=op_id,
                operation_type=tipo,
                client_id=client.id,
                user_id=trader.id,
                amount_usd=Decimal(str(usd)),
                exchange_rate=Decimal(str(tc)),
                base_rate=Decimal(str(base)),
                amount_pen=pen,
                origen='sistema',
                status='Completada',
                created_at=datetime(2026, fech.month, fech.day, 9, 0, 0),
                completed_at=datetime(2026, fech.month, fech.day, 14, 30, 0),
            )
            db.session.add(op)
            db.session.flush()
            created_ops[op_id] = op

            # Generar asiento contable
            try:
                JournalService.create_entry_for_completed_operation(
                    op, created_by_id=master.id
                )
                print(f'  ✓ {op_id} {tipo} USD {usd:,} @ {tc}  →  asiento generado')
            except Exception as e:
                print(f'  ⚠ {op_id} asiento falló: {e}')

        db.session.commit()

        # ── 4. Gastos Abril 2026 ─────────────────────────────────────────────
        print('\n--- Creando gastos ---')
        gastos_data = [
            # (fecha, category, desc, amount, voucher_type, voucher_num, ruc, supplier, expense_type)
            (date(2026,4,1),  '6211', f'{TAG} Planilla operadores abril',
             Decimal('4500.00'), 'planilla', None, None, None, 'planilla'),
            (date(2026,4,5),  '6381', f'{TAG} Servicio internet y telefonia',
             Decimal('354.00'),  'Factura', 'F001-00312', '20100023528', 'CLARO SAC', 'servicio'),
            (date(2026,4,8),  '6391', f'{TAG} Utiles de oficina',
             Decimal('150.00'),  'Boleta', 'B001-00089', None, None, 'suministro'),
            (date(2026,4,10), '6392', f'{TAG} Honorarios contables',
             Decimal('590.00'),  'Recibo',  'RH-00045', '10456789012', 'Estudio Contable XYZ', 'servicio'),
            (date(2026,4,15), '6751', f'{TAG} Gastos bancarios y comisiones',
             Decimal('200.00'),  'Boleta', 'B003-00210', None, None, 'servicio'),
            (date(2026,4,20), '6391', f'{TAG} Alquiler oficina virtual',
             Decimal('1180.00'), 'Factura', 'F002-00156', '20601234567', 'Cowork Lima SAC', 'servicio'),
        ]

        for (fech, cat, desc, amount, vtype, vnum, ruc, supplier, etype) in gastos_data:
            # Evitar duplicados
            if ExpenseRecord.query.filter_by(description=desc).first():
                print(f'  [ya existe] {desc}')
                continue

            p = JournalService.get_or_create_period(fech)

            igv_pen = base_pen = None
            if vtype == 'Factura':
                igv_pen  = (amount / Decimal('1.18') * Decimal('0.18')).quantize(Decimal('0.01'))
                base_pen = amount - igv_pen

            record = ExpenseRecord(
                period_id=p.id,
                expense_date=fech,
                category=cat,
                description=desc,
                amount_pen=amount,
                base_pen=base_pen,
                igv_pen=igv_pen,
                credito_fiscal=False,
                expense_type=etype,
                voucher_type=vtype,
                voucher_number=vnum,
                supplier_ruc=ruc,
                supplier_name=supplier,
                created_by=master.id,
            )
            db.session.add(record)
            db.session.flush()

            # Asiento según tipo
            if etype == 'planilla':
                lines = [
                    {'account_code': cat, 'description': desc,
                     'debe': amount, 'haber': Decimal('0'), 'currency': 'PEN'},
                    {'account_code': '4111', 'description': f'Por pagar planilla: {desc}',
                     'debe': Decimal('0'), 'haber': amount, 'currency': 'PEN'},
                ]
            elif vtype == 'Factura':
                lines = [
                    {'account_code': cat, 'description': desc,
                     'debe': amount, 'haber': Decimal('0'), 'currency': 'PEN'},
                    {'account_code': '4211', 'description': f'Factura por pagar: {desc}',
                     'debe': Decimal('0'), 'haber': amount, 'currency': 'PEN'},
                ]
            else:
                lines = [
                    {'account_code': cat, 'description': desc,
                     'debe': amount, 'haber': Decimal('0'), 'currency': 'PEN'},
                    {'account_code': '4699', 'description': f'Por pagar: {desc}',
                     'debe': Decimal('0'), 'haber': amount, 'currency': 'PEN'},
                ]

            entry = JournalService.create_entry(
                entry_type='gasto',
                description=f'Gasto: {desc}',
                lines=lines,
                source_type='expense',
                source_id=record.id,
                entry_date=fech,
                created_by=master.id,
            )
            if entry:
                record.journal_entry_id = entry.id
            db.session.flush()
            print(f'  ✓ Gasto {cat} {vtype or ""} S/ {amount}')

        db.session.commit()

        # ── 5. Amarres ───────────────────────────────────────────────────────
        print('\n--- Creando amarres ---')
        matches_data = [
            # (buy_op_id, sell_op_id, usd, notas)
            ('C-SEED-001', 'V-SEED-001', 4000, 'Amarre prueba C2C — compra parcial'),
            ('C-SEED-002', 'V-SEED-004', 3000, 'Amarre prueba C2C — venta parcial'),
            ('C-SEED-003', 'V-SEED-002', 7000, 'Amarre prueba C2C — compra parcial'),
            ('C-SEED-005', 'V-SEED-003', 10000, 'Amarre prueba SELF-MATCH trader1'),
        ]

        created_matches = []
        for (buy_id, sell_id, usd, notas) in matches_data:
            buy_op  = created_ops.get(buy_id)
            sell_op = created_ops.get(sell_id)
            if not buy_op or not sell_op:
                print(f'  ⚠ Operación no encontrada: {buy_id} / {sell_id}')
                continue

            # Verificar si ya existe
            existing = AccountingMatch.query.filter_by(
                buy_operation_id=buy_op.id,
                sell_operation_id=sell_op.id,
                status='Activo'
            ).first()
            if existing:
                print(f'  [ya existe] {buy_id} ↔ {sell_id}')
                created_matches.append(existing)
                continue

            success, msg, match = AccountingService.create_match(
                buy_operation_id=buy_op.id,
                sell_operation_id=sell_op.id,
                matched_amount_usd=Decimal(str(usd)),
                user_id=master.id,
                notes=notas,
            )
            if success:
                created_matches.append(match)
                tipo = match.match_type or 'client_to_client'
                print(f'  ✓ {buy_id} ↔ {sell_id}  USD {usd:,}  [{tipo}]'
                      f'  util. total S/ {float(match.profit_pen):.2f}'
                      f'  |  QoriCash S/ {float(match.house_profit_pen or 0):.2f}')
            else:
                print(f'  ✗ {buy_id} ↔ {sell_id}: {msg}')

        db.session.commit()

        # ── 6. Lote de Neteo ─────────────────────────────────────────────────
        print('\n--- Creando lote de neteo ---')
        # Solo los 3 primeros matches (C2C) en el lote; el self-match queda libre
        batch_match_ids = [m.id for m in created_matches[:3] if m and not m.batch_id]
        if batch_match_ids:
            success, msg, batch = AccountingService.create_batch(
                match_ids=batch_match_ids,
                description=f'{TAG} Lote neteo quincenal Abril 2026',
                netting_date='2026-04-16',
                user_id=master.id,
            )
            if success:
                print(f'  ✓ Lote {batch.batch_code} con {len(batch_match_ids)} amarre(s)')
            else:
                print(f'  ✗ Lote falló: {msg}')
        else:
            print('  Sin amarres disponibles para el lote.')

        db.session.commit()

        # ── Resumen ──────────────────────────────────────────────────────────
        from app.models.journal_entry import JournalEntry
        from sqlalchemy import extract, func
        entries_count = JournalEntry.query.filter(
            extract('year',  JournalEntry.entry_date) == 2026,
            extract('month', JournalEntry.entry_date) == 4,
            JournalEntry.status == 'activo',
        ).count()

        print('\n' + '='*50)
        print('SEED COMPLETADO — Resumen:')
        print(f'  Operaciones : {len([o for o in created_ops.values()])}')
        print(f'  Gastos      : {len(gastos_data)}')
        print(f'  Amarres     : {len(created_matches)}')
        print(f'  Asientos    : {entries_count} en Libro Diario Abril 2026')
        print('='*50)
        print()
        print('Para borrar: python3 seed_abril.py --delete')


# ===========================================================================
if __name__ == '__main__':
    if '--delete' in sys.argv:
        delete_seed()
    else:
        create_seed()

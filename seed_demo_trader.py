"""
Crea el usuario demo_trader con datos robustos de demostración.
Idempotente — puede ejecutarse múltiples veces de forma segura.

Uso:
    python seed_demo_trader.py

Credenciales del demo:
    Usuario : demo_trader
    Email   : demo@qoricash.pe
    Password: Demo@2026
"""
import os
import random
from datetime import datetime, timedelta, date

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.client import Client
from app.models.operation import Operation
from app.models.trader_daily_profit import TraderDailyProfit
from app.models.trader_goal import TraderGoal
from werkzeug.security import generate_password_hash

# ─── Parámetros ──────────────────────────────────────────────────────────────
DEMO_USERNAME   = 'demo_trader'
DEMO_EMAIL      = 'demo@qoricash.pe'
DEMO_PASSWORD   = 'Demo@2026'
DEMO_DNI        = '12345678'

# Semilla fija para reproducibilidad
rng = random.Random(42)

# ─── Datos de clientes ────────────────────────────────────────────────────────
CLIENTES = [
    # (document_type, dni, apellido_paterno, apellido_materno, nombres, email, razon_social, persona_contacto)
    ('DNI', '10000001', 'MENDOZA',   'GARCÍA',   'CARLOS ALBERTO',  'carlos.mendoza@gmail.com',     None, None),
    ('DNI', '10000002', 'QUISPE',    'TORRES',   'MARÍA ELENA',     'mquispe.torres@gmail.com',     None, None),
    ('DNI', '10000003', 'SILVA',     'PAREDES',  'ROBERTO ANDRÉS',  'roberto.silva@outlook.com',    None, None),
    ('DNI', '10000004', 'FLORES',    'VÁSQUEZ',  'ANA LUCÍA',       'ana.flores.v@gmail.com',       None, None),
    ('DNI', '10000005', 'HUANCA',    'MAMANI',   'JUAN PABLO',      'jhuancam@gmail.com',           None, None),
    ('DNI', '10000006', 'CASTILLO',  'ROJAS',    'PATRICIA SOFÍA',  'pcastillo.rojas@gmail.com',    None, None),
    ('DNI', '10000007', 'RAMOS',     'SÁNCHEZ',  'MIGUEL ANGEL',    'mramos.sanchez@gmail.com',     None, None),
    ('RUC', '20100000001', None, None, None,     'textil@textil-andino.pe',      'TEXTIL ANDINO SAC',           'Jorge Andrade'),
    ('DNI', '10000009', 'AYALA',     'PAZ',      'CARMEN ROSA',     'carmen.ayala@gmail.com',       None, None),
    ('DNI', '10000010', 'TAPIA',     'LEÓN',     'FERNANDO JOSÉ',   'ftapialeon@gmail.com',         None, None),
    ('DNI', '10000011', 'MORALES',   'ARCE',     'LUCÍA FERNANDA',  'lucia.morales.a@gmail.com',    None, None),
    ('DNI', '10000012', 'VARGAS',    'CRUZ',     'DIEGO AUGUSTO',   'dvargas.cruz@outlook.com',     None, None),
    ('RUC', '20200000002', None, None, None,     'finanzas@importnorte.com',      'IMPORTACIONES DEL NORTE SAC', 'Sandra Villanueva'),
    ('DNI', '10000014', 'GUTIÉRREZ', 'PINO',     'ALEJANDRO RAÚL',  'agutierrez.pino@gmail.com',    None, None),
    ('DNI', '10000015', 'HERRERA',   'TELLO',    'CLAUDIA BEATRIZ', 'claudia.herrera@gmail.com',    None, None),
    ('DNI', '10000016', 'CÓNDOR',    'VILLANUEVA','EDWIN OMAR',     'econdor.v@gmail.com',          None, None),
    ('DNI', '10000017', 'ESPINOZA',  'RÍOS',     'NATALIA VALERIA', 'nespinoza.rios@gmail.com',     None, None),
    ('RUC', '20300000003', None, None, None,     'contabilidad@exppacifico.com',  'EXPORTACIONES PACÍFICO SAC',  'Luis Palomino'),
    ('DNI', '10000019', 'PINTO',     'SALINAS',  'CÉSAR AUGUSTO',   'cpinto.salinas@gmail.com',     None, None),
    ('DNI', '10000020', 'LUNA',      'CASTRO',   'VERÓNICA ISABEL', 'vluna.castro@gmail.com',       None, None),
]

# ─── Distribución de operaciones por cliente ─────────────────────────────────
# (dni_cliente, mes, tipo, amount_usd, tc, base_rate)
# Compra: QoriCash compra USD al cliente  → tc < base_rate  → profit = (base - tc) * usd
# Venta : QoriCash vende USD al cliente   → tc > base_rate  → profit = (tc - base) * usd
OPERACIONES = [
    # ── TEXTIL ANDINO SAC (cliente estrella) ───────────────────
    ('20100000001', 3, 'Venta',  10000, 3.7550, 3.7200),
    ('20100000001', 3, 'Compra',  8000, 3.6900, 3.7200),
    ('20100000001', 4, 'Venta',  12000, 3.7600, 3.7210),
    ('20100000001', 4, 'Compra',  9500, 3.6850, 3.7210),
    ('20100000001', 4, 'Venta',  11000, 3.7580, 3.7200),
    ('20100000001', 5, 'Venta',  10500, 3.7540, 3.7190),
    ('20100000001', 5, 'Compra',  8500, 3.6900, 3.7190),
    ('20100000001', 5, 'Venta',   9000, 3.7560, 3.7200),
    # ── EXPORTACIONES PACÍFICO SAC ──────────────────────────────
    ('20300000003', 3, 'Venta',   8000, 3.7520, 3.7190),
    ('20300000003', 3, 'Compra',  6000, 3.6920, 3.7190),
    ('20300000003', 4, 'Venta',   9500, 3.7550, 3.7200),
    ('20300000003', 4, 'Compra',  7000, 3.6880, 3.7200),
    ('20300000003', 5, 'Venta',   8500, 3.7530, 3.7180),
    # ── IMPORTACIONES DEL NORTE SAC ─────────────────────────────
    ('20200000002', 3, 'Compra',  5000, 3.6950, 3.7210),
    ('20200000002', 3, 'Venta',   4500, 3.7510, 3.7210),
    ('20200000002', 4, 'Compra',  6000, 3.6900, 3.7200),
    ('20200000002', 4, 'Venta',   5500, 3.7540, 3.7200),
    ('20200000002', 5, 'Compra',  4000, 3.6920, 3.7190),
    ('20200000002', 5, 'Venta',   5000, 3.7520, 3.7190),
    # ── CARLOS MENDOZA ──────────────────────────────────────────
    ('10000001', 3, 'Venta',  3000, 3.7500, 3.7180),
    ('10000001', 3, 'Compra', 2500, 3.6980, 3.7180),
    ('10000001', 4, 'Venta',  3500, 3.7520, 3.7200),
    ('10000001', 5, 'Venta',  4000, 3.7490, 3.7170),
    ('10000001', 5, 'Compra', 2000, 3.7000, 3.7170),
    # ── ROBERTO SILVA ───────────────────────────────────────────
    ('10000003', 3, 'Venta',  2000, 3.7490, 3.7170),
    ('10000003', 4, 'Compra', 1500, 3.7010, 3.7200),
    ('10000003', 5, 'Venta',  2500, 3.7510, 3.7180),
    # ── MARÍA QUISPE ────────────────────────────────────────────
    ('10000002', 3, 'Compra', 1200, 3.7020, 3.7200),
    ('10000002', 4, 'Venta',  1800, 3.7480, 3.7160),
    ('10000002', 5, 'Compra',  900, 3.7010, 3.7180),
    # ── ANA FLORES ──────────────────────────────────────────────
    ('10000004', 3, 'Venta',  2200, 3.7500, 3.7180),
    ('10000004', 4, 'Compra', 1800, 3.6990, 3.7200),
    ('10000004', 5, 'Venta',  2500, 3.7520, 3.7190),
    # ── PATRICIA CASTILLO ───────────────────────────────────────
    ('10000006', 3, 'Venta',  1500, 3.7470, 3.7160),
    ('10000006', 4, 'Venta',  1200, 3.7490, 3.7170),
    # ── FERNANDO TAPIA ──────────────────────────────────────────
    ('10000010', 4, 'Compra', 2000, 3.6980, 3.7190),
    ('10000010', 4, 'Venta',  1500, 3.7500, 3.7190),
    ('10000010', 5, 'Venta',  1800, 3.7510, 3.7180),
    # ── ALEJANDRO GUTIÉRREZ ─────────────────────────────────────
    ('10000014', 3, 'Venta',  1000, 3.7460, 3.7150),
    ('10000014', 4, 'Compra',  800, 3.7030, 3.7210),
    ('10000014', 5, 'Venta',  1200, 3.7490, 3.7170),
    # ── MIGUEL RAMOS ────────────────────────────────────────────
    ('10000007', 3, 'Compra',  700, 3.7050, 3.7220),
    ('10000007', 4, 'Venta',   900, 3.7480, 3.7160),
    # ── LUCÍA MORALES ───────────────────────────────────────────
    ('10000011', 3, 'Venta',   600, 3.7450, 3.7140),
    ('10000011', 5, 'Compra',  500, 3.7060, 3.7220),
    # ── DIEGO VARGAS ────────────────────────────────────────────
    ('10000012', 4, 'Venta',   800, 3.7470, 3.7160),
    ('10000012', 5, 'Compra',  600, 3.7050, 3.7210),
    # ── CARMEN AYALA ────────────────────────────────────────────
    ('10000009', 3, 'Compra',  400, 3.7060, 3.7220),
    ('10000009', 4, 'Venta',   500, 3.7460, 3.7150),
    # ── CLAUDIA HERRERA ─────────────────────────────────────────
    ('10000015', 3, 'Venta',   350, 3.7450, 3.7140),
    ('10000015', 5, 'Venta',   400, 3.7470, 3.7160),
    # ── JUAN HUANCA ─────────────────────────────────────────────
    ('10000005', 4, 'Compra',  300, 3.7070, 3.7230),
    ('10000005', 5, 'Venta',   500, 3.7490, 3.7170),
    # ── NATALIA ESPINOZA ─────────────────────────────────────────
    ('10000017', 4, 'Venta',   700, 3.7480, 3.7160),
    ('10000017', 5, 'Compra',  600, 3.7040, 3.7200),
    # ── VERÓNICA LUNA ───────────────────────────────────────────
    ('10000020', 3, 'Venta',   450, 3.7460, 3.7150),
    ('10000020', 5, 'Venta',   600, 3.7500, 3.7180),
    # ── CÉSAR PINTO ─────────────────────────────────────────────
    ('10000019', 4, 'Compra',  500, 3.7050, 3.7210),
    ('10000019', 5, 'Venta',   800, 3.7490, 3.7170),
    # ── EDWIN CÓNDOR ────────────────────────────────────────────
    ('10000016', 3, 'Compra',  600, 3.7020, 3.7200),
    ('10000016', 4, 'Venta',   750, 3.7470, 3.7160),
]


def get_op_day(mes, idx_in_month):
    """Genera un día laborable dentro del mes dado."""
    base_days = {3: 1, 4: 1, 5: 1}
    start = datetime(2026, mes, base_days[mes], 9, 0, 0)
    # Distribuir operaciones a lo largo del mes (cada ~1 día)
    offset_days = idx_in_month * 0.7
    dt = start + timedelta(days=offset_days, hours=rng.randint(0, 7))
    # Saltar fines de semana
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt


def run():
    app = create_app()
    with app.app_context():
        # ── 1. Crear / actualizar usuario demo ───────────────────────────────
        demo = User.query.filter_by(username=DEMO_USERNAME).first()
        if not demo:
            demo = User(
                username=DEMO_USERNAME,
                email=DEMO_EMAIL,
                dni=DEMO_DNI,
                role='Trader',
                status='Activo',
            )
            db.session.add(demo)
            print(f'[+] Usuario creado: {DEMO_USERNAME}')
        else:
            print(f'[=] Usuario ya existe: {DEMO_USERNAME} (actualizando)')

        # Siempre forzar rol Trader y contraseña (idempotente)
        demo.role   = 'Trader'
        demo.status = 'Activo'
        demo.password_hash = generate_password_hash(DEMO_PASSWORD, method='pbkdf2:sha256')
        db.session.flush()  # para obtener demo.id

        demo_id = demo.id

        # ── 2. Crear clientes demo ────────────────────────────────────────────
        client_map = {}  # dni → client.id
        created_clients = 0
        for row in CLIENTES:
            doc_type, dni, ap, am, nombres, email, razon_social, contacto = row
            existing = Client.query.filter_by(dni=dni).first()
            if existing:
                client_map[dni] = existing.id
                continue

            c = Client(
                document_type=doc_type,
                dni=dni,
                email=email,
                status='Activo',
                has_complete_documents=True,
                created_by=demo_id,
            )
            if doc_type == 'RUC':
                c.razon_social = razon_social
                c.persona_contacto = contacto
            else:
                c.apellido_paterno = ap
                c.apellido_materno = am
                c.nombres = nombres

            c.bank_accounts_json = '[]'
            db.session.add(c)
            db.session.flush()
            client_map[dni] = c.id
            created_clients += 1

        print(f'[+] Clientes creados: {created_clients} | ya existentes: {len(CLIENTES) - created_clients}')

        # ── 3. Crear operaciones demo ─────────────────────────────────────────
        existing_ops = Operation.query.filter_by(user_id=demo_id).count()
        if existing_ops > 0:
            print(f'[=] Ya existen {existing_ops} operaciones demo — omitiendo seed de operaciones')
        else:
            ops_por_mes = {3: 0, 4: 0, 5: 0}
            created_ops = 0

            for row in OPERACIONES:
                dni_cli, mes, op_type, amount_usd, tc, base_rate = row
                client_id = client_map.get(dni_cli)
                if not client_id:
                    continue

                idx = ops_por_mes[mes]
                ops_por_mes[mes] += 1
                created_at = get_op_day(mes, idx)
                completed_at = created_at + timedelta(minutes=rng.randint(25, 120))

                amount_pen = round(amount_usd * tc, 2)
                spread = tc - base_rate
                # Compra: QoriCash compra USD barato → spread negativo (tc < base)
                # Venta:  QoriCash vende USD caro   → spread positivo (tc > base)

                op_id = Operation.generate_operation_id()

                op = Operation(
                    operation_id=op_id,
                    client_id=client_id,
                    user_id=demo_id,
                    operation_type=op_type,
                    origen='sistema',
                    amount_usd=amount_usd,
                    amount_pen=amount_pen,
                    exchange_rate=tc,
                    base_rate=base_rate,
                    pips=round(abs(spread) * 10000, 1),
                    status='Completada',
                    created_at=created_at,
                    completed_at=completed_at,
                    updated_at=completed_at,
                    client_deposits_json='[]',
                    client_payments_json='[]',
                    operator_proofs_json='[]',
                    modification_logs_json='[]',
                    notes_read_by_json='[]',
                )
                db.session.add(op)
                created_ops += 1

            print(f'[+] Operaciones creadas: {created_ops}')

        # ── 4. Meta mensual ───────────────────────────────────────────────────
        for month, year, goal_val in [(3, 2026, 9000), (4, 2026, 9000), (5, 2026, 9000)]:
            existing_goal = TraderGoal.query.filter_by(
                user_id=demo_id, month=month, year=year
            ).first()
            if not existing_goal:
                g = TraderGoal(
                    user_id=demo_id,
                    month=month,
                    year=year,
                    goal_amount_pen=goal_val,
                    created_by=demo_id,
                )
                db.session.add(g)
        print('[+] Metas mensuales configuradas')

        # ── 5. Utilidades diarias (abril y mayo) ─────────────────────────────
        existing_profits = TraderDailyProfit.query.filter_by(user_id=demo_id).count()
        if existing_profits > 0:
            print(f'[=] Ya existen {existing_profits} entradas de utilidad — omitiendo')
        else:
            # Utilidades diarias realistas para días laborables
            daily_amounts = {
                # Abril 2026 (lun-vie)
                date(2026, 4,  1): 310.50,
                date(2026, 4,  2): 285.00,
                date(2026, 4,  3): 420.00,
                date(2026, 4,  6): 370.80,
                date(2026, 4,  7): 295.50,
                date(2026, 4,  8): 340.00,
                date(2026, 4,  9): 410.20,
                date(2026, 4, 10): 380.00,
                date(2026, 4, 13): 290.00,
                date(2026, 4, 14): 360.50,
                date(2026, 4, 15): 445.00,
                date(2026, 4, 16): 320.00,
                date(2026, 4, 17): 275.00,
                date(2026, 4, 22): 395.00,
                date(2026, 4, 23): 430.50,
                date(2026, 4, 24): 310.00,
                date(2026, 4, 27): 350.00,
                date(2026, 4, 28): 385.00,
                date(2026, 4, 29): 290.50,
                date(2026, 4, 30): 415.00,
                # Mayo 2026
                date(2026, 5,  4): 360.00,
                date(2026, 5,  5): 420.50,
                date(2026, 5,  6): 390.00,
            }

            for profit_date, amount in daily_amounts.items():
                dp = TraderDailyProfit(
                    user_id=demo_id,
                    profit_date=profit_date,
                    profit_amount_pen=amount,
                    created_by=demo_id,
                )
                db.session.add(dp)
            print(f'[+] Utilidades diarias: {len(daily_amounts)} entradas')

        # ── Guardar todo ──────────────────────────────────────────────────────
        db.session.commit()
        print('\n✓ Demo trader listo.')
        print(f'  Usuario  : {DEMO_USERNAME}')
        print(f'  Email    : {DEMO_EMAIL}')
        print(f'  Password : {DEMO_PASSWORD}')
        print(f'  Rol      : Trader (MODO DEMO — escrituras bloqueadas)')


if __name__ == '__main__':
    run()

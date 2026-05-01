"""
seed_ops_test.py — Operaciones completadas para pruebas de amarres
==================================================================
Crea 5 Compras + 4 Ventas con status=Completada listas para amarrar.
Usa clientes y traders existentes en el sistema (toma los primeros disponibles).

Render shell:
    python3 seed_ops_test.py          # crear
    python3 seed_ops_test.py --delete # borrar

IDs generados: TSOP-C01 … TSOP-C05 y TSOP-V01 … TSOP-V04
"""
import sys
from datetime import datetime
from decimal import Decimal

from app import create_app
from app.extensions import db

app = create_app()

PREFIX = 'TSOP-'

# ── Definición de operaciones de prueba ─────────────────────────────────────
#
# Compras (house compra USD al cliente):
#   exchange_rate = TC que le paga al cliente (menor → más barato para la casa)
#   base_rate     = TC referencia interna (mayor que exchange → margen del trader)
#   profit_trader = (base - exchange) × USD
#
# Ventas (house vende USD al cliente):
#   exchange_rate = TC que cobra al cliente (mayor → más caro para el cliente)
#   base_rate     = TC referencia interna (menor que exchange → margen del trader)
#   profit_trader = (exchange - base) × USD
#
# Combinaciones sugeridas para amarrar:
#   TSOP-C01 $1,000 ←→ TSOP-V01 $1,000  (match exacto)
#   TSOP-C02 $2,000 ←→ TSOP-V02 $2,000  (match exacto)
#   TSOP-C03 $500   ←→ TSOP-V03 $500    (parcial de V03 $3,000)
#   TSOP-C04 $1,500 ←→ TSOP-V03 $1,500  (segundo parcial de V03, agota C04)
#   TSOP-C05 $3,000 ←→ TSOP-V03 $1,000  (tercer parcial, saldo TSOP-C05 = $2,000)
#                   ←→ TSOP-V04 $1,500  (otro parcial, saldo = $500 libre)

COMPRAS = [
    # (suffix, amount_usd, exchange_rate, base_rate, trader_idx)
    ('C01', 1000.00, 3.7200, 3.7450, 0),
    ('C02', 2000.00, 3.7150, 3.7450, 1),
    ('C03',  500.00, 3.7250, 3.7450, 0),
    ('C04', 1500.00, 3.7200, 3.7500, 1),
    ('C05', 3000.00, 3.7180, 3.7450, 0),
]

VENTAS = [
    # (suffix, amount_usd, exchange_rate, base_rate, trader_idx)
    ('V01', 1000.00, 3.7850, 3.7550, 0),
    ('V02', 2000.00, 3.7800, 3.7500, 1),
    ('V03', 3000.00, 3.7820, 3.7520, 0),
    ('V04', 1500.00, 3.7830, 3.7530, 1),
]


# ===========================================================================
# CREAR
# ===========================================================================

def create_seed():
    with app.app_context():
        from app.models.operation import Operation
        from app.models.client import Client
        from app.models.user import User

        # ── Verificar que no existan ya ───────────────────────────────────
        existing = Operation.query.filter(
            Operation.operation_id.like(f'{PREFIX}%')
        ).count()
        if existing:
            print(f'Ya existen {existing} operaciones {PREFIX}*. Usa --delete primero.')
            return

        # ── Tomar clientes existentes ─────────────────────────────────────
        clients = Client.query.limit(4).all()
        if not clients:
            print('ERROR: No hay clientes en el sistema. Crea al menos un cliente primero.')
            return

        # ── Tomar traders existentes (rol Trader o Master) ────────────────
        traders = User.query.filter(User.role.in_(['Trader', 'Master'])).limit(2).all()
        if not traders:
            traders = User.query.limit(2).all()
        if not traders:
            print('ERROR: No hay usuarios en el sistema.')
            return

        print(f'Usando {len(clients)} clientes y {len(traders)} traders.')
        for t in traders:
            print(f'  Trader[{traders.index(t)}]: {t.username} (id={t.id})')
        for c in clients[:4]:
            print(f'  Cliente[{clients.index(c)}]: {c.full_name or c.razon_social} (id={c.id})')

        now = datetime(2026, 5, 1, 14, 0, 0)  # fecha referencia pruebas

        created = []

        def make_op(suffix, op_type, amount_usd, exchange_rate, base_rate, trader_idx, client_idx):
            amount_pen = round(amount_usd * exchange_rate, 2)
            op = Operation(
                operation_id=f'{PREFIX}{suffix}',
                operation_type=op_type,
                origen='sistema',
                amount_usd=Decimal(str(amount_usd)),
                exchange_rate=Decimal(str(exchange_rate)),
                base_rate=Decimal(str(base_rate)),
                pips=Decimal(str(round(abs(base_rate - exchange_rate) * 100, 1))),
                amount_pen=Decimal(str(amount_pen)),
                client_id=clients[client_idx % len(clients)].id,
                user_id=traders[trader_idx % len(traders)].id,
                status='Completada',
                created_at=now,
                completed_at=now,
                notes=f'[TEST] Operación de prueba para amarres',
            )
            db.session.add(op)
            created.append(op)

        client_idx = 0
        for suffix, amount, tc, base, tidx in COMPRAS:
            make_op(suffix, 'Compra', amount, tc, base, tidx, client_idx)
            client_idx += 1

        for suffix, amount, tc, base, tidx in VENTAS:
            make_op(suffix, 'Venta', amount, tc, base, tidx, client_idx)
            client_idx += 1

        db.session.commit()

        print(f'\n✓ Creadas {len(created)} operaciones completadas listas para amarrar:\n')
        print(f'  {"ID":<12} {"Tipo":<8} {"USD":>10} {"TC":>8} {"Base":>8} {"Trader"}')
        print('  ' + '-' * 60)
        for op in created:
            trader = next((t for t in traders if t.id == op.user_id), None)
            tname = trader.username if trader else '—'
            print(f'  {op.operation_id:<12} {op.operation_type:<8} '
                  f'${float(op.amount_usd):>9,.2f} '
                  f'{float(op.exchange_rate):>8.4f} '
                  f'{float(op.base_rate):>8.4f} '
                  f'{tname}')

        print('\nCombinaciones sugeridas:')
        print('  TSOP-C01 $1,000  ←→  TSOP-V01 $1,000  (match exacto)')
        print('  TSOP-C02 $2,000  ←→  TSOP-V02 $2,000  (match exacto)')
        print('  TSOP-C03 $500    ←→  TSOP-V03 $500    (parcial)')
        print('  TSOP-C04 $1,500  ←→  TSOP-V03 $1,500  (parcial)')
        print('  TSOP-C05 $3,000  ←→  TSOP-V03 $1,000  (parcial)')
        print('                   ←→  TSOP-V04 $1,500  (parcial, saldo $500 libre)')


# ===========================================================================
# BORRAR
# ===========================================================================

def delete_seed():
    with app.app_context():
        from app.models.operation import Operation
        from app.models.accounting_match import AccountingMatch

        ops = Operation.query.filter(Operation.operation_id.like(f'{PREFIX}%')).all()
        if not ops:
            print(f'No se encontraron operaciones {PREFIX}*.')
            return

        op_ids = [o.id for o in ops]

        # Borrar amarres vinculados primero
        matches = AccountingMatch.query.filter(
            (AccountingMatch.buy_operation_id.in_(op_ids)) |
            (AccountingMatch.sell_operation_id.in_(op_ids))
        ).all()

        if matches:
            print(f'Borrando {len(matches)} amarre(s) vinculados...')
            for m in matches:
                db.session.delete(m)
            db.session.flush()

        print(f'Borrando {len(ops)} operaciones de prueba...')
        for op in ops:
            db.session.delete(op)

        db.session.commit()
        print('Listo.')


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == '__main__':
    if '--delete' in sys.argv:
        delete_seed()
    else:
        create_seed()

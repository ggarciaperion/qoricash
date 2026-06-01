"""
Script para registrar gastos bancarios BANBIF de mayo 2026.
Ejecutar en Render shell: python3 registrar_gastos_banbif_mayo.py
"""
from app import create_app
from app.extensions import db
from app.services.accounting.journal_service import JournalService
from datetime import date
from decimal import Decimal

app = create_app()

# TC SBS mayo 2026
TC = Decimal('3.414')

ASIENTOS = [
    {
        'desc': 'Gastos bancarios BANBIF USD mayo - mantenimiento 20/05 3.50 + 31/05 6.35 TC 3.414',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6591', 'description': 'Gastos bancarios BANBIF USD equiv PEN', 'debe': Decimal('33.63'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1050', 'description': 'BANBIF USD debito mantenimiento TC 3.414', 'debe': Decimal('0'), 'haber': Decimal('33.63'), 'currency': 'USD', 'amount_usd': Decimal('9.85'), 'exchange_rate': TC},
        ]
    },
    {
        'desc': 'ITF BANBIF USD mayo - 3 cargos consolidados TC 3.414',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6791', 'description': 'ITF mayo BANBIF USD equiv PEN', 'debe': Decimal('0.51'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1050', 'description': 'BANBIF USD debito ITF TC 3.414', 'debe': Decimal('0'), 'haber': Decimal('0.51'), 'currency': 'USD', 'amount_usd': Decimal('0.15'), 'exchange_rate': TC},
        ]
    },
    {
        'desc': 'Intereses por sobregiro BANBIF Soles mayo',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6711', 'description': 'Intereses sobregiro BANBIF PEN mayo', 'debe': Decimal('0.80'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1049', 'description': 'BANBIF PEN debito intereses sobregiro', 'debe': Decimal('0'), 'haber': Decimal('0.80'), 'currency': 'PEN'},
        ]
    },
    {
        'desc': 'ITF BANBIF Soles mayo - 2 cargos consolidados',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6791', 'description': 'ITF mayo BANBIF PEN', 'debe': Decimal('0.25'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1049', 'description': 'BANBIF PEN debito ITF', 'debe': Decimal('0'), 'haber': Decimal('0.25'), 'currency': 'PEN'},
        ]
    },
    {
        'desc': 'Gastos bancarios BANBIF Soles mayo - BIFNET 170.65 + mantenimiento 60.00',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6591', 'description': 'Gastos bancarios BANBIF PEN mayo', 'debe': Decimal('230.65'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1049', 'description': 'BANBIF PEN debito comisiones y mantenimiento', 'debe': Decimal('0'), 'haber': Decimal('230.65'), 'currency': 'PEN'},
        ]
    },
]

with app.app_context():
    from app.models.user import User
    master = User.query.filter_by(role='Master').first()
    if not master:
        print('ERROR: No se encontro usuario Master.')
        exit(1)
    print('Usuario Master: {} (id={})'.format(master.username, master.id))

    ok = 0
    for a in ASIENTOS:
        entry = JournalService.create_entry(
            entry_type='manual',
            description=a['desc'],
            lines=a['lines'],
            source_type='manual',
            entry_date=a['date'],
            created_by=master.id,
        )
        if entry:
            print('OK {} -> {}'.format(entry.entry_number, a['desc'][:60]))
            ok += 1
        else:
            print('ERROR -> {}'.format(a['desc'][:60]))

    print('\n{}/{} asientos registrados.'.format(ok, len(ASIENTOS)))

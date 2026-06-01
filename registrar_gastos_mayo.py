"""
Script para registrar gastos bancarios de mayo 2026.
Ejecutar en Render shell: python3 registrar_gastos_mayo.py
"""
from app import create_app
from app.extensions import db
from app.services.accounting.journal_service import JournalService
from datetime import date
from decimal import Decimal

app = create_app()

ASIENTOS = [
    {
        'desc': 'Gastos bancarios BCP Soles mayo - mantenimiento 35 + envio 5.50 + telecredito 23.71 + TD 10',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6591', 'description': 'Gastos bancarios BCP PEN mayo', 'debe': Decimal('74.21'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1041', 'description': 'BCP PEN debito gastos bancarios', 'debe': Decimal('0'), 'haber': Decimal('74.21'), 'currency': 'PEN'},
        ]
    },
    {
        'desc': 'ITF BCP Soles mayo - 19 cargos consolidados',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6791', 'description': 'ITF mayo BCP PEN', 'debe': Decimal('71.45'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1041', 'description': 'BCP PEN debito ITF', 'debe': Decimal('0'), 'haber': Decimal('71.45'), 'currency': 'PEN'},
        ]
    },
    {
        'desc': 'Gastos bancarios BCP USD mayo - mantenimiento 13 + envio 2.30 + intereses 0.06 + porte 1.32 TC 3.414',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6591', 'description': 'Gastos bancarios BCP USD equiv PEN', 'debe': Decimal('56.95'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1044', 'description': 'BCP USD debito gastos bancarios TC 3.414', 'debe': Decimal('0'), 'haber': Decimal('56.95'), 'currency': 'USD', 'amount_usd': Decimal('16.68'), 'exchange_rate': Decimal('3.414')},
        ]
    },
    {
        'desc': 'ITF BCP USD mayo - 13 cargos consolidados TC 3.414',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6791', 'description': 'ITF mayo BCP USD equiv PEN', 'debe': Decimal('70.16'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1044', 'description': 'BCP USD debito ITF TC 3.414', 'debe': Decimal('0'), 'haber': Decimal('70.16'), 'currency': 'USD', 'amount_usd': Decimal('20.55'), 'exchange_rate': Decimal('3.414')},
        ]
    },
    {
        'desc': 'ITF Interbank Soles mayo - 20 cargos consolidados',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6791', 'description': 'ITF mayo IBK PEN', 'debe': Decimal('14.80'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1048', 'description': 'Interbank PEN debito ITF', 'debe': Decimal('0'), 'haber': Decimal('14.80'), 'currency': 'PEN'},
        ]
    },
    {
        'desc': 'ITF Interbank USD mayo - 10 cargos consolidados TC 3.414',
        'date': date(2026, 5, 31),
        'lines': [
            {'account_code': '6791', 'description': 'ITF mayo IBK USD equiv PEN', 'debe': Decimal('12.80'), 'haber': Decimal('0'), 'currency': 'PEN'},
            {'account_code': '1047', 'description': 'Interbank USD debito ITF TC 3.414', 'debe': Decimal('0'), 'haber': Decimal('12.80'), 'currency': 'USD', 'amount_usd': Decimal('3.75'), 'exchange_rate': Decimal('3.414')},
        ]
    },
]

with app.app_context():
    for a in ASIENTOS:
        entry = JournalService.create_entry(
            entry_type='manual',
            description=a['desc'],
            lines=a['lines'],
            source_type='manual',
            entry_date=a['date'],
            created_by=1,
        )
        if entry:
            print('OK {} -> {}'.format(entry.entry_number, a['desc'][:60]))
        else:
            print('ERROR -> {}'.format(a['desc'][:60]))
    print('\nListo. {} asientos procesados.'.format(len(ASIENTOS)))

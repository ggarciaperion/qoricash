"""
Asiento de apertura abril 2026 — saldos iniciales viables.

Lógica de los montos:
  BCP PEN S/20,000 + April ops net +20,640 = S/40,640 al 30/04
    → Mayo consumió ~S/36K en operaciones → saldo actual S/4,021 ✓

  BCP USD $12,000 (S/40,968 a TC 3.414) - April ops net $6,047 = $5,953 al 30/04
    → Mayo cargos $37 + movimiento neto ops → saldo actual $5,802 ✓

  Capital total: S/60,968 (aporte inicial de accionistas)

Ejecutar en Render shell: python3 apertura_abril.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal
from datetime import date

app = create_app()

TC_APERTURA = Decimal('3.414')
BCP_PEN_INI = Decimal('20000.00')
BCP_USD_INI_USD = Decimal('12000.00')
BCP_USD_INI_PEN = (BCP_USD_INI_USD * TC_APERTURA).quantize(Decimal('0.01'))  # 40,968.00
CAPITAL_TOTAL = BCP_PEN_INI + BCP_USD_INI_PEN                                # 60,968.00

with app.app_context():
    from app.models.accounting_account import AccountingAccount
    from app.services.accounting.journal_service import JournalService
    from app.models.user import User

    master = User.query.filter_by(role='Master').first()
    if not master:
        print('ERROR: No se encontro usuario Master.')
        exit(1)

    # Asegurar que exista cuenta 5011 en catálogo
    if not AccountingAccount.query.filter_by(code='5011').first():
        db.session.add(AccountingAccount(
            code='5011',
            name='Capital social',
            type='patrimonio',
            nature='acreedora',
            currency='PEN',
            parent_code='50',
        ))
        db.session.commit()
        print('Cuenta 5011 Capital social creada.')
    else:
        print('Cuenta 5011 ya existe.')

    print('\nMontos apertura:')
    print('  DEBE 1041 BCP PEN       : S/{}'.format(BCP_PEN_INI))
    print('  DEBE 1044 BCP USD       : S/{} (${} x TC {})'.format(
        BCP_USD_INI_PEN, BCP_USD_INI_USD, TC_APERTURA))
    print('  HABER 5011 Capital      : S/{}'.format(CAPITAL_TOTAL))

    entry = JournalService.create_entry(
        entry_type='manual',
        description='Saldo inicial apertura operaciones abril 2026 — BCP PEN + BCP USD',
        lines=[
            {
                'account_code': '1041',
                'description': 'Saldo inicial BCP PEN apertura',
                'debe': BCP_PEN_INI,
                'haber': Decimal('0'),
                'currency': 'PEN',
            },
            {
                'account_code': '1044',
                'description': 'Saldo inicial BCP USD apertura TC 3.414',
                'debe': BCP_USD_INI_PEN,
                'haber': Decimal('0'),
                'currency': 'USD',
                'amount_usd': BCP_USD_INI_USD,
                'exchange_rate': TC_APERTURA,
            },
            {
                'account_code': '5011',
                'description': 'Capital social aportado inicio operaciones',
                'debe': Decimal('0'),
                'haber': CAPITAL_TOTAL,
                'currency': 'PEN',
            },
        ],
        source_type='manual',
        entry_date=date(2026, 4, 1),
        created_by=master.id,
    )

    if entry:
        print('\nAsiento creado: {} | DEBE={} HABER={}'.format(
            entry.entry_number, entry.total_debe, entry.total_haber
        ))
        print('\nSaldos resultantes en abril:')
        print('  1041 BCP PEN : S/20,000 (apertura) + S/20,640 (ops) = S/40,640')
        print('  1044 BCP USD : S/40,968 (apertura) - S/20,640 (ops) = S/20,328')
        print('  5011 Capital : S/60,968')
        print('\nAlertas eliminadas: 1044 ya no tiene saldo negativo.')
    else:
        print('ERROR al crear asiento de apertura.')

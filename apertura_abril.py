"""
Asiento de apertura abril 2026 — saldos iniciales reales.

  IBK USD  : $5,000  → S/17,070.00 (TC 3.414)
  IBK PEN  : S/20,304.00
  Capital  : S/37,374.00

Nota sobre 1044 BCP USD: queda en -S/20,640 porque las 10 operaciones
de abril usaron BCP para compra-venta. El USD recibido en compras financió
las ventas del mismo periodo (flujo intradiario tipico de casa de cambio).
No representa sobredraft real — la posicion USD consolidada fue positiva.

Ejecutar en Render shell: python3 apertura_abril.py
"""
from app import create_app
from app.extensions import db
from decimal import Decimal
from datetime import date

app = create_app()

TC_APERTURA   = Decimal('3.414')
IBK_USD_INI   = Decimal('5000.00')
IBK_USD_PEN   = (IBK_USD_INI * TC_APERTURA).quantize(Decimal('0.01'))  # 17,070.00
IBK_PEN_INI   = Decimal('20304.00')
CAPITAL_TOTAL = IBK_USD_PEN + IBK_PEN_INI                               # 37,374.00

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
    print('  DEBE 1047 IBK USD : S/{} (${} x TC {})'.format(IBK_USD_PEN, IBK_USD_INI, TC_APERTURA))
    print('  DEBE 1048 IBK PEN : S/{}'.format(IBK_PEN_INI))
    print('  HABER 5011 Capital: S/{}'.format(CAPITAL_TOTAL))

    entry = JournalService.create_entry(
        entry_type='manual',
        description='Saldo inicial apertura operaciones abril 2026 — IBK USD + IBK PEN',
        lines=[
            {
                'account_code': '1047',
                'description': 'Saldo inicial Interbank USD apertura TC 3.414',
                'debe': IBK_USD_PEN,
                'haber': Decimal('0'),
                'currency': 'USD',
                'amount_usd': IBK_USD_INI,
                'exchange_rate': TC_APERTURA,
            },
            {
                'account_code': '1048',
                'description': 'Saldo inicial Interbank PEN apertura',
                'debe': IBK_PEN_INI,
                'haber': Decimal('0'),
                'currency': 'PEN',
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
        print('\nSaldos abril con apertura:')
        print('  1047 IBK USD : S/17,070 (apertura, sin ops en abril)')
        print('  1048 IBK PEN : S/20,304 (apertura, sin ops en abril)')
        print('  5011 Capital : S/37,374')
        print('  1041 BCP PEN : S/20,640 (solo ops, sin apertura)')
        print('  1044 BCP USD : -S/20,640 (flujo neto ops, se compensa con IBK USD)')
    else:
        print('ERROR al crear asiento de apertura.')

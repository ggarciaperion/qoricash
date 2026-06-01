from app import create_app
from app.models.accounting_account import AccountingAccount
from app.extensions import db

app = create_app()
with app.app_context():
    cuentas = [
        AccountingAccount(
            code='4611',
            name='Prestamos de accionistas',
            type='pasivo',
            nature='acreedora',
            currency='PEN',
            parent_code='46'
        ),
        AccountingAccount(
            code='4711',
            name='Intereses por pagar',
            type='pasivo',
            nature='acreedora',
            currency='PEN',
            parent_code='47'
        ),
        AccountingAccount(
            code='6711',
            name='Gastos financieros - intereses',
            type='gasto',
            nature='deudora',
            currency='PEN',
            parent_code='67'
        ),
    ]
    for c in cuentas:
        existing = AccountingAccount.query.filter_by(code=c.code).first()
        if not existing:
            db.session.add(c)
            print('Creada: {} - {}'.format(c.code, c.name))
        else:
            print('Ya existe: {}'.format(c.code))
    db.session.commit()
    print('Listo.')

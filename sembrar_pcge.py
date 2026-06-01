"""
Siembra el catálogo de cuentas PCGE mínimo necesario para QoriCash.

Agrega cuentas que puedan faltar sin tocar las existentes.
Idempotente: se puede ejecutar múltiples veces sin duplicar.

Ejecutar en Render shell: python3 sembrar_pcge.py
"""
from app import create_app
from app.extensions import db

app = create_app()

# (código, nombre, tipo, naturaleza, padre)
CUENTAS_PCGE = [
    # ── Caja y Bancos ─────────────────────────────────────────────────────────
    ('10',   'Efectivo y Equivalentes de Efectivo', 'activo',    'deudora',    None),
    ('101',  'Caja',                                'activo',    'deudora',    '10'),
    ('1011', 'Caja Moneda Nacional',                'activo',    'deudora',    '101'),
    ('1012', 'Caja Moneda Extranjera',              'activo',    'deudora',    '101'),
    ('104',  'Cuentas Corrientes en Instituciones Financieras', 'activo', 'deudora', '10'),
    ('1041', 'BCP — Cta. Cte. PEN',                'activo',    'deudora',    '104'),
    ('1044', 'BCP — Cta. Cte. USD',                'activo',    'deudora',    '104'),
    ('1047', 'Interbank — Cta. Cte. USD',          'activo',    'deudora',    '104'),
    ('1048', 'Interbank — Cta. Cte. PEN',          'activo',    'deudora',    '104'),
    ('1049', 'BanBif — Cta. Cte. PEN',             'activo',    'deudora',    '104'),
    ('1050', 'BanBif — Cta. Cte. USD',             'activo',    'deudora',    '104'),
    # ── Gastos de servicios prestados por terceros ────────────────────────────
    ('63',   'Gastos de Servicios Prestados por Terceros', 'gasto', 'deudora', None),
    ('631',  'Transportes, correos y gastos de viaje',     'gasto', 'deudora', '63'),
    ('633',  'Producción encargada a terceros',            'gasto', 'deudora', '63'),
    ('636',  'Servicios básicos',                          'gasto', 'deudora', '63'),
    ('6311', 'Arrendamiento de inmuebles',                 'gasto', 'deudora', '63'),
    ('6317', 'Servicios de limpieza',                      'gasto', 'deudora', '63'),
    ('6321', 'Alimentos y bebidas',                        'gasto', 'deudora', '63'),
    ('6331', 'Otros servicios de terceros',                'gasto', 'deudora', '63'),
    ('6363', 'Servicios de comunicaciones',                'gasto', 'deudora', '63'),
    ('6391', 'Otros gastos de servicios',                  'gasto', 'deudora', '63'),
    # ── Cargas financieras ────────────────────────────────────────────────────
    ('67',   'Gastos Financieros',                'gasto',    'deudora',    None),
    ('671',  'Gastos en operaciones de endeudamiento', 'gasto', 'deudora',  '67'),
    ('6711', 'Intereses de préstamos y otras obligaciones', 'gasto', 'deudora', '67'),
    ('676',  'Diferencia de cambio',              'gasto',    'deudora',    '67'),
    ('6762', 'Pérdida por diferencia de cambio',  'gasto',    'deudora',    '676'),
    # ── Tributos ──────────────────────────────────────────────────────────────
    ('64',   'Gastos por Tributos',               'gasto',    'deudora',    None),
    ('641',  'Gobierno central',                  'gasto',    'deudora',    '64'),
    ('6411', 'Impuesto a las transacciones financieras', 'gasto', 'deudora', '641'),
    ('659',  'Otros gastos de gestión',           'gasto',    'deudora',    None),
    ('6591', 'Gastos bancarios y comisiones',     'gasto',    'deudora',    '659'),
    ('6791', 'Impuesto a las transacciones financieras (ITF)', 'gasto', 'deudora', '67'),
    # ── Ingresos de gestión ───────────────────────────────────────────────────
    ('75',   'Otros Ingresos de Gestión',         'ingreso',  'acreedora',  None),
    ('759',  'Otros ingresos de gestión',         'ingreso',  'acreedora',  '75'),
    ('7591', 'Ingresos por diferencia de cambio — operaciones', 'ingreso', 'acreedora', '75'),
    # ── Ingresos financieros ──────────────────────────────────────────────────
    ('77',   'Ingresos Financieros',              'ingreso',  'acreedora',  None),
    ('771',  'Ganancia por diferencia de cambio', 'ingreso',  'acreedora',  '77'),
    ('7711', 'Ganancia diferencial cambiario — amarres', 'ingreso', 'acreedora', '771'),
    ('776',  'Ingresos financieros diversos',     'ingreso',  'acreedora',  '77'),
    ('7761', 'Ganancia por diferencia de cambio — ajuste monetario', 'ingreso', 'acreedora', '776'),
    # ── Patrimonio ────────────────────────────────────────────────────────────
    ('50',   'Capital',                           'patrimonio', 'acreedora', None),
    ('501',  'Capital social',                    'patrimonio', 'acreedora', '50'),
    ('5011', 'Capital social aportado',           'patrimonio', 'acreedora', '501'),
    ('35',   'Resultados Acumulados',             'patrimonio', 'acreedora', None),
    ('3511', 'Utilidades acumuladas',             'patrimonio', 'acreedora', '35'),
]

with app.app_context():
    from app.models.accounting_account import AccountingAccount

    creadas  = 0
    omitidas = 0

    for code, name, typ, nat, parent in CUENTAS_PCGE:
        existing = AccountingAccount.query.filter_by(code=code).first()
        if existing:
            omitidas += 1
        else:
            db.session.add(AccountingAccount(
                code        = code,
                name        = name,
                type        = typ,
                nature      = nat,
                currency    = 'PEN',
                parent_code = parent,
            ))
            creadas += 1

    db.session.commit()

    print('=' * 60)
    print('SIEMBRA PCGE COMPLETADA')
    print('=' * 60)
    print(f'  Cuentas creadas : {creadas}')
    print(f'  Ya existían     : {omitidas}')
    print(f'  Total catálogo  : {AccountingAccount.query.count()} cuentas')
    print()
    print('Cuentas clave verificadas:')
    for code in ('7711', '7591', '7761', '6762', '5011', '1041'):
        acc = AccountingAccount.query.filter_by(code=code).first()
        if acc:
            print(f'  ✓ {code} — {acc.name}')
        else:
            print(f'  ✗ {code} — NO ENCONTRADA')

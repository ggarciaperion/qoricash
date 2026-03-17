"""
Cuentas bancarias oficiales de QoriCash SAC — Fuente única de verdad.
RUC: 20615113698

Para actualizar las cuentas, modificar SOLO este archivo.
Todos los demás módulos (email_service, position, run.py, etc.) importan desde aquí.
"""

QORICASH_RUC = '20615113698'
QORICASH_TITULAR = 'QORICASH SAC'

# Estructura: { 'BANCO': { 'USD': {...}, 'PEN': {...} } }
QORICASH_ACCOUNTS = {
    'BCP': {
        'USD': {
            'banco': 'BCP',
            'tipo': 'Cuenta Corriente',
            'moneda': 'USD',
            'numero': '1917357790119',
            'cci': '00219100735779011959',
        },
        'PEN': {
            'banco': 'BCP',
            'tipo': 'Cuenta Corriente',
            'moneda': 'PEN',
            'numero': '1937353150041',
            'cci': '00219300735315004118',
        },
    },
    'INTERBANK': {
        'USD': {
            'banco': 'INTERBANK',
            'tipo': 'Cuenta Corriente',
            'moneda': 'USD',
            'numero': '200-3007757589',
            'cci': '00320000300775758939',
        },
        'PEN': {
            'banco': 'INTERBANK',
            'tipo': 'Cuenta Corriente',
            'moneda': 'PEN',
            'numero': '200-3007757571',
            'cci': '00320000300775757137',
        },
    },
}

# Lista plana para reconciliación bancaria (formato: "BCP USD (numero)")
ALLOWED_BANK_NAMES = [
    f"{banco} {moneda} ({data['numero']})"
    for banco, monedas in QORICASH_ACCOUNTS.items()
    for moneda, data in monedas.items()
]


def get_accounts_for_currency(currency: str) -> list:
    """Retorna lista de cuentas para la moneda dada ('USD' o 'PEN').

    Cada elemento incluye todos los campos del banco más 'titular' y 'ruc'.
    """
    return [
        {**data, 'titular': QORICASH_TITULAR, 'ruc': QORICASH_RUC}
        for monedas in QORICASH_ACCOUNTS.values()
        for c, data in monedas.items()
        if c == currency
    ]

"""
Smoke test: valida que las cuentas bancarias de QoriCash en la configuración sean válidas.

Detecta de forma automática:
  - Bancos prohibidos (BANBIF, PICHINCHA)
  - Números de cuenta cortos / demo (< 10 dígitos)
  - CCIs con formato incorrecto (≠ 20 dígitos o con caracteres no numéricos)
  - Bancos requeridos ausentes (BCP, INTERBANK)
  - Monedas faltantes por banco (USD, PEN)

Ejecutar:
  cd /Users/gianpierre/Desktop/Qoricash/qoricash
  python -m pytest tests/test_bank_accounts.py -v
"""
import sys
import os
import importlib.util

# Cargar bank_accounts.py directamente (evita ejecutar app/__init__.py con Flask/eventlet)
_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'config', 'bank_accounts.py')
_spec = importlib.util.spec_from_file_location('bank_accounts', _config_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

QORICASH_ACCOUNTS = _mod.QORICASH_ACCOUNTS
ALLOWED_BANK_NAMES = _mod.ALLOWED_BANK_NAMES
get_accounts_for_currency = _mod.get_accounts_for_currency
QORICASH_RUC = _mod.QORICASH_RUC
QORICASH_TITULAR = _mod.QORICASH_TITULAR

BANNED_BANKS = ['BANBIF', 'PICHINCHA']
REQUIRED_BANKS = ['BCP', 'INTERBANK']
MIN_ACCOUNT_DIGITS = 10
CCI_DIGITS = 20


def test_no_banned_banks():
    """BANBIF y PICHINCHA no deben estar en las cuentas de QoriCash."""
    for bank in QORICASH_ACCOUNTS:
        assert bank not in BANNED_BANKS, f"Banco prohibido encontrado en config: {bank}"


def test_required_banks_present():
    """BCP e INTERBANK deben estar en la configuración."""
    for bank in REQUIRED_BANKS:
        assert bank in QORICASH_ACCOUNTS, f"Banco requerido ausente: {bank}"


def test_both_currencies_per_bank():
    """Cada banco debe tener cuentas en USD y PEN."""
    for banco, monedas in QORICASH_ACCOUNTS.items():
        assert 'USD' in monedas, f"{banco}: falta cuenta en USD"
        assert 'PEN' in monedas, f"{banco}: falta cuenta en PEN"


def test_account_numbers_not_demo():
    """Números de cuenta deben tener al menos 10 dígitos (descarta cuentas demo)."""
    for banco, monedas in QORICASH_ACCOUNTS.items():
        for moneda, data in monedas.items():
            digits_only = data['numero'].replace('-', '')
            assert len(digits_only) >= MIN_ACCOUNT_DIGITS, (
                f"{banco} {moneda}: número de cuenta sospechoso (muy corto): '{data['numero']}'"
            )


def test_cci_format():
    """CCIs deben tener exactamente 20 dígitos numéricos."""
    for banco, monedas in QORICASH_ACCOUNTS.items():
        for moneda, data in monedas.items():
            cci = data['cci']
            assert len(cci) == CCI_DIGITS, (
                f"{banco} {moneda}: CCI tiene {len(cci)} dígitos, se esperan 20: '{cci}'"
            )
            assert cci.isdigit(), (
                f"{banco} {moneda}: CCI contiene caracteres no numéricos: '{cci}'"
            )


def test_ruc_format():
    """El RUC debe tener 11 dígitos."""
    assert len(QORICASH_RUC) == 11 and QORICASH_RUC.isdigit(), (
        f"RUC inválido: '{QORICASH_RUC}'"
    )


def test_get_accounts_for_currency_usd():
    """get_accounts_for_currency('USD') debe retornar una cuenta por banco."""
    accounts = get_accounts_for_currency('USD')
    assert len(accounts) == len(QORICASH_ACCOUNTS), (
        f"Se esperaban {len(QORICASH_ACCOUNTS)} cuentas USD, se obtuvieron {len(accounts)}"
    )
    for acc in accounts:
        assert 'titular' in acc and acc['titular'] == QORICASH_TITULAR
        assert 'ruc' in acc and acc['ruc'] == QORICASH_RUC
        assert acc['moneda'] == 'USD'


def test_get_accounts_for_currency_pen():
    """get_accounts_for_currency('PEN') debe retornar una cuenta por banco."""
    accounts = get_accounts_for_currency('PEN')
    assert len(accounts) == len(QORICASH_ACCOUNTS), (
        f"Se esperaban {len(QORICASH_ACCOUNTS)} cuentas PEN, se obtuvieron {len(accounts)}"
    )
    for acc in accounts:
        assert acc['moneda'] == 'PEN'


def test_allowed_bank_names_format():
    """ALLOWED_BANK_NAMES debe seguir el formato 'BANCO MONEDA (numero)'."""
    assert len(ALLOWED_BANK_NAMES) == len(QORICASH_ACCOUNTS) * 2, (
        "ALLOWED_BANK_NAMES debe tener 2 entradas por banco (USD y PEN)"
    )
    for name in ALLOWED_BANK_NAMES:
        assert '(' in name and ')' in name, f"Formato incorrecto en ALLOWED_BANK_NAMES: '{name}'"

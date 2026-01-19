"""
Utilidades para el sistema de referidos
"""
import random
import string


def generate_referral_code(length=6):
    """
    Generar un código de referido único

    Args:
        length: Longitud del código (default: 6)

    Returns:
        str: Código de 6 caracteres alfanuméricos en mayúsculas
    """
    # Excluir caracteres similares (I, O, 0, 1) para evitar confusión
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=length))


def is_valid_referral_code_format(code):
    """
    Validar formato de código de referido

    Args:
        code: Código a validar

    Returns:
        bool: True si el formato es válido
    """
    if not code or len(code) != 6:
        return False

    # Solo letras mayúsculas y números
    return code.isalnum() and code.isupper()


def calculate_referral_discount(operation_type, base_rate):
    """
    Calcular el tipo de cambio con descuento de referido

    Args:
        operation_type: 'Compra' o 'Venta'
        base_rate: Tipo de cambio base

    Returns:
        float: Tipo de cambio ajustado
    """
    discount = 0.003

    if operation_type == 'Compra':
        # Compra: QoriCash compra dólares al cliente
        # Beneficio: suma 0.003 al tipo de cambio (cliente recibe más soles)
        return round(base_rate + discount, 3)
    elif operation_type == 'Venta':
        # Venta: QoriCash vende dólares al cliente
        # Beneficio: resta 0.003 al tipo de cambio (cliente paga menos soles)
        return round(base_rate - discount, 3)

    return base_rate

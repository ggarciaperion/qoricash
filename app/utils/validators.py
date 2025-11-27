"""
Validadores para QoriCash Trading V2
"""
import re


def validate_dni(dni):
    """
    Validar DNI peruano (8 dígitos)
    
    Args:
        dni: DNI a validar
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    if not dni:
        return False, 'DNI es requerido'
    
    # Remover espacios
    dni = str(dni).strip()
    
    # Validar longitud
    if len(dni) != 8:
        return False, 'DNI debe tener 8 dígitos'
    
    # Validar que solo contenga números
    if not dni.isdigit():
        return False, 'DNI debe contener solo números'
    
    return True, None


def validate_email(email):
    """
    Validar formato de email
    
    Args:
        email: Email a validar
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    if not email:
        return False, 'Email es requerido'
    
    # Patrón de email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, 'Formato de email inválido'
    
    return True, None


def validate_phone(phone):
    """
    Validar teléfono peruano
    
    Args:
        phone: Teléfono a validar
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    if not phone:
        return True, None  # Teléfono es opcional
    
    # Remover espacios y guiones
    phone = str(phone).strip().replace(' ', '').replace('-', '')
    
    # Validar longitud (9 dígitos para celular, 7 para fijo)
    if len(phone) not in [7, 9]:
        return False, 'Teléfono debe tener 7 o 9 dígitos'
    
    # Validar que solo contenga números
    if not phone.isdigit():
        return False, 'Teléfono debe contener solo números'
    
    return True, None


def validate_password(password):
    """
    Validar contraseña
    
    Args:
        password: Contraseña a validar
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    if not password:
        return False, 'Contraseña es requerida'
    
    # Longitud mínima
    if len(password) < 8:
        return False, 'Contraseña debe tener al menos 8 caracteres'
    
    # Al menos un número
    if not any(c.isdigit() for c in password):
        return False, 'Contraseña debe contener al menos un número'
    
    return True, None


def validate_amount(amount):
    """
    Validar monto numérico positivo
    
    Args:
        amount: Monto a validar
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    try:
        amount_float = float(amount)
        
        if amount_float <= 0:
            return False, 'El monto debe ser mayor a 0'
        
        return True, None
    
    except (ValueError, TypeError):
        return False, 'Monto inválido'


def validate_exchange_rate(rate):
    """
    Validar tipo de cambio
    
    Args:
        rate: Tipo de cambio a validar
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    try:
        rate_float = float(rate)
        
        if rate_float <= 0:
            return False, 'Tipo de cambio debe ser mayor a 0'
        
        # Validar rango razonable (entre 2.5 y 5.0 soles por dólar)
        if rate_float < 2.5 or rate_float > 5.0:
            return False, 'Tipo de cambio fuera del rango esperado (2.5 - 5.0)'
        
        return True, None
    
    except (ValueError, TypeError):
        return False, 'Tipo de cambio inválido'

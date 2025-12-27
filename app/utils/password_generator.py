"""
Utilidades para generación de contraseñas seguras
"""
import secrets
import string


def generate_temporary_password(length=12):
    """
    Generar contraseña temporal segura

    La contraseña generada incluye:
    - Letras mayúsculas
    - Letras minúsculas
    - Dígitos
    - Al menos un carácter especial

    Args:
        length: Longitud de la contraseña (mínimo 8, default 12)

    Returns:
        str: Contraseña temporal generada
    """
    if length < 8:
        length = 8

    # Definir caracteres permitidos
    letters = string.ascii_letters  # a-z, A-Z
    digits = string.digits  # 0-9
    special = '@#$%&*'  # Caracteres especiales fáciles de recordar

    # Asegurar que la contraseña tenga al menos:
    # - 1 letra mayúscula
    # - 1 letra minúscula
    # - 1 dígito
    # - 1 carácter especial
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]

    # Completar el resto de la longitud con caracteres aleatorios
    all_chars = letters + digits + special
    password += [secrets.choice(all_chars) for _ in range(length - 4)]

    # Mezclar los caracteres de forma segura
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def generate_simple_password(length=8):
    """
    Generar contraseña simple (solo letras y números, sin caracteres especiales)
    Útil para envío por SMS o cuando caracteres especiales causan problemas

    Args:
        length: Longitud de la contraseña (mínimo 6, default 8)

    Returns:
        str: Contraseña simple generada
    """
    if length < 6:
        length = 6

    # Solo letras y números (evitar confusión: 0/O, 1/l/I)
    chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'

    # Asegurar variedad
    password = [
        secrets.choice('ABCDEFGHJKMNPQRSTUVWXYZ'),  # Al menos una mayúscula
        secrets.choice('abcdefghjkmnpqrstuvwxyz'),  # Al menos una minúscula
        secrets.choice('23456789'),  # Al menos un número
    ]

    # Completar el resto
    password += [secrets.choice(chars) for _ in range(length - 3)]

    # Mezclar
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)

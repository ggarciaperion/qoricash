"""
Formateadores para QoriCash Trading V2
"""
from datetime import datetime
import pytz
from app.utils.constants import TIMEZONE, DATETIME_FORMAT_DISPLAY


def get_peru_timezone():
    """Obtener timezone de Perú"""
    return pytz.timezone(TIMEZONE)


def now_peru():
    """
    Obtener fecha/hora actual en timezone de Perú (naive datetime)

    Returns:
        datetime: Fecha/hora actual en Perú sin timezone info
    """
    # Obtener hora actual en Perú con timezone
    peru_time = datetime.now(get_peru_timezone())
    # Retornar sin timezone info (naive) para compatibilidad con DB
    return peru_time.replace(tzinfo=None)


def format_currency(amount, currency='USD'):
    """
    Formatear cantidad como moneda
    
    Args:
        amount: Cantidad a formatear
        currency: Tipo de moneda ('USD' o 'PEN')
    
    Returns:
        str: Cantidad formateada
    """
    try:
        amount_float = float(amount)
        
        if currency == 'USD':
            return f"$ {amount_float:,.2f}"
        elif currency == 'PEN':
            return f"S/ {amount_float:,.2f}"
        else:
            return f"{amount_float:,.2f}"
    
    except (ValueError, TypeError):
        return "0.00"


def format_datetime(dt, format_str=DATETIME_FORMAT_DISPLAY):
    """
    Formatear datetime
    
    Args:
        dt: Datetime a formatear
        format_str: Formato deseado
    
    Returns:
        str: Datetime formateado
    """
    if not dt:
        return ''
    
    # Si es naive, asumir UTC y convertir a Peru
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    # Convertir a timezone de Perú
    peru_tz = get_peru_timezone()
    dt_peru = dt.astimezone(peru_tz)
    
    return dt_peru.strftime(format_str)


def format_date(dt):
    """
    Formatear solo la fecha
    
    Args:
        dt: Datetime a formatear
    
    Returns:
        str: Fecha formateada (DD/MM/YYYY)
    """
    if not dt:
        return ''
    
    return dt.strftime('%d/%m/%Y')


def parse_date(date_str, format_str='%Y-%m-%d'):
    """
    Parsear string a datetime
    
    Args:
        date_str: String con fecha
        format_str: Formato del string
    
    Returns:
        datetime: Fecha parseada
    """
    try:
        return datetime.strptime(date_str, format_str)
    except (ValueError, TypeError):
        return None


def format_phone(phone):
    """
    Formatear teléfono
    
    Args:
        phone: Teléfono a formatear
    
    Returns:
        str: Teléfono formateado
    """
    if not phone:
        return ''
    
    # Remover espacios y guiones
    phone = str(phone).strip().replace(' ', '').replace('-', '')
    
    # Formatear según longitud
    if len(phone) == 9:
        # Celular: 999 999 999
        return f"{phone[:3]} {phone[3:6]} {phone[6:]}"
    elif len(phone) == 7:
        # Fijo: 999 9999
        return f"{phone[:3]} {phone[3:]}"
    else:
        return phone


def truncate_text(text, length=50, suffix='...'):
    """
    Truncar texto a longitud específica
    
    Args:
        text: Texto a truncar
        length: Longitud máxima
        suffix: Sufijo a agregar si se trunca
    
    Returns:
        str: Texto truncado
    """
    if not text:
        return ''
    
    if len(text) <= length:
        return text
    
    return text[:length].rsplit(' ', 1)[0] + suffix

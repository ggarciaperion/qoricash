"""
Blueprint para páginas legales (Política de Privacidad, Términos y Condiciones)

Rutas públicas sin autenticación requerida para cumplir con requisitos de App Store y Play Store
"""
from flask import Blueprint, render_template
from datetime import datetime

legal_bp = Blueprint('legal', __name__)

@legal_bp.route('/privacy-policy')
def privacy_policy():
    """
    Política de Privacidad de QoriCash

    Requerida por:
    - Apple App Store (obligatorio para publicación)
    - Google Play Store (obligatorio para publicación)
    - Ley de Protección de Datos Personales del Perú (Ley N° 29733)

    URL: https://app.qoricash.pe/privacy-policy
    """
    now = datetime.now()
    return render_template(
        'legal/privacy-policy.html',
        current_date=now.strftime('%d de %B de %Y'),
        current_year=now.year
    )

@legal_bp.route('/terms-of-service')
def terms_of_service():
    """
    Términos y Condiciones de Uso de QoriCash

    Requerida por:
    - Apple App Store (recomendado)
    - Google Play Store (recomendado)
    - Buenas prácticas legales

    URL: https://app.qoricash.pe/terms-of-service
    """
    now = datetime.now()
    return render_template(
        'legal/terms-of-service.html',
        current_date=now.strftime('%d de %B de %Y'),
        current_year=now.year
    )

# Alias compatibles (por si acaso)
@legal_bp.route('/privacy')
def privacy_alias():
    """Alias para /privacy-policy"""
    now = datetime.now()
    return render_template(
        'legal/privacy-policy.html',
        current_date=now.strftime('%d de %B de %Y'),
        current_year=now.year
    )

@legal_bp.route('/terms')
def terms_alias():
    """Alias para /terms-of-service"""
    now = datetime.now()
    return render_template(
        'legal/terms-of-service.html',
        current_date=now.strftime('%d de %B de %Y'),
        current_year=now.year
    )

# Rutas adicionales para mayor compatibilidad
@legal_bp.route('/legal/privacy')
def legal_privacy():
    """Ruta /legal/privacy para compatibilidad con app stores"""
    now = datetime.now()
    return render_template(
        'legal/privacy-policy.html',
        current_date=now.strftime('%d de %B de %Y'),
        current_year=now.year
    )

@legal_bp.route('/legal/terms')
def legal_terms():
    """Ruta /legal/terms para compatibilidad con app stores"""
    now = datetime.now()
    return render_template(
        'legal/terms-of-service.html',
        current_date=now.strftime('%d de %B de %Y'),
        current_year=now.year
    )

"""
Blueprint para páginas legales (Política de Privacidad, Términos y Condiciones)

Rutas públicas sin autenticación requerida para cumplir con requisitos de App Store y Play Store
"""
from flask import Blueprint, render_template
from app.extensions import limiter

legal_bp = Blueprint('legal', __name__)

@legal_bp.route('/privacy-policy')
@limiter.exempt
def privacy_policy():
    """
    Política de Privacidad de QoriCash

    Requerida por:
    - Apple App Store (obligatorio para publicación)
    - Google Play Store (obligatorio para publicación)
    - Ley de Protección de Datos Personales del Perú (Ley N° 29733)

    URL: https://app.qoricash.pe/privacy-policy
    """
    return render_template('privacy-policy.html')

@legal_bp.route('/terms-of-service')
@limiter.exempt
def terms_of_service():
    """
    Términos y Condiciones de Uso de QoriCash

    Requerida por:
    - Apple App Store (recomendado)
    - Google Play Store (recomendado)
    - Buenas prácticas legales

    URL: https://app.qoricash.pe/terms-of-service
    """
    return render_template('terms-of-service.html')

# Alias compatibles (por si acaso)
@legal_bp.route('/privacy')
@limiter.exempt
def privacy_alias():
    """Alias para /privacy-policy"""
    return render_template('privacy-policy.html')

@legal_bp.route('/terms')
@limiter.exempt
def terms_alias():
    """Alias para /terms-of-service"""
    return render_template('terms-of-service.html')

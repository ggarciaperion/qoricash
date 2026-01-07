"""
Rutas para documentos legales de QoriCash
"""
from flask import Blueprint, render_template

legal_bp = Blueprint('legal', __name__, url_prefix='/legal')


@legal_bp.route('/terms')
def terms():
    """Términos y Condiciones de QoriCash"""
    return render_template('legal/terms.html')


@legal_bp.route('/privacy')
def privacy():
    """Política de Privacidad y Tratamiento de Datos Personales"""
    return render_template('legal/privacy.html')

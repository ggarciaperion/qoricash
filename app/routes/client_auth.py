"""
Rutas de Autenticación para Clientes (Mobile App)
TEMPORAL - Solo DNI sin contraseña para pruebas
"""
from flask import Blueprint, request, jsonify
from app.models.client import Client
from app.extensions import db, csrf
import logging

logger = logging.getLogger(__name__)

client_auth_bp = Blueprint('client_auth', __name__, url_prefix='/api/client')


@client_auth_bp.route('/login', methods=['POST'])
@csrf.exempt  # Eximir de CSRF para app móvil
def client_login():
    """
    Login temporal para clientes - Solo DNI

    IMPORTANTE: Este es un endpoint TEMPORAL para pruebas.
    En producción debe requerir contraseña.

    Request JSON:
    {
        "dni": "12345678"
    }

    Returns:
        JSON: {
            "success": true,
            "client": {...},
            "message": "Login exitoso"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        dni = data.get('dni', '').strip()

        if not dni:
            return jsonify({
                'success': False,
                'message': 'DNI es requerido'
            }), 400

        # Buscar cliente por DNI
        client = Client.query.filter_by(dni=dni).first()

        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado. Verifica el DNI.'
            }), 404

        # Verificar que el cliente esté activo
        if client.status != 'Activo':
            return jsonify({
                'success': False,
                'message': 'Cliente inactivo. Contacta al administrador.'
            }), 403

        logger.info(f"Login exitoso de cliente: {client.dni}")

        return jsonify({
            'success': True,
            'message': 'Login exitoso',
            'client': client.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Error en login de cliente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al iniciar sesión: {str(e)}'
        }), 500


@client_auth_bp.route('/verify/<dni>', methods=['GET'])
@csrf.exempt
def verify_client(dni):
    """
    Verificar si un cliente existe y está activo

    Args:
        dni: Número de documento del cliente

    Returns:
        JSON: {"success": true, "exists": true, "active": true}
    """
    try:
        client = Client.query.filter_by(dni=dni).first()

        if not client:
            return jsonify({
                'success': True,
                'exists': False,
                'active': False
            }), 200

        return jsonify({
            'success': True,
            'exists': True,
            'active': client.status == 'Activo',
            'client_name': client.get_full_name() if hasattr(client, 'get_full_name') else client.nombres or client.razon_social
        }), 200

    except Exception as e:
        logger.error(f"Error al verificar cliente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al verificar cliente: {str(e)}'
        }), 500


@client_auth_bp.route('/exchange-rates', methods=['GET'])
@csrf.exempt
def get_exchange_rates():
    """
    Obtener tipos de cambio actuales

    Returns:
        JSON: {
            "success": true,
            "rates": {
                "compra": 3.75,
                "venta": 3.77
            }
        }
    """
    try:
        # TEMPORAL: Tipos de cambio hardcodeados
        # TODO: Obtener de configuración o base de datos controlada por Master
        return jsonify({
            'success': True,
            'rates': {
                'compra': 3.75,  # Tipo de cambio de compra (cliente vende USD)
                'venta': 3.77    # Tipo de cambio de venta (cliente compra USD)
            }
        }), 200

    except Exception as e:
        logger.error(f"Error al obtener tipos de cambio: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener tipos de cambio: {str(e)}'
        }), 500


@client_auth_bp.route('/health', methods=['GET'])
def health():
    """Health check para cliente auth"""
    return jsonify({
        'status': 'ok',
        'service': 'QoriCash Client Auth API',
        'version': '1.0.0-temporal'
    }), 200

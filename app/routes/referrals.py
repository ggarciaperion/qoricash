"""
Rutas de API para sistema de referidos
"""
from flask import Blueprint, request, jsonify
from app.extensions import db, csrf
from app.models.client import Client
from app.utils.referral import is_valid_referral_code_format, calculate_referral_discount
import logging

logger = logging.getLogger(__name__)

# Blueprint para referidos
referrals_bp = Blueprint('referrals', __name__, url_prefix='/api/referrals')

# Deshabilitar CSRF para endpoints de API
csrf.exempt(referrals_bp)


@referrals_bp.route('/validate', methods=['POST'])
def validate_referral_code():
    """
    Validar código de referido

    Body (JSON):
        - code: Código de referido a validar
        - client_dni: DNI del cliente que quiere usar el código (opcional)

    Returns:
        - success: bool
        - message: str
        - is_valid: bool
        - referrer: dict (opcional) - Información del referidor
    """
    try:
        data = request.get_json() or {}
        code = data.get('code', '').strip().upper()
        client_dni = data.get('client_dni', '').strip()

        if not code:
            return jsonify({
                'success': False,
                'message': 'Código de referido es requerido',
                'is_valid': False
            }), 400

        # Validar formato
        if not is_valid_referral_code_format(code):
            return jsonify({
                'success': True,
                'message': 'Formato de código inválido',
                'is_valid': False
            }), 200

        # Buscar el código en la base de datos
        referrer = Client.query.filter_by(referral_code=code).first()
        if not referrer:
            return jsonify({
                'success': True,
                'message': 'Código de referido no existe',
                'is_valid': False
            }), 200

        # Si se proporciona DNI, validar que no sea el propio código
        if client_dni:
            client = Client.query.filter_by(dni=client_dni).first()
            if client:
                # No puede usar su propio código
                if client.referral_code == code:
                    return jsonify({
                        'success': True,
                        'message': 'No puedes usar tu propio código de referido',
                        'is_valid': False
                    }), 200

                # Verificar si ya usó un código
                if client.used_referral_code:
                    return jsonify({
                        'success': True,
                        'message': 'Ya has usado un código de referido anteriormente',
                        'is_valid': False
                    }), 200

        # Código válido
        return jsonify({
            'success': True,
            'message': '¡Código válido! Se aplicará un descuento de 0.003 en tu tipo de cambio',
            'is_valid': True,
            'referrer': {
                'name': referrer.full_name,
                'code': referrer.referral_code
            }
        }), 200

    except Exception as e:
        logger.error(f'❌ Error validating referral code: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al validar código: {str(e)}',
            'is_valid': False
        }), 500


@referrals_bp.route('/stats/<string:client_dni>', methods=['GET'])
def get_referral_stats(client_dni):
    """
    Obtener estadísticas de referidos para un cliente

    Returns:
        - success: bool
        - referral_code: str - Código del cliente
        - total_referred: int - Total de clientes referidos
        - referred_clients: list - Lista de clientes referidos
    """
    try:
        client = Client.query.filter_by(dni=client_dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener clientes referidos
        referred_clients = Client.query.filter_by(referred_by=client.id).all()

        return jsonify({
            'success': True,
            'referral_code': client.referral_code,
            'total_referred': len(referred_clients),
            'referred_clients': [
                {
                    'id': ref.id,
                    'name': ref.full_name,
                    'document_type': ref.document_type,
                    'created_at': ref.created_at.isoformat() if ref.created_at else None
                }
                for ref in referred_clients
            ]
        }), 200

    except Exception as e:
        logger.error(f'❌ Error getting referral stats: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al obtener estadísticas: {str(e)}'
        }), 500


@referrals_bp.route('/calculate-discount', methods=['POST'])
def calculate_discount():
    """
    Calcular tipo de cambio con descuento de referido

    Body (JSON):
        - operation_type: 'Compra' | 'Venta'
        - base_rate: float - Tipo de cambio base
        - has_referral: bool - Si tiene código de referido válido

    Returns:
        - success: bool
        - base_rate: float
        - discounted_rate: float
        - discount: float
    """
    try:
        data = request.get_json() or {}
        operation_type = data.get('operation_type')
        base_rate = data.get('base_rate')
        has_referral = data.get('has_referral', False)

        if not operation_type or base_rate is None:
            return jsonify({
                'success': False,
                'message': 'operation_type y base_rate son requeridos'
            }), 400

        if not has_referral:
            return jsonify({
                'success': True,
                'base_rate': base_rate,
                'discounted_rate': base_rate,
                'discount': 0
            }), 200

        # Calcular tipo de cambio con descuento
        discounted_rate = calculate_referral_discount(operation_type, base_rate)

        return jsonify({
            'success': True,
            'base_rate': base_rate,
            'discounted_rate': discounted_rate,
            'discount': 0.003
        }), 200

    except Exception as e:
        logger.error(f'❌ Error calculating discount: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al calcular descuento: {str(e)}'
        }), 500

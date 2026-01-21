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


@referrals_bp.after_request
def after_request(response):
    """Agregar headers CORS a todas las respuestas del blueprint"""
    origin = request.headers.get('Origin')

    # Lista de orígenes permitidos
    allowed_origins = [
        'http://localhost:3000',  # Desarrollo local
        'https://qoricash.pe',     # Producción
        'https://www.qoricash.pe'  # Producción con www
    ]

    # Si el origen está en la lista, agregarlo
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'

    return response


@referrals_bp.route('/validate', methods=['OPTIONS', 'POST'])
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
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

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
    Obtener estadísticas completas de referidos para un cliente

    Returns:
        - success: bool
        - referral_code: str - Código del cliente
        - total_referred_clients: int - Total de clientes referidos
        - total_completed_operations: int - Operaciones completadas de referidos
        - total_pips_earned: float - Total de pips ganados
        - pips_available: float - Pips disponibles para usar
        - completed_uses: int - Usos válidos (operaciones completadas)
        - referral_history: list - Historial de operaciones completadas
        - referred_clients: list - Lista de clientes referidos
    """
    try:
        client = Client.query.filter_by(dni=client_dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Usar el servicio completo de referidos
        from app.services.referral_service import referral_service
        stats = referral_service.get_referral_stats(client)

        return jsonify({
            'success': True,
            **stats  # Expandir todas las estadísticas del servicio
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


@referrals_bp.route('/generate-reward-code', methods=['OPTIONS', 'POST'])
def generate_reward_code():
    """
    Generar un código de recompensa canjeando 30 pips

    Body (JSON):
        - client_dni: DNI del cliente que canjea

    Returns:
        - success: bool
        - message: str
        - reward_code: dict (código generado)
    """
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        data = request.get_json() or {}
        client_dni = data.get('client_dni', '').strip()

        if not client_dni:
            return jsonify({
                'success': False,
                'message': 'DNI del cliente es requerido'
            }), 400

        # Buscar cliente
        client = Client.query.filter_by(dni=client_dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Generar código de recompensa
        from app.services.referral_service import referral_service
        success, message, reward_code = referral_service.generate_reward_code(client)

        if success and reward_code:
            return jsonify({
                'success': True,
                'message': message,
                'reward_code': reward_code.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except Exception as e:
        logger.error(f'❌ Error generating reward code: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al generar código: {str(e)}'
        }), 500


@referrals_bp.route('/reward-codes/<string:client_dni>', methods=['GET'])
def get_reward_codes(client_dni):
    """
    Obtener códigos de recompensa de un cliente

    Returns:
        - success: bool
        - reward_codes: list
    """
    try:
        client = Client.query.filter_by(dni=client_dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener códigos de recompensa
        from app.services.referral_service import referral_service
        reward_codes = referral_service.get_client_reward_codes(client)

        return jsonify({
            'success': True,
            'reward_codes': reward_codes
        }), 200

    except Exception as e:
        logger.error(f'❌ Error getting reward codes: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al obtener códigos: {str(e)}'
        }), 500

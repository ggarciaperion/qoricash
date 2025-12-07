"""
Rutas API para la Plataforma Web Pública
Este módulo proporciona endpoints para que la plataforma web pública
pueda registrar clientes y operaciones en el sistema interno
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.client_service import ClientService
from app.services.operation_service import OperationService
from app.services.file_service import FileService
from app.services.notification_service import NotificationService
from app.utils.decorators import require_role
from app.models.client import Client
from app.models.operation import Operation
from app.extensions import db, csrf
import logging

logger = logging.getLogger(__name__)

platform_api_bp = Blueprint('platform_api', __name__, url_prefix='/api/platform')


@platform_api_bp.route('/register-client', methods=['POST'])
@csrf.exempt  # Eximir de CSRF para APIs externas
@login_required
@require_role('Plataforma', 'Master')
def register_client():
    """
    API: Registrar cliente desde la plataforma web pública

    Permite al rol Plataforma registrar automáticamente clientes
    que se crean desde la página web pública

    Request JSON:
    {
        "document_type": "DNI|CE|RUC",
        "dni": "12345678",
        "apellido_paterno": "García" (para DNI/CE),
        "apellido_materno": "Pérez" (para DNI/CE),
        "nombres": "Juan" (para DNI/CE),
        "razon_social": "Empresa SAC" (para RUC),
        "persona_contacto": "Nombre" (para RUC),
        "email": "email@ejemplo.com",
        "phone": "987654321",
        "direccion": "Av. Principal 123",
        "distrito": "Lima",
        "provincia": "Lima",
        "departamento": "Lima",
        "bank_accounts": [
            {
                "origen": "Lima",
                "bank_name": "BCP",
                "account_type": "Ahorro",
                "currency": "S/",
                "account_number": "19123456789012345678"
            }
        ],
        "dni_front_url": "https://...",
        "dni_back_url": "https://...",
        "dni_representante_front_url": "https://..." (para RUC),
        "dni_representante_back_url": "https://..." (para RUC),
        "ficha_ruc_url": "https://..." (para RUC)
    }

    Returns:
        JSON: {"success": true, "client": {...}, "message": "..."}
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        # Validar campos requeridos
        required_fields = ['document_type', 'dni', 'email']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return jsonify({
                'success': False,
                'message': f'Campos requeridos faltantes: {", ".join(missing_fields)}'
            }), 400

        # Verificar si el cliente ya existe
        existing_client = Client.query.filter_by(dni=data['dni']).first()
        if existing_client:
            return jsonify({
                'success': False,
                'message': f'Ya existe un cliente con el documento {data["dni"]}',
                'client_id': existing_client.id
            }), 409

        # Preparar datos para el servicio
        client_data = {
            'document_type': data['document_type'],
            'dni': data['dni'],
            'email': data['email'],
            'phone': data.get('phone', ''),
            'direccion': data.get('direccion', ''),
            'distrito': data.get('distrito', ''),
            'provincia': data.get('provincia', ''),
            'departamento': data.get('departamento', ''),
            'bank_accounts': data.get('bank_accounts', []),
            'created_by_id': current_user.id
        }

        # Campos específicos según tipo de documento
        if data['document_type'] in ['DNI', 'CE']:
            client_data.update({
                'apellido_paterno': data.get('apellido_paterno', ''),
                'apellido_materno': data.get('apellido_materno', ''),
                'nombres': data.get('nombres', ''),
                'dni_front_url': data.get('dni_front_url', ''),
                'dni_back_url': data.get('dni_back_url', '')
            })
        elif data['document_type'] == 'RUC':
            client_data.update({
                'razon_social': data.get('razon_social', ''),
                'persona_contacto': data.get('persona_contacto', ''),
                'dni_representante_front_url': data.get('dni_representante_front_url', ''),
                'dni_representante_back_url': data.get('dni_representante_back_url', ''),
                'ficha_ruc_url': data.get('ficha_ruc_url', '')
            })

        # Crear cliente usando el servicio
        success, result = ClientService.create_client(client_data)

        if not success:
            return jsonify({
                'success': False,
                'message': result
            }), 400

        # Enviar notificación
        NotificationService.emit_client_created(result)

        logger.info(f"Cliente creado desde plataforma web: {result.dni} por {current_user.username}")

        return jsonify({
            'success': True,
            'message': 'Cliente registrado exitosamente desde la plataforma web',
            'client': result.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error al registrar cliente desde plataforma: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al registrar cliente: {str(e)}'
        }), 500


@platform_api_bp.route('/register-operation', methods=['POST'])
@csrf.exempt  # Eximir de CSRF para APIs externas
@login_required
@require_role('Plataforma', 'Master')
def register_operation():
    """
    API: Registrar operación desde la plataforma web pública

    Permite al rol Plataforma registrar automáticamente operaciones
    que se crean desde la página web pública

    Request JSON:
    {
        "client_dni": "12345678",
        "operation_type": "Compra|Venta",
        "amount_usd": 1000.00,
        "exchange_rate": 3.75,
        "source_account": "19123456789012345678",
        "destination_account": "19187654321098765432",
        "notes": "Operación desde web"
    }

    Returns:
        JSON: {"success": true, "operation": {...}, "message": "..."}
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        # Validar campos requeridos
        required_fields = ['client_dni', 'operation_type', 'amount_usd', 'exchange_rate']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return jsonify({
                'success': False,
                'message': f'Campos requeridos faltantes: {", ".join(missing_fields)}'
            }), 400

        # Buscar cliente por DNI
        client = Client.query.filter_by(dni=data['client_dni']).first()
        if not client:
            return jsonify({
                'success': False,
                'message': f'No existe un cliente con el documento {data["client_dni"]}. Debe registrar el cliente primero.'
            }), 404

        # Crear operación usando el servicio
        success, message, operation = OperationService.create_operation(
            current_user=current_user,
            client_id=client.id,
            operation_type=data['operation_type'],
            amount_usd=data['amount_usd'],
            exchange_rate=data['exchange_rate'],
            source_account=data.get('source_account'),
            destination_account=data.get('destination_account'),
            notes=data.get('notes'),
            origen='plataforma'  # ← IMPORTANTE: Marcar origen como plataforma
        )

        if not success:
            return jsonify({
                'success': False,
                'message': message
            }), 400

        # Enviar notificación
        NotificationService.emit_operation_created(operation)

        logger.info(f"Operación creada desde plataforma web: {operation.operation_id} por {current_user.username}")

        return jsonify({
            'success': True,
            'message': 'Operación registrada exitosamente desde la plataforma web',
            'operation': operation.to_dict(include_relations=True)
        }), 201

    except Exception as e:
        logger.error(f"Error al registrar operación desde plataforma: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al registrar operación: {str(e)}'
        }), 500


@platform_api_bp.route('/get-client/<dni>', methods=['GET'])
@login_required
@require_role('Plataforma', 'Master')
def get_client_by_dni(dni):
    """
    API: Obtener información de un cliente por DNI

    Permite verificar si un cliente ya existe en el sistema
    antes de intentar registrarlo

    Args:
        dni: Número de documento del cliente

    Returns:
        JSON: {"success": true, "client": {...}} o {"success": false, "message": "..."}
    """
    try:
        client = Client.query.filter_by(dni=dni).first()

        if not client:
            return jsonify({
                'success': False,
                'message': f'No se encontró cliente con documento {dni}'
            }), 404

        return jsonify({
            'success': True,
            'client': client.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Error al buscar cliente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al buscar cliente: {str(e)}'
        }), 500


@platform_api_bp.route('/health', methods=['GET'])
def health_check():
    """
    API: Health check para verificar que el servicio está disponible

    No requiere autenticación

    Returns:
        JSON: {"status": "ok"}
    """
    return jsonify({
        'status': 'ok',
        'service': 'QoriCash Platform API',
        'version': '1.0.0'
    }), 200

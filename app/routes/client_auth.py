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


@client_auth_bp.route('/create-operation', methods=['POST'])
@csrf.exempt
def create_operation():
    """
    API: Crear operación desde app móvil (cliente)

    Request JSON:
    {
        "client_dni": "12345678",
        "operation_type": "Compra|Venta",
        "amount_usd": 1000.00,
        "exchange_rate": 3.75,
        "source_account": "19123456789012345678",
        "destination_account": "19187654321098765432",
        "notes": "Operación desde app móvil"
    }

    Returns:
        JSON: {"success": true, "operation": {...}}
    """
    try:
        from app.models.client import Client
        from app.models.user import User
        from app.services.operation_service import OperationService
        from app.services.notification_service import NotificationService

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
                'message': f'No existe un cliente con el documento {data["client_dni"]}'
            }), 404

        if client.status != 'Activo':
            return jsonify({
                'success': False,
                'message': 'Cliente inactivo. Contacta al administrador.'
            }), 403

        # Obtener usuario plataforma para crear la operación
        platform_user = User.query.filter_by(role='Plataforma').first()
        if not platform_user:
            return jsonify({
                'success': False,
                'message': 'Error de configuración del sistema'
            }), 500

        # Crear operación usando el servicio
        success, message, operation = OperationService.create_operation(
            current_user=platform_user,
            client_id=client.id,
            operation_type=data['operation_type'],
            amount_usd=data['amount_usd'],
            exchange_rate=data['exchange_rate'],
            source_account=data.get('source_account'),
            destination_account=data.get('destination_account'),
            notes=data.get('notes', 'Operación desde app móvil'),
            origen='app'
        )

        if not success:
            return jsonify({
                'success': False,
                'message': message
            }), 400

        # Enviar notificación
        try:
            NotificationService.emit_operation_created(operation)
        except Exception as e:
            logger.warning(f"Error enviando notificación: {str(e)}")

        logger.info(f"Operación creada desde app móvil: {operation.operation_id} para cliente {client.dni}")

        return jsonify({
            'success': True,
            'message': 'Operación creada exitosamente',
            'operation': operation.to_dict(include_relations=True)
        }), 201

    except Exception as e:
        logger.error(f"Error al crear operación desde app móvil: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Error al crear operación: {str(e)}'
        }), 500


@client_auth_bp.route('/my-operations/<dni>', methods=['GET'])
@csrf.exempt
def get_client_operations(dni):
    """
    Obtener operaciones del cliente por DNI

    Query params:
        - status: filtrar por estado (Pendiente, En proceso, etc.)
        - limit: limitar resultados

    Returns:
        JSON: {"success": true, "operations": [...]}
    """
    try:
        from app.models.client import Client
        from app.models.operation import Operation

        # Buscar cliente
        client = Client.query.filter_by(dni=dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener parámetros de filtro
        status_filter = request.args.get('status')
        limit = request.args.get('limit', type=int)

        # Query base
        query = Operation.query.filter_by(client_id=client.id).order_by(Operation.created_at.desc())

        # Aplicar filtros
        if status_filter:
            query = query.filter_by(status=status_filter)

        if limit:
            query = query.limit(limit)

        operations = query.all()

        return jsonify({
            'success': True,
            'operations': [op.to_dict(include_relations=True) for op in operations]
        }), 200

    except Exception as e:
        logger.error(f"Error al obtener operaciones del cliente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener operaciones: {str(e)}'
        }), 500


@client_auth_bp.route('/operation/<int:operation_id>', methods=['GET'])
@csrf.exempt
def get_operation_detail(operation_id):
    """
    Obtener detalle de una operación por ID

    Args:
        operation_id: ID de la operación

    Returns:
        JSON: {"success": true, "operation": {...}}
    """
    try:
        from app.models.operation import Operation

        operation = Operation.query.get(operation_id)
        if not operation:
            return jsonify({
                'success': False,
                'message': 'Operación no encontrada'
            }), 404

        return jsonify({
            'success': True,
            'operation': operation.to_dict(include_relations=True)
        }), 200

    except Exception as e:
        logger.error(f"Error al obtener detalle de operación: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener operación: {str(e)}'
        }), 500


@client_auth_bp.route('/upload-deposit-proof/<int:operation_id>', methods=['POST'])
@csrf.exempt
def upload_deposit_proof(operation_id):
    """
    Subir comprobante de abono desde app móvil

    Args:
        operation_id: ID de la operación

    Form data:
        file: archivo imagen del comprobante
        deposit_index: índice del depósito (default 0)

    Returns:
        JSON: {"success": true, "message": "...", "url": "..."}
    """
    try:
        from app.models.operation import Operation
        from app.services.file_service import FileService

        operation = Operation.query.get(operation_id)
        if not operation:
            return jsonify({
                'success': False,
                'message': 'Operación no encontrada'
            }), 404

        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No se envió ningún archivo'
            }), 400

        file = request.files['file']
        deposit_index = request.form.get('deposit_index', 0, type=int)

        logger.info(f"Subiendo comprobante para operación {operation.operation_id}, deposit_index: {deposit_index}")

        file_service = FileService()
        success, message, url = file_service.upload_file(
            file,
            'deposits',
            f"{operation.operation_id}_deposit_{deposit_index}"
        )

        if not success:
            return jsonify({
                'success': False,
                'message': message
            }), 400

        # Actualizar el abono con la URL del comprobante
        deposits = operation.client_deposits or []

        # Asegurar que existe el índice
        while len(deposits) <= deposit_index:
            deposits.append({})

        deposits[deposit_index]['comprobante_url'] = url
        operation.client_deposits = deposits

        # Cambiar estado a "En proceso" si está pendiente
        if operation.status == 'Pendiente':
            operation.status = 'En proceso'

        db.session.commit()

        logger.info(f"Comprobante subido exitosamente para operación {operation.operation_id}")

        return jsonify({
            'success': True,
            'message': 'Comprobante subido exitosamente',
            'url': url
        }), 200

    except Exception as e:
        logger.error(f"Error al subir comprobante: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Error al subir comprobante: {str(e)}'
        }), 500


@client_auth_bp.route('/health', methods=['GET'])
def health():
    """Health check para cliente auth"""
    return jsonify({
        'status': 'ok',
        'service': 'QoriCash Client Auth API',
        'version': '1.0.0-temporal'
    }), 200

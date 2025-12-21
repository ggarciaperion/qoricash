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
        importe: importe del abono (opcional)
        codigo_operacion: código de la operación (opcional)

    Returns:
        JSON: {"success": true, "message": "...", "url": "..."}
    """
    try:
        from app.models.operation import Operation
        from app.services.file_service import FileService
        from sqlalchemy.orm.attributes import flag_modified

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
        importe = request.form.get('importe', type=float)
        codigo_operacion = request.form.get('codigo_operacion', type=str)

        logger.info(f"Subiendo comprobante para operación {operation.operation_id}, deposit_index: {deposit_index}, importe: {importe}, codigo_operacion: {codigo_operacion}")
        logger.info(f"Form data recibida: {request.form.to_dict()}")

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

        # Actualizar el abono con la URL del comprobante y datos adicionales
        deposits = operation.client_deposits or []
        logger.info(f"📋 Deposits actuales: {deposits}")

        # Asegurar que existe el índice
        while len(deposits) <= deposit_index:
            deposits.append({})

        # Actualizar el comprobante con todos los datos
        deposits[deposit_index]['comprobante_url'] = url
        logger.info(f"✅ URL guardada: {url}")

        if importe is not None:
            # Convertir explícitamente a float
            deposits[deposit_index]['importe'] = float(importe)
            logger.info(f"✅ Importe guardado: {deposits[deposit_index]['importe']} (tipo: {type(deposits[deposit_index]['importe'])})")
        else:
            logger.warning(f"⚠️ Importe es None, no se guardará")

        if codigo_operacion:
            # Convertir explícitamente a string
            deposits[deposit_index]['codigo_operacion'] = str(codigo_operacion)
            logger.info(f"✅ Código guardado: {deposits[deposit_index]['codigo_operacion']} (tipo: {type(deposits[deposit_index]['codigo_operacion'])})")
        else:
            logger.warning(f"⚠️ Código de operación está vacío, no se guardará")

        # Agregar cuenta_cargo para que se muestre en el modal del operador
        # Usar la cuenta origen de la operación
        if operation.source_account:
            deposits[deposit_index]['cuenta_cargo'] = operation.source_account
            logger.info(f"✅ Cuenta cargo guardada: {deposits[deposit_index]['cuenta_cargo']}")

        # Actualizar y marcar el campo como modificado para SQLAlchemy
        operation.client_deposits = deposits
        flag_modified(operation, 'client_deposits')

        logger.info(f"📦 Deposits completo antes de commit: {deposits}")
        logger.info(f"📦 Deposit[{deposit_index}] = {deposits[deposit_index]}")

        # Cambiar estado a "En proceso" si está pendiente
        logger.info(f"🔍 Estado actual de operación {operation.operation_id}: {operation.status}")
        logger.info(f"🔍 Operador asignado actual: {operation.assigned_operator_id}")

        if operation.status == 'Pendiente':
            operation.status = 'En proceso'
            logger.info(f"🔄 Estado cambiado a 'En proceso' para operación {operation.operation_id}")

        # Auto-asignar operador si está "En proceso" y NO tiene operador asignado
        if operation.status == 'En proceso' and not operation.assigned_operator_id:
            logger.info(f"🎯 Iniciando auto-asignación de operador para {operation.operation_id}")

            from app.services.operation_service import OperationService

            try:
                operator_id = OperationService.assign_operator_balanced()
                logger.info(f"🎯 Resultado de assign_operator_balanced(): {operator_id}")

                if operator_id:
                    operation.assigned_operator_id = operator_id
                    logger.info(f"✅ Operador {operator_id} auto-asignado a operación {operation.operation_id}")
                else:
                    logger.warning(f"⚠️ assign_operator_balanced() retornó None - No hay operadores activos disponibles")
            except Exception as e:
                logger.error(f"❌ Error al asignar operador: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            if operation.status != 'En proceso':
                logger.info(f"ℹ️ No se asigna operador porque estado no es 'En proceso': {operation.status}")
            if operation.assigned_operator_id:
                logger.info(f"ℹ️ No se asigna operador porque ya tiene uno asignado: {operation.assigned_operator_id}")

        # Commit de todos los cambios
        logger.info(f"💾 Guardando cambios en base de datos...")
        db.session.commit()
        logger.info(f"✅ Cambios guardados exitosamente")

        # Refrescar la operación desde la DB para confirmar que se guardó correctamente
        db.session.refresh(operation)

        logger.info(f"🔍 VERIFICACIÓN POST-COMMIT:")
        logger.info(f"  📋 Estado final: {operation.status}")
        logger.info(f"  👤 Operador asignado final: {operation.assigned_operator_id}")
        logger.info(f"  📦 Deposits en DB: {operation.client_deposits}")

        # Verificar que los datos se guardaron correctamente
        saved_deposit = operation.client_deposits[deposit_index] if operation.client_deposits else {}
        logger.info(f"  ✅ Deposit[{deposit_index}] verificado:")
        logger.info(f"     - importe: {saved_deposit.get('importe')}")
        logger.info(f"     - codigo: {saved_deposit.get('codigo_operacion')}")
        logger.info(f"     - url: {saved_deposit.get('comprobante_url')}")
        logger.info(f"     - cuenta_cargo: {saved_deposit.get('cuenta_cargo')}")

        return jsonify({
            'success': True,
            'message': 'Comprobante subido exitosamente',
            'url': url,
            'deposit': saved_deposit  # Devolver el deposit guardado para verificación
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

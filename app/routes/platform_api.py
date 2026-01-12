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


@platform_api_bp.after_request
def after_request(response):
    """Agregar headers CORS a todas las respuestas del blueprint"""
    origin = request.headers.get('Origin')

    # Lista de orígenes permitidos
    allowed_origins = [
        'http://localhost:3000',  # Página web QoriCash
        'http://localhost:8081',  # App móvil Expo
        'http://localhost:8082',  # App móvil Expo (alternativo)
        'http://localhost:19006',  # App móvil Expo (web)
        'https://app.qoricash.pe'  # App móvil en producción
    ]

    # Si el origen está en la lista, agregarlo
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'

    return response


@platform_api_bp.route('/register-client', methods=['POST'])
@csrf.exempt  # Eximir de CSRF para APIs externas
@login_required
@require_role('Plataforma', 'Master', 'App')
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
@require_role('Plataforma', 'Master', 'App')
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
@require_role('Plataforma', 'Master', 'App')
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


@platform_api_bp.route('/exchange-rates', methods=['GET', 'POST'])
@login_required
@require_role('Master')
def manage_exchange_rates():
    """
    API: Obtener o actualizar tipos de cambio (solo Master)

    GET: Obtener tipos actuales
    POST: Actualizar tipos de cambio

    Request JSON (POST):
    {
        "buy_rate": 3.75,
        "sell_rate": 3.77
    }

    Returns:
        JSON: {
            "success": true,
            "rates": {"compra": 3.75, "venta": 3.77}
        }
    """
    from app.models.exchange_rate import ExchangeRate

    try:
        if request.method == 'GET':
            # Obtener tipos actuales
            rate = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()

            if rate:
                return jsonify({
                    'success': True,
                    'rates': rate.to_dict()
                }), 200
            else:
                return jsonify({
                    'success': True,
                    'rates': {
                        'compra': 3.75,
                        'venta': 3.77,
                        'updated_by': None,
                        'updated_at': None
                    }
                }), 200

        elif request.method == 'POST':
            # Actualizar tipos de cambio
            data = request.get_json()

            buy_rate = data.get('buy_rate')
            sell_rate = data.get('sell_rate')

            # Validaciones
            if not buy_rate or not sell_rate:
                return jsonify({
                    'success': False,
                    'message': 'Debe proporcionar buy_rate y sell_rate'
                }), 400

            try:
                buy_rate = float(buy_rate)
                sell_rate = float(sell_rate)
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Los tipos de cambio deben ser números válidos'
                }), 400

            # Validar rango razonable
            if buy_rate <= 0 or sell_rate <= 0:
                return jsonify({
                    'success': False,
                    'message': 'Los tipos de cambio deben ser mayores a 0'
                }), 400

            if buy_rate > 10 or sell_rate > 10:
                return jsonify({
                    'success': False,
                    'message': 'Los tipos de cambio parecen inusualmente altos (>10)'
                }), 400

            if sell_rate < buy_rate:
                return jsonify({
                    'success': False,
                    'message': 'El tipo de cambio de venta debe ser mayor o igual al de compra'
                }), 400

            # Actualizar tipos de cambio
            new_rate = ExchangeRate.update_rates(
                buy_rate=buy_rate,
                sell_rate=sell_rate,
                user_id=current_user.id
            )

            logger.info(f"💱 Tipos de cambio actualizados por {current_user.username}: Compra={buy_rate}, Venta={sell_rate}")

            # Emitir evento Socket.IO para actualizar tipos en tiempo real en todas las apps
            try:
                from app.extensions import socketio
                event_data = {
                    'compra': float(buy_rate),
                    'venta': float(sell_rate),
                    'updated_by': current_user.username,
                    'updated_at': new_rate.updated_at.isoformat()
                }
                # Emitir a TODOS los clientes conectados (broadcast)
                socketio.emit('tipos_cambio_actualizados', event_data, namespace='/')
                logger.info(f"📡 Evento Socket.IO emitido a TODOS los clientes: tipos_cambio_actualizados - Compra: {buy_rate}, Venta: {sell_rate}")
            except Exception as socket_error:
                logger.error(f"❌ Error al emitir evento Socket.IO: {str(socket_error)}")
                logger.exception(socket_error)

            return jsonify({
                'success': True,
                'message': 'Tipos de cambio actualizados exitosamente',
                'rates': new_rate.to_dict()
            }), 200

    except Exception as e:
        logger.error(f"Error al gestionar tipos de cambio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Error al gestionar tipos de cambio: {str(e)}'
        }), 500


@platform_api_bp.route('/health', methods=['GET'])
def health_check():
    """
    API: Health check para verificar que el servicio está disponible

    No requiere autenticación

    Returns:
        JSON: {"status": "ok"}
    """
    from flask import current_app

    # Lista de rutas registradas (para debug)
    routes = []
    for rule in current_app.url_map.iter_rules():
        if 'platform' in rule.rule or 'exchange' in rule.rule:
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                'path': rule.rule
            })

    return jsonify({
        'status': 'ok',
        'service': 'QoriCash Platform API',
        'version': '1.0.1',
        'registered_routes': routes[:10]  # Primeras 10 rutas para debug
    }), 200


@platform_api_bp.route('/public/exchange-rates', methods=['GET'])
@csrf.exempt
def get_public_exchange_rates():
    """
    API: Obtener tipos de cambio actuales (público, sin autenticación)

    Endpoint público para que la página web y app móvil obtengan
    los tipos de cambio actuales sin necesidad de autenticación

    Returns:
        JSON: {
            "success": true,
            "data": {
                "tipo_compra": 3.75,
                "tipo_venta": 3.77,
                "fecha_actualizacion": "2025-01-11T12:00:00"
            }
        }
    """
    try:
        from app.models.exchange_rate import ExchangeRate
        from datetime import datetime

        # Obtener tipos de cambio desde la base de datos
        try:
            rate = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()

            if rate:
                return jsonify({
                    'success': True,
                    'data': {
                        'tipo_compra': float(rate.buy_rate),
                        'tipo_venta': float(rate.sell_rate),
                        'fecha_actualizacion': rate.updated_at.isoformat() if rate.updated_at else None
                    }
                }), 200
        except Exception as db_error:
            logger.warning(f"Error al consultar base de datos: {str(db_error)}")
            # Continuar con valores por defecto

        # Valores por defecto si no hay registros o si hay error en BD
        return jsonify({
            'success': True,
            'data': {
                'tipo_compra': 3.75,
                'tipo_venta': 3.77,
                'fecha_actualizacion': datetime.utcnow().isoformat()
            }
        }), 200

    except Exception as e:
        logger.error(f"Error al obtener tipos de cambio públicos: {str(e)}")
        # Aún en caso de error, retornar valores por defecto
        return jsonify({
            'success': True,
            'data': {
                'tipo_compra': 3.75,
                'tipo_venta': 3.77,
                'fecha_actualizacion': None
            }
        }), 200

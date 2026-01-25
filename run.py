"""
Entry point para QoriCash Trading V2

Desarrollo: python run.py
Producción: gunicorn -c gunicorn_config.py run:app
"""
# CRÍTICO: Monkey patch de eventlet DEBE ser lo primero
# Esto debe ejecutarse antes de cualquier import de threading, SQLAlchemy, etc.
import eventlet
eventlet.monkey_patch()

# Configurar psycopg2 para eventlet INMEDIATAMENTE después del monkey patch
try:
    from psycogreen.eventlet import patch_psycopg
    patch_psycopg()
    print("[RUN.PY] psycopg2 patched con psycogreen")
except ImportError:
    print("[RUN.PY] WARNING: psycogreen no disponible")

import os
from dotenv import load_dotenv

# Cargar variables de entorno (después de monkey patch)
load_dotenv()

# Ahora sí importar la app (para que config.py ya tenga las variables disponibles)
from app import create_app

# Crear aplicación (usado por gunicorn)
app = create_app()

# Obtener socketio después de crear la app
from app.extensions import socketio

# Healthcheck endpoint - SIN rate limiting, optimizado para respuesta rápida
from app.extensions import limiter
from flask import jsonify
import time

@app.route('/health')
@limiter.exempt
def health_check():
    """
    Endpoint para health checks de Render
    Responde inmediatamente sin consultas a BD
    """
    # Leer versión del deploy
    version_info = 'UNKNOWN'
    try:
        version_file = os.path.join(os.path.dirname(__file__), 'VERSION.txt')
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                version_info = f.read().strip().replace('\n', ' | ')
    except:
        pass

    return jsonify({
        'status': 'healthy',
        'service': 'qoricash-trading',
        'timestamp': time.time(),
        'version': version_info,
        'build': 'b10ba85'
    }), 200, {'Cache-Control': 'no-cache, no-store, must-revalidate'}

# TEMPORAL: Endpoint para limpiar bancos fantasma
@app.route('/admin/cleanup-banks-now')
@limiter.exempt
def cleanup_banks_now():
    """
    ENDPOINT TEMPORAL: Limpia bancos fantasma de la base de datos

    Elimina todos los bancos que NO están en el desplegable oficial del modal
    "Agregar Cuenta Bancaria a Reconciliación"

    ELIMINAR ESTE ENDPOINT después de ejecutarlo una vez
    """
    from app.extensions import db
    from app.models.bank_balance import BankBalance

    # Lista OFICIAL de bancos permitidos
    allowed_banks = [
        'BCP USD (654321)',
        'INTERBANK USD (456789)',
        'BANBIF USD (369852)',
        'PICHINCHA USD (159796)',
        'BCP PEN (123456)',
        'INTERBANK PEN (987654)',
        'BANBIF PEN (741852)',
        'PICHINCHA PEN (753951)'
    ]

    try:
        all_banks = BankBalance.query.all()
        deleted_banks = []
        kept_banks = []

        for bank in all_banks:
            if bank.bank_name not in allowed_banks:
                deleted_banks.append({
                    'name': bank.bank_name,
                    'id': bank.id,
                    'initial_usd': float(bank.initial_balance_usd or 0),
                    'initial_pen': float(bank.initial_balance_pen or 0)
                })
                db.session.delete(bank)
            else:
                kept_banks.append({
                    'name': bank.bank_name,
                    'initial_usd': float(bank.initial_balance_usd or 0),
                    'initial_pen': float(bank.initial_balance_pen or 0)
                })

        db.session.commit()

        total_usd_deleted = sum(b['initial_usd'] for b in deleted_banks)
        total_pen_deleted = sum(b['initial_pen'] for b in deleted_banks)
        total_usd_remaining = sum(b['initial_usd'] for b in kept_banks)
        total_pen_remaining = sum(b['initial_pen'] for b in kept_banks)

        return jsonify({
            'success': True,
            'deleted_count': len(deleted_banks),
            'deleted_banks': deleted_banks,
            'deleted_totals': {
                'usd': total_usd_deleted,
                'pen': total_pen_deleted
            },
            'remaining_count': len(kept_banks),
            'remaining_banks': kept_banks,
            'remaining_totals': {
                'usd': total_usd_remaining,
                'pen': total_pen_remaining
            },
            'message': f'✓ Eliminados {len(deleted_banks)} bancos fantasma. Total correcto USD: ${total_usd_remaining}'
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# TEMPORAL: Endpoint para actualizar constraints y corregir canal de operaciones
@app.route('/admin/fix-app-channel-now')
@limiter.exempt
def fix_app_channel_now():
    """
    ENDPOINT TEMPORAL URGENTE: Actualiza constraints y corrige canal de operaciones

    1. Actualiza constraints de la BD para soportar 'app' y 'Expirada'
    2. Corrige operaciones creadas desde app móvil

    ELIMINAR ESTE ENDPOINT después de ejecutarlo una vez
    """
    from app.extensions import db
    from app.models.operation import Operation
    from sqlalchemy import text

    results = {
        'migration_executed': False,
        'operations_updated': [],
        'errors': []
    }

    try:
        # 1. Actualizar constraint de origen
        try:
            db.session.execute(text("ALTER TABLE operations DROP CONSTRAINT IF EXISTS check_operation_origen"))
            db.session.execute(text("ALTER TABLE operations ADD CONSTRAINT check_operation_origen CHECK (origen IN ('sistema', 'plataforma', 'app'))"))
            results['origen_constraint'] = 'Updated'
        except Exception as e:
            results['errors'].append(f'Error updating origen constraint: {str(e)}')

        # 2. Actualizar constraint de status
        try:
            db.session.execute(text("ALTER TABLE operations DROP CONSTRAINT IF EXISTS check_operation_status"))
            db.session.execute(text("ALTER TABLE operations ADD CONSTRAINT check_operation_status CHECK (status IN ('Pendiente', 'En proceso', 'Completada', 'Cancelado', 'Expirada'))"))
            results['status_constraint'] = 'Updated'
        except Exception as e:
            results['errors'].append(f'Error updating status constraint: {str(e)}')

        db.session.commit()
        results['migration_executed'] = True

        # 3. Actualizar operaciones creadas desde la app móvil
        # Buscar por dos criterios:
        # A) Operaciones con notes='Operación desde app móvil'
        # B) Operaciones creadas por usuarios con rol 'Plataforma'

        from app.models.user import User
        from sqlalchemy import or_

        # Obtener ID del usuario Plataforma
        plataforma_user = User.query.filter_by(role='Plataforma').first()

        # Buscar operaciones que cumplan alguno de los criterios
        query_filters = [Operation.notes.like('%app móvil%')]
        if plataforma_user:
            query_filters.append(Operation.user_id == plataforma_user.id)

        app_operations = Operation.query.filter(or_(*query_filters)).all()

        for op in app_operations:
            old_origen = op.origen
            if op.origen != 'app':
                op.origen = 'app'
                created_by = 'Plataforma' if op.user_id == (plataforma_user.id if plataforma_user else None) else 'App móvil'
                results['operations_updated'].append({
                    'operation_id': op.operation_id,
                    'old_origen': old_origen,
                    'new_origen': 'app',
                    'created_by': created_by,
                    'notes': op.notes[:50] if op.notes else None
                })

        db.session.commit()

        return jsonify({
            'success': True,
            'migration_executed': results['migration_executed'],
            'constraints_updated': {
                'origen': results.get('origen_constraint', 'Error'),
                'status': results.get('status_constraint', 'Error')
            },
            'operations_updated_count': len(results['operations_updated']),
            'operations_updated': results['operations_updated'],
            'errors': results['errors'],
            'message': f"✓ Constraints actualizados y {len(results['operations_updated'])} operaciones corregidas a canal 'app'"
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'partial_results': results
        }), 500

# TEMPORAL: Endpoint para actualizar operaciones específicas a canal app
@app.route('/admin/update-operation-channel/<operation_id>/<new_origen>')
@limiter.exempt
def update_operation_channel(operation_id, new_origen):
    """
    ENDPOINT TEMPORAL: Actualiza el origen de una operación específica

    Uso: /admin/update-operation-channel/EXP-1153/app
    """
    from app.extensions import db
    from app.models.operation import Operation

    try:
        if new_origen not in ['sistema', 'plataforma', 'app', 'web']:
            return jsonify({
                'success': False,
                'error': f'Origen inválido: {new_origen}. Debe ser: sistema, plataforma, app o web'
            }), 400

        operation = Operation.query.filter_by(operation_id=operation_id).first()

        if not operation:
            return jsonify({
                'success': False,
                'error': f'Operación {operation_id} no encontrada'
            }), 404

        old_origen = operation.origen
        operation.origen = new_origen
        db.session.commit()

        return jsonify({
            'success': True,
            'operation_id': operation_id,
            'old_origen': old_origen,
            'new_origen': new_origen,
            'message': f'✓ Operación {operation_id} actualizada de "{old_origen}" a "{new_origen}"'
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# TEMPORAL: Endpoint para actualizar TODAS las operaciones con plataforma a app
@app.route('/admin/migrate-all-plataforma-to-app')
@limiter.exempt
def migrate_all_plataforma_to_app():
    """
    ENDPOINT TEMPORAL: Actualiza TODAS las operaciones con origen='plataforma' a origen='app'

    Esto es útil si todas las operaciones 'plataforma' son realmente de la app móvil
    """
    from app.extensions import db
    from app.models.operation import Operation

    try:
        # Buscar todas las operaciones con origen='plataforma'
        plataforma_ops = Operation.query.filter_by(origen='plataforma').all()

        updated = []
        for op in plataforma_ops:
            old_origen = op.origen
            op.origen = 'app'
            updated.append({
                'operation_id': op.operation_id,
                'old_origen': old_origen,
                'new_origen': 'app',
                'client_dni': op.client.dni if op.client else None,
                'created_at': op.created_at.isoformat() if op.created_at else None
            })

        db.session.commit()

        return jsonify({
            'success': True,
            'total_updated': len(updated),
            'operations': updated,
            'message': f'✓ {len(updated)} operaciones actualizadas de "plataforma" a "app"'
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# TEMPORAL: Endpoint para ejecutar manualmente el scheduler de expiración
@app.route('/admin/expire-operations-now')
@limiter.exempt
def expire_operations_now():
    """
    ENDPOINT TEMPORAL URGENTE: Ejecuta manualmente el scheduler de expiración

    Cancela operaciones pendientes que hayan excedido el tiempo límite de 15 minutos
    """
    from app.services.operation_expiry_service import OperationExpiryService
    from datetime import timedelta
    from app.utils.formatters import now_peru

    try:
        # Información del sistema
        current_time = now_peru()
        cutoff_time = current_time - timedelta(minutes=15)

        # Ejecutar el servicio de expiración
        expired_count = OperationExpiryService.expire_old_operations()

        return jsonify({
            'success': True,
            'current_time_peru': current_time.isoformat(),
            'cutoff_time': cutoff_time.isoformat(),
            'operations_cancelled': expired_count,
            'message': f'✓ {expired_count} operaciones canceladas. Operaciones creadas antes de {cutoff_time.strftime("%H:%M:%S")} fueron canceladas.'
        }), 200
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# TEMPORAL: Endpoint para verificar operaciones pendientes específicas
@app.route('/admin/check-pending-operations')
@limiter.exempt
def check_pending_operations():
    """
    ENDPOINT TEMPORAL: Verifica operaciones pendientes y su elegibilidad para expiración
    """
    from app.models.operation import Operation
    from datetime import timedelta
    from app.utils.formatters import now_peru

    try:
        current_time = now_peru()
        cutoff_time = current_time - timedelta(minutes=15)
        protection_cutoff = current_time - timedelta(hours=24)

        # Buscar todas las operaciones pendientes
        pending_ops = Operation.query.filter_by(status='Pendiente').all()

        operations_info = []
        for op in pending_ops:
            age_minutes = (current_time - op.created_at).total_seconds() / 60 if op.created_at else 0
            should_expire = (
                op.created_at < cutoff_time and
                op.created_at > protection_cutoff and
                op.origen in ['web', 'app', 'plataforma']
            ) if op.created_at else False

            operations_info.append({
                'operation_id': op.operation_id,
                'created_at': op.created_at.isoformat() if op.created_at else None,
                'age_minutes': round(age_minutes, 1),
                'origen': op.origen,
                'should_expire': should_expire,
                'reason': 'Will be cancelled' if should_expire else (
                    'Too recent (< 15 min)' if age_minutes < 15 else
                    'Too old (> 24h)' if age_minutes > 1440 else
                    'Wrong origen (sistema)' if op.origen == 'sistema' else
                    'Unknown'
                )
            })

        return jsonify({
            'success': True,
            'current_time_peru': current_time.isoformat(),
            'cutoff_time': cutoff_time.isoformat(),
            'protection_cutoff': protection_cutoff.isoformat(),
            'total_pending': len(pending_ops),
            'should_expire_count': sum(1 for op in operations_info if op['should_expire']),
            'operations': sorted(operations_info, key=lambda x: x['age_minutes'], reverse=True)
        }), 200
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# TEMPORAL: Endpoint para verificar que los templates están actualizados
@app.route('/admin/check-template-version')
@limiter.exempt
def check_template_version():
    """
    ENDPOINT TEMPORAL: Verificar qué versión del template se está sirviendo
    """
    from app.models.operation import Operation

    # Obtener una operación con origen='app'
    app_op = Operation.query.filter_by(origen='app').first()

    if not app_op:
        return jsonify({
            'error': 'No hay operaciones con origen=app en la base de datos'
        })

    # Renderizar solo la celda del canal para esta operación
    from flask import render_template_string

    template = """
    {% if op.origen == 'plataforma' %}
        <span class="badge bg-purple" style="background-color: #6f42c1;">Web</span>
    {% elif op.origen == 'app' %}
        <span class="badge bg-info">App</span>
    {% else %}
        <span class="badge bg-secondary">Sistema</span>
    {% endif %}
    """

    html = render_template_string(template, op=app_op)

    return jsonify({
        'operation_id': app_op.operation_id,
        'origen_in_db': app_op.origen,
        'expected_badge': 'App (blue bg-info)',
        'rendered_html': html.strip(),
        'template_has_app_support': 'elif op.origen' in template,
        'message': 'Si rendered_html muestra "App", el template está correcto'
    })

def start_operation_expiry_scheduler():
    """
    Tarea periódica para expirar operaciones automáticamente
    Se ejecuta cada 60 segundos en un greenlet separado
    """
    while True:
        try:
            with app.app_context():
                from app.services.operation_expiry_service import OperationExpiryService
                expired_count = OperationExpiryService.expire_old_operations()
                if expired_count > 0:
                    print(f"[SCHEDULER] ⏱️ {expired_count} operaciones expiradas automáticamente")
        except Exception as e:
            print(f"[SCHEDULER] Error en scheduler de expiración: {str(e)}")

        # Esperar 60 segundos antes de la próxima verificación
        eventlet.sleep(60)

if __name__ == '__main__':
    # Iniciar scheduler de expiración en un greenlet separado
    print("[RUN.PY] Iniciando scheduler de expiracion de operaciones...")
    eventlet.spawn(start_operation_expiry_scheduler)

    # Solo para desarrollo local
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True
    )

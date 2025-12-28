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

        # 3. Actualizar operaciones creadas con notes='Operación desde app móvil'
        # Estas son las operaciones que fueron creadas desde la app pero tienen origen incorrecto
        app_operations = Operation.query.filter(
            Operation.notes.like('%app móvil%')
        ).all()

        for op in app_operations:
            old_origen = op.origen
            if op.origen != 'app':
                op.origen = 'app'
                results['operations_updated'].append({
                    'operation_id': op.operation_id,
                    'old_origen': old_origen,
                    'new_origen': 'app',
                    'notes': op.notes
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
    print("[RUN.PY] 🕒 Iniciando scheduler de expiración de operaciones...")
    eventlet.spawn(start_operation_expiry_scheduler)

    # Solo para desarrollo local
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True
    )

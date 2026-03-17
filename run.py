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

# =============================================================================
# CLI COMMANDS (reemplazan los endpoints /admin/* que eran inseguros)
# Uso en Render Shell: flask <command>
# =============================================================================

@app.cli.command("cleanup-banks")
def cleanup_banks_now():
    """
    ENDPOINT TEMPORAL: Limpia bancos fantasma de la base de datos

    Elimina todos los bancos que NO están en el desplegable oficial del modal
    "Agregar Cuenta Bancaria a Reconciliación"

    ELIMINAR ESTE ENDPOINT después de ejecutarlo una vez
    """
    from app.extensions import db
    from app.models.bank_balance import BankBalance
    from app.config.bank_accounts import ALLOWED_BANK_NAMES

    # Lista OFICIAL importada desde app/config/bank_accounts.py
    allowed_banks = ALLOWED_BANK_NAMES

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

        print(f"✓ Eliminados {len(deleted_banks)} bancos fantasma")
        print(f"✓ Restantes: {len(kept_banks)} bancos — USD total: ${total_usd_remaining}")

    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"✗ Error: {e}")
        traceback.print_exc()


@app.cli.command("fix-app-channel")
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
            db.session.execute(text("ALTER TABLE operations ADD CONSTRAINT check_operation_origen CHECK (origen IN ('sistema', 'plataforma', 'app', 'web'))"))
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
        # Buscar operaciones con notes='Operación desde app móvil'

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
                    'notes': op.notes[:50] if op.notes else None
                })

        db.session.commit()

        print(f"✓ Constraints actualizados, {len(results['operations_updated'])} operaciones corregidas")
        if results['errors']:
            print(f"  Errores parciales: {results['errors']}")

    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"✗ Error: {e}")
        traceback.print_exc()


@app.cli.command("update-operation-channel")
def update_operation_channel():
    """Uso: flask update-operation-channel (editar script para especificar ID y origen)"""
    from app.extensions import db
    from app.models.operation import Operation
    # Editar estas variables antes de ejecutar:
    operation_id = None  # ej: 'EXP-1153'
    new_origen = None    # ej: 'app'
    if not operation_id or new_origen not in ['sistema', 'app', 'web']:
        print("✗ Define operation_id y new_origen en el script antes de ejecutar")
        return
    try:
        op = Operation.query.filter_by(operation_id=operation_id).first()
        if not op:
            print(f"✗ Operación {operation_id} no encontrada")
            return
        old = op.origen
        op.origen = new_origen
        db.session.commit()
        print(f"✓ {operation_id}: '{old}' → '{new_origen}'")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error: {e}")


@app.cli.command("migrate-plataforma-to-app")
def migrate_all_plataforma_to_app():
    """Actualiza TODAS las operaciones con origen=plataforma a origen=app"""
    from app.extensions import db
    from app.models.operation import Operation
    try:
        ops = Operation.query.filter_by(origen='plataforma').all()
        for op in ops:
            op.origen = 'app'
        db.session.commit()
        print(f"✓ {len(ops)} operaciones actualizadas a origen=app")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error: {e}")


@app.cli.command("expire-operations")
def expire_operations_now():
    """Ejecuta manualmente el scheduler de expiración de operaciones"""
    from app.services.operation_expiry_service import OperationExpiryService
    try:
        count = OperationExpiryService.expire_old_operations()
        print(f"✓ {count} operaciones expiradas")
    except Exception as e:
        print(f"✗ Error: {e}")


@app.cli.command("check-pending-operations")
def check_pending_operations():
    """Lista operaciones pendientes y su elegibilidad para expiración"""
    from app.models.operation import Operation
    from datetime import timedelta
    from app.utils.formatters import now_peru
    try:
        now = now_peru()
        cutoff = now - timedelta(minutes=15)
        ops = Operation.query.filter_by(status='Pendiente').all()
        print(f"Total pendientes: {len(ops)}")
        for op in sorted(ops, key=lambda x: x.created_at or now, reverse=True):
            age = round((now - op.created_at).total_seconds() / 60, 1) if op.created_at else 0
            flag = "→ EXPIRA" if op.created_at and op.created_at < cutoff and op.origen != 'sistema' else ""
            print(f"  {op.operation_id}  {age} min  {op.origen}  {flag}")
    except Exception as e:
        print(f"✗ Error: {e}")


@app.cli.command("cleanup-web-users")
def cleanup_web_users():
    """Consolida usuarios Web/Plataforma duplicados en el usuario canónico"""
    from app.extensions import db
    from app.models.user import User
    from app.models.client import Client
    from sqlalchemy import text
    try:
        canonical = User.query.filter(
            (User.email == 'web@qoricash.pe') | (User.dni == '99999997')
        ).order_by(User.id.asc()).first()
        if not canonical:
            print("✗ No se encontró el usuario Web canónico")
            return
        duplicates = User.query.filter(
            User.role.in_(['Web', 'Plataforma']), User.id != canonical.id
        ).all()
        reassigned = 0
        for dup in duplicates:
            clients = Client.query.filter_by(created_by=dup.id).all()
            for c in clients:
                c.created_by = canonical.id
                reassigned += 1
            db.session.execute(
                text("UPDATE operations SET user_id=:cid WHERE user_id=:did"),
                {'cid': canonical.id, 'did': dup.id}
            )
            dup.status = 'Inactivo'
        canonical.role = 'Web'
        canonical.status = 'Activo'
        db.session.commit()
        print(f"✓ {len(duplicates)} duplicados desactivados, {reassigned} clientes reasignados")
    except Exception as e:
        db.session.rollback()
        print(f"✗ Error: {e}")


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

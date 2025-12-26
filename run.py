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

if __name__ == '__main__':
    # Solo para desarrollo local
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True
    )

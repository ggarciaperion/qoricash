"""
Configuración de Gunicorn para producción en Render
"""
import os

# Bind
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Workers - 1 worker con eventlet para Socket.IO (512MB RAM plan Starter)
workers = 1
worker_class = 'eventlet'
worker_connections = 1000
threads = 1

# Timeouts
timeout = 180
graceful_timeout = 90
keepalive = 5

# Memory limits (optimizado para plan Starter)
max_requests = 250
max_requests_jitter = 25

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Preload
preload_app = False

# Worker temp directory
worker_tmp_dir = '/dev/shm'

print(f"✓ Gunicorn configurado: {workers} workers, timeout {timeout}s")

# Hook: Ejecutar cuando cada worker arranca (más confiable que on_starting con eventlet)
def post_worker_init(worker):
    """
    Hook que se ejecuta cuando cada worker termina de inicializarse.
    Con 1 solo worker, esto se ejecuta una vez.
    """
    print(f"🔧 Worker {worker.pid} inicializado - Verificando DB...")

    try:
        # Importar aquí para evitar problemas de importación circular
        from app import create_app
        from app.extensions import db
        from app.models.user import User

        app = create_app()

        with app.app_context():
            # Verificar si las tablas ya existen consultando User
            try:
                User.query.first()
                print("✓ Tablas de DB ya existen")
            except:
                # Si falla, crear tablas
                print("Creando tablas de base de datos...")
                db.create_all()
                print("✓ Tablas creadas")

            # Verificar/crear usuario Master
            master_exists = User.query.filter_by(role='Master').first()
            if not master_exists:
                print("Creando usuario Master...")
                master = User(
                    username='admin',
                    email='admin@qoricash.com',
                    dni='12345678',
                    role='Master',
                    status='Activo'
                )
                master.set_password('Admin123!')
                db.session.add(master)
                db.session.commit()
                print("✓ Usuario Master creado (admin@qoricash.com / Admin123!)")
            else:
                print(f"✓ Usuario Master existe: {master_exists.username}")

    except Exception as e:
        print(f"❌ Error en inicialización DB: {e}")
        # No hacer traceback para no llenar logs

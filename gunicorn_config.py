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

# Timeouts
timeout = 120
graceful_timeout = 60
keepalive = 2

# Memory limits (optimizado para plan Starter)
max_requests = 500
max_requests_jitter = 50

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

# Hook: Ejecutar SOLO UNA VEZ cuando gunicorn arranca (antes de crear workers)
def on_starting(server):
    """
    Hook que se ejecuta UNA SOLA VEZ cuando gunicorn inicia,
    antes de crear los workers. Ideal para inicialización de DB.
    """
    print("🔧 Ejecutando inicialización de base de datos...")

    # Monkey patch de eventlet PRIMERO
    import eventlet
    eventlet.monkey_patch()

    # Importar aquí para evitar problemas de importación circular
    from app import create_app
    from app.extensions import db
    from app.models.user import User

    app = create_app()

    with app.app_context():
        try:
            print("Creando tablas de base de datos...")
            db.create_all()
            print("✓ Tablas creadas exitosamente")

            # Crear usuario Master por defecto si no existe
            master_exists = User.query.filter_by(role='Master').first()
            if not master_exists:
                print("Creando usuario Master por defecto...")
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
                print("✓ Usuario Master creado:")
                print("  Username/Email: admin@qoricash.com")
                print("  Password: Admin123!")
            else:
                print(f"✓ Usuario Master ya existe: {master_exists.username}")

        except Exception as e:
            print(f"❌ Error al inicializar base de datos: {e}")
            import traceback
            traceback.print_exc()

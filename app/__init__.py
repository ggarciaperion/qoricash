"""
Factory de la aplicación Flask para QoriCash Trading V2

Este archivo crea y configura la aplicación Flask usando el patrón Factory.
"""
# IMPORTANTE: Monkey patch de eventlet DEBE ir PRIMERO, antes de cualquier otra importación
import eventlet

# CRITICAL: Desactivar DNS monkey patching para permitir Cloudinary/S3
# Parchear solo lo necesario para Socket.IO
eventlet.monkey_patch(
    os=True,
    select=True,
    socket=True,
    thread=True,
    time=True
)

import logging
import os
from flask import Flask
from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, socketio, limiter, mail, cors

# Scheduler global para expiración de operaciones
_scheduler_greenlet = None


def create_app(config_name=None):
    """
    Factory para crear la aplicación Flask
    
    Args:
        config_name: Nombre de la configuración ('development', 'production', 'testing')
    
    Returns:
        Flask app instance
    """
    app = Flask(__name__)

    # ProxyFix: Render es un reverse proxy — sin esto, request.remote_addr es la IP
    # interna de Render (compartida por todos los usuarios), lo que hace que el
    # rate limiter bloquee a TODOS cuando un solo bot/usuario supera el límite.
    # x_for=1 le dice a Flask que confíe en el primer X-Forwarded-For hop de Render.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Cargar configuración
    if config_name:
        from app.config import config
        app.config.from_object(config[config_name])
    else:
        app.config.from_object(get_config())
    
    # Inicializar extensiones
    initialize_extensions(app)
    
    # Registrar blueprints
    register_blueprints(app)
    
    # Configurar logging
    configure_logging(app)
    
    # Registrar error handlers
    register_error_handlers(app)

    # Configurar Shell context (para flask shell)
    register_shell_context(app)

    # Inicializar scheduler de expiración de operaciones usando eventlet
    # IMPORTANTE: Usar eventlet en lugar de APScheduler para compatibilidad con SocketIO
    start_operation_expiry_scheduler(app)

    # Aplicar headers de seguridad HTTP en todas las respuestas
    from app.utils.security import configure_security_headers
    configure_security_headers(app)

    # Advertir si rate limiting usa memoria (no persiste entre workers ni reinicios)
    import os
    if not os.environ.get('REDIS_URL'):
        logging.warning(
            '[Security] REDIS_URL no configurada — rate limiting usa memoria volátil. '
            'Configura REDIS_URL en Render para rate limiting efectivo en producción.'
        )

    # Migración: tabla lead_hunter_queue (idempotente)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS lead_hunter_queue (
                    id                   SERIAL PRIMARY KEY,
                    found_at             TIMESTAMP DEFAULT NOW(),
                    razon_social         VARCHAR(300),
                    ruc                  VARCHAR(20),
                    rubro                VARCHAR(150),
                    departamento         VARCHAR(100),
                    provincia            VARCHAR(100),
                    distrito             VARCHAR(100),
                    email                VARCHAR(200),
                    telefono             VARCHAR(200),
                    web                  VARCHAR(300),
                    fuente               VARCHAR(80),
                    score                INTEGER DEFAULT 0,
                    potencial            VARCHAR(20),
                    tamano_empresa       VARCHAR(30),
                    volumen_estimado_usd NUMERIC(15,2),
                    accion_sugerida      TEXT,
                    notas                TEXT,
                    status               VARCHAR(20) DEFAULT 'pendiente' NOT NULL,
                    reviewed_by          INTEGER REFERENCES users(id),
                    reviewed_at          TIMESTAMP,
                    reject_reason        VARCHAR(200),
                    prospecto_id         INTEGER REFERENCES prospectos(id)
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_lhq_status ON lead_hunter_queue(status)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_lhq_score ON lead_hunter_queue(score DESC)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] lead_hunter_queue: {e}")

    # Migración: tabla web push subscriptions (idempotente)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    endpoint   TEXT    NOT NULL UNIQUE,
                    p256dh     TEXT    NOT NULL,
                    auth       VARCHAR(100) NOT NULL,
                    user_agent VARCHAR(250),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_push_sub_user ON push_subscriptions(user_id)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] push_subscriptions: {e}")

    # Migración: tablas del ecosistema de Agentes IA (idempotente)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_status (
                    id           SERIAL PRIMARY KEY,
                    agent_id     VARCHAR(50) UNIQUE NOT NULL,
                    name         VARCHAR(100) NOT NULL,
                    description  VARCHAR(300),
                    icon         VARCHAR(50),
                    color        VARCHAR(20),
                    status       VARCHAR(20) DEFAULT 'idle',
                    last_run     TIMESTAMP,
                    next_run     TIMESTAMP,
                    run_interval INTEGER DEFAULT 900,
                    tasks_today  INTEGER DEFAULT 0,
                    errors_today INTEGER DEFAULT 0,
                    total_tasks  INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    last_result  TEXT,
                    last_error   TEXT,
                    enabled      BOOLEAN DEFAULT TRUE,
                    paused_by    INTEGER REFERENCES users(id),
                    paused_at    TIMESTAMP,
                    performance  FLOAT DEFAULT 100.0,
                    created_at   TIMESTAMP DEFAULT NOW(),
                    updated_at   TIMESTAMP DEFAULT NOW()
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id         SERIAL PRIMARY KEY,
                    agent_id   VARCHAR(50) NOT NULL,
                    level      VARCHAR(10) DEFAULT 'INFO',
                    message    TEXT NOT NULL,
                    detail     TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_agent_logs_agent ON agent_logs(agent_id)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_agent_logs_created ON agent_logs(created_at DESC)"
            ))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_alerts (
                    id          SERIAL PRIMARY KEY,
                    agent_id    VARCHAR(50),
                    severity    VARCHAR(20) DEFAULT 'warning',
                    title       VARCHAR(200) NOT NULL,
                    message     TEXT NOT NULL,
                    resolved    BOOLEAN DEFAULT FALSE,
                    resolved_by INTEGER REFERENCES users(id),
                    resolved_at TIMESTAMP,
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_metrics (
                    id                  SERIAL PRIMARY KEY,
                    agent_id            VARCHAR(50) NOT NULL,
                    date                DATE NOT NULL,
                    runs                INTEGER DEFAULT 0,
                    tasks_completed     INTEGER DEFAULT 0,
                    errors              INTEGER DEFAULT 0,
                    prospects_found     INTEGER DEFAULT 0,
                    prospects_validated INTEGER DEFAULT 0,
                    emails_sent         INTEGER DEFAULT 0,
                    emails_analyzed     INTEGER DEFAULT 0,
                    bounces_detected    INTEGER DEFAULT 0,
                    opportunities       INTEGER DEFAULT 0,
                    duplicates_removed  INTEGER DEFAULT 0,
                    followups_scheduled INTEGER DEFAULT 0,
                    created_at          TIMESTAMP DEFAULT NOW(),
                    UNIQUE(agent_id, date)
                )
            """))
            db.session.commit()
            logging.info('[Migration] ✅ Tablas agent_status/logs/alerts/metrics OK')
    except Exception as e:
        logging.warning(f'[Migration] agent_tables: {e}')

    # Migración: tablas del Centro de Inteligencia Comercial IA (idempotente)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS email_eventos (
                    id SERIAL PRIMARY KEY,
                    cuenta VARCHAR(100) NOT NULL,
                    mensaje_id VARCHAR(400) UNIQUE,
                    remitente VARCHAR(300),
                    asunto VARCHAR(500),
                    tipo VARCHAR(50),
                    confianza FLOAT DEFAULT 1.0,
                    ia_usada BOOLEAN DEFAULT false,
                    ia_tokens INTEGER DEFAULT 0,
                    accion VARCHAR(300),
                    email_afectado VARCHAR(200),
                    email_nuevo VARCHAR(200),
                    sheets_tab VARCHAR(50),
                    crm_updated BOOLEAN DEFAULT false,
                    sheets_updated BOOLEAN DEFAULT false,
                    procesado_en TIMESTAMP WITHOUT TIME ZONE
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS oportunidades_comerciales (
                    id SERIAL PRIMARY KEY,
                    empresa VARCHAR(300),
                    contacto VARCHAR(200),
                    cargo VARCHAR(150),
                    email VARCHAR(200),
                    telefono VARCHAR(100),
                    sector VARCHAR(100),
                    prioridad VARCHAR(20),
                    score INTEGER DEFAULT 0,
                    volumen_usd_est INTEGER DEFAULT 0,
                    necesidad TEXT,
                    recomendacion TEXT,
                    cuerpo_email TEXT,
                    estado VARCHAR(50) DEFAULT 'nuevo',
                    cuenta_origen VARCHAR(100),
                    mensaje_id VARCHAR(400),
                    prospecto_creado_id INTEGER REFERENCES prospectos(id),
                    wa_alerta_enviada BOOLEAN DEFAULT false,
                    detectado_en TIMESTAMP WITHOUT TIME ZONE,
                    actualizado_en TIMESTAMP WITHOUT TIME ZONE
                )
            """))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS ejecuciones_motor (
                    id SERIAL PRIMARY KEY,
                    motor VARCHAR(50),
                    inicio TIMESTAMP WITHOUT TIME ZONE,
                    fin TIMESTAMP WITHOUT TIME ZONE,
                    duracion_seg FLOAT,
                    correos_analizados INTEGER DEFAULT 0,
                    rebotes INTEGER DEFAULT 0,
                    oportunidades INTEGER DEFAULT 0,
                    actualizaciones INTEGER DEFAULT 0,
                    no_contactar INTEGER DEFAULT 0,
                    ia_tokens INTEGER DEFAULT 0,
                    ia_costo_usd FLOAT DEFAULT 0.0,
                    errores INTEGER DEFAULT 0,
                    estado VARCHAR(20) DEFAULT 'ok',
                    resumen TEXT
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_email_eventos_cuenta ON email_eventos(cuenta)"
            ))
            db.session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_email_eventos_mensaje_id ON email_eventos(mensaje_id)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_email_eventos_tipo ON email_eventos(tipo)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_email_eventos_procesado_en ON email_eventos(procesado_en)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_oportunidades_comerciales_estado ON oportunidades_comerciales(estado)"
            ))
            db.session.commit()
            logging.info('[Migration] ✅ Tablas email_eventos/oportunidades_comerciales/ejecuciones_motor OK')
    except Exception as e:
        logging.warning(f'[Migration] inteligencia_comercial_tables: {e}')

    # Aplicar migraciones de columnas nuevas (idempotente — usa ADD COLUMN IF NOT EXISTS)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE clients ADD COLUMN IF NOT EXISTS registration_canal VARCHAR(20)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] registration_canal: {e}")

    # Migracion: columnas vigencia en asignaciones_prospecto
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE asignaciones_prospecto "
                "ADD COLUMN IF NOT EXISTS dias_extra INTEGER DEFAULT 0"
            ))
            db.session.execute(text(
                "ALTER TABLE asignaciones_prospecto "
                "ADD COLUMN IF NOT EXISTS extension_solicitada BOOLEAN DEFAULT FALSE"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] asignaciones_prospecto vigencia: {e}")

    # Migracion: columnas de account lockout en users
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0"
            ))
            db.session.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] users lockout columns: {e}")

    # Migracion: columnas faltantes en operations (base_rate, pips, new_operation_email_sent)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE operations ADD COLUMN IF NOT EXISTS base_rate NUMERIC(10, 4)"
            ))
            db.session.execute(text(
                "ALTER TABLE operations ADD COLUMN IF NOT EXISTS pips NUMERIC(8, 1)"
            ))
            db.session.execute(text(
                "ALTER TABLE operations ADD COLUMN IF NOT EXISTS new_operation_email_sent "
                "BOOLEAN NOT NULL DEFAULT false"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] operations columnas faltantes: {e}")

    # Migración: columnas de nombre de banco en operations (source_bank_name, destination_bank_name)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE operations ADD COLUMN IF NOT EXISTS source_bank_name VARCHAR(100)"
            ))
            db.session.execute(text(
                "ALTER TABLE operations ADD COLUMN IF NOT EXISTS destination_bank_name VARCHAR(100)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] operations bank name columns: {e}")

    # Migración: coupon_code en operations
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE operations ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(20)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] operations coupon_code: {e}")

    # Migracion: tabla notifications si no existe
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    title VARCHAR(200) NOT NULL,
                    message VARCHAR(500) NOT NULL,
                    notif_type VARCHAR(30) NOT NULL DEFAULT 'info',
                    category VARCHAR(50) NOT NULL DEFAULT 'general',
                    link VARCHAR(300),
                    is_read BOOLEAN NOT NULL DEFAULT false,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    read_at TIMESTAMP
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] notifications tabla: {e}")

    # Crear tablas del modulo Prospeccion si no existen
    try:
        with app.app_context():
            from sqlalchemy import text, inspect as sa_inspect
            inspector = sa_inspect(db.engine)
            existing = inspector.get_table_names()
            if "prospectos" not in existing:
                db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS prospectos (
                        id SERIAL PRIMARY KEY,
                        razon_social VARCHAR(300), ruc VARCHAR(20), tipo VARCHAR(50),
                        rubro VARCHAR(150), departamento VARCHAR(100), provincia VARCHAR(100),
                        nombre_contacto VARCHAR(200), cargo VARCHAR(150),
                        email VARCHAR(200), email_alt VARCHAR(200), telefono VARCHAR(50),
                        cliente_lfc VARCHAR(50), score INTEGER DEFAULT 0,
                        clasificacion VARCHAR(80), canal VARCHAR(80), fuente VARCHAR(80),
                        remitente VARCHAR(100), tipo_ultimo_envio VARCHAR(80),
                        fecha_primer_contacto VARCHAR(30), fecha_ultimo_contacto VARCHAR(30),
                        fecha_proximo_contacto VARCHAR(30), num_contactos INTEGER DEFAULT 0,
                        estado_email VARCHAR(80), estado_comercial VARCHAR(80),
                        nivel_interes VARCHAR(80), grupo VARCHAR(80), notas TEXT,
                        creado_en TIMESTAMP DEFAULT NOW(), actualizado_en TIMESTAMP DEFAULT NOW()
                    )
                """))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_prospectos_email ON prospectos(email)"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_prospectos_ruc ON prospectos(ruc)"))
                db.session.commit()
                logging.info("[Prospeccion] Tabla prospectos creada.")
            if "wa_messages" not in existing:
                db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS wa_messages (
                        id         SERIAL PRIMARY KEY,
                        numero     VARCHAR(25)  NOT NULL,
                        nombre     VARCHAR(120) DEFAULT '',
                        empresa    VARCHAR(200) DEFAULT '',
                        mensaje    TEXT         NOT NULL,
                        direccion  VARCHAR(10)  NOT NULL,
                        wa_id      VARCHAR(120) DEFAULT '',
                        leido      BOOLEAN      DEFAULT FALSE,
                        created_at TIMESTAMP    DEFAULT NOW()
                    )
                """))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_wa_messages_numero ON wa_messages(numero)"))
                db.session.commit()
                logging.info("[CRM] Tabla wa_messages creada.")
            # Columnas de media (si la tabla ya existía sin ellas)
            db.session.execute(text("ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS media_id   VARCHAR(120) DEFAULT ''"))
            db.session.execute(text("ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS media_tipo VARCHAR(20)  DEFAULT ''"))
            db.session.commit()
            if "asignaciones_prospecto" not in existing:
                db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS asignaciones_prospecto (
                        id SERIAL PRIMARY KEY,
                        prospecto_id INTEGER REFERENCES prospectos(id),
                        trader_id INTEGER REFERENCES users(id),
                        activo BOOLEAN DEFAULT TRUE,
                        asignado_por INTEGER REFERENCES users(id),
                        asignado_en TIMESTAMP DEFAULT NOW(),
                        CONSTRAINT uq_asignacion UNIQUE (prospecto_id, trader_id)
                    )
                """))
                db.session.commit()
                logging.info("[Prospeccion] Tabla asignaciones_prospecto creada.")
            if "actividades_prospecto" not in existing:
                db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS actividades_prospecto (
                        id SERIAL PRIMARY KEY,
                        prospecto_id INTEGER REFERENCES prospectos(id),
                        user_id INTEGER REFERENCES users(id),
                        tipo VARCHAR(50), descripcion TEXT, resultado VARCHAR(200),
                        nuevo_estado VARCHAR(80), creado_en TIMESTAMP DEFAULT NOW()
                    )
                """))
                db.session.commit()
                logging.info("[Prospeccion] Tabla actividades_prospecto creada.")
    except Exception as e:
        logging.warning(f"[Prospeccion] Error creando tablas: {e}")

    # Migración: CRM avanzado — nuevas columnas en prospectos + tabla prospecto_emails
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            # Nuevas columnas en prospectos (IF NOT EXISTS es idempotente en PostgreSQL)
            for col_sql in [
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS telefono_alt VARCHAR(50)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS tamano_empresa VARCHAR(30)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS volumen_estimado_usd NUMERIC(15,2)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS prioridad VARCHAR(20)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS direccion VARCHAR(300)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS subsector VARCHAR(150)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS telefono_3 VARCHAR(50)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS telefono_4 VARCHAR(50)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS email_3 VARCHAR(200)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS email_4 VARCHAR(200)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS facebook VARCHAR(300)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS instagram VARCHAR(300)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS linkedin VARCHAR(300)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS apellido_paterno VARCHAR(100)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS apellido_materno VARCHAR(100)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS contacto_wa VARCHAR(50)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS ultimo_precio VARCHAR(50)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS respuesta_campana VARCHAR(200)",
                "ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS bandeja VARCHAR(80)",
            ]:
                db.session.execute(text(col_sql))

            # Normalizar estados legacy → canónicos
            for old, new in [
                ("P1", "contactado"), ("P2", "interesado"),
                ("P3", "negociando"), ("P4", "cliente"),
                ("seguimiento", "contactado"), ("negociacion", "negociando"),
                ("presentado", "contactado"), ("precio_enviado", "interesado"),
            ]:
                db.session.execute(text(
                    f"UPDATE prospectos SET estado_comercial = '{new}' WHERE estado_comercial = '{old}'"
                ))

            # Columnas nuevas en actividades_prospecto (timeline enriquecido)
            for col_sql in [
                "ALTER TABLE actividades_prospecto ADD COLUMN IF NOT EXISTS canal VARCHAR(30)",
                "ALTER TABLE actividades_prospecto ADD COLUMN IF NOT EXISTS bandeja VARCHAR(100)",
            ]:
                db.session.execute(text(col_sql))

            # Tabla de seguimientos programados
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS seguimientos_prospecto (
                    id               SERIAL PRIMARY KEY,
                    prospecto_id     INTEGER NOT NULL REFERENCES prospectos(id) ON DELETE CASCADE,
                    user_id          INTEGER NOT NULL REFERENCES users(id),
                    tipo             VARCHAR(50),
                    descripcion      TEXT,
                    fecha_programada TIMESTAMP NOT NULL,
                    completado       BOOLEAN NOT NULL DEFAULT FALSE,
                    completado_en    TIMESTAMP,
                    creado_en        TIMESTAMP DEFAULT NOW()
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_seguimiento_pid ON seguimientos_prospecto(prospecto_id)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_seguimiento_fecha ON seguimientos_prospecto(fecha_programada)"
            ))

            # Tabla de emails adicionales por prospecto
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS prospecto_emails (
                    id           SERIAL PRIMARY KEY,
                    prospecto_id INTEGER NOT NULL REFERENCES prospectos(id) ON DELETE CASCADE,
                    email        VARCHAR(200) NOT NULL,
                    activo       BOOLEAN NOT NULL DEFAULT TRUE,
                    creado_en    TIMESTAMP DEFAULT NOW()
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_prospecto_email_pid ON prospecto_emails(prospecto_id)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Prospeccion CRM] Error en migración de columnas/tabla: {e}")

    # Migración: tabla comercial_envios
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS comercial_envios (
                    id        SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id),
                    user_id   INTEGER NOT NULL REFERENCES users(id),
                    sent_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                    compra    VARCHAR(10),
                    venta     VARCHAR(10)
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_comercial_envios_client_id ON comercial_envios(client_id)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_comercial_envios_user_id ON comercial_envios(user_id)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_comercial_envios_sent_at ON comercial_envios(sent_at)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Comercial] Error creando tabla comercial_envios: {e}")

    # Migración: columna reassigned_at en clients
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE clients ADD COLUMN IF NOT EXISTS reassigned_at TIMESTAMP"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Clients] Error añadiendo columna reassigned_at: {e}")

    # Migración: columna relacion_empresa en clients (rol del contacto en empresa RUC)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE clients ADD COLUMN IF NOT EXISTS relacion_empresa VARCHAR(100)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Clients] Error añadiendo columna relacion_empresa: {e}")

    # Migración: tabla sanctions_entries (screening OFAC/ONU)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS sanctions_entries (
                    id              SERIAL PRIMARY KEY,
                    source          VARCHAR(20)  NOT NULL,
                    entity_type     VARCHAR(20),
                    uid             VARCHAR(100),
                    name            VARCHAR(400) NOT NULL,
                    name_normalized VARCHAR(400),
                    aliases_json    TEXT,
                    nationality     VARCHAR(100),
                    program         VARCHAR(300),
                    loaded_at       TIMESTAMP DEFAULT NOW()
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_sanctions_entries_source ON sanctions_entries(source)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_sanctions_entries_name_normalized ON sanctions_entries(name_normalized)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Sanctions] Error creando tabla sanctions_entries: {e}")

    # Pre-cargar listas de sanciones en background al arrancar (para que estén listas en el primer uso)
    try:
        from app.services import sanctions_screening_service as _sss
        _sss.ensure_lists_loaded(app)
    except Exception as e:
        logging.warning(f"[Sanctions] No se pudo iniciar pre-carga: {e}")

    # Migración: columna session_token en users (sesión única por usuario)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS session_token VARCHAR(36)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Auth] Error añadiendo session_token a users: {e}")

    # Migración: tabla datatec_rates (precio DATATEC — fila única, source of truth)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS datatec_rates (
                    id           SERIAL PRIMARY KEY,
                    compra       NUMERIC(10,4) NOT NULL DEFAULT 0,
                    venta        NUMERIC(10,4) NOT NULL DEFAULT 0,
                    compra_tarde NUMERIC(10,4),
                    venta_tarde  NUMERIC(10,4),
                    updated_by   INTEGER REFERENCES users(id),
                    updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[TCLive] Error creando tabla datatec_rates: {e}")

    # Migración: tabla datatec_entries (audit log TC Live — Pricing Engine)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS datatec_entries (
                    id         SERIAL PRIMARY KEY,
                    compra     NUMERIC(10,4) NOT NULL,
                    venta      NUMERIC(10,4) NOT NULL,
                    created_at TIMESTAMP     NOT NULL DEFAULT NOW(),
                    user_id    INTEGER       REFERENCES users(id),
                    notes      VARCHAR(300)
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_datatec_entries_created ON datatec_entries(created_at)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[TCLive] Error creando tabla datatec_entries: {e}")

    # Migración: tablas de Tesorería — bank_movements y daily_closures
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS bank_movements (
                    id             SERIAL PRIMARY KEY,
                    movement_date  TIMESTAMP    NOT NULL DEFAULT NOW(),
                    bank_name      VARCHAR(100) NOT NULL,
                    bank_key       VARCHAR(50)  NOT NULL,
                    currency       VARCHAR(3)   NOT NULL,
                    amount         NUMERIC(14,2) NOT NULL,
                    balance_after  NUMERIC(14,2),
                    movement_type  VARCHAR(50)  NOT NULL,
                    source_type    VARCHAR(50),
                    source_id      INTEGER,
                    operation_id   INTEGER      REFERENCES operations(id) ON DELETE SET NULL,
                    description    VARCHAR(300),
                    reference_code VARCHAR(50),
                    counterpart    VARCHAR(200),
                    closure_date   DATE,
                    created_by     INTEGER      REFERENCES users(id),
                    created_at     TIMESTAMP    DEFAULT NOW()
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_bm_bank_currency_date ON bank_movements(bank_key, currency, movement_date)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_bm_closure_date ON bank_movements(closure_date)"
            ))
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS daily_closures (
                    id                    SERIAL PRIMARY KEY,
                    closure_date          DATE         NOT NULL UNIQUE,
                    status                VARCHAR(20)  NOT NULL DEFAULT 'borrador',
                    system_balances_json  TEXT,
                    validated_balances_json TEXT,
                    differences_json      TEXT,
                    operations_completed  INTEGER      DEFAULT 0,
                    total_volume_usd      NUMERIC(14,2) DEFAULT 0,
                    realized_profit_pen   NUMERIC(14,2) DEFAULT 0,
                    house_profit_pen      NUMERIC(14,2) DEFAULT 0,
                    trader_profit_pen     NUMERIC(14,2) DEFAULT 0,
                    pending_operations    INTEGER      DEFAULT 0,
                    unmatched_usd         NUMERIC(14,2) DEFAULT 0,
                    open_matches          INTEGER      DEFAULT 0,
                    has_discrepancies     BOOLEAN      DEFAULT FALSE,
                    discrepancy_reason    TEXT,
                    closed_by             INTEGER      REFERENCES users(id),
                    closed_at             TIMESTAMP,
                    notes                 TEXT,
                    created_at            TIMESTAMP    DEFAULT NOW()
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_dc_closure_date ON daily_closures(closure_date)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] treasury tables (bank_movements/daily_closures): {e}")

    # Migración: tabla internal_transfers (traslados internos de fondos propios)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS internal_transfers (
                    id                   SERIAL PRIMARY KEY,
                    transfer_code        VARCHAR(30)   NOT NULL UNIQUE,
                    transfer_date        TIMESTAMP     NOT NULL DEFAULT NOW(),
                    origin_bank          VARCHAR(20)   NOT NULL,
                    origin_currency      VARCHAR(3)    NOT NULL,
                    origin_account       VARCHAR(120)  NOT NULL,
                    dest_bank            VARCHAR(20)   NOT NULL,
                    dest_currency        VARCHAR(3)    NOT NULL,
                    dest_account         VARCHAR(120)  NOT NULL,
                    amount               NUMERIC(15,2) NOT NULL,
                    commission           NUMERIC(15,2) NOT NULL DEFAULT 0,
                    itf_amount           NUMERIC(15,2) NOT NULL DEFAULT 0,
                    description          VARCHAR(500),
                    reference_code       VARCHAR(100),
                    journal_entry_id     INTEGER REFERENCES journal_entries(id) ON DELETE SET NULL,
                    movement_salida_id   INTEGER REFERENCES bank_movements(id)  ON DELETE SET NULL,
                    movement_entrada_id  INTEGER REFERENCES bank_movements(id)  ON DELETE SET NULL,
                    status               VARCHAR(20)   NOT NULL DEFAULT 'activo',
                    created_by           INTEGER REFERENCES users(id),
                    created_at           TIMESTAMP     DEFAULT NOW(),
                    anulado_by           INTEGER REFERENCES users(id),
                    anulado_at           TIMESTAMP,
                    anulado_reason       VARCHAR(500)
                )
            """))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_it_transfer_date ON internal_transfers(transfer_date)"
            ))
            db.session.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_it_status ON internal_transfers(status)"
            ))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] internal_transfers table: {e}")

    # Migración: columnas faltantes en daily_closures (tabla creada con schema reducido)
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            _alter_cols = [
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS total_bought_usd NUMERIC(14,2) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS total_sold_usd NUMERIC(14,2) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS avg_buy_rate NUMERIC(10,4) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS avg_sell_rate NUMERIC(10,4) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS gross_spread_pen NUMERIC(14,2) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS expenses_pen NUMERIC(14,2) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS net_profit_pen NUMERIC(14,2) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS unmatched_completed_usd NUMERIC(14,2) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS max_discrepancy_usd NUMERIC(14,2) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS max_discrepancy_pen NUMERIC(14,2) DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS validated_by INTEGER REFERENCES users(id)",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS validated_at TIMESTAMP",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            ]
            for sql in _alter_cols:
                db.session.execute(text(sql))
            db.session.commit()
    except Exception as e:
        logging.warning(f"[Migration] daily_closures alter columns: {e}")

    # Migración: columnas apertura/cierre/resultado en daily_closures
    # Corrección definitiva: b1c2a3j4a5d6 fue stampeado sin ejecutar upgrade().
    try:
        with app.app_context():
            from app.extensions import db
            from sqlalchemy import text
            _dc_cols = [
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS opening_balance_json TEXT NOT NULL DEFAULT '{}'",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS opening_total_usd NUMERIC(15,2) NOT NULL DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS opening_total_pen NUMERIC(15,2) NOT NULL DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS opening_registered_at TIMESTAMP WITHOUT TIME ZONE",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS opening_registered_by INTEGER REFERENCES users(id)",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS closing_balance_json TEXT NOT NULL DEFAULT '{}'",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS closing_total_usd NUMERIC(15,2) NOT NULL DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS closing_total_pen NUMERIC(15,2) NOT NULL DEFAULT 0",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS closing_registered_at TIMESTAMP WITHOUT TIME ZONE",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS closing_registered_by INTEGER REFERENCES users(id)",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS result_usd NUMERIC(15,2)",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS result_pen NUMERIC(15,2)",
                "ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS result_label VARCHAR(20)",
            ]
            for sql in _dc_cols:
                db.session.execute(text(sql))
            db.session.commit()
            logging.info("[Migration] daily_closures apertura/cierre/resultado columns ensured")
    except Exception as e:
        logging.warning(f"[Migration] daily_closures apertura/cierre columns: {e}")

    # Sembrar competidores FX (idempotente — solo inserta si no existen)
    try:
        with app.app_context():
            from app.services.fx_monitor.monitor_service import FXMonitorService
            FXMonitorService.seed_competitors()
    except Exception as e:
        logging.warning(f"[FX] seed_competitors falló (puede que las tablas no existan aún): {e}")

    # Inicializar schedulers del módulo Mercado
    start_market_schedulers(app)

    # Agentes IA desactivados: reemplazados por scripts directos y cron jobs.
    # La auditoría contable corre via cron_auditoria_diaria.py (Render Cron Job).
    # Los modelos se importan para que SQLAlchemy registre las tablas correctamente.
    try:
        from app.models import inteligencia as _m_intel  # noqa: F401
        from app.models import prospecto as _m_prosp     # noqa: F401
        logging.info('[Agents] Modelos registrados — agentes IA desactivados (usar scripts directos)')
    except Exception as _agent_err:
        logging.warning(f'[Agents] Error registrando modelos: {_agent_err}')

    # Registrar CLI commands (aquí para que estén disponibles sin importar
    # cómo Flask CLI descubra la app — factory o instancia directa)
    register_cli_commands(app)

    # Context processor: inyecta pb_access para el widget Precio Base
    @app.context_processor
    def inject_pb_access():
        from flask_login import current_user
        pb = False
        try:
            if current_user.is_authenticated:
                if current_user.is_trading_desk():
                    pb = True
                elif current_user.role == 'Trader':
                    from app.models.datatec_rate import PrecioBaseAccess
                    pb = PrecioBaseAccess.has_access(current_user.id)
        except Exception:
            pb = False
        return dict(pb_access=pb)

    return app


def initialize_extensions(flask_app):
    """Inicializar extensiones de Flask"""
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)
    socketio.init_app(flask_app)
    mail.init_app(flask_app)

    # CORS - Permitir solicitudes desde el frontend web
    # Incluye localhost para desarrollo y dominios de producción
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "https://qoricash.vercel.app",
        "https://www.qoricash.pe",
        "https://qoricash.pe",
        "https://qoricash-web.onrender.com"
    ]

    cors.init_app(
        flask_app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )

    if flask_app.config['RATELIMIT_ENABLED']:
        limiter.init_app(flask_app)

    # Configurar user_loader para Flask-Login
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        """Devuelve JSON para peticiones AJAX; redirige al login para navegador normal."""
        from flask import request, jsonify, redirect, url_for
        if request.is_json or request.headers.get('X-CSRFToken') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Sesión expirada. Por favor recarga la página e inicia sesión nuevamente.', 'session_expired': True}), 401
        return redirect(url_for('auth.login'))

    @flask_app.before_request
    def enforce_single_session():
        """
        Sesión única por usuario: si el token de sesión en la cookie no coincide
        con el token en la base de datos, significa que el usuario inició sesión
        en otro dispositivo o ventana → cerrar esta sesión automáticamente.
        """
        from flask import request, session as flask_session, redirect, url_for, jsonify
        from flask_login import current_user, logout_user

        # Solo verificar rutas de usuario autenticado (no login, static, sw.js, etc.)
        if request.path.startswith('/static') or request.path == '/sw.js':
            return

        if not current_user.is_authenticated:
            return

        token_in_session = flask_session.get('_session_token')
        token_in_db      = current_user.session_token

        # Si no hay token en DB (usuario logueado antes de esta feature) → asignar uno nuevo
        if not token_in_db:
            import uuid
            current_user.session_token = str(uuid.uuid4())
            flask_session['_session_token'] = current_user.session_token
            db.session.commit()
            return

        if token_in_session != token_in_db:
            # Sesión invalidada por nuevo login en otro lugar
            logout_user()
            flask_session.clear()
            if request.is_json or request.headers.get('X-CSRFToken') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'session_expired': True,
                    'message': 'Tu sesión fue cerrada porque iniciaste sesión en otro dispositivo.',
                }), 401
            return redirect(url_for('auth.login') + '?kicked=1')

    # Importar eventos de Socket.IO
    with flask_app.app_context():
        import app.socketio_events

    # Registrar filtros personalizados de Jinja2
    register_template_filters(flask_app)

    # Configurar headers de seguridad
    configure_security_headers(flask_app)

    # Bloquear escrituras del usuario demo
    configure_demo_mode(flask_app)


def register_blueprints(app):
    """Registrar blueprints de la aplicación"""
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.users import users_bp
    from app.routes.clients import clients_bp
    from app.routes.operations import operations_bp
    # position_bp eliminado — reemplazado por Finanzas
    from app.routes.platform import platform_bp
    from app.routes.platform_api import platform_api_bp
    from app.routes.client_auth import client_auth_bp
    from app.routes.web_api import web_api_bp
    from app.routes.legal import legal_bp
    from app.routes.referrals import referrals_bp
    from app.routes.compliance import compliance_bp
    from app.routes.complaints import complaints_bp
    from app.routes.fx_monitor import fx_monitor_bp
    from app.routes.market import market_bp
    from app.routes.contabilidad import contabilidad_bp
    from app.routes.auditoria import auditoria_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(clients_bp, url_prefix='/clients')
    app.register_blueprint(operations_bp, url_prefix='/operations')
    # position_bp desregistrado — reemplazado por Finanzas
    app.register_blueprint(platform_bp)  # Sin prefijo, las rutas ya tienen /api/platform
    app.register_blueprint(platform_api_bp)  # API pública plataforma: /api/platform/*
    app.register_blueprint(client_auth_bp)  # Autenticación de clientes: /api/client/* (web + móvil)
    app.register_blueprint(web_api_bp)  # API Web QoriCash: /api/web/*
    app.register_blueprint(legal_bp)  # Rutas legales: /legal/terms, /legal/privacy
    app.register_blueprint(referrals_bp)  # Sistema de referidos
    app.register_blueprint(compliance_bp, url_prefix='/compliance')  # Módulo de compliance
    app.register_blueprint(complaints_bp, url_prefix='/complaints')  # Módulo de reclamos
    app.register_blueprint(fx_monitor_bp)  # Monitor de competencia
    app.register_blueprint(market_bp)      # Módulo Mercado
    app.register_blueprint(contabilidad_bp, url_prefix='/contabilidad')  # Módulo Contable
    app.register_blueprint(auditoria_bp,   url_prefix='/contabilidad/auditoria')  # Agente Auditoría IA

    from app.routes.notifications import notifications_bp
    app.register_blueprint(notifications_bp)  # API de notificaciones internas
    from app.routes.prospeccion import prospeccion_bp
    app.register_blueprint(prospeccion_bp)     # Modulo de Prospeccion comercial
    from app.routes.comercial import comercial_bp
    app.register_blueprint(comercial_bp)       # Modulo Comercial — cartera de clientes
    from app.routes.alertas_tc import alertas_tc_bp
    app.register_blueprint(alertas_tc_bp)      # Modulo Alertas TC — leads desde qoricash.pe
    from app.routes.push import push_bp
    app.register_blueprint(push_bp)            # Web Push: /api/push/*
    from app.routes.crm import crm_bp
    app.register_blueprint(crm_bp)             # CRM WhatsApp: /crm/*
    from app.routes.finanzas import finanzas_bp
    app.register_blueprint(finanzas_bp, url_prefix='/finanzas')  # Control Financiero
    from app.routes.treasury import treasury_bp
    app.register_blueprint(treasury_bp, url_prefix='/treasury')  # Tesorería
    from app.routes.ai import ai_bp
    app.register_blueprint(ai_bp)                                # Agentes IA: /ai/*

    # agentes_bp desactivado — panel de Agentes IA removido del sistema

# Service Worker debe servirse desde la raíz del dominio (scope /)
    import os
    from flask import send_from_directory
    @app.route('/sw.js')
    def service_worker():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'sw.js',
            mimetype='application/javascript',
        )


def configure_logging(app):
    """Configurar logging de la aplicación"""
    if not app.debug and not app.testing:
        # Configurar logging para producción
        logging.basicConfig(
            level=getattr(logging, app.config['LOG_LEVEL']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Logger de la app
        app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))


def register_error_handlers(app):
    """Registrar manejadores de errores"""
    from flask import jsonify

    @app.errorhandler(404)
    def not_found_error(error):
        # Siempre retornar JSON para APIs
        return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        import traceback, logging as _log
        tb = traceback.format_exc()
        _log.error(f'[500] {request.path}\n{tb}')
        # JSON para peticiones AJAX / API
        if (request.is_json or
                request.path.startswith('/api/') or
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
        # Páginas HTML: solo mostrar traceback en modo debug (nunca en producción)
        if app.debug:
            return (
                f'<h2 style="color:red">Error 500 — {request.path}</h2>'
                f'<pre style="background:#f8f8f8;padding:16px;border-radius:6px">'
                f'{tb}</pre>',
                500,
            )
        return (
            '<div style="font-family:sans-serif;text-align:center;padding:60px 20px">'
            '<h2 style="color:#c0392b">Error interno del servidor</h2>'
            '<p style="color:#555">Ocurrió un problema inesperado. El equipo técnico ha sido notificado.</p>'
            '<a href="/" style="color:#2980b9">Volver al inicio</a>'
            '</div>',
            500,
        )

    @app.errorhandler(403)
    def forbidden_error(error):
        # Siempre retornar JSON para APIs
        return jsonify({'success': False, 'error': 'Acceso denegado'}), 403

    @app.errorhandler(413)
    def request_too_large(error):
        return jsonify({'success': False, 'message': 'Los archivos son demasiado grandes. El límite es 10 MB por solicitud. Usa imágenes más pequeñas.'}), 413


def configure_demo_mode(flask_app):
    """
    Bloquea todas las escrituras del usuario demo_trader.
    Cualquier POST/PUT/DELETE devuelve JSON con demo_mode=True
    sin tocar la base de datos de producción.
    """
    from flask import request, jsonify
    from flask_login import current_user

    DEMO_WHITELIST = {'/auth/logout', '/auth/login'}

    @flask_app.before_request
    def block_demo_writes():
        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return None
        if request.path in DEMO_WHITELIST:
            return None
        try:
            if current_user.is_authenticated and current_user.is_demo:
                return jsonify({
                    'demo_mode': True,
                    'success': False,
                    'message': 'Modo Demo activo — esta acción no se guarda en producción.'
                }), 200
        except Exception:
            pass
        return None


def configure_security_headers(flask_app):
    """
    Configurar headers de seguridad HTTP para proteger contra ataques comunes
    """
    @flask_app.after_request
    def add_security_headers(response):
        # Prevenir clickjacking
        response.headers['X-Frame-Options'] = 'DENY'

        # Prevenir MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Habilitar protección XSS del navegador
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Forzar HTTPS en producción (HSTS)
        if not flask_app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Content Security Policy - SOLO para rutas de API web/cliente
        # No aplicar CSP al sistema administrativo para no romper estilos de CDN
        from flask import request
        if request.path.startswith('/api/'):
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.socket.io https://vercel.live; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https: blob:; "
                "connect-src 'self' https://app.qoricash.pe wss://app.qoricash.pe https://qoricash.vercel.app https://vitals.vercel-insights.com; "
                "frame-ancestors 'none';"
            )

        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy (antes Feature-Policy)
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response


def register_template_filters(flask_app):
    """Registrar filtros personalizados de Jinja2"""

    def format_currency_filter(value, decimals=2):
        """
        Formatea un número como moneda con separador de miles (coma)
        Ejemplo: 1000000.50 -> 1,000,000.50
        """
        try:
            num = float(value)
            formatted = f"{num:,.{decimals}f}"
            return formatted
        except (ValueError, TypeError):
            return "0.00"

    # Registrar el filtro en el entorno de Jinja2
    flask_app.jinja_env.filters['format_currency'] = format_currency_filter

    # Exponer now_peru() como global de templates
    from app.utils.formatters import now_peru
    flask_app.jinja_env.globals['now_peru'] = now_peru


def register_shell_context(app):
    """Registrar contexto para flask shell"""
    @app.shell_context_processor
    def make_shell_context():
        from app.models.user import User
        from app.models.client import Client
        from app.models.operation import Operation
        return {
            'db': db,
            'User': User,
            'Client': Client,
            'Operation': Operation
        }


def start_operation_expiry_scheduler(app):
    """
    Iniciar scheduler de expiración de operaciones usando eventlet
    Se ejecuta en un greenlet separado cada 60 segundos

    IMPORTANTE: Solo se inicia UNA vez globalmente, incluso si gunicorn
    tiene múltiples workers. Usamos una variable global para evitar duplicados.
    """
    global _scheduler_greenlet

    # Solo iniciar si no está ya corriendo
    if _scheduler_greenlet is not None:
        logging.info("[SCHEDULER] Ya existe un scheduler en ejecución, no se inicia otro")
        return

    def scheduler_loop():
        """Loop infinito que expira operaciones cada 60 segundos"""
        logging.info("[SCHEDULER] ✅ Scheduler de expiración de operaciones iniciado")

        while True:
            try:
                with app.app_context():
                    from app.services.operation_expiry_service import OperationExpiryService
                    expired_count = OperationExpiryService.expire_old_operations()
                    if expired_count > 0:
                        logging.info(f"[SCHEDULER] ⏱️ {expired_count} operaciones canceladas automáticamente")
            except Exception as e:
                logging.error(f"[SCHEDULER] ❌ Error en scheduler de expiración: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())

            # Esperar 60 segundos antes de la próxima verificación
            eventlet.sleep(60)

    # Iniciar el scheduler en un greenlet separado
    _scheduler_greenlet = eventlet.spawn(scheduler_loop)
    logging.info("[SCHEDULER] 🚀 Greenlet de scheduler spawneado")


def start_market_schedulers(app):
    """Iniciar greenlets para jobs del módulo Mercado (precios, noticias, macro, fx_monitor)"""

    def _run_every(interval_sec, job_name, fn):
        def loop():
            logging.info(f"[MARKET] ✅ {job_name} iniciado (cada {interval_sec//60} min)")
            eventlet.sleep(30)  # pequeño delay al arrancar para no saturar el inicio
            while True:
                try:
                    with app.app_context():
                        fn()
                        db.session.remove()  # liberar sesión al terminar cada ciclo
                except Exception as e:
                    import traceback
                    logging.error(f"[MARKET] ❌ {job_name}: {e}\n{traceback.format_exc()}")
                    try:
                        db.session.remove()
                    except Exception:
                        pass
                import gc
                gc.collect()
                eventlet.sleep(interval_sec)
        eventlet.spawn(loop)

    def _prices():
        from app.services.market.market_service import MarketService
        r = MarketService.run_price_cycle()
        logging.info(f"[MARKET] Precios: {r}")

    def _news():
        from app.services.market.market_service import MarketService
        r = MarketService.run_news_cycle()
        logging.info(f"[MARKET] Noticias: {r}")

    def _macro():
        from app.services.market.market_service import MarketService
        r = MarketService.run_macro_cycle()
        logging.info(f"[MARKET] Macro: {r}")

    def _fx_monitor():
        from app.services.fx_monitor.monitor_service import FXMonitorService
        from app.services.fx_monitor import live_cache
        r = FXMonitorService.run_scrape_cycle()
        # Notificar a clientes SSE inmediatamente — latencia <500ms hasta pantalla
        live_cache.notify()
        logging.info(f"[MARKET] FX Monitor: {r}")

    def _calendar():
        from app.services.market.market_service import MarketService
        r = MarketService.run_calendar_cycle()
        logging.info(f"[MARKET] Calendario: {r}")

    _run_every(5  * 60, 'Precios de mercado',   _prices)
    _run_every(15 * 60, 'Noticias RSS',          _news)
    _run_every(6  * 3600, 'Indicadores macro',   _macro)
    # FX Monitor: loop back-to-back con watchdog de dos niveles.
    # Nivel 1 — inner loop: captura errores por ciclo, reintenta en 2s.
    # Nivel 2 — watchdog: si el greenlet muere por cualquier razón, lo respawnea.
    def _fx_monitor_loop():
        import eventlet as _ev
        import gc as _gc
        from datetime import datetime, timezone, timedelta
        _LIMA = timezone(timedelta(hours=-5))
        _log  = logging.getLogger(__name__)
        _log.info('[FX-WATCH] Loop iniciado')
        _ev.sleep(30)  # delay inicial
        consecutive_errors = 0
        while True:
            try:
                with app.app_context():
                    _fx_monitor()
                    db.session.remove()
                consecutive_errors = 0
                t = datetime.now(_LIMA).time()
                from datetime import time as _time
                in_market = _time(9, 0) <= t < _time(13, 30)
                _gc.collect()
                if in_market:
                    _ev.sleep(45)   # horario de mercado: ciclo cada 45s
                else:
                    _log.info('[FX-WATCH] Fuera de horario — próximo ciclo en 30 min')
                    _ev.sleep(1800)
            except Exception as e:
                import traceback
                consecutive_errors += 1
                _log.error(f'[FX-WATCH] ❌ Error #{consecutive_errors}: {e}\n{traceback.format_exc()}')
                try:
                    db.session.remove()
                except Exception:
                    pass
                backoff = min(2 * consecutive_errors, 30)
                _ev.sleep(backoff)

    def _fx_monitor_watchdog():
        import eventlet as _ev
        _log = logging.getLogger(__name__)
        gt = eventlet.spawn(_fx_monitor_loop)
        _log.info('[FX-WATCH] Watchdog activo')
        while True:
            _ev.sleep(15)
            if gt.dead:
                _log.critical('[FX-WATCH] 🚨 Loop muerto — respawneando automáticamente')
                gt = eventlet.spawn(_fx_monitor_loop)

    eventlet.spawn(_fx_monitor_watchdog)
    _run_every(24 * 3600, 'Calendario económico', _calendar)

    # Análisis diario a las 8:30 AM Lima, lunes a viernes
    def _daily_analysis_at_time():
        from datetime import datetime, timezone, timedelta
        _LIMA = timezone(timedelta(hours=-5))

        def _next_830(now_lima):
            """Próximo 8:30 AM Lima en día hábil (lun-vie)."""
            target = now_lima.replace(hour=8, minute=30, second=0, microsecond=0)
            if now_lima >= target:
                target += timedelta(days=1)
            while target.weekday() >= 5:  # saltar sábado (5) y domingo (6)
                target += timedelta(days=1)
            return target

        def loop():
            logging.info("[MARKET] ✅ Scheduler análisis diario 8:30 AM Lima iniciado")
            while True:
                now  = datetime.now(_LIMA)
                next_run = _next_830(now)
                wait_secs = (next_run - now).total_seconds()
                logging.info(
                    f"[MARKET] Próximo análisis diario en "
                    f"{int(wait_secs//3600)}h {int((wait_secs%3600)//60)}m "
                    f"({next_run.strftime('%Y-%m-%d %H:%M')} Lima)"
                )
                eventlet.sleep(wait_secs)
                try:
                    with app.app_context():
                        from app.services.market.market_service import MarketService
                        r = MarketService.run_daily_analysis_cycle()
                        logging.info(f"[MARKET] Análisis base 8:30 AM: {r}")
                except Exception as e:
                    import traceback
                    logging.error(f"[MARKET] ❌ Análisis diario: {e}\n{traceback.format_exc()}")

        eventlet.spawn(loop)

    _daily_analysis_at_time()

    # ── Lead Hunter: corre diariamente a las 7:00 AM Lima ────────────────────
    def _lead_hunter_daily():
        """Caza de prospectos automática — una vez al día a las 7 AM Lima."""
        import datetime as _dt
        _LIMA_TZ = _dt.timezone(_dt.timedelta(hours=-5))

        def loop():
            logging.info('[LEAD_HUNTER] Scheduler iniciado — corre diario a las 7:00 AM Lima')
            while True:
                try:
                    now_l = _dt.datetime.now(_LIMA_TZ)
                    target = now_l.replace(hour=7, minute=0, second=0, microsecond=0)
                    if now_l >= target:
                        target += _dt.timedelta(days=1)
                    wait_secs = (target - now_l).total_seconds()
                    logging.info(f'[LEAD_HUNTER] Próxima caza en {wait_secs/3600:.1f}h')
                    eventlet.sleep(wait_secs)
                    with app.app_context():
                        from app.services.ai.lead_hunter_agent import run_hunt
                        r = run_hunt(sources=['sunat', 'news'], min_score=40, max_new_leads=80)
                        logging.info(f'[LEAD_HUNTER] Ciclo: {r.get("insertados",0)} nuevos prospectos')
                except Exception as e:
                    import traceback
                    logging.error(f'[LEAD_HUNTER] ❌ {e}\n{traceback.format_exc()}')
                    eventlet.sleep(3600)  # reintentar en 1h si falla

        eventlet.spawn(loop)

    _lead_hunter_daily()


def register_cli_commands(app):
    """Registra CLI commands dentro del factory para que siempre estén disponibles."""

    # ── backfill-ledger ──────────────────────────────────────────────────────
    import click

    @app.cli.command("backfill-ledger")
    @click.option('--apply', is_flag=True, default=False,
                  help='Ejecuta el backfill real. Sin este flag corre en dry-run.')
    @click.option('--no-recalc', is_flag=True, default=False,
                  help='Omite el recálculo de balance_after al finalizar.')
    def backfill_ledger(apply, no_recalc):
        """
        Reconstruye el ledger BankMovement a partir de operaciones históricas.

        Por defecto corre en DRY-RUN (sólo reporta).
        Para aplicar cambios: flask backfill-ledger --apply

        Seguro, idempotente: salta operaciones que ya tienen BankMovements.
        """
        from app.services.ledger_backfill import run_backfill
        dry_run = not apply
        recalc  = not no_recalc

        if dry_run:
            print('\n[DRY-RUN] No se escribirá nada. Usa --apply para aplicar.\n')
        else:
            print('\n[APPLY] Iniciando backfill real...\n')

        result = run_backfill(dry_run=dry_run, recalc=recalc, user_id=None)

        print(f"  Operaciones completadas totales : {result['ops_total']}")
        print(f"  Ya en ledger (skipped)          : {result['ops_skipped']}")
        print(f"  Sin banco determinable (no_bank): {result['ops_no_bank']}")
        print(f"  Procesadas                      : {result['ops_processed']}")
        print(f"  BankMovements {'a crear' if dry_run else 'creados'}          : {result['movements_created']}")

        if result.get('recalc_result'):
            r = result['recalc_result']
            print(f"  Recalc balance_after            : {r['updated']} registros en {r['pairs']} cuentas")

        if result['errors']:
            print(f"\n  ERRORES ({len(result['errors'])}):")
            for e in result['errors']:
                print(f"    - {e}")

        if dry_run and result.get('preview'):
            print(f"\n  Preview (primeras 20 entradas):")
            for p in result['preview'][:20]:
                sign = '+' if p['delta'] > 0 else ''
                print(f"    [{p['fecha'][:10]}] {p['op']:10} {p['acct_name']:35} "
                      f"{p['currency']} {sign}{p['delta']:>12,.2f}  ({p['client']})")

        print()
        if dry_run:
            print("→ Para aplicar: flask backfill-ledger --apply\n")
        else:
            print("✓ Backfill completado.\n")

    @app.cli.command("backfill-bank-names")
    def backfill_bank_names():
        """
        Rellena source_bank_name / destination_bank_name en operaciones históricas.
        Fallback cuando no se encuentra la cuenta del cliente: INTERBANK.
        Uso: flask backfill-bank-names
        """
        from app.extensions import db
        from app.models.operation import Operation
        from sqlalchemy import text, inspect as sa_inspect
        import traceback

        try:
            inspector = sa_inspect(db.engine)
            existing_cols = [c['name'] for c in inspector.get_columns('operations')]

            for col in ('source_bank_name', 'destination_bank_name'):
                if col not in existing_cols:
                    db.session.execute(
                        text(f"ALTER TABLE operations ADD COLUMN IF NOT EXISTS {col} VARCHAR(100)")
                    )
                    db.session.commit()
                    print(f"✓ Columna {col} creada")
                else:
                    print(f"  Columna {col} ya existe")

            ops = Operation.query.filter(
                (Operation.source_bank_name == None) | (Operation.destination_bank_name == None)  # noqa
            ).all()
            print(f"  Operaciones a procesar: {len(ops)}")

            updated = 0
            for op in ops:
                src_bank = op.source_bank_name
                dst_bank = op.destination_bank_name

                if op.client:
                    try:
                        for acct in (op.client.bank_accounts or []):
                            if src_bank is None and acct.get('account_number') == op.source_account:
                                src_bank = acct.get('bank_name')
                            if dst_bank is None and acct.get('account_number') == op.destination_account:
                                dst_bank = acct.get('bank_name')
                    except Exception:
                        pass

                if src_bank is None and op.source_account:
                    src_bank = 'INTERBANK'
                if dst_bank is None and op.destination_account:
                    dst_bank = 'INTERBANK'

                op.source_bank_name = src_bank
                op.destination_bank_name = dst_bank
                updated += 1

            db.session.commit()
            print(f"✓ {updated} operaciones actualizadas con nombres de banco")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("regenerate-journal-entries")
    def regenerate_journal_entries():
        """
        Anula y regenera asientos contables de operaciones COMPLETADAS de hoy.
        Usar después de corregir qc_bank en los flujos o cuando los asientos
        tengan códigos PCGE incorrectos.
        Uso: flask regenerate-journal-entries
        """
        from app.extensions import db
        from app.models.operation import Operation
        from app.models.journal_entry import JournalEntry
        from app.services.accounting.journal_service import JournalService
        from app.utils.formatters import now_peru
        from datetime import datetime, time
        import traceback

        try:
            hoy = now_peru().date()
            inicio = datetime.combine(hoy, time.min)
            fin    = datetime.combine(hoy, time.max)

            ops = Operation.query.filter(
                Operation.status == 'Completada',
                Operation.created_at >= inicio,
                Operation.created_at <= fin,
            ).all()
            print(f"  Operaciones completadas hoy ({hoy}): {len(ops)}")

            anulados = 0
            recreados = 0

            for op in ops:
                # Anular asientos existentes de esta operación
                existing = JournalEntry.query.filter_by(
                    source_type='operation',
                    source_id=op.id,
                    status='activo'
                ).all()
                for entry in existing:
                    entry.status = 'anulado'
                    entry.annulled_at = now_peru()
                    entry.annulled_reason = 'Regenerado vía flask regenerate-journal-entries'
                    anulados += 1
                db.session.flush()

                # Recrear asiento con lógica corregida
                nuevo = JournalService.create_entry_for_completed_operation(op)
                if nuevo:
                    recreados += 1
                    print(f"  ✓ {op.operation_id} → {nuevo.entry_number}")
                else:
                    print(f"  ✗ {op.operation_id} — asiento no generado (sin amount_pen?)")

            print(f"✓ Anulados: {anulados}  |  Recreados: {recreados}")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("create-tables")
    def create_tables():
        """Crea todas las tablas faltantes usando db.create_all() (seguro, idempotente)."""
        from app.extensions import db
        from app.models.system_config import SystemConfig
        import traceback
        try:
            db.create_all()
            # Seed parámetros fiscales por defecto (idempotente)
            # UIT: solo insertar si no existe (puede ser actualizada manualmente)
            if not db.session.get(SystemConfig, 'UIT'):
                db.session.add(SystemConfig(key='UIT', value='5350',
                                            description='Unidad Impositiva Tributaria vigente (S/)'))

            # RUC y RAZON_SOCIAL: siempre forzar los valores correctos de la empresa
            company_defaults = [
                ('RUC',          '20615113698', 'RUC de la empresa (para exportaciones SUNAT)'),
                ('RAZON_SOCIAL', 'QORICASH SAC', 'Razón social de la empresa'),
            ]
            for key, value, desc in company_defaults:
                existing = db.session.get(SystemConfig, key)
                if existing:
                    existing.value = value
                    existing.description = desc
                else:
                    db.session.add(SystemConfig(key=key, value=value, description=desc))
            db.session.commit()
            print("✓ Tablas creadas / verificadas correctamente")
        except Exception as e:
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("refresh-market")
    def refresh_market():
        """Ejecuta manualmente todos los ciclos de mercado: precios, noticias, macro, calendario."""
        from app.services.market.market_service import MarketService
        import traceback

        print("=== CICLO DE PRECIOS ===")
        try:
            r = MarketService.run_price_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n=== CICLO DE NOTICIAS ===")
        try:
            r = MarketService.run_news_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n=== CICLO MACRO ===")
        try:
            r = MarketService.run_macro_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n=== CICLO CALENDARIO ===")
        try:
            r = MarketService.run_calendar_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n✓ refresh-market completado")

    @app.cli.command("refresh-fx")
    def refresh_fx():
        """Siembra competidores y ejecuta ciclo de scraping FX Monitor."""
        from app.services.fx_monitor.monitor_service import FXMonitorService
        import traceback

        print("=== SEEDING COMPETIDORES ===")
        try:
            FXMonitorService.seed_competitors()
            print("  ✓ Competidores sembrados")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n=== CICLO FX SCRAPING ===")
        try:
            r = FXMonitorService.run_scrape_cycle()
            print(f"  Resultado: {r}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            traceback.print_exc()

        print("\n✓ refresh-fx completado")

    @app.cli.command("seed-accounts")
    def seed_accounts():
        """Carga el catálogo de cuentas PCGE para QoriCash (idempotente)."""
        from app.extensions import db
        from app.models.accounting_account import AccountingAccount
        import traceback

        ACCOUNTS = [
            # ── ACTIVO CORRIENTE ────────────────────────────────────────────
            ('1011', 'Caja Moneda Nacional',              'activo',    'deudora',   'PEN'),
            ('1012', 'Caja Moneda Extranjera',            'activo',    'deudora',   'USD'),
            ('1041', 'BCP – Cta. Cte. PEN',               'activo',    'deudora',   'PEN'),
            ('1044', 'BCP – Cta. Cte. USD',               'activo',    'deudora',   'USD'),
            ('1047', 'Interbank – Cta. Cte. USD',         'activo',    'deudora',   'USD'),
            ('1048', 'Interbank – Cta. Cte. PEN',         'activo',    'deudora',   'PEN'),
            ('1049', 'BanBif – Cta. Cte. PEN',            'activo',    'deudora',   'PEN'),
            ('1050', 'BanBif – Cta. Cte. USD',            'activo',    'deudora',   'USD'),
            ('1051', 'Pichincha – Cta. Cte. PEN',         'activo',    'deudora',   'PEN'),
            ('1052', 'Pichincha – Cta. Cte. USD',         'activo',    'deudora',   'USD'),
            ('1211', 'Clientes por cobrar',               'activo',    'deudora',   'PEN'),
            # ── ACTIVO NO CORRIENTE (inmuebles, maq. y equipo) ─────────────
            ('3321', 'Instalaciones en curso',            'activo',    'deudora',   'PEN'),
            ('3351', 'Muebles y enseres',                 'activo',    'deudora',   'PEN'),
            ('3361', 'Equipos de cómputo',                'activo',    'deudora',   'PEN'),
            ('3362', 'Equipos de oficina',                'activo',    'deudora',   'PEN'),
            # ── DEPRECIACIÓN ACUMULADA (contra-cuenta, naturaleza acreedora)
            ('3921', 'Deprec. acum. – Instalaciones',    'activo',    'acreedora', 'PEN'),
            ('3951', 'Deprec. acum. – Muebles y enseres','activo',    'acreedora', 'PEN'),
            ('3961', 'Deprec. acum. – Equipos cómputo',  'activo',    'acreedora', 'PEN'),
            ('3962', 'Deprec. acum. – Equipos oficina',  'activo',    'acreedora', 'PEN'),
            # ── PASIVO ──────────────────────────────────────────────────────
            # NOTA: 4011 PCGE = IGV (Impuesto General a las Ventas)
            # Casa de cambio exonerada de IGV — 4011 se usa si hay crédito fiscal prorrata
            ('4011', 'IGV – Cuenta propia',               'pasivo',    'acreedora', 'PEN'),
            ('4017', 'IR – Pago a cuenta mensual',        'pasivo',    'acreedora', 'PEN'),
            ('4031', 'EsSalud por pagar',                 'pasivo',    'acreedora', 'PEN'),
            ('4032', 'AFP / ONP por pagar',               'pasivo',    'acreedora', 'PEN'),
            ('4111', 'Remuneraciones por pagar',          'pasivo',    'acreedora', 'PEN'),
            ('4211', 'Facturas por pagar',                'pasivo',    'acreedora', 'PEN'),
            ('4699', 'Otras cuentas por pagar',           'pasivo',    'acreedora', 'PEN'),
            # ── PATRIMONIO ──────────────────────────────────────────────────
            ('501',  'Capital social',                    'patrimonio','acreedora', 'PEN'),
            ('591',  'Utilidades acumuladas',             'patrimonio','acreedora', 'PEN'),
            ('592',  'Pérdidas acumuladas',               'patrimonio','deudora',   'PEN'),
            # ── INGRESOS ────────────────────────────────────────────────────
            ('7711', 'Ganancia diferencial cambiario',    'ingreso',   'acreedora', 'PEN'),
            ('7712', 'Otros ingresos financieros',        'ingreso',   'acreedora', 'PEN'),
            ('7761', 'Ganancia por diferencia de cambio – ajuste monetario', 'ingreso', 'acreedora', 'PEN'),
            # ── GASTOS ──────────────────────────────────────────────────────
            ('621',  'Remuneraciones al personal',        'gasto',     'deudora',   'PEN'),
            ('627',  'Seguridad social – EsSalud/AFP',    'gasto',     'deudora',   'PEN'),
            ('6311', 'Transporte y delivery',             'gasto',     'deudora',   'PEN'),
            ('6361', 'Energía / telecomunicaciones',      'gasto',     'deudora',   'PEN'),
            ('6381', 'Honorarios (contador, legal)',      'gasto',     'deudora',   'PEN'),
            ('6391', 'Comisiones bancarias / ITF',        'gasto',     'deudora',   'PEN'),
            ('6392', 'Servicios de tecnología / software','gasto',     'deudora',   'PEN'),
            ('6411', 'IR – Pago a cuenta (gasto)',        'gasto',     'deudora',   'PEN'),
            ('6511', 'Otros gastos de gestión',           'gasto',     'deudora',   'PEN'),
            ('6762', 'Pérdida por diferencia de cambio',  'gasto',     'deudora',   'PEN'),
            ('6814', 'Depreciación – Inmuebles, maq. y equipo', 'gasto','deudora',  'PEN'),
        ]

        # Actualizar nombre de 4011 si fue registrado con el nombre incorrecto de IR
        _old_4011 = AccountingAccount.query.filter_by(code='4011').first()
        if _old_4011 and 'IR' in (_old_4011.name or '').upper():
            _old_4011.name = 'IGV – Cuenta propia'

        try:
            created = 0
            skipped = 0
            for code, name, type_, nature, currency in ACCOUNTS:
                existing = AccountingAccount.query.filter_by(code=code).first()
                if existing:
                    skipped += 1
                    continue
                acc = AccountingAccount(
                    code=code, name=name, type=type_,
                    nature=nature, currency=currency, is_active=True
                )
                db.session.add(acc)
                created += 1
            # Desactivar cuentas BBVA/Scotiabank si existen (QoriCash no opera en esos bancos)
            deactivated = 0
            for old_code in ('1042', '1043', '1045', '1046'):
                old_acc = AccountingAccount.query.filter_by(code=old_code).first()
                if old_acc and old_acc.is_active:
                    old_acc.is_active = False
                    deactivated += 1
            db.session.commit()
            print(f"✓ seed-accounts: {created} cuentas creadas, {skipped} ya existían, {deactivated} desactivadas")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error en seed-accounts: {e}")
            traceback.print_exc()

    @app.cli.command("seed-demo-contabilidad")
    def seed_demo_contabilidad():
        """Carga datos demo de contabilidad para Enero-Marzo 2026 (visualización)."""
        from app.extensions import db
        from app.models.accounting_period import AccountingPeriod
        from app.models.expense_record import ExpenseRecord
        from app.models.operation import Operation
        from app.models.client import Client
        from app.services.accounting.journal_service import JournalService
        from datetime import date, datetime
        from decimal import Decimal
        from sqlalchemy import extract
        import traceback

        # ── Buscar un cliente existente para las Operaciones del LIG ────────
        demo_client = Client.query.first()
        if not demo_client:
            print("  · Sin clientes en BD — se crearán asientos pero NO operaciones (LIG vacío)")

        def _seed_month(year, month, month_tag, ops_data, spreads_data, gastos_data, op_prefix):
            """Siembra un mes completo. Idempotente: salta si ya hay datos demo."""
            # Período
            period = AccountingPeriod.query.filter_by(year=year, month=month).first()
            if not period:
                period = AccountingPeriod(year=year, month=month, status='abierto')
                db.session.add(period)
                db.session.flush()
                print(f"  ✓ Período {month_tag} {year} creado")
            else:
                print(f"  · Período {month_tag} {year} ya existe")

            # Chequeo de idempotencia: ¿ya existen asientos demo en este mes?
            existing = db.session.query(JournalService._model()).filter(
                JournalService._model().source_type == 'demo',
                extract('year',  JournalService._model().entry_date) == year,
                extract('month', JournalService._model().entry_date) == month,
            ).first() if hasattr(JournalService, '_model') else None

            # Usamos JournalEntry directamente para la verificación
            from app.models.journal_entry import JournalEntry
            existing = JournalEntry.query.filter(
                JournalEntry.source_type == 'demo',
                extract('year',  JournalEntry.entry_date) == year,
                extract('month', JournalEntry.entry_date) == month,
            ).first()
            if existing:
                print(f"  · Asientos demo {month_tag} ya existen — saltando")
                return

            # ── Asientos de operaciones ──────────────────────────────────
            op_counter = [0]
            for d, tipo, cliente, usd, tc, pen, acc_pen, acc_usd in ops_data:
                pen_d = Decimal(str(pen))
                usd_d = Decimal(str(usd))
                tc_d  = Decimal(str(tc))
                if tipo == 'Compra':
                    lines = [
                        {'account_code': acc_pen, 'description': f'Ingreso PEN – {cliente}',
                         'debe': pen_d, 'haber': Decimal('0'), 'currency': 'PEN'},
                        {'account_code': acc_usd, 'description': f'Egreso USD – {cliente}',
                         'debe': Decimal('0'), 'haber': pen_d,
                         'currency': 'USD', 'amount_usd': usd_d, 'exchange_rate': tc_d},
                    ]
                    glosa = f'DEMO Compra USD – {cliente}'
                else:
                    lines = [
                        {'account_code': acc_usd, 'description': f'Ingreso USD – {cliente}',
                         'debe': pen_d, 'haber': Decimal('0'),
                         'currency': 'USD', 'amount_usd': usd_d, 'exchange_rate': tc_d},
                        {'account_code': acc_pen, 'description': f'Egreso PEN – {cliente}',
                         'debe': Decimal('0'), 'haber': pen_d, 'currency': 'PEN'},
                    ]
                    glosa = f'DEMO Venta USD – {cliente}'

                e = JournalService.create_entry(
                    entry_type='operacion_completada',
                    description=glosa,
                    lines=lines,
                    source_type='demo',
                    source_id=None,
                    entry_date=d,
                    created_by=None,
                )
                print(f"  ✓ {e.entry_number}  {glosa[:55]}")

                # Crear Operation para el LIG si hay cliente disponible
                if demo_client:
                    op_counter[0] += 1
                    op_id = f'{op_prefix}-{op_counter[0]:03d}'
                    if not Operation.query.filter_by(operation_id=op_id).first():
                        op = Operation(
                            operation_id=op_id,
                            client_id=demo_client.id,
                            operation_type=tipo,
                            origen='sistema',
                            amount_usd=usd_d,
                            exchange_rate=tc_d,
                            amount_pen=pen_d,
                            status='Completada',
                            completed_at=datetime(d.year, d.month, d.day, 14, 0, 0),
                        )
                        db.session.add(op)

            # ── Asientos de spread ───────────────────────────────────────
            for d, glosa, lines in spreads_data:
                e = JournalService.create_entry('calce_netting', glosa, lines,
                                                source_type='demo', entry_date=d)
                print(f"  ✓ {e.entry_number}  {glosa}")

            # ── Gastos + ExpenseRecords ──────────────────────────────────
            for d, cat, desc, monto, vtype, vnum, ruc, proveedor in gastos_data:
                pen_d = Decimal(str(monto))
                e = JournalService.create_entry(
                    entry_type='gasto',
                    description=f'DEMO Gasto: {desc}',
                    lines=[
                        {'account_code': cat,  'description': desc,
                         'debe': pen_d, 'haber': Decimal('0'), 'currency': 'PEN'},
                        {'account_code': '4699','description': f'Por pagar: {desc}',
                         'debe': Decimal('0'), 'haber': pen_d, 'currency': 'PEN'},
                    ],
                    source_type='demo',
                    entry_date=d,
                    created_by=None,
                )
                er = ExpenseRecord(
                    period_id=period.id,
                    expense_date=d,
                    category=cat,
                    description=desc,
                    amount_pen=pen_d,
                    voucher_type=vtype,
                    voucher_number=vnum,
                    supplier_ruc=ruc,
                    supplier_name=proveedor,
                    journal_entry_id=e.id if e else None,
                    created_by=None,
                )
                db.session.add(er)
                print(f"  ✓ Gasto: {desc[:50]}  S/ {monto:.2f}")

            db.session.commit()
            print(f"  ✓ {month_tag} {year} completado\n")

        # ═══════════════════════════════════════════════════════════════════
        # DATOS ENERO 2026
        # ═══════════════════════════════════════════════════════════════════
        print("\n── Enero 2026 ─────────────────────────────────────────────")
        _seed_month(2026, 1, 'Ene',
            ops_data=[
                (date(2026,1, 5), 'Compra', 'Roberto Castillo',    4_000, 3.7100, 14_840.00, '1041','1044'),
                (date(2026,1, 8), 'Venta',  'Sonia Vargas',        2_800, 3.6900, 10_332.00, '1041','1044'),
                (date(2026,1,12), 'Compra', 'Inversiones Norte SAC',7_500, 3.7200, 27_900.00, '1048','1047'),
                (date(2026,1,15), 'Venta',  'Miguel Torres',        3_000, 3.6800, 11_040.00, '1048','1047'),
                (date(2026,1,19), 'Compra', 'Diana Quispe',         6_000, 3.7300, 22_380.00, '1041','1044'),
                (date(2026,1,22), 'Venta',  'Transporte Lima SAC', 10_000, 3.6700, 36_700.00, '1041','1044'),
                (date(2026,1,26), 'Compra', 'Arturo Mendoza',       5_500, 3.7100, 20_405.00, '1041','1044'),
                (date(2026,1,29), 'Venta',  'Cecilia Flores',       4_200, 3.6800, 15_456.00, '1041','1044'),
            ],
            spreads_data=[
                (date(2026,1,31), 'DEMO Spread compra USD Ene-2026',
                 [{'account_code':'1041','description':'Spread compra','debe':Decimal('1620.00'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario compra','debe':Decimal('0'),'haber':Decimal('1620.00'),'currency':'PEN'}]),
                (date(2026,1,31), 'DEMO Spread venta USD Ene-2026',
                 [{'account_code':'1041','description':'Spread venta','debe':Decimal('980.00'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario venta','debe':Decimal('0'),'haber':Decimal('980.00'),'currency':'PEN'}]),
            ],
            gastos_data=[
                (date(2026,1, 2),'6391','Alquiler local Ene-2026',         3_500.00,'Factura','F001-00198','20512345678','Inmobiliaria Central SAC'),
                (date(2026,1, 5),'6361','Energía eléctrica enero',           295.00,'Boleta', 'B003-08750','20331376783','Enel Distribución Perú SAC'),
                (date(2026,1, 5),'6361','Telefonía e internet enero',        450.00,'Boleta', 'B002-01423','20116544526','Claro Perú SAC'),
                (date(2026,1,10),'6381','Honorarios contador Ene-2026',      800.00,'Recibo', 'RH-001-0312','10412345678','Juan Pérez Quispe CPC'),
                (date(2026,1,15),'6391','Comisión bancaria BCP enero',       160.00, None,     None,         None,         None),
                (date(2026,1,20),'6391','Publicidad digital enero',          500.00,'Factura','F004-00701','20601234567','Digital Media SAC'),
                (date(2026,1,25),'6511','Útiles de escritorio',              210.00,'Boleta', 'B005-02201','10298765432','Librería San Juan EIRL'),
                (date(2026,1,31),'6361','Internet adicional enero',          250.00,'Boleta', 'B006-04321','20116544526','Movistar Perú SAC'),
            ],
            op_prefix='DEMO-ENE26',
        )

        # ═══════════════════════════════════════════════════════════════════
        # DATOS FEBRERO 2026
        # ═══════════════════════════════════════════════════════════════════
        print("── Febrero 2026 ───────────────────────────────────────────")
        _seed_month(2026, 2, 'Feb',
            ops_data=[
                (date(2026,2, 3), 'Compra', 'Carlos Mendoza',           5_000, 3.7200, 18_600.00, '1041','1044'),
                (date(2026,2, 5), 'Venta',  'Ana Torres',               3_200, 3.6800, 11_776.00, '1041','1044'),
                (date(2026,2, 7), 'Compra', 'Empresa XYZ SAC',         10_000, 3.7300, 37_300.00, '1048','1047'),
                (date(2026,2,10), 'Venta',  'Luis García',              2_500, 3.6700,  9_175.00, '1048','1047'),
                (date(2026,2,12), 'Compra', 'María López',              8_000, 3.7100, 29_680.00, '1041','1044'),
                (date(2026,2,14), 'Venta',  'Importaciones ABC SAC',   15_000, 3.6900, 55_350.00, '1041','1044'),
                (date(2026,2,17), 'Compra', 'Pedro Sánchez',            4_500, 3.7400, 16_830.00, '1041','1044'),
                (date(2026,2,19), 'Venta',  'Rosa Flores',              6_000, 3.6800, 22_080.00, '1041','1044'),
                (date(2026,2,21), 'Compra', 'Exportadores del Perú SAC',20_000, 3.7200, 74_400.00, '1041','1044'),
                (date(2026,2,24), 'Venta',  'Jorge Huanca',             3_800, 3.6600, 13_908.00, '1041','1044'),
                (date(2026,2,26), 'Compra', 'Patricia Quispe',          7_500, 3.7300, 27_975.00, '1048','1047'),
                (date(2026,2,28), 'Venta',  'Comercial Lima SAC',      12_000, 3.7000, 44_400.00, '1048','1047'),
            ],
            spreads_data=[
                (date(2026,2,28), 'DEMO Spread compra USD Feb-2026',
                 [{'account_code':'1041','description':'Spread compra','debe':Decimal('1850.50'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario compra','debe':Decimal('0'),'haber':Decimal('1850.50'),'currency':'PEN'}]),
                (date(2026,2,28), 'DEMO Spread venta USD Feb-2026',
                 [{'account_code':'1041','description':'Spread venta','debe':Decimal('1240.00'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario venta','debe':Decimal('0'),'haber':Decimal('1240.00'),'currency':'PEN'}]),
            ],
            gastos_data=[
                (date(2026,2, 1),'6391','Alquiler local Feb-2026',          3_500.00,'Factura','F001-00234','20512345678','Inmobiliaria Central SAC'),
                (date(2026,2, 3),'6361','Servicio de energía eléctrica',      320.00,'Boleta', 'B003-08921','20331376783','Enel Distribución Perú SAC'),
                (date(2026,2, 3),'6361','Telefonía e internet empresarial',   450.00,'Boleta', 'B002-01567','20116544526','Claro Perú SAC'),
                (date(2026,2, 8),'6381','Honorarios contador Feb-2026',       800.00,'Recibo', 'RH-001-0345','10412345678','Juan Pérez Quispe CPC'),
                (date(2026,2,10),'6391','Comisión bancaria BCP Feb-2026',     185.00, None,     None,         None,         None),
                (date(2026,2,15),'6391','Comisión bancaria Interbank Feb-2026',120.00, None,     None,         None,         None),
                (date(2026,2,17),'6391','Publicidad en redes sociales',       600.00,'Factura','F004-00789','20601234567','Digital Media SAC'),
                (date(2026,2,20),'6511','Material de oficina y útiles',       280.00,'Boleta', 'B005-02345','10298765432','Librería San Juan EIRL'),
                (date(2026,2,25),'6391','Servicio de limpieza de local',      350.00,'Recibo', 'RC-002-0123','20456789012','Limpiezas Rápidas SAC'),
                (date(2026,2,28),'6361','Internet y comunicaciones añadidas', 250.00,'Boleta', 'B006-04567','20116544526','Movistar Perú SAC'),
            ],
            op_prefix='DEMO-FEB26',
        )

        # ═══════════════════════════════════════════════════════════════════
        # DATOS MARZO 2026 (mes actual — el que se ve por defecto)
        # ═══════════════════════════════════════════════════════════════════
        print("── Marzo 2026 (mes actual) ────────────────────────────────")
        _seed_month(2026, 3, 'Mar',
            ops_data=[
                (date(2026,3, 2), 'Compra', 'Fernanda Villanueva',    6_000, 3.7150, 22_290.00, '1041','1044'),
                (date(2026,3, 4), 'Venta',  'Grupo Andino SAC',       4_500, 3.6950, 16_627.50, '1041','1044'),
                (date(2026,3, 6), 'Compra', 'Humberto Palomino',      3_200, 3.7200, 11_904.00, '1048','1047'),
                (date(2026,3,10), 'Venta',  'Exportaciones Sur EIRL', 8_000, 3.6800, 29_440.00, '1048','1047'),
                (date(2026,3,12), 'Compra', 'Luz Marina Rojas',       5_000, 3.7300, 18_650.00, '1041','1044'),
                (date(2026,3,14), 'Venta',  'Comercio Global SAC',   12_000, 3.6900, 44_280.00, '1041','1044'),
                (date(2026,3,17), 'Compra', 'Omar Salinas',            7_000, 3.7250, 26_075.00, '1041','1044'),
                (date(2026,3,19), 'Venta',  'Importex Perú SAC',      9_500, 3.6850, 35_007.50, '1041','1044'),
                (date(2026,3,21), 'Compra', 'Cristina Pacheco',        4_000, 3.7200, 14_880.00, '1041','1044'),
                (date(2026,3,24), 'Venta',  'Negocios Lima SAC',      15_000, 3.6750, 55_125.00, '1041','1044'),
                (date(2026,3,26), 'Compra', 'Raúl Contreras',          6_500, 3.7300, 24_245.00, '1048','1047'),
                (date(2026,3,28), 'Venta',  'Trading Norte SAC',      11_000, 3.6900, 40_590.00, '1048','1047'),
                (date(2026,3,31), 'Compra', 'Vanessa Herrera',         3_500, 3.7200, 13_020.00, '1041','1044'),
            ],
            spreads_data=[
                (date(2026,3,31), 'DEMO Spread compra USD Mar-2026',
                 [{'account_code':'1041','description':'Spread compra','debe':Decimal('2105.75'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario compra','debe':Decimal('0'),'haber':Decimal('2105.75'),'currency':'PEN'}]),
                (date(2026,3,31), 'DEMO Spread venta USD Mar-2026',
                 [{'account_code':'1041','description':'Spread venta','debe':Decimal('1487.50'),'haber':Decimal('0'),'currency':'PEN'},
                  {'account_code':'7711','description':'Dif. cambiario venta','debe':Decimal('0'),'haber':Decimal('1487.50'),'currency':'PEN'}]),
            ],
            gastos_data=[
                (date(2026,3, 2),'6391','Alquiler local Mar-2026',          3_500.00,'Factura','F001-00271','20512345678','Inmobiliaria Central SAC'),
                (date(2026,3, 4),'6361','Energía eléctrica marzo',            308.00,'Boleta', 'B003-09104','20331376783','Enel Distribución Perú SAC'),
                (date(2026,3, 4),'6361','Telefonía e internet marzo',         450.00,'Boleta', 'B002-01689','20116544526','Claro Perú SAC'),
                (date(2026,3, 9),'6381','Honorarios contador Mar-2026',       800.00,'Recibo', 'RH-001-0378','10412345678','Juan Pérez Quispe CPC'),
                (date(2026,3,11),'6391','Comisión bancaria BCP marzo',        195.00, None,     None,         None,         None),
                (date(2026,3,15),'6391','Comisión bancaria Interbank marzo',   130.00, None,     None,         None,         None),
                (date(2026,3,18),'6391','Campaña publicidad marzo',           750.00,'Factura','F004-00832','20601234567','Digital Media SAC'),
                (date(2026,3,20),'6511','Material de oficina marzo',          195.00,'Boleta', 'B005-02489','10298765432','Librería San Juan EIRL'),
                (date(2026,3,25),'6391','Servicio de limpieza marzo',         350.00,'Recibo', 'RC-002-0145','20456789012','Limpiezas Rápidas SAC'),
                (date(2026,3,28),'6391','Renovación dominio web',             320.00,'Factura','F007-00112','20789012345','TechHost Perú SAC'),
                (date(2026,3,31),'6361','Internet adicional marzo',           250.00,'Boleta', 'B006-04789','20116544526','Movistar Perú SAC'),
            ],
            op_prefix='DEMO-MAR26',
        )

        print("✓ seed-demo-contabilidad completado — Ene, Feb, Mar 2026")
        print("  Para eliminar estos datos: flask drop-demo-contabilidad")

    @app.cli.command("drop-demo-contabilidad")
    def drop_demo_contabilidad():
        """Elimina TODOS los datos demo de contabilidad (Ene-Mar 2026)."""
        from app.extensions import db
        from app.models.accounting_period import AccountingPeriod
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine
        from app.models.expense_record import ExpenseRecord
        from app.models.operation import Operation
        from sqlalchemy import extract
        import traceback

        YEAR = 2026
        try:
            # Operaciones demo (LIG)
            op_del = Operation.query.filter(
                Operation.operation_id.like('DEMO-%')
            ).delete(synchronize_session=False)
            print(f"  ✓ {op_del} operaciones demo eliminadas")

            for month in [1, 2, 3]:
                # Expense records
                er_del = ExpenseRecord.query.filter(
                    db.extract('year',  ExpenseRecord.expense_date) == YEAR,
                    db.extract('month', ExpenseRecord.expense_date) == month,
                ).delete(synchronize_session=False)

                # Journal entries (cascade a lines via source_type='demo')
                je_ids = [r[0] for r in db.session.query(JournalEntry.id).filter(
                    JournalEntry.source_type == 'demo',
                    extract('year',  JournalEntry.entry_date) == YEAR,
                    extract('month', JournalEntry.entry_date) == month,
                ).all()]
                if je_ids:
                    JournalEntryLine.query.filter(
                        JournalEntryLine.journal_entry_id.in_(je_ids)
                    ).delete(synchronize_session=False)
                    JournalEntry.query.filter(JournalEntry.id.in_(je_ids)).delete(
                        synchronize_session=False)

                period = AccountingPeriod.query.filter_by(year=YEAR, month=month).first()
                if period:
                    db.session.delete(period)

                month_names = {1:'Ene', 2:'Feb', 3:'Mar'}
                print(f"  ✓ {month_names[month]} {YEAR}: {er_del} gastos, {len(je_ids)} asientos eliminados")

            db.session.commit()
            print(f"\n✓ drop-demo-contabilidad completado")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("seed-demo-multibanco")
    def seed_demo_multibanco():
        """
        Crea cliente demo con cuentas en 3 bancos y 2 operaciones con pagos múltiples.
        Diseñado para visualizar el Libro Caja y Bancos desagregado por banco.
        Idempotente: salta si ya existen los datos.
        """
        from app.extensions import db
        from app.models.client import Client
        from app.models.operation import Operation
        from app.models.accounting_period import AccountingPeriod
        from app.services.accounting.journal_service import JournalService
        from datetime import date, datetime
        from decimal import Decimal
        import json, traceback

        DEMO_DNI   = '72345678'
        DEMO_EMAIL = 'demo.multibanco@qoricash.pe'

        try:
            # ── 1. Cliente demo ─────────────────────────────────────────────
            client = Client.query.filter_by(dni=DEMO_DNI).first()
            if not client:
                client = Client(
                    document_type='DNI',
                    dni=DEMO_DNI,
                    email=DEMO_EMAIL,
                    nombres='María Gracia',
                    apellido_paterno='Villanueva',
                    apellido_materno='Torres',
                    phone='999888777',
                )
                # 5 cuentas en 3 bancos (PEN y USD)
                cuentas = [
                    {'bank_name': 'BCP',        'account_type': 'Ahorro',    'currency': 'S/',
                     'account_number': '19173537790119',        'origen': 'Lima'},
                    {'bank_name': 'BBVA',       'account_type': 'Ahorro',    'currency': 'S/',
                     'account_number': '00110123456789',        'origen': 'Lima'},
                    {'bank_name': 'INTERBANK',  'account_type': 'Ahorro',    'currency': 'S/',
                     'account_number': '09830123456789',        'origen': 'Lima'},
                    {'bank_name': 'BCP',        'account_type': 'Ahorro',    'currency': '$',
                     'account_number': '19174567890234',        'origen': 'Lima'},
                    {'bank_name': 'SCOTIABANK', 'account_type': 'Corriente', 'currency': '$',
                     'account_number': '00001234567890',        'origen': 'Lima'},
                ]
                client.bank_accounts_json = json.dumps(cuentas)
                db.session.add(client)
                db.session.flush()
                print(f"  ✓ Cliente creado: {client.nombres} {client.apellido_paterno} (DNI {DEMO_DNI})")
                print(f"       BCP PEN     19173537790119")
                print(f"       BBVA PEN    00110123456789")
                print(f"       INTERBANK PEN 09830123456789")
                print(f"       BCP USD     19174567890234")
                print(f"       SCOTIABANK USD 00001234567890")
            else:
                print(f"  · Cliente {DEMO_DNI} ya existe — reutilizando")

            # ── 2. Período contable Marzo 2026 ──────────────────────────────
            period = AccountingPeriod.query.filter_by(year=2026, month=3).first()
            if not period:
                period = AccountingPeriod(year=2026, month=3, status='abierto')
                db.session.add(period)
                db.session.flush()

            # ── Operación A: COMPRA $3,000 con 3 abonos PEN / 2 pagos USD ──
            OP_A_ID = 'DEMO-MB-COMPRA-001'
            if not Operation.query.filter_by(operation_id=OP_A_ID).first():
                # Cliente paga en 3 abonos PEN desde 3 bancos distintos
                deposits_a = [
                    {'importe': 4000.00, 'codigo_operacion': 'BCK-001',
                     'cuenta_cargo': '19173537790119',   # BCP PEN
                     'comprobante_url': ''},
                    {'importe': 4000.00, 'codigo_operacion': 'BCK-002',
                     'cuenta_cargo': '00110123456789',   # BBVA PEN
                     'comprobante_url': ''},
                    {'importe': 3160.00, 'codigo_operacion': 'BCK-003',
                     'cuenta_cargo': '09830123456789',   # INTERBANK PEN
                     'comprobante_url': ''},
                ]
                # QoriCash paga USD al cliente en 2 cuentas distintas
                payments_a = [
                    {'importe': 1500.00, 'cuenta_destino': '19174567890234'},   # BCP USD
                    {'importe': 1500.00, 'cuenta_destino': '00001234567890'},   # SCOTIABANK USD
                ]
                op_a = Operation(
                    operation_id=OP_A_ID,
                    client_id=client.id,
                    operation_type='Compra',
                    origen='sistema',
                    amount_usd=Decimal('3000.00'),
                    exchange_rate=Decimal('3.7200'),
                    amount_pen=Decimal('11160.00'),
                    status='Completada',
                    completed_at=datetime(2026, 3, 10, 14, 30, 0),
                    client_deposits_json=json.dumps(deposits_a),
                    client_payments_json=json.dumps(payments_a),
                )
                db.session.add(op_a)
                db.session.flush()

                entry_a = JournalService.create_entry_for_completed_operation(op_a)
                if entry_a:
                    print(f"\n  ✓ Operación A: {OP_A_ID}  COMPRA $3,000 @ 3.7200 = S/ 11,160")
                    print(f"    Abonos PEN:")
                    print(f"      BCP PEN   S/ 4,000.00  → cuenta 1041 DEBE")
                    print(f"      BCP PEN   S/ 4,000.00  → cuenta 1041 DEBE (cliente BBVA→fallback BCP)")
                    print(f"      INTERBANK S/ 3,160.00  → cuenta 1048 DEBE")
                    print(f"    Pagos USD:")
                    print(f"      BCP USD   $1,500 (S/ 5,580) → cuenta 1044 HABER")
                    print(f"      BCP USD   $1,500 (S/ 5,580) → cuenta 1044 HABER (cliente Scotia→fallback BCP)")
                    print(f"    Asiento: {entry_a.entry_number}  DEBE S/{entry_a.total_debe}  HABER S/{entry_a.total_haber}")
                else:
                    print(f"  ✗ Error al crear asiento para {OP_A_ID}")
            else:
                print(f"  · {OP_A_ID} ya existe — saltando")

            # ── Operación B: VENTA $2,000 con 2 abonos USD / 2 pagos PEN ───
            OP_B_ID = 'DEMO-MB-VENTA-001'
            if not Operation.query.filter_by(operation_id=OP_B_ID).first():
                # Cliente deposita USD desde 2 cuentas
                deposits_b = [
                    {'importe': 1200.00, 'codigo_operacion': 'BKV-001',
                     'cuenta_cargo': '19174567890234',   # BCP USD
                     'comprobante_url': ''},
                    {'importe':  800.00, 'codigo_operacion': 'BKV-002',
                     'cuenta_cargo': '00001234567890',   # SCOTIABANK USD
                     'comprobante_url': ''},
                ]
                # QoriCash paga PEN al cliente en 2 bancos
                payments_b = [
                    {'importe': 4000.00, 'cuenta_destino': '19173537790119'},   # BCP PEN
                    {'importe': 3380.00, 'cuenta_destino': '00110123456789'},   # BBVA PEN
                ]
                op_b = Operation(
                    operation_id=OP_B_ID,
                    client_id=client.id,
                    operation_type='Venta',
                    origen='sistema',
                    amount_usd=Decimal('2000.00'),
                    exchange_rate=Decimal('3.6900'),
                    amount_pen=Decimal('7380.00'),
                    status='Completada',
                    completed_at=datetime(2026, 3, 18, 10, 15, 0),
                    client_deposits_json=json.dumps(deposits_b),
                    client_payments_json=json.dumps(payments_b),
                )
                db.session.add(op_b)
                db.session.flush()

                entry_b = JournalService.create_entry_for_completed_operation(op_b)
                if entry_b:
                    print(f"\n  ✓ Operación B: {OP_B_ID}  VENTA $2,000 @ 3.6900 = S/ 7,380")
                    print(f"    Abonos USD:")
                    print(f"      BCP USD   $1,200 (S/ 4,428) → cuenta 1044 DEBE")
                    print(f"      BCP USD   $  800 (S/ 2,952) → cuenta 1044 DEBE (cliente Scotia→fallback BCP)")
                    print(f"    Pagos PEN:")
                    print(f"      BCP PEN   S/ 4,000.00 → cuenta 1041 HABER")
                    print(f"      BCP PEN   S/ 3,380.00 → cuenta 1041 HABER (cliente BBVA→fallback BCP)")
                    print(f"    Asiento: {entry_b.entry_number}  DEBE S/{entry_b.total_debe}  HABER S/{entry_b.total_haber}")
                else:
                    print(f"  ✗ Error al crear asiento para {OP_B_ID}")
            else:
                print(f"  · {OP_B_ID} ya existe — saltando")

            db.session.commit()
            print(f"\n✓ seed-demo-multibanco completado")
            print(f"  Para eliminar: flask drop-demo-multibanco")
            print(f"  Ver en: /contabilidad/caja?year=2026&month=3")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("drop-demo-multibanco")
    def drop_demo_multibanco():
        """Elimina el cliente y operaciones del seed-demo-multibanco."""
        from app.extensions import db
        from app.models.client import Client
        from app.models.operation import Operation
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine
        import traceback

        try:
            # Asientos de las operaciones demo
            for op_id in ['DEMO-MB-COMPRA-001', 'DEMO-MB-VENTA-001']:
                op = Operation.query.filter_by(operation_id=op_id).first()
                if op:
                    je = JournalEntry.query.filter_by(
                        source_type='operation', source_id=op.id
                    ).first()
                    if je:
                        JournalEntryLine.query.filter_by(
                            journal_entry_id=je.id
                        ).delete(synchronize_session=False)
                        db.session.delete(je)
                    db.session.delete(op)
                    print(f"  ✓ Operación {op_id} + asiento eliminados")

            # Cliente demo
            client = Client.query.filter_by(dni='72345678').first()
            if client:
                db.session.delete(client)
                print(f"  ✓ Cliente demo DNI 72345678 eliminado")

            db.session.commit()
            print(f"✓ drop-demo-multibanco completado")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("clear-complaints")
    def clear_complaints():
        """Elimina TODOS los reclamos de la tabla complaints (producción)."""
        from app.extensions import db
        from app.models.complaint import Complaint
        import traceback
        try:
            count = Complaint.query.count()
            if count == 0:
                print("✓ No hay reclamos que eliminar.")
                return
            print(f"  Se van a eliminar {count} reclamo(s)...")
            Complaint.query.delete()
            db.session.commit()
            print(f"✓ {count} reclamo(s) eliminado(s) correctamente.")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    @app.cli.command("drop-all-demo")
    def drop_all_demo():
        """
        Limpieza completa de TODOS los datos demo:
        asientos, gastos, operaciones, períodos, cliente demo,
        compliance/KYC, matches y batches ligados a operaciones demo.
        """
        from app.extensions import db
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine
        from app.models.expense_record import ExpenseRecord
        from app.models.operation import Operation
        from app.models.accounting_period import AccountingPeriod
        from app.models.accounting_batch import AccountingBatch
        from app.models.accounting_match import AccountingMatch
        from app.models.journal_sequence import JournalSequence
        from app.models.client import Client
        from app.models.compliance import (
            ClientRiskProfile, ComplianceAlert, RestrictiveListCheck,
            TransactionMonitoring, ComplianceDocument, ComplianceAudit,
        )
        from sqlalchemy import extract
        import traceback

        DEMO_DNI  = '72345678'
        DEMO_YEAR = 2026
        DEMO_MONTHS = [1, 2, 3]

        try:
            # ── 1. Recopilar IDs de operaciones demo ────────────────────────
            demo_ops = Operation.query.filter(
                Operation.operation_id.like('DEMO-%')
            ).all()
            demo_op_ids = [op.id for op in demo_ops]
            print(f"  · {len(demo_op_ids)} operaciones demo encontradas")

            # ── 2. Compliance ligado a operaciones y cliente demo ───────────
            demo_client = Client.query.filter_by(dni=DEMO_DNI).first()
            demo_client_id = demo_client.id if demo_client else None

            if demo_op_ids:
                tm_del = TransactionMonitoring.query.filter(
                    TransactionMonitoring.operation_id.in_(demo_op_ids)
                ).delete(synchronize_session=False)
                alert_op_del = ComplianceAlert.query.filter(
                    ComplianceAlert.operation_id.in_(demo_op_ids)
                ).delete(synchronize_session=False)
                print(f"  ✓ {tm_del} transaction_monitoring, {alert_op_del} alertas (ops) eliminadas")

            if demo_client_id:
                alert_cl_del = ComplianceAlert.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False)
                rlc_del = RestrictiveListCheck.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False)
                doc_del = ComplianceDocument.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False)
                audit_del = ComplianceAudit.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False) if hasattr(ComplianceAudit, 'client_id') else 0
                profile_del = ClientRiskProfile.query.filter_by(
                    client_id=demo_client_id
                ).delete(synchronize_session=False)
                print(f"  ✓ KYC/compliance del cliente demo: {alert_cl_del} alertas, "
                      f"{rlc_del} listas restrictivas, {doc_del} docs, {profile_del} perfil de riesgo")

            # ── 3. Accounting matches y batches de ops demo ─────────────────
            if demo_op_ids:
                try:
                    match_del = AccountingMatch.query.filter(
                        (AccountingMatch.buy_operation_id.in_(demo_op_ids)) |
                        (AccountingMatch.sell_operation_id.in_(demo_op_ids))
                    ).delete(synchronize_session=False)
                    print(f"  ✓ {match_del} accounting_matches eliminados")
                except Exception:
                    db.session.rollback()
                    print(f"  · accounting_matches no existe — saltando")

                try:
                    batch_ids_used = [
                        r[0] for r in db.session.query(AccountingMatch.batch_id)
                        .filter(AccountingMatch.batch_id.isnot(None)).all()
                    ]
                    orphan_batches = AccountingBatch.query.filter(
                        AccountingBatch.id.notin_(batch_ids_used) if batch_ids_used
                        else AccountingBatch.id.isnot(None)
                    ).all()
                    for b in orphan_batches:
                        db.session.delete(b)
                    print(f"  ✓ {len(orphan_batches)} batches huérfanos eliminados")
                except Exception:
                    db.session.rollback()
                    print(f"  · accounting_batches no existe — saltando")

            # ── 4. Journal entries de las operaciones demo ──────────────────
            if demo_op_ids:
                je_op_ids = [r[0] for r in db.session.query(JournalEntry.id).filter(
                    JournalEntry.source_id.in_(demo_op_ids),
                    JournalEntry.source_type == 'operation',
                ).all()]
                if je_op_ids:
                    JournalEntryLine.query.filter(
                        JournalEntryLine.journal_entry_id.in_(je_op_ids)
                    ).delete(synchronize_session=False)
                    JournalEntry.query.filter(
                        JournalEntry.id.in_(je_op_ids)
                    ).delete(synchronize_session=False)
                    print(f"  ✓ {len(je_op_ids)} asientos de operaciones eliminados")

            # ── 5. Operaciones demo ─────────────────────────────────────────
            op_del = Operation.query.filter(
                Operation.operation_id.like('DEMO-%')
            ).delete(synchronize_session=False)
            print(f"  ✓ {op_del} operaciones demo eliminadas")

            # ── 6. Asientos demo (source_type='demo') + gastos por mes ──────
            for month in DEMO_MONTHS:
                er_del = ExpenseRecord.query.filter(
                    extract('year',  ExpenseRecord.expense_date) == DEMO_YEAR,
                    extract('month', ExpenseRecord.expense_date) == month,
                ).delete(synchronize_session=False)

                je_ids = [r[0] for r in db.session.query(JournalEntry.id).filter(
                    JournalEntry.source_type == 'demo',
                    extract('year',  JournalEntry.entry_date) == DEMO_YEAR,
                    extract('month', JournalEntry.entry_date) == month,
                ).all()]
                if je_ids:
                    JournalEntryLine.query.filter(
                        JournalEntryLine.journal_entry_id.in_(je_ids)
                    ).delete(synchronize_session=False)
                    JournalEntry.query.filter(
                        JournalEntry.id.in_(je_ids)
                    ).delete(synchronize_session=False)

                period = AccountingPeriod.query.filter_by(year=DEMO_YEAR, month=month).first()
                if period:
                    db.session.delete(period)

                names = {1:'Ene', 2:'Feb', 3:'Mar'}
                print(f"  ✓ {names[month]} {DEMO_YEAR}: {er_del} gastos, {len(je_ids)} asientos demo")

            # ── 7. Asiento de apertura demo (si existe) ─────────────────────
            apertura_del = JournalEntry.query.filter(
                JournalEntry.entry_type == 'apertura',
                extract('year', JournalEntry.entry_date) == DEMO_YEAR,
            ).all()
            for ap in apertura_del:
                JournalEntryLine.query.filter_by(
                    journal_entry_id=ap.id
                ).delete(synchronize_session=False)
                db.session.delete(ap)
            if apertura_del:
                print(f"  ✓ {len(apertura_del)} asiento(s) de apertura eliminados")

            # ── 8. Secuencia de numeración 2026 (reset) ─────────────────────
            seq = JournalSequence.query.filter_by(year=DEMO_YEAR).first()
            if seq:
                db.session.delete(seq)
                print(f"  ✓ JournalSequence {DEMO_YEAR} eliminada (se reiniciará desde AS-2026-0001)")

            # ── 9. Cliente demo ─────────────────────────────────────────────
            if demo_client:
                db.session.delete(demo_client)
                print(f"  ✓ Cliente demo DNI {DEMO_DNI} eliminado")

            db.session.commit()
            print(f"\n✓ drop-all-demo completado — base de datos lista para producción")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")
            traceback.print_exc()

    # ── send-test-emails ────────────────────────────────────────────────────
    @app.cli.command("send-test-emails")
    def send_test_emails():
        """Envía un correo de prueba de cada tipo a ggarcia@qoricash.pe para validar plantillas."""
        from app.services.email_templates import EmailTemplates
        from app.services.email_service import EmailService
        from app.extensions import mail
        from flask_mail import Message
        from datetime import datetime

        TEST = 'ggarcia@qoricash.pe'

        class C:
            id = 9999; dni = '12345678'; document_type = 'DNI'; document_number = '12345678'
            email = TEST; phone = '987654321'; full_name = 'Gianpierre Garcia'; razon_social = None
            bank_accounts = [{'bank_name': 'BCP', 'currency': 'PEN', 'account_number': '191-12345678-0-12'}]

        class CRuc:
            id = 9998; dni = '20612345678'; document_type = 'RUC'; document_number = '20612345678'
            email = TEST; phone = '01-4567890'; full_name = None; razon_social = 'DEMO EMPRESA S.A.C.'
            bank_accounts = []

        class T:
            id = 1; username = 'ggarcia'; email = TEST; role = 'Trader'

        class Proof:
            comprobante_url = 'https://www.qoricash.pe'; comentario = 'Transferencia procesada'

        class Inv:
            invoice_number = 'B001-00000123'; nubefact_enlace_pdf = None

        class Op:
            operation_id = 'EXP-TEST-001'; operation_type = 'Compra'
            amount_usd = 5000.00; exchange_rate = 3.4620; amount_pen = 17310.00
            status = 'Pendiente'; notes = 'Operacion de prueba de plantilla'
            operator_proofs = [Proof()]; invoices = [Inv()]
            new_operation_email_sent = False
            user = T(); created_at = datetime(2026, 5, 6, 9, 30)
            completed_at = datetime(2026, 5, 6, 10, 15)
            class client:
                full_name = 'Gianpierre Garcia'; razon_social = None; email = TEST
            client = client()

        def send(subject, html):
            mail.send(Message(subject=subject, recipients=[TEST], html=html))

        results = []

        def try_send(name, fn):
            try:
                fn()
                results.append((name, True))
                print(f"  [OK]  {name}")
            except Exception as e:
                results.append((name, False))
                print(f"  [FAIL]  {name}  — {e}")

        print(f"\n=== Enviando correos de prueba a {TEST} ===\n")

        try_send("Bienvenida Movil",        lambda: EmailTemplates.send_welcome_email_from_mobile(C()))
        try_send("Bienvenida Web",          lambda: EmailTemplates.send_welcome_email_from_web(C()))
        try_send("Activacion + Contrasena", lambda: EmailTemplates.send_activation_with_temp_password(C(), T(), 'Qori2026!'))
        try_send("Activacion Auto",         lambda: EmailTemplates.send_activation_without_password(C()))
        try_send("Nueva Operacion",         lambda: send('Nueva Operacion #EXP-TEST-001 - QoriCash', EmailService._render_new_operation_template(Op())))
        try_send("Operacion Completada",    lambda: send('Operacion Completada #EXP-TEST-001 - QoriCash', EmailService._render_completed_operation_template(Op())))
        try_send("Operacion Cancelada",     lambda: send('Operacion Cancelada - EXP-TEST-001 | QoriCash', EmailService._render_canceled_operation_template(Op(), 'Plazo vencido')))
        try_send("Modificacion de Importe", lambda: send('Actualizacion de Importe - EXP-TEST-001 | QoriCash', EmailService._render_amount_modified_template(Op(), 4800.00, 16627.20)))
        try_send("Nuevo Cliente (Trader)",  lambda: send('Bienvenido a QoriCash - Registro en Proceso', EmailService._render_new_client_template(CRuc(), T())))
        try_send("Cliente Activado",        lambda: send('Cuenta Activada - Bienvenido a QoriCash', EmailService._render_client_activation_template(C(), T())))
        try_send("Contrasena Temporal",     lambda: send('Recuperacion de Contrasena - QoriCash', EmailService._render_temporary_password_template('Gianpierre Garcia', 'Temp#2026')))

        complaint = {
            'complaint_number': 'REC-2026-001', 'tipo_solicitud': 'Reclamo',
            'tipo_documento': 'DNI', 'numero_documento': '12345678',
            'nombres': 'Gianpierre', 'apellidos': 'Garcia',
            'email': TEST, 'telefono': '987654321',
            'direccion': 'Av. Brasil 2790, Pueblo Libre',
            'detalle': 'Correo de prueba del sistema de reclamaciones.',
        }
        try_send("Reclamo", lambda: send('[Reclamo] Libro de Reclamaciones - Gianpierre Garcia', EmailService._render_complaint_template(complaint)))

        ok = sum(1 for _, s in results if s)
        print(f"\n{ok}/{len(results)} correos enviados correctamente\n")

    @app.cli.command("normalize-prospectos")
    def normalize_prospectos():
        """
        Normaliza departamento y tamano_empresa en todos los prospectos.
        Unifica variantes en mayúsculas/minúsculas/sin tilde al nombre canónico.
        Uso: flask normalize-prospectos
        """
        import unicodedata
        from app.extensions import db
        from app.models.prospecto import Prospecto

        # ── Departamentos canónicos del Perú ──────────────────────────────────
        DEPTOS = [
            "Amazonas", "Áncash", "Apurímac", "Arequipa", "Ayacucho",
            "Cajamarca", "Callao", "Cusco", "Huancavelica", "Huánuco",
            "Ica", "Junín", "La Libertad", "Lambayeque", "Lima",
            "Loreto", "Madre de Dios", "Moquegua", "Pasco", "Piura",
            "Puno", "San Martín", "Tacna", "Tumbes", "Ucayali",
        ]

        # ── Tamaños canónicos ─────────────────────────────────────────────────
        TAMANOS = ["MYPE", "Pequeña", "Mediana", "Grande"]

        def _key(s):
            """Clave de comparación: sin tildes, sin espacios extra, minúsculas."""
            s = s.strip()
            s = unicodedata.normalize("NFD", s)
            s = "".join(c for c in s if unicodedata.category(c) != "Mn")
            return s.lower()

        depto_map  = {_key(d): d for d in DEPTOS}
        tamano_map = {_key(t): t for t in TAMANOS}

        # Alias adicionales frecuentes
        depto_map.update({
            "ancash":          "Áncash",
            "apurimac":        "Apurímac",
            "huanuco":         "Huánuco",
            "junin":           "Junín",
            "san martin":      "San Martín",
            "madre de dios":   "Madre de Dios",
            "la libertad":     "La Libertad",
        })
        tamano_map.update({
            "mype":            "MYPE",
            "micro":           "MYPE",
            "microempresa":    "MYPE",
            "pequena empresa": "Pequeña",
            "pequena":         "Pequeña",
            "mediana empresa": "Mediana",
            "grande empresa":  "Grande",
        })

        prospectos = Prospecto.query.all()
        d_updated = d_skipped = t_updated = t_skipped = 0

        for p in prospectos:
            # Departamento
            if p.departamento:
                canonical = depto_map.get(_key(p.departamento))
                if canonical and canonical != p.departamento:
                    p.departamento = canonical
                    d_updated += 1
                else:
                    d_skipped += 1

            # Tamaño empresa
            if p.tamano_empresa:
                canonical = tamano_map.get(_key(p.tamano_empresa))
                if canonical and canonical != p.tamano_empresa:
                    p.tamano_empresa = canonical
                    t_updated += 1
                else:
                    t_skipped += 1

        try:
            db.session.commit()
            print(f"✓ Departamentos: {d_updated} normalizados, {d_skipped} ya correctos")
            print(f"✓ Tamaños:       {t_updated} normalizados, {t_skipped} ya correctos")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error: {e}")

    # ── fix-movimientos-banco ─────────────────────────────────────────────────
    @app.cli.command("fix-movimientos-banco")
    @click.option('--ops', default='EXP-526,EXP-528',
                  help='Códigos de operación separados por coma.')
    @click.option('--de', 'banco_origen', default='BCP',
                  help='Banco incorrecto registrado (origen).')
    @click.option('--a', 'banco_destino', default='INTERBANK',
                  help='Banco correcto real (destino).')
    @click.option('--apply', is_flag=True, default=False,
                  help='Sin este flag corre en dry-run (solo muestra cambios).')
    def fix_movimientos_banco(ops, banco_origen, banco_destino, apply):
        """
        Corrige el banco de BankMovements de operaciones ya completadas.

        Dry-run por defecto. Para aplicar: flask fix-movimientos-banco --apply

        Ejemplo:
          flask fix-movimientos-banco --ops EXP-526,EXP-528 --de BCP --a INTERBANK --apply
        """
        from app.models import Operation
        from app.models.bank_movement import BankMovement
        from app.models.bank_balance  import BankBalance
        from app.config.bank_accounts import QORICASH_ACCOUNTS

        # Construir mapa de nombres de cuenta: { 'BCP': { 'USD': 'BCP USD (...)', 'PEN': '...' } }
        acct_names = {}
        for banco, monedas in QORICASH_ACCOUNTS.items():
            acct_names[banco] = {}
            for moneda, data in monedas.items():
                acct_names[banco][moneda] = f"{banco} {moneda} ({data['numero']})"

        target_ops = [o.strip() for o in ops.split(',') if o.strip()]
        print(f"\n{'[DRY-RUN] ' if not apply else '[APPLY] '}Corrigiendo movimientos: {target_ops}")
        print(f"  Banco incorrecto : {banco_origen}")
        print(f"  Banco correcto   : {banco_destino}\n")

        operations = Operation.query.filter(
            Operation.operation_id.in_(target_ops)
        ).all()

        if not operations:
            print("ERROR: No se encontraron las operaciones indicadas.")
            return

        total_movs = 0
        for op in operations:
            print(f"── {op.operation_id} (id={op.id}, tipo={op.operation_type}, estado={op.status})")
            movs = BankMovement.query.filter(
                BankMovement.operation_id == op.id,
                BankMovement.bank_key == banco_origen,
            ).all()

            if not movs:
                print(f"   Sin BankMovements con bank_key={banco_origen}\n")
                continue

            for mv in movs:
                amt   = float(mv.amount)
                cur   = mv.currency
                old_acct = acct_names.get(banco_origen, {}).get(cur)
                new_acct = acct_names.get(banco_destino, {}).get(cur)
                print(f"   MOV id={mv.id}  {cur}  {mv.movement_type}  amt={amt:+.2f}")
                print(f"     bank_name: {mv.bank_name} → {new_acct}")

                if not old_acct or not new_acct:
                    print(f"     ⚠ Cuenta no encontrada para {banco_origen}/{banco_destino} {cur}")
                    continue

                # BankBalance: revertir en origen y aplicar en destino
                bb_orig = BankBalance.query.filter_by(bank_name=old_acct).first()
                bb_dest = BankBalance.query.filter_by(bank_name=new_acct).first()

                if bb_orig:
                    old_bal = float(bb_orig.balance_usd if cur == 'USD' else bb_orig.balance_pen)
                    new_bal = round(old_bal - amt, 2)
                    print(f"     BankBalance {old_acct}: {old_bal:+.2f} → {new_bal:+.2f}")
                else:
                    print(f"     ⚠ Sin BankBalance para {old_acct}")

                if bb_dest:
                    old_bal2 = float(bb_dest.balance_usd if cur == 'USD' else bb_dest.balance_pen)
                    new_bal2 = round(old_bal2 + amt, 2)
                    print(f"     BankBalance {new_acct}: {old_bal2:+.2f} → {new_bal2:+.2f}")
                else:
                    print(f"     ⚠ Sin BankBalance para {new_acct}")

                if apply:
                    mv.bank_key  = banco_destino
                    mv.bank_name = new_acct

                total_movs += 1
            print()

        print(f"Total BankMovements a corregir: {total_movs}")

        if not apply:
            print("\n→ Para aplicar: flask fix-movimientos-banco --apply")
            return

        # ── Paso 1: guardar cambios en BankMovement ───────────────────────────
        from sqlalchemy.orm import Session
        try:
            with db.session.no_autoflush:
                db.session.flush()
            db.session.commit()
            print("✓ BankMovements corregidos.")
        except Exception as exc:
            db.session.rollback()
            print(f"✗ Error en BankMovements: {exc}")
            return

        # ── Paso 2: recalcular BankBalance via SQL raw ────────────────────────
        # Usamos DDL para deshabilitar temporalmente el CHECK de balance positivo,
        # ya que el INTERBANK USD puede quedar negativo (refleja la deuda real
        # del sistema: esos USD salieron físicamente de INTERBANK pero nunca
        # fueron descontados de su BankBalance).
        from sqlalchemy import text

        # Reconstruir deltas netos por cuenta
        deltas = {}   # { acct_name: { 'col': 'balance_usd'|'balance_pen', 'delta': float } }
        for op in operations:
            movs_fixed = BankMovement.query.filter(
                BankMovement.operation_id == op.id,
                BankMovement.bank_key == banco_destino,
            ).all()
            for mv in movs_fixed:
                amt = float(mv.amount)
                cur = mv.currency
                old_acct = acct_names.get(banco_origen,  {}).get(cur)
                new_acct = acct_names.get(banco_destino, {}).get(cur)
                col = 'balance_usd' if cur == 'USD' else 'balance_pen'
                if old_acct:
                    deltas.setdefault(old_acct, {'col': col, 'delta': 0.0})['delta'] = round(
                        deltas[old_acct]['delta'] - amt, 2)
                if new_acct:
                    deltas.setdefault(new_acct, {'col': col, 'delta': 0.0})['delta'] = round(
                        deltas[new_acct]['delta'] + amt, 2)

        try:
            with db.engine.connect() as conn:
                # Deshabilitar constraint temporalmente
                conn.execute(text(
                    "ALTER TABLE bank_balances DROP CONSTRAINT IF EXISTS check_balance_usd_positive"
                ))
                conn.execute(text(
                    "ALTER TABLE bank_balances DROP CONSTRAINT IF EXISTS check_balance_pen_positive"
                ))

                for acct_name, info in deltas.items():
                    col   = info['col']
                    delta = info['delta']
                    if delta == 0:
                        continue
                    result = conn.execute(
                        text(f"UPDATE bank_balances SET {col} = {col} + :delta, "
                             f"updated_at = now() WHERE bank_name = :name RETURNING {col}"),
                        {'delta': delta, 'name': acct_name}
                    ).fetchone()
                    new_val = result[0] if result else '(no row)'
                    print(f"   BankBalance {acct_name}.{col}: {'+' if delta >= 0 else ''}{delta:.2f} → {new_val}")

                # Restaurar constraints (NOT VALID evita re-validar filas existentes)
                conn.execute(text(
                    "ALTER TABLE bank_balances ADD CONSTRAINT check_balance_usd_positive "
                    "CHECK (balance_usd >= -99999999) NOT VALID"
                ))
                conn.execute(text(
                    "ALTER TABLE bank_balances ADD CONSTRAINT check_balance_pen_positive "
                    "CHECK (balance_pen >= -99999999) NOT VALID"
                ))
                conn.commit()
            print("✓ BankBalance ajustados correctamente.")
            print("\n⚠ Nota: si INTERBANK USD quedó negativo, significa que el sistema")
            print("  no tenía registradas entradas previas de esa cuenta. Usa 'Apertura'")
            print("  en Control de Finanzas para registrar el saldo real actual de INTERBANK.")
        except Exception as exc:
            print(f"✗ Error al ajustar BankBalance: {exc}")
            print("  Los BankMovements ya están corregidos. Solo BankBalance requiere ajuste manual.")

    # ── analizar-utilidad-trader ──────────────────────────────────────────────
    @app.cli.command("analizar-utilidad-trader")
    @click.option('--username', default='gian', help='Parte del username a buscar.')
    @click.option('--mes', default=None, help='Mes en formato YYYY-MM (default: mes actual).')
    def analizar_utilidad_trader(username, mes):
        """
        Analiza las operaciones del mes de un trader y muestra el detalle
        de margen por operación para identificar por qué la utilidad es incorrecta.

        Ejemplo:
          flask analizar-utilidad-trader --username gian --mes 2026-06
        """
        from app.models.user import User
        from app.models.operation import Operation
        from app.models.client import Client
        from sqlalchemy import or_, and_
        from decimal import Decimal
        from datetime import datetime

        user = User.query.filter(User.username.ilike(f'%{username}%')).first()
        if not user:
            print(f"✗ Usuario con username '%{username}%' no encontrado.")
            return
        print(f"Usuario: {user.username} | ID: {user.id} | Rol: {user.role}")

        if mes:
            y, m = int(mes.split('-')[0]), int(mes.split('-')[1])
        else:
            now = datetime.now()
            y, m = now.year, now.month
        start = datetime(y, m, 1)
        end   = datetime(y, m+1, 1) if m < 12 else datetime(y+1, 1, 1)
        print(f"Período: {start.date()} → {end.date()}\n")

        ops = Operation.query.join(Client, Operation.client_id == Client.id).filter(
            or_(Operation.user_id == user.id, and_(Operation.user_id == None, Client.created_by == user.id)),
            Operation.status == 'Completada',
            Operation.base_rate.isnot(None),
            Operation.base_rate > 0,
            Operation.created_at >= start,
            Operation.created_at < end,
        ).order_by(Operation.created_at).all()

        print(f"Operaciones completadas con base_rate: {len(ops)}\n")
        print(f"{'Fecha':<14} {'ID':<10} {'Tipo':<8} {'USD':>10} {'TC':>8} {'Base':>8} {'Margen PEN':>12}")
        print("-" * 75)

        total = Decimal('0')
        negativas = 0
        for op in ops:
            tc   = Decimal(str(op.exchange_rate))
            base = Decimal(str(op.base_rate))
            usd  = Decimal(str(op.amount_usd))
            m_val = (base - tc) * usd if op.operation_type == 'Compra' else (tc - base) * usd
            total += m_val
            flag = ' <<<' if m_val < -50 else ''
            if m_val < -50:
                negativas += 1
            print(f"{op.created_at.strftime('%d/%m %H:%M'):<14} {op.operation_id or str(op.id):<10} {op.operation_type:<8} {float(usd):>10,.0f} {float(tc):>8.4f} {float(base):>8.4f} {float(m_val):>12,.2f}{flag}")

        print("-" * 75)
        print(f"{'TOTAL':>58} {float(total):>12,.2f}")
        print(f"\nOperaciones con margen negativo significativo (< -50): {negativas}")
        print(f"Utilidad total del mes (TC vs Base): S/ {float(total):,.2f}")

        # ── Cálculo alternativo desde amarres ─────────────────────────────────
        print("\n" + "=" * 75)
        print("UTILIDAD DESDE AMARRES (fuente real)")
        print("=" * 75)
        from app.models.accounting_match import AccountingMatch
        from sqlalchemy import or_, and_
        buy_op  = db.aliased(Operation, name='buy_op_a')
        sell_op = db.aliased(Operation, name='sell_op_a')
        Client2 = __import__('app.models.client', fromlist=['Client']).Client

        buy_matches = db.session.query(
            AccountingMatch.id,
            AccountingMatch.buy_operation_id,
            AccountingMatch.sell_operation_id,
            AccountingMatch.matched_amount_usd,
            AccountingMatch.trader_buy_profit_pen,
            AccountingMatch.trader_sell_profit_pen,
            AccountingMatch.profit_pen,
            AccountingMatch.created_at,
        ).join(buy_op, AccountingMatch.buy_operation_id == buy_op.id)\
         .join(Client2, buy_op.client_id == Client2.id)\
         .filter(
            or_(buy_op.user_id == user.id, and_(buy_op.user_id == None, Client2.created_by == user.id)),
            AccountingMatch.status == 'Activo',
            buy_op.created_at >= start,
            buy_op.created_at < end,
        ).all()

        sell_matches = db.session.query(
            AccountingMatch.id,
            AccountingMatch.buy_operation_id,
            AccountingMatch.sell_operation_id,
            AccountingMatch.matched_amount_usd,
            AccountingMatch.trader_buy_profit_pen,
            AccountingMatch.trader_sell_profit_pen,
            AccountingMatch.profit_pen,
            AccountingMatch.created_at,
        ).join(sell_op, AccountingMatch.sell_operation_id == sell_op.id)\
         .join(Client2, sell_op.client_id == Client2.id)\
         .filter(
            or_(sell_op.user_id == user.id, and_(sell_op.user_id == None, Client2.created_by == user.id)),
            AccountingMatch.status == 'Activo',
            sell_op.created_at >= start,
            sell_op.created_at < end,
        ).all()

        seen_ids = set()
        all_matches = []
        for row in buy_matches + sell_matches:
            if row.id not in seen_ids:
                seen_ids.add(row.id)
                all_matches.append(row)
        all_matches.sort(key=lambda r: r.created_at)

        print(f"Amarres relacionados al trader este mes: {len(all_matches)}\n")
        print(f"{'Fecha Amarre':<14} {'Buy Op':<10} {'Sell Op':<10} {'USD':>10} {'T.Buy PEN':>12} {'T.Sell PEN':>12} {'Total PEN':>12}")
        print("-" * 85)

        total_buy  = Decimal('0')
        total_sell = Decimal('0')
        total_amar = Decimal('0')
        for r in all_matches:
            tb = Decimal(str(r.trader_buy_profit_pen or 0))
            ts = Decimal(str(r.trader_sell_profit_pen or 0))
            tp = tb + ts
            total_buy  += tb
            total_sell += ts
            total_amar += tp
            print(f"{r.created_at.strftime('%d/%m %H:%M'):<14} {str(r.buy_operation_id):<10} {str(r.sell_operation_id):<10} {float(r.matched_amount_usd or 0):>10,.0f} {float(tb):>12,.2f} {float(ts):>12,.2f} {float(tp):>12,.2f}")

        print("-" * 85)
        print(f"{'TOTAL':>44} {float(total_buy):>12,.2f} {float(total_sell):>12,.2f} {float(total_amar):>12,.2f}")
        print(f"\n✓ Utilidad real del mes desde amarres: S/ {float(total_amar):,.2f}")

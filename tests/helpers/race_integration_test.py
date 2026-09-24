#!/usr/bin/env python3
"""
Subprocess helper: integración real del race condition scheduler ↔ webhook.

Llama OperationExpiryService.expire_inactive_bot_sessions() con:
  - Flask app context real + PostgreSQL
  - requests.post mockeado (simula envíos WA sin llamadas reales)

Funciones de producción ejercitadas:
  - OperationExpiryService.expire_inactive_bot_sessions() — scheduler real
  - WaBotSession.query con with_for_update() — lock real en PostgreSQL
  - updated_at como campo gobernante de expiración (onupdate=now_peru)

Escenario 1 — actividad reciente (webhook actualiza updated_at primero):
  updated_at = NOW() → scheduler ve cutoff superado → NO expira.
  session_started_at sin cambio → guardia _respuesta_ia: no drift → enviaría respuesta.

Escenario 2 — inactividad (scheduler corre con updated_at viejo):
  updated_at = NOW() - 20 min → scheduler expira sesión.
  session_started_at cambia (T_A → T_B) → guardia _respuesta_ia detecta drift → descarta IA tardía.

Escenario 3 — carrera coordinada (scheduler↔webhook simultáneos):
  Scheduler identifica sesión stale → justo antes del SELECT FOR UPDATE,
  el webhook actualiza updated_at en una conexión independiente y confirma.
  Scheduler revalida bajo lock, ve actividad reciente → NO expira.
  Coordinación con threading.Event (sin sleeps arbitrarios).

Uso:
    python3 race_integration_test.py <db_url>
"""
import sys, os, json
from datetime import timedelta
from unittest.mock import MagicMock

DB_URL = sys.argv[1] if len(sys.argv) > 1 else 'postgresql://gianpierre@localhost/qoricash_test'

os.environ['DATABASE_URL']             = DB_URL
os.environ.setdefault('SECRET_KEY',          'test-race-int')
os.environ.setdefault('WTF_CSRF_SECRET_KEY', 'test-race-csrf')
os.environ.setdefault('ANTHROPIC_API_KEY',   '')
os.environ.setdefault('CLOUDINARY_URL',      '')
os.environ.setdefault('TWILIO_ACCOUNT_SID',  '')
os.environ.setdefault('TWILIO_AUTH_TOKEN',   '')
os.environ.setdefault('TWILIO_PHONE_NUMBER', '')

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, '..', '..'))

# Pre-mock cloudinary (evita crash eventlet/kqueue en macOS)
from unittest.mock import MagicMock as _MM
for _m in ('cloudinary', 'cloudinary.uploader', 'cloudinary.api',
           'cloudinary.exceptions', 'cloudinary.utils'):
    sys.modules.setdefault(_m, _MM())

PHONE1 = '51000000001_race'
PHONE2 = '51000000002_race'
PHONE3 = '51000000003_race'

try:
    from app import create_app
    from app.extensions import db

    # 'development' lee DATABASE_URL del env (ya seteado a DB_URL arriba).
    # 'testing' usaría TestingConfig que fuerza sqlite:///:memory:, lo que
    # impediría que el hilo psycopg2 del escenario 3 comparta la misma BD.
    app = create_app('development')
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
    app.config['WTF_CSRF_ENABLED']        = False
    app.config['TESTING']                 = True
    app.config['RATELIMIT_ENABLED']       = False

    # Matar los greenlets del scheduler de fondo para que no interfieran con
    # los escenarios de prueba. eventlet.monkey_patch() (en app/__init__.py)
    # convierte threading en greenlets cooperativos; si el scheduler corre
    # durante un _webhook_done.wait(), puede expirar sesiones de prueba.
    import app as _app_module
    if getattr(_app_module, '_scheduler_greenlet', None) is not None:
        try:
            _app_module._scheduler_greenlet.kill()
        except Exception:
            pass
        _app_module._scheduler_greenlet = True  # truthy → start_* no vuelve a spawnar

    with app.app_context():
        db.create_all()  # crea tablas nuevas; no modifica las existentes

        # El schema de qoricash_test puede ser antiguo (migrado manualmente en P4f).
        # Añadimos las columnas que el modelo actual necesita pero que pueden faltar.
        from sqlalchemy import text
        _schema_upgrades = [
            # wa_bot_sessions: columnas del modelo WaBotSession que pueden faltar
            # Columna legada 'phone' (NOT NULL): relajar para permitir inserts del ORM
            # que solo escribe en 'numero'. Si la columna no existe el ALTER es no-op.
            "ALTER TABLE wa_bot_sessions ALTER COLUMN phone DROP NOT NULL",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS numero VARCHAR(25)",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS estado VARCHAR(50) NOT NULL DEFAULT 'inicio'",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS bot_pausado BOOLEAN DEFAULT FALSE",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS nombre VARCHAR(120) DEFAULT ''",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) DEFAULT ''",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS dni_front VARCHAR(120) DEFAULT ''",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS dni_back VARCHAR(120) DEFAULT ''",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS ruc_doc VARCHAR(120) DEFAULT ''",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_timestamp TIMESTAMP",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_token VARCHAR(36)",
            "ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_intentos INTEGER DEFAULT 0",
            # wa_messages: columnas del modelo WaMessage que pueden faltar en el schema de prueba
            "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS numero VARCHAR(25)",
            "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS nombre VARCHAR(120) DEFAULT ''",
            "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS empresa VARCHAR(200) DEFAULT ''",
            "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS mensaje TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS direccion VARCHAR(10)",
            "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS wa_id VARCHAR(120) DEFAULT ''",
            "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS leido BOOLEAN DEFAULT FALSE",
            "ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS tipo VARCHAR(20)",
        ]
        for _ddl in _schema_upgrades:
            try:
                db.session.execute(text(_ddl))
            except Exception:
                db.session.rollback()
        # Índice único en numero (requerido por WaBotSession.get_or_create)
        try:
            db.session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_wbs_numero "
                "ON wa_bot_sessions(numero)"
            ))
        except Exception:
            db.session.rollback()
        db.session.commit()

        from app.models.wa_bot_session import WaBotSession
        from app.services.operation_expiry_service import OperationExpiryService
        import app.services.operation_expiry_service as _expiry_mod
        from app.utils.formatters import now_peru

        # Mock requests.post en operation_expiry_service para capturar envíos WA
        wa_sent = []
        _real_req = _expiry_mod.requests
        mock_req  = MagicMock()
        mock_req.post.side_effect = (
            lambda *a, **kw: wa_sent.append(kw.get('json', {})) or MagicMock(status_code=200)
        )
        _expiry_mod.requests = mock_req

        # now_peru() es el mismo reloj que usa expire_inactive_bot_sessions();
        # usar utcnow() generaría timestamps 5 h posteriores al cutoff Peru → no expiraría.
        now_local = now_peru()
        stale     = now_local - timedelta(minutes=20)

        try:
            # Limpiar sesiones de prueba anteriores
            db.session.execute(
                text("DELETE FROM wa_bot_sessions WHERE numero IN (:p1, :p2, :p3)"),
                {'p1': PHONE1, 'p2': PHONE2, 'p3': PHONE3}
            )
            db.session.commit()

            # ── Escenario 1: webhook actualizó updated_at → actividad reciente ─
            # Simula: el webhook recibió un mensaje del cliente y actualizó
            # updated_at ANTES de que el scheduler corriera. El scheduler debe
            # ver updated_at >= cutoff y NO expirar la sesión.
            s1 = WaBotSession(numero=PHONE1, estado='conversando')
            db.session.add(s1)
            db.session.flush()
            # Forzar updated_at via SQL para evitar que onupdate lo sobreescriba
            db.session.execute(text(
                "UPDATE wa_bot_sessions "
                "SET session_started_at = :ssa, updated_at = :ua "
                "WHERE numero = :n"
            ), {'ssa': stale, 'ua': now_local, 'n': PHONE1})
            db.session.commit()

            ssa_before_s1 = (
                WaBotSession.query.filter_by(numero=PHONE1).first().session_started_at
            )
            count_s1 = OperationExpiryService.expire_inactive_bot_sessions()

            s1_after = WaBotSession.query.filter_by(numero=PHONE1).first()
            s1_not_expired = (
                s1_after.estado == 'conversando'
                and s1_after.session_started_at == ssa_before_s1
            )

            # ── Escenario 2: updated_at viejo → inactividad → scheduler expira ─
            # Simula: el webhook está procesando IA. El scheduler corre antes de
            # que IA termine. session_started_at cambia → guardia detecta drift.
            wa_sent.clear()
            s2 = WaBotSession(numero=PHONE2, estado='conversando')
            db.session.add(s2)
            db.session.flush()
            # updated_at = 20 min atrás (> umbral 15 min) → debe expirar
            db.session.execute(text(
                "UPDATE wa_bot_sessions "
                "SET session_started_at = :ssa, updated_at = :ua "
                "WHERE numero = :n"
            ), {'ssa': stale, 'ua': stale, 'n': PHONE2})
            db.session.commit()

            # Guardia _respuesta_ia: leer session_started_at ANTES de que IA termine
            ssa_before_s2 = (
                WaBotSession.query.filter_by(numero=PHONE2).first().session_started_at
            )

            count_s2 = OperationExpiryService.expire_inactive_bot_sessions()

            s2_after      = WaBotSession.query.filter_by(numero=PHONE2).first()
            ssa_after_s2  = s2_after.session_started_at
            # Drift: session_started_at cambió (T_A viejo → T_B nuevo por scheduler)
            drift_s2   = (ssa_after_s2 != ssa_before_s2)
            s2_expired = (s2_after.estado == 'inicio' and drift_s2)
            # Mensaje WA enviado al número
            wa_notified = any(
                PHONE2.lstrip('+') in str(m.get('to', ''))
                for m in wa_sent
            )

            # ── Escenario 3: carrera coordinada scheduler ↔ webhook ─────────
            # El scheduler identifica PHONE3 como candidata (updated_at stale).
            # Antes de que ejecute SELECT FOR UPDATE, el webhook (conexión
            # psycopg2 independiente) actualiza updated_at = NOW() y confirma.
            # El scheduler lee el row bajo lock y ve actividad reciente → no expira.
            import psycopg2 as _psycopg2
            from sqlalchemy import event as _sa_event

            wa_sent.clear()
            s3 = WaBotSession(numero=PHONE3, estado='conversando')
            db.session.add(s3)
            db.session.flush()
            db.session.execute(text(
                "UPDATE wa_bot_sessions "
                "SET session_started_at = :ssa, updated_at = :ua "
                "WHERE numero = :n"
            ), {'ssa': stale, 'ua': stale, 'n': PHONE3})
            db.session.commit()

            # Diseño del intercept: el "webhook" corre síncronamente DENTRO del
            # handler before_cursor_execute, antes de que el SELECT FOR UPDATE llegue
            # a PostgreSQL. No se usa threading.Event ni wait() para evitar que el
            # hub de eventlet (activado por monkey_patch en app/__init__.py) ceda a
            # otros greenlets durante una espera — lo que podría hacer que el scheduler
            # de fondo (si no estuviera matado) expirara PHONE3 y contaminara el resultado.
            _s3_handled  = [False]   # one-shot flag
            _s3_wb_error = []        # captura errores del "webhook" inline

            def _before_cursor_s3(conn, cursor, statement, parameters, context, executemany):
                """Antes del SELECT FOR UPDATE: actualizar updated_at en conexión independiente."""
                if 'FOR UPDATE' not in statement.upper():
                    return
                if _s3_handled[0]:
                    return
                _s3_handled[0] = True
                # Simula el webhook confirmando actividad antes de que el lock se adquiera.
                # La I/O de psycopg2 puede ceder al hub eventlet, pero no hay otros
                # greenlets activos que expiren PHONE3 (scheduler fue matado arriba).
                try:
                    _c3 = _psycopg2.connect(DB_URL)
                    _c3.autocommit = True
                    _cur3 = _c3.cursor()
                    _cur3.execute(
                        "UPDATE wa_bot_sessions SET updated_at = NOW() WHERE numero = %s",
                        (PHONE3,)
                    )
                    _c3.close()
                except Exception as _we3:
                    _s3_wb_error.append(str(_we3))

            _sa_event.listen(db.engine, 'before_cursor_execute', _before_cursor_s3)

            count_s3 = OperationExpiryService.expire_inactive_bot_sessions()

            # Remover listener fuera del handler (evita "deque mutated during iteration")
            try:
                _sa_event.remove(db.engine, 'before_cursor_execute', _before_cursor_s3)
            except Exception:
                pass

            s3_after = WaBotSession.query.filter_by(numero=PHONE3).first()
            s3_not_expired = (s3_after is not None and s3_after.estado == 'conversando')
            s3_no_wa = not any(
                PHONE3.lstrip('+') in str(m.get('to', ''))
                for m in wa_sent
            )
            s3_webhook_ok = (len(_s3_wb_error) == 0)

        finally:
            _expiry_mod.requests = _real_req
            db.session.execute(
                text("DELETE FROM wa_bot_sessions WHERE numero IN (:p1, :p2, :p3)"),
                {'p1': PHONE1, 'p2': PHONE2, 'p3': PHONE3}
            )
            db.session.commit()

    print(json.dumps({
        'ok':                    s1_not_expired and s2_expired and s3_not_expired and s3_no_wa,
        'scenario1_not_expired': s1_not_expired,
        'scenario1_count':       count_s1,
        'scenario2_expired':     s2_expired,
        'scenario2_drift':       drift_s2,
        'scenario2_wa_notified': wa_notified,
        'scenario2_count':       count_s2,
        'scenario3_not_expired':   s3_not_expired,
        'scenario3_no_wa':         s3_no_wa,
        'scenario3_webhook_ok':    s3_webhook_ok,
        'scenario3_count':         count_s3,
        'scenario3_handler_fired': _s3_handled[0],
    }))

except Exception as exc:
    import traceback
    print(json.dumps({'ok': False, 'error': str(exc), 'trace': traceback.format_exc()}))
    sys.exit(1)

"""
Pruebas de integración para el hotfix de notificaciones — SQLite real.

Sin SMTP real, sin WA real, sin acceso a Render.

T4_real  Ciclo completo de sesión del chatbot:
         - crea operación con relación client en DB real
         - commit → session.remove() (simula teardown del request)
         - confirma que acceder a op.client en objeto expirado-desvinculado
           falla con DetachedInstanceError
         - ejecuta el closure corregido (_send_new_op_email):
           abre su propio app_context, consulta por operation_id string,
           accede a client.email en el objeto fresco — sin error de sesión

T_flag   El UPDATE de new_operation_email_sent queda committed y visible
         desde una conexión raw independiente (no el mismo ORM session).

LIMITACIONES CONOCIDAS:
- concurrencia: la verificación de idempotencia en memoria no es atómica
  frente a dos greenlets que pasen el check antes de que el primer UPDATE
  se confirme — no corregido en este hotfix
- pérdida de tareas: spawn_n no es cola persistente; si el proceso cae
  entre el spawn y mail.send(), el email se pierde sin recovery automático
"""

import os
import sys
import tempfile
import unittest

# ── Ruta al proyecto ──────────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy.orm.exc import DetachedInstanceError

# ── Base de datos temporal en archivo (necesaria para multi-conexión) ─────────
_db_fd, _DB_FILE = tempfile.mkstemp(suffix='_notif_test.db')
os.close(_db_fd)
_DB_URI = f'sqlite:///{_DB_FILE}'

# ── Flask app de integración (independiente del app principal) ────────────────
int_app = Flask('notif_integration')
int_app.config.update(
    TESTING=True,
    SECRET_KEY='test-integration',
    SQLALCHEMY_DATABASE_URI=_DB_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
int_db = SQLAlchemy(int_app)


# ── Modelos mínimos que replican las columnas relevantes ─────────────────────

class TClient(int_db.Model):
    __tablename__ = 'ti_clients'
    id    = int_db.Column(int_db.Integer, primary_key=True)
    email = int_db.Column(int_db.String(200))


class TOperation(int_db.Model):
    __tablename__ = 'ti_operations'
    id                      = int_db.Column(int_db.Integer, primary_key=True)
    operation_id            = int_db.Column(int_db.String(50), unique=True, nullable=False)
    new_operation_email_sent = int_db.Column(int_db.Boolean, default=False, nullable=False)
    client_id               = int_db.Column(int_db.Integer, int_db.ForeignKey('ti_clients.id'))
    client                  = int_db.relationship('TClient', lazy='select')


with int_app.app_context():
    int_db.create_all()


# ─────────────────────────────────────────────────────────────────────────────
class TestIntegration(unittest.TestCase):

    def setUp(self):
        with int_app.app_context():
            int_db.session.execute(sa.text('DELETE FROM ti_operations'))
            int_db.session.execute(sa.text('DELETE FROM ti_clients'))
            int_db.session.commit()

    def tearDown(self):
        # Limpiar sesión entre tests
        try:
            int_db.session.remove()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # T4_real: ciclo de sesión del chatbot con DB real
    # ──────────────────────────────────────────────────────────────────────────
    def test_T4_real_chatbot_session_lifecycle(self):
        """
        Replica el ciclo completo de _crear_op_y_confirmar:
        1. Crea operación + cliente en la sesión del request
        2. Commit (expire_on_commit expira todos los atributos)
        3. Captura op.operation_id — fuerza carga de columnas escalares
           pero NO carga la relación op.client
        4. session.remove() — objeto queda detached, client sin cargar
        5. Confirma DetachedInstanceError al acceder op.client (bug original)
        6. Ejecuta el closure corregido con su propio app_context:
           re-consulta por string ID → fresh.client.email accesible → OK
        """
        # ── 1-3. Ciclo del request ────────────────────────────────────────────
        with int_app.app_context():
            cli = TClient(email='cliente@empresa.com')
            int_db.session.add(cli)
            int_db.session.flush()

            op = TOperation(
                operation_id='OP-INT-T4',
                new_operation_email_sent=False,
                client_id=cli.id,
            )
            int_db.session.add(op)
            int_db.session.commit()  # expire_on_commit=True → atributos expirados

            # El código de producción accede op.operation_id DESPUÉS del commit
            # (línea _op_id_for_email = op.operation_id en wa_bot.py):
            # esto carga las columnas escalares pero NO la relación client.
            _op_id_for_email = op.operation_id  # fuerza reload de columnas

            # Teardown del request
            int_db.session.remove()  # op queda detached

        # ── 4. Confirmar que el objeto está desvinculado ──────────────────────
        insp = sa.inspect(op)
        self.assertTrue(insp.detached,
                        'El objeto no está detached — test no válido')

        # ── 5. Reproducir el bug pre-fix ──────────────────────────────────────
        # op.operation_id ya está en memoria (cargado antes del remove)
        # op.client NO está en memoria → lazy-load falla sin sesión
        detached_confirmed = False
        try:
            _ = op.client  # relationship access → DetachedInstanceError
        except DetachedInstanceError:
            detached_confirmed = True
        except Exception as e:
            self.fail(f'Esperaba DetachedInstanceError, got {type(e).__name__}: {e}')

        self.assertTrue(
            detached_confirmed,
            'DetachedInstanceError no reproducido — test no cubre el bug real'
        )

        # ── 6. Ejecutar el closure corregido ──────────────────────────────────
        # Replica exactamente _send_new_op_email de wa_bot.py (versión corregida):
        # - Abre su propio app_context
        # - Consulta por string ID (no usa el objeto expirado)
        # - Accede a fresh.client.email en la nueva sesión

        reached_send = {'ok': False, 'error': None, 'client_email': None}

        def _send_new_op_email():
            """Closure corregido — replica el código de wa_bot.py."""
            with int_app.app_context():
                try:
                    fresh = TOperation.query.filter_by(
                        operation_id=_op_id_for_email
                    ).first()
                    if fresh is None:
                        reached_send['error'] = 'Operación no encontrada'
                        return
                    # Acceso completo — columnas Y relaciones
                    _ = fresh.new_operation_email_sent
                    reached_send['client_email'] = fresh.client.email  # relationship OK
                    # [aquí iría EmailService.send_new_operation_email(fresh)]
                    reached_send['ok'] = True
                except Exception as e:
                    reached_send['error'] = f'{type(e).__name__}: {e}'

        _send_new_op_email()  # en tests spawn_n es síncrono

        self.assertTrue(
            reached_send['ok'],
            f"Greenlet no llegó al envío: {reached_send['error']}"
        )
        self.assertEqual(
            reached_send['client_email'], 'cliente@empresa.com',
            f'client.email incorrecto: {reached_send["client_email"]}'
        )
        print(
            f'  T4_real PASS: DetachedInstanceError reproducido; '
            f're-query OK; client.email={reached_send["client_email"]}'
        )

    # ──────────────────────────────────────────────────────────────────────────
    # T_flag: UPDATE committed, visible desde conexión raw independiente
    # ──────────────────────────────────────────────────────────────────────────
    def test_T_flag_persist_visible_from_new_connection(self):
        """
        El UPDATE ejecutado en _send() queda persistido:
        - rowcount = 1 (UPDATE afectó la fila)
        - consulta desde engine.connect() (conexión independiente del ORM)
          devuelve new_operation_email_sent=True
        Esto descarta que solo sea visible en caché del mismo session.
        """
        # ── Crear operación con flag=False ────────────────────────────────────
        with int_app.app_context():
            op = TOperation(
                operation_id='OP-INT-FLAG',
                new_operation_email_sent=False,
            )
            int_db.session.add(op)
            int_db.session.commit()

        # ── Ejecutar el UPDATE exacto de _send() en email_service.py ─────────
        with int_app.app_context():
            result = int_db.session.execute(
                sa.text(
                    'UPDATE ti_operations SET new_operation_email_sent=1 '
                    'WHERE operation_id=:oid'
                ),
                {'oid': 'OP-INT-FLAG'}
            )
            int_db.session.commit()
            rowcount = result.rowcount

        # ── Verificar con conexión raw completamente independiente ────────────
        # Abrimos el motor directamente al archivo SQLite, sin pasar por el
        # ORM session del Flask app (demuestra que el valor fue realmente committed).
        raw_engine = sa.create_engine(_DB_URI, connect_args={'check_same_thread': False})
        with raw_engine.connect() as raw_conn:
            row = raw_conn.execute(
                sa.text(
                    'SELECT new_operation_email_sent FROM ti_operations '
                    'WHERE operation_id=:oid'
                ),
                {'oid': 'OP-INT-FLAG'}
            ).fetchone()
        raw_engine.dispose()

        self.assertEqual(rowcount, 1,
                         f'UPDATE afectó {rowcount} filas, esperaba 1')
        self.assertIsNotNone(row,
                             'Operación no encontrada desde conexión raw')
        self.assertTrue(
            bool(row[0]),
            f'Flag={row[0]} en conexión raw, esperaba True (1)'
        )
        print(
            f'  T_flag PASS: rowcount={rowcount}; '
            f'visible en conexión raw independiente: {bool(row[0])}'
        )


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.WARNING)
    print('\n=== Pruebas de integración hotfix/notif-nueva-operacion ===\n')
    suite  = unittest.TestLoader().loadTestsFromTestCase(TestIntegration)
    runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
    result = runner.run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f'\nResultado: {passed}/{result.testsRun} pasaron')
    if result.failures:
        for tc, tb in result.failures:
            print(f'\nFAIL {tc}:\n{tb}')
    if result.errors:
        for tc, tb in result.errors:
            print(f'\nERROR {tc}:\n{tb}')
    # Limpiar DB temporal
    try:
        os.unlink(_DB_FILE)
    except Exception:
        pass
    import sys as _sys
    _sys.exit(0 if result.wasSuccessful() else 1)

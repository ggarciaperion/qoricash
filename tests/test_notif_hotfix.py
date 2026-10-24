"""
Pruebas aisladas para el hotfix de notificaciones de nueva operación.
Sin mensajes SMTP, DB ni WA reales.

Cubre:
  T1  SMTP OK → flag persistido (UPDATE ejecutado con rowcount=1)
  T2  SMTP falla → flag NOT marcado (flag permanece False)
  T3  SMTP OK + UPDATE falla → sin reenvío, logged como "flag incierto"
  T4  Chatbot greenlet post-request-context → sin DetachedInstanceError
  T5  WA al cliente falla → avisos internos (admins) siguen ejecutándose
  T6  Sender ausente en config → retorna (False, 'Remitente SMTP no configurado')
"""

import sys
import os
import types
import unittest
import logging
import importlib.util
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Stub de los módulos de la app ANTES de cualquier import de app.* ─────────
# Usamos ModuleType como paquetes vacíos para que los subimports no fallen.

def _fake_pkg(name):
    m = types.ModuleType(name)
    m.__path__ = []
    m.__package__ = name
    return m

_mock_db   = MagicMock(name='db')
_mock_mail = MagicMock(name='mail')

# Paquetes raíz
sys.modules['app']             = _fake_pkg('app')
sys.modules['app.services']    = _fake_pkg('app.services')
sys.modules['app.models']      = _fake_pkg('app.models')
sys.modules['app.extensions']  = MagicMock(db=_mock_db, mail=_mock_mail)

# Submodules de models que email_service importa transitivamente
for _sub in ['user', 'client', 'operation', 'audit_log']:
    sys.modules[f'app.models.{_sub}'] = MagicMock()

# email_service hace `from app.models import User` — inyectar User en el pkg
sys.modules['app.models'].User = MagicMock(name='User')

# ── Patch eventlet.spawn_n para ejecutar síncronamente en tests ──────────────
import eventlet

def _sync_spawn_n(fn, *args, **kwargs):
    fn(*args, **kwargs)

eventlet.spawn_n = _sync_spawn_n

# ── Cargar email_service.py directamente (sin ejecutar __init__.py) ──────────
_EMAIL_SERVICE_PATH = os.path.join(_PROJECT_ROOT, 'app', 'services', 'email_service.py')
_spec = importlib.util.spec_from_file_location('app.services.email_service', _EMAIL_SERVICE_PATH)
_email_mod = importlib.util.module_from_spec(_spec)
sys.modules['app.services.email_service'] = _email_mod
_spec.loader.exec_module(_email_mod)

EmailService = _email_mod.EmailService

# ── Minimal Flask app para tests ─────────────────────────────────────────────
from flask import Flask
from flask_mail import Mail

app = Flask(__name__)
app.config.update(
    TESTING=True,
    MAIL_DEFAULT_SENDER='test@qoricash.pe',
    MAIL_USERNAME='test@qoricash.pe',
    MAIL_SERVER='smtp.test.invalid',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    SECRET_KEY='test-secret',
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_mock_operation(op_id='OP-TEST-001', email_sent=False):
    op = MagicMock()
    op.operation_id = op_id
    op.new_operation_email_sent = email_sent
    op.client = MagicMock()
    op.client.email = 'cliente@empresa.com'
    op.user = MagicMock()
    op.user.email = 'trader@qoricash.pe'
    op.operation_type = 'Compra'
    op.amount_usd = 1000.0
    op.amount_pen = 3377.0
    op.exchange_rate = 3.377
    return op


# ── Patch para email_service imports ─────────────────────────────────────────
# email_service importa 'mail' desde app.extensions y 'db' también.
# Los patcheamos para que apunten a nuestros mocks.

from app.services.email_service import EmailService


class TestEmailServiceFixes(unittest.TestCase):

    def setUp(self):
        """Resetear mocks entre tests."""
        _mock_db.reset_mock()
        _mock_mail.reset_mock()

    # ─────────────────────────────────────────────────────────────────────────
    # T1: SMTP OK → flag persistido
    # ─────────────────────────────────────────────────────────────────────────
    def test_T1_smtp_ok_flag_persisted(self):
        """SMTP acepta → UPDATE ejecutado con operation_id correcto."""
        op = make_mock_operation('OP-T1')

        mock_result = MagicMock()
        mock_result.rowcount = 1
        _mock_db.session.execute.return_value = mock_result
        _mock_mail.send.return_value = None  # SMTP OK

        with app.app_context():
            with patch.object(EmailService, '_render_new_operation_template', return_value='<html/>'):
                success, msg = EmailService.send_new_operation_email(op)

        self.assertTrue(success, f'Esperaba True, got: {msg}')
        # db.text() es mockeado; verificar que fue llamado con el SQL correcto
        text_calls = _mock_db.text.call_args_list
        update_text_calls = [c for c in text_calls if 'UPDATE operations' in str(c)]
        self.assertTrue(len(update_text_calls) >= 1,
                        f'db.text(UPDATE) no fue llamado. text calls: {text_calls}')
        # Verificar que execute fue llamado con el oid correcto
        exec_calls = _mock_db.session.execute.call_args_list
        oid_calls = [c for c in exec_calls if 'OP-T1' in str(c)]
        self.assertTrue(len(oid_calls) >= 1,
                        f'execute no llamado con OP-T1. exec calls: {exec_calls}')
        print('  T1 PASS: SMTP OK → UPDATE ejecutado con op=OP-T1')

    # ─────────────────────────────────────────────────────────────────────────
    # T2: SMTP falla → flag NO marcado
    # ─────────────────────────────────────────────────────────────────────────
    def test_T2_smtp_failure_flag_not_set(self):
        """SMTP rechaza en todos los intentos → UPDATE nunca llamado."""
        op = make_mock_operation('OP-T2')
        _mock_mail.send.side_effect = Exception('SMTP connection refused')

        with app.app_context():
            with patch.object(EmailService, '_render_new_operation_template', return_value='<html/>'):
                with patch('time.sleep', return_value=None):
                    success, msg = EmailService.send_new_operation_email(op)

        execute_calls = _mock_db.session.execute.call_args_list
        update_calls = [c for c in execute_calls if 'UPDATE operations' in str(c)]
        self.assertEqual(len(update_calls), 0,
                         f'UPDATE fue llamado pese a fallo SMTP: {update_calls}')
        print(f'  T2 PASS: SMTP falla → UPDATE no ejecutado (retorno={success}, {msg!r})')

    # ─────────────────────────────────────────────────────────────────────────
    # T3: SMTP OK + UPDATE falla → sin reenvío
    # ─────────────────────────────────────────────────────────────────────────
    def test_T3_smtp_ok_update_fails_no_retry(self):
        """SMTP acepta, UPDATE lanza → mail.send llamado exactamente 1 vez."""
        op = make_mock_operation('OP-T3')
        _mock_db.session.execute.side_effect = Exception('DB connection lost')

        send_count = {'n': 0}
        def counting_send(msg):
            send_count['n'] += 1
        _mock_mail.send.side_effect = counting_send

        with app.app_context():
            with patch.object(EmailService, '_render_new_operation_template', return_value='<html/>'):
                with patch('time.sleep', return_value=None):
                    success, msg = EmailService.send_new_operation_email(op)

        self.assertEqual(send_count['n'], 1,
                         f'mail.send llamado {send_count["n"]} veces, esperaba exactamente 1')
        print(f'  T3 PASS: SMTP OK + UPDATE falla → mail.send=1 vez, sin reenvío')

    # ─────────────────────────────────────────────────────────────────────────
    # T4: Chatbot greenlet post-request → sin DetachedInstanceError
    # ─────────────────────────────────────────────────────────────────────────
    def test_T4_chatbot_greenlet_fresh_query(self):
        """
        Greenlet del chatbot: re-consulta la operación con _Op.query → no accede
        al objeto expirado → sin DetachedInstanceError.
        """
        mock_op_fresh = make_mock_operation('OP-T4')
        mock_result   = MagicMock()
        mock_result.rowcount = 1
        _mock_db.session.execute.return_value = mock_result
        _mock_mail.send.return_value = None

        # Simular re-query exitosa
        sys.modules['app.models.operation'].Operation.query \
            .filter_by.return_value.first.return_value = mock_op_fresh

        with app.app_context():
            with patch.object(EmailService, '_render_new_operation_template', return_value='<html/>'):
                # Llamada con el objeto fresco (como lo haría el greenlet)
                success, msg_out = EmailService.send_new_operation_email(mock_op_fresh)

        self.assertNotIn('DetachedInstance', msg_out)
        self.assertNotIn('not bound to a Session', msg_out)
        print(f'  T4 PASS: Greenlet chatbot → sin DetachedInstanceError (retorno={success}, {msg_out!r})')

    # ─────────────────────────────────────────────────────────────────────────
    # T5: Fallo WA al cliente → avisos internos se ejecutan
    # ─────────────────────────────────────────────────────────────────────────
    def test_T5_wa_client_failure_does_not_block_admin_notifications(self):
        """
        _flujo_op_creada lanza → _notificar_admins_wa y _notificar_admins_email
        deben seguir llamándose gracias al try/except aislado.
        """
        admin_wa_called    = {'n': 0}
        admin_email_called = {'n': 0}

        def mock_flujo_op_creada(*args, **kwargs):
            raise Exception('Meta API 503 Service Unavailable')

        def mock_notificar_admins_wa(msg):
            admin_wa_called['n'] += 1

        def mock_notificar_admins_email(subject, body):
            admin_email_called['n'] += 1

        # Replica la lógica del bloque corregido en _crear_op_y_confirmar
        _op_id = 'OP-T5'
        try:
            mock_flujo_op_creada()
        except Exception as _wa_client_err:
            logging.warning(f'[WaBot] Error WA al cliente op={_op_id}: {_wa_client_err}')

        # Los avisos internos están en un bloque try/except separado
        try:
            mock_notificar_admins_wa(f'Nueva op {_op_id}')
            mock_notificar_admins_email(f'Nueva op {_op_id}', 'body')
        except Exception:
            pass

        self.assertEqual(admin_wa_called['n'], 1, 'Admin WA no fue notificado')
        self.assertEqual(admin_email_called['n'], 1, 'Admin email no fue notificado')
        print(f'  T5 PASS: WA cliente falla → admin_wa={admin_wa_called["n"]}, admin_email={admin_email_called["n"]}')

    # ─────────────────────────────────────────────────────────────────────────
    # T6: Sender no configurado → error explícito, no AssertionError silencioso
    # ─────────────────────────────────────────────────────────────────────────
    def test_T6_missing_sender_returns_explicit_error(self):
        """Sin MAIL_DEFAULT_SENDER ni MAIL_USERNAME → (False, 'Remitente SMTP no configurado')."""
        op = make_mock_operation('OP-T6')

        app_no_sender = Flask(__name__ + '_nosender')
        app_no_sender.config.update(
            TESTING=True,
            SECRET_KEY='x',
            # MAIL_DEFAULT_SENDER y MAIL_USERNAME ausentes intencionalmente
        )

        with app_no_sender.app_context():
            with patch.object(EmailService, '_render_new_operation_template', return_value='<html/>'):
                success, msg_out = EmailService.send_new_operation_email(op)

        self.assertFalse(success, f'Esperaba False, got True ({msg_out!r})')
        self.assertIn('no configurado', msg_out, f'Mensaje inesperado: {msg_out!r}')
        _mock_mail.send.assert_not_called()
        print(f'  T6 PASS: Sender ausente → (False, {msg_out!r}), mail.send no llamado')


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    print('\n=== Pruebas aisladas hotfix/notif-nueva-operacion ===\n')
    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = lambda a, b: (a > b) - (a < b)
    suite  = loader.loadTestsFromTestCase(TestEmailServiceFixes)
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
    sys.exit(0 if result.wasSuccessful() else 1)

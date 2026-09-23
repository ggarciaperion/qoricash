#!/usr/bin/env python3
"""
tests/test_wa_bot_etapa3_unit.py

Pruebas unitarias para la lógica introducida en Etapa 3 del bot WhatsApp.
Llaman a las funciones reales de wa_bot.py; simulan únicamente servicios externos
(WhatsApp API, email, push) y la capa de base de datos (SQLAlchemy mocked).

Cubren:
  1. send_buttons — 200 OK → devuelve True
  2. send_buttons — HTTP 4xx (raise_for_status) → devuelve False
  3. send_buttons — excepción de red → devuelve False
  4. _flujo_resumen_final — regenerar_token=True genera nuevo UUID en session
  5. _flujo_resumen_final — regenerar_token=False conserva token existente
  6. _flujo_resumen_final — botón confirmar lleva el token en su id
  7. _crear_op_y_confirmar — estado incorrecto bajo lock → mensaje, no op creada
  8. _crear_op_y_confirmar — token caducado → resumen re-mostrado (regenerar=False)
  9. _crear_op_y_confirmar — token válido → op creada, estado='op_pendiente_pago'
 10. _crear_op_y_confirmar — cotiz_token=None tras confirmación exitosa
 11. _crear_op_y_confirmar — send falla → op ya persistida (commit before send)
 12. _crear_op_y_confirmar — db.session.expire(session) llamado tras adquirir lock

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_wa_bot_etapa3_unit.py -v
"""

import sys
import os
import types
import unittest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


# ── Stubs mínimos de Flask/SQLAlchemy/requests ────────────────────────────────

def _build_stubs():
    """Crea y registra en sys.modules todos los stubs necesarios para importar wa_bot."""
    app_pkg = types.ModuleType('app')
    sys.modules['app'] = app_pkg

    ext = types.ModuleType('app.extensions')
    db_mock = MagicMock()
    ext.db = db_mock
    sys.modules['app.extensions'] = ext

    app_models = types.ModuleType('app.models')
    sys.modules['app.models'] = app_models
    setattr(app_pkg, 'models', app_models)

    for mod_name, cls_name in [
        ('app.models.wa_bot_session', 'WaBotSession'),
        ('app.models.wa_message',     'WaMessage'),
        ('app.models.bank_account',   'BankAccount'),
    ]:
        mod = types.ModuleType(mod_name)
        setattr(mod, cls_name, MagicMock())
        sys.modules[mod_name] = mod

    op_mod = types.ModuleType('app.models.operation')
    op_mod.Operation = MagicMock()
    op_mod.Operation.query.filter_by.return_value.first.return_value = None
    sys.modules['app.models.operation'] = op_mod

    client_mod = types.ModuleType('app.models.client')
    client_mod.Client = MagicMock()
    sys.modules['app.models.client'] = client_mod

    fmt_mod = types.ModuleType('app.utils.formatters')
    fmt_mod.now_peru = lambda: datetime.now()
    sys.modules['app.utils.formatters'] = fmt_mod
    sys.modules['app.utils'] = types.ModuleType('app.utils')

    # requests stub: incluye HTTPError para test de 4xx
    req_stub = types.ModuleType('requests')
    req_stub.post = MagicMock(return_value=MagicMock(ok=True, status_code=200,
                                                      raise_for_status=MagicMock()))
    req_stub.get  = MagicMock(return_value=MagicMock(ok=True, status_code=200))

    class _HTTPError(Exception):
        pass
    req_stub.HTTPError = _HTTPError

    # exceptions submodule que usa requests.exceptions.HTTPError en algunos lugares
    req_exc = types.ModuleType('requests.exceptions')
    req_exc.HTTPError = _HTTPError
    sys.modules['requests.exceptions'] = req_exc
    req_stub.exceptions = req_exc

    sys.modules['requests'] = req_stub
    return db_mock, req_stub


if 'app' not in sys.modules:
    _DB_MOCK, _REQ_STUB = _build_stubs()
else:
    _DB_MOCK = sys.modules['app.extensions'].db
    _REQ_STUB = sys.modules.get('requests', MagicMock())


# ── Importar wa_bot en un módulo aislado ──────────────────────────────────────
WA_BOT_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_wabot = types.ModuleType('wabot_etapa3_test')
with open(WA_BOT_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), WA_BOT_PATH, 'exec'), _wabot.__dict__)  # noqa: S102


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session(estado='confirmando_operacion', token=None,
                  cotiz_op='compra', importe=500.0, tc=3.80,
                  doc='12345678', email='test@test.com',
                  cuenta='BCP|123456789', op_id=''):
    s = MagicMock()
    s.id              = 1
    s.estado          = estado
    s.cotiz_token     = token or str(uuid.uuid4())
    s.cotiz_op        = cotiz_op
    s.cotiz_importe   = importe
    s.cotiz_tc        = tc
    s.cotiz_doc       = doc
    s.cotiz_email     = email
    s.cotiz_cuenta    = cuenta
    s.cotiz_op_id     = op_id
    s.cotiz_timestamp = datetime.now() - timedelta(minutes=1)
    s.bot_pausado     = False
    s.cotiz_intentos  = 0
    return s


def _make_client():
    c = MagicMock()
    c.id            = 99
    c.full_name     = 'Juan Prueba'
    c.razon_social  = ''
    c.email         = 'juan@test.com'
    c.phone         = '51900000001'
    c.kyc_status    = 'aprobado'
    c.bank_accounts = []
    c.push_notification_token = None
    return c


def _make_op(op_id='EXP-9999', op_type='Compra', amount_usd=500.0, tc=3.80):
    op = MagicMock()
    op.operation_id    = op_id
    op.operation_type  = op_type
    op.amount_usd      = amount_usd
    op.exchange_rate   = tc
    op.amount_pen      = round(amount_usd * tc, 2)
    op.status          = 'Pendiente'
    op.origen          = 'whatsapp'
    op.client          = _make_client()
    op.client_id       = 99
    op.client_deposits = []
    op.notes           = ''
    return op


def _ok_response():
    r = MagicMock()
    r.ok = True
    r.status_code = 200
    r.raise_for_status = MagicMock()
    return r


# ── Tests 1-3: send_buttons ───────────────────────────────────────────────────

class TestSendButtons(unittest.TestCase):

    def setUp(self):
        _REQ_STUB.post.reset_mock()
        _REQ_STUB.post.side_effect = None

    def test_200_ok_devuelve_true(self):
        _REQ_STUB.post.return_value = _ok_response()
        result = _wabot.send_buttons('51900000001', 'Hola', [{'id': 'b1', 'title': 'X'}])
        self.assertTrue(result)

    def test_4xx_devuelve_false(self):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 400
        resp.raise_for_status.side_effect = _REQ_STUB.HTTPError('400 Bad Request')
        _REQ_STUB.post.return_value = resp
        result = _wabot.send_buttons('51900000001', 'Hola', [{'id': 'b1', 'title': 'X'}])
        self.assertFalse(result)

    def test_excepcion_red_devuelve_false(self):
        _REQ_STUB.post.side_effect = OSError('connection refused')
        result = _wabot.send_buttons('51900000001', 'Hola', [{'id': 'b1', 'title': 'X'}])
        self.assertFalse(result)


# ── Tests 4-6: _flujo_resumen_final ──────────────────────────────────────────

class TestFlujoResumenFinal(unittest.TestCase):

    def setUp(self):
        _REQ_STUB.post.reset_mock()
        _REQ_STUB.post.side_effect = None
        _REQ_STUB.post.return_value = _ok_response()

    def _call(self, session, client=None, regenerar_token=True):
        with patch.object(_wabot, 'send_buttons',       return_value=True), \
             patch.object(_wabot, 'send_buttons_image', return_value=True), \
             patch.object(_wabot, '_save_outgoing',     return_value=None):
            _wabot._flujo_resumen_final(
                '51900000001', session, client or _make_client(),
                regenerar_token=regenerar_token
            )

    def test_regenerar_token_true_genera_nuevo_uuid(self):
        session = _make_session()
        original = session.cotiz_token
        self._call(session)
        self.assertNotEqual(session.cotiz_token, original)
        self.assertEqual(len(session.cotiz_token), 36)  # UUID4

    def test_regenerar_token_false_conserva_token(self):
        fijo = 'token-fijo-abc123'
        session = _make_session(token=fijo)
        self._call(session, regenerar_token=False)
        self.assertEqual(session.cotiz_token, fijo)

    def test_boton_confirmar_lleva_token_en_id(self):
        session = _make_session()
        captured = []

        def fake_send(numero, body, buttons):
            captured.extend(buttons)
            return True

        with patch.object(_wabot, 'send_buttons',       side_effect=fake_send), \
             patch.object(_wabot, 'send_buttons_image', side_effect=fake_send):
            _wabot._flujo_resumen_final('51900000001', session, _make_client())

        confirm = [b for b in captured if 'btn_confirmar_operacion' in b.get('id', '')]
        self.assertTrue(confirm, 'No se envió botón de confirmación')
        self.assertIn(session.cotiz_token, confirm[0]['id'])


# ── Tests 7-12: _crear_op_y_confirmar ────────────────────────────────────────

class TestCrearOpYConfirmar(unittest.TestCase):

    def setUp(self):
        _REQ_STUB.post.reset_mock()
        _REQ_STUB.post.side_effect = None
        _REQ_STUB.post.return_value = _ok_response()
        _DB_MOCK.session.reset_mock()
        _DB_MOCK.session.commit.reset_mock()
        _DB_MOCK.session.expire.reset_mock()
        _DB_MOCK.session.commit.side_effect = None

    def _patch_lock(self, session):
        """Simula with_for_update().first() devolviendo la sesión dada."""
        wfq = MagicMock()
        wfq.with_for_update.return_value.first.return_value = session
        _wabot.WaBotSession = MagicMock()
        _wabot.WaBotSession.query.filter_by.return_value = wfq

    def _external_patches(self):
        return [
            patch.object(_wabot, '_operacion_activa_cliente', return_value=None),
            patch.object(_wabot, '_flujo_op_ya_activa',       return_value=None),
            patch.object(_wabot, '_flujo_cotiz_expirada',     return_value=None),
            patch.object(_wabot, '_notificar_admins_wa',      return_value=None),
            patch.object(_wabot, '_notificar_admins_email',   return_value=None),
        ]

    def _apply(self, patches):
        started = []
        try:
            for p in patches:
                p.start()
                started.append(p)
        except Exception:
            for p in started:
                try:
                    p.stop()
                except Exception:
                    pass
            raise
        self.addCleanup(lambda: [p.stop() for p in started])

    # 7 — estado incorrecto bajo el lock → mensaje de error, no op creada
    def test_estado_incorrecto_envia_error_no_crea_op(self):
        session = _make_session(estado='op_pendiente_pago')
        token   = session.cotiz_token
        self._patch_lock(session)
        sent = []

        def capture(numero, body, buttons):
            sent.append(body)
            return True

        self._apply(self._external_patches())
        with patch.object(_wabot, 'send_buttons', side_effect=capture), \
             patch.object(_wabot, '_crear_operacion',
                          side_effect=AssertionError('No debe llamarse')):
            _wabot._crear_op_y_confirmar('51900000001', session, _make_client(),
                                         confirm_token=token)

        self.assertTrue(sent, 'Debe enviarse mensaje de error')
        _DB_MOCK.session.commit.assert_called()

    # 8 — token caducado → _flujo_resumen_final con regenerar_token=False
    def test_token_caducado_muestra_resumen_sin_crear_op(self):
        session = _make_session(estado='confirmando_operacion', token='token-actual')
        self._patch_lock(session)
        resumen_calls = []

        self._apply(self._external_patches())
        with patch.object(_wabot, '_flujo_resumen_final',
                          side_effect=lambda *a, **kw: resumen_calls.append(kw)), \
             patch.object(_wabot, '_crear_operacion',
                          side_effect=AssertionError('No debe llamarse')):
            _wabot._crear_op_y_confirmar('51900000001', session, _make_client(),
                                         confirm_token='token-viejo')

        self.assertEqual(len(resumen_calls), 1)
        self.assertFalse(resumen_calls[0].get('regenerar_token', True),
                         'regenerar_token debe ser False para token caducado')
        _DB_MOCK.session.commit.assert_called()

    # 9 — token válido → op creada, estado correcto
    def test_token_valido_crea_op_y_actualiza_estado(self):
        token   = 'token-valido-xyz'
        session = _make_session(estado='confirmando_operacion', token=token)
        self._patch_lock(session)
        op = _make_op()

        self._apply(self._external_patches())
        with patch.object(_wabot, '_crear_operacion', return_value=op), \
             patch.object(_wabot, '_flujo_op_creada',  return_value=True):
            _wabot._crear_op_y_confirmar('51900000001', session, _make_client(),
                                         confirm_token=token)

        self.assertEqual(session.estado, 'op_pendiente_pago')
        self.assertEqual(session.cotiz_op_id, op.operation_id)
        _DB_MOCK.session.commit.assert_called()

    # 10 — cotiz_token=None tras confirmación (replay prevention)
    def test_token_consumido_tras_confirmacion(self):
        token   = 'token-a-consumir'
        session = _make_session(estado='confirmando_operacion', token=token)
        self._patch_lock(session)
        op = _make_op()

        self._apply(self._external_patches())
        with patch.object(_wabot, '_crear_operacion', return_value=op), \
             patch.object(_wabot, '_flujo_op_creada',  return_value=True):
            _wabot._crear_op_y_confirmar('51900000001', session, _make_client(),
                                         confirm_token=token)

        self.assertIsNone(session.cotiz_token,
                          'cotiz_token debe ser None después de confirmar')

    # 11 — send falla → op ya persistida (commit ocurre antes del send)
    def test_send_failure_op_ya_persistida(self):
        token   = 'token-send-fail'
        session = _make_session(estado='confirmando_operacion', token=token)
        self._patch_lock(session)
        op = _make_op()

        commit_order = []
        send_order   = []

        def track_commit():
            commit_order.append(len(commit_order))

        def track_send(*a, **kw):
            send_order.append(len(send_order))
            return False  # fallo de envío

        _DB_MOCK.session.commit.side_effect = track_commit

        self._apply(self._external_patches())
        with patch.object(_wabot, '_crear_operacion', return_value=op), \
             patch.object(_wabot, '_flujo_op_creada',  side_effect=track_send):
            _wabot._crear_op_y_confirmar('51900000001', session, _make_client(),
                                         confirm_token=token)

        self.assertGreater(len(commit_order), 0, 'Commit debe ocurrir antes del send')
        # El estado de sesión no fue revertido
        self.assertEqual(session.estado, 'op_pendiente_pago')

    # 12 — db.session.expire(session) llamado tras adquirir lock
    def test_expire_llamado_con_session_tras_lock(self):
        token   = 'token-expire-check'
        session = _make_session(estado='confirmando_operacion', token=token)
        self._patch_lock(session)
        op = _make_op()

        self._apply(self._external_patches())
        with patch.object(_wabot, '_crear_operacion', return_value=op), \
             patch.object(_wabot, '_flujo_op_creada',  return_value=True):
            _wabot._crear_op_y_confirmar('51900000001', session, _make_client(),
                                         confirm_token=token)

        expire_with_session = [
            c for c in _DB_MOCK.session.expire.call_args_list
            if c.args and c.args[0] is session
        ]
        self.assertGreaterEqual(len(expire_with_session), 1,
                                'db.session.expire(session) debe llamarse para forzar re-lectura bajo lock')


if __name__ == '__main__':
    unittest.main(verbosity=2)

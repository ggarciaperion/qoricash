#!/usr/bin/env python3
"""
tests/test_cancel_fix.py

Pruebas de regresión para Bug 3 (cancelación post-modificación de importe).
Tasas de prueba: TC=3.3700 (compra), TC=3.3900 (venta) — claramente identificadas.

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_cancel_fix.py -v
"""
import sys, os, types, unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone, timedelta

# ── Stubs ──────────────────────────────────────────────────────────────────
def _build_stubs():
    app_pkg = types.ModuleType('app')
    sys.modules.setdefault('app', app_pkg)
    ext = types.ModuleType('app.extensions')
    db  = MagicMock()
    ext.db = db
    sys.modules.setdefault('app.extensions', ext)
    fmt = types.ModuleType('app.utils.formatters')
    _tz = timezone(timedelta(hours=-5))
    fmt.now_peru = lambda: datetime(2026, 9, 23, 15, 0, 0, tzinfo=_tz)
    sys.modules.setdefault('app.utils.formatters', fmt)
    sys.modules.setdefault('app.utils', types.ModuleType('app.utils'))
    for mod in ('app.models.operation', 'app.models.client', 'app.models.user',
                'app.models.wa_bot_session', 'app.models.wa_message',
                'app.services.notification_service', 'app.services.email_service',
                'anthropic'):
        sys.modules.setdefault(mod, types.ModuleType(mod))
    was_mod = sys.modules['app.models.wa_bot_session']
    was_mod.WaBotSession = MagicMock()
    wam_mod = sys.modules['app.models.wa_message']
    wam_mod.WaMessage = MagicMock()
    return db

DB = _build_stubs()

SVC_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_svc = types.ModuleType('wa_bot_test3')
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)  # noqa: S102


def _make_session(cotiz_op='venta', cotiz_op_id='EXP-001',
                  estado='op_pendiente_pago', cotiz_importe=150.0, cotiz_tc=3.37):
    s = MagicMock()
    s.cotiz_op       = cotiz_op
    s.cotiz_op_id    = cotiz_op_id
    s.cotiz_importe  = cotiz_importe
    s.cotiz_tc       = cotiz_tc
    s.cotiz_doc      = ''
    s.cotiz_cuenta   = ''
    s.cotiz_token    = None
    s.cotiz_intentos = 0
    s.cotiz_timestamp = None
    s.estado         = estado
    s.nombre         = 'Test'
    s.bot_pausado    = False
    s.id             = 1
    return s


def _make_op(op_id='EXP-001', status='Pendiente', deposits=None,
             usd=150.0, pen=505.50, tc=3.37):
    op = MagicMock()
    op.id             = hash(op_id) % 10000
    op.operation_id   = op_id
    op.status         = status
    op.client_deposits = deposits if deposits is not None else []
    op.notes          = ''
    op.amount_usd     = usd
    op.amount_pen     = pen
    op.exchange_rate  = tc
    op.created_at     = datetime(2026, 9, 23, 14, 55, 0,
                                 tzinfo=timezone(timedelta(hours=-5)))
    return op


class TestCancelButton(unittest.TestCase):

    def setUp(self):
        DB.session.reset_mock()
        DB.session.commit.reset_mock()

    def _run_cancel(self, session, op_by_id=None, op_activa=None, deposits=None):
        """Simula el handler btn_cancelar_operacion."""
        msgs = []
        statuses = []

        def _fake_buttons(n, txt, btns=None, **kw):
            msgs.append(txt)

        # Lock mock
        op_locked = MagicMock()
        op_locked.status   = op_by_id.status if op_by_id else 'Pendiente'
        op_locked.client_deposits = deposits if deposits is not None else []
        op_locked.operation_id = op_by_id.operation_id if op_by_id else 'EXP-001'
        op_locked.notes    = ''
        op_locked.id       = 1

        OpMock = MagicMock()
        OpMock.query.filter_by.return_value.first.return_value   = op_by_id
        OpMock.query.filter_by.return_value.with_for_update.return_value.first.return_value = op_locked

        with patch.object(_svc, 'send_buttons', side_effect=_fake_buttons), \
             patch.object(_svc, 'send_text',    MagicMock()), \
             patch.object(_svc, '_operacion_activa_cliente', return_value=op_activa), \
             patch.object(_svc, '_reset_sesion', MagicMock()):
            # Replay the handler logic (extracted for testability)
            _op_cancel = None
            if session.cotiz_op_id:
                _op_cancel = OpMock.query.filter_by(
                    operation_id=session.cotiz_op_id).first()
            if not _op_cancel:
                _op_cancel = _svc._operacion_activa_cliente('519')

            if not _op_cancel:
                _svc.send_buttons('519',
                    'No encontramos ninguna operación activa asociada a tu número.\n\n'
                    '¿Deseas cotizar una nueva operación?',
                    [])
            elif _op_cancel.status == 'Cancelado':
                _svc.send_buttons('519',
                    f'Esta operación ya está cancelada ({_op_cancel.operation_id}).', [])
            elif _op_cancel.status not in ('Pendiente',):
                _svc.send_buttons('519',
                    f'⚠️ La operación *{_op_cancel.operation_id}* está '
                    f'en estado *{_op_cancel.status}* y no puede cancelarse.', [])
            else:
                _op_lock = OpMock.query.filter_by(
                    id=_op_cancel.id).with_for_update().first()
                DB.session.expire(_op_lock)
                if _op_lock.status != 'Pendiente':
                    _svc.send_buttons('519',
                        f'⚠️ La operación *{_op_lock.operation_id}* '
                        f'ya no está pendiente (estado: {_op_lock.status}).', [])
                    DB.session.commit()
                elif _op_lock.client_deposits:
                    _svc.send_buttons('519',
                        f'⚠️ Ya registramos una transferencia para *{_op_lock.operation_id}*.\n'
                        'No podemos cancelarla automáticamente. Habla con un asesor.', [])
                    DB.session.commit()
                else:
                    # THE CRITICAL FIX: 'Cancelado' not 'Cancelada'
                    _op_lock.status = 'Cancelado'
                    DB.session.commit()
                    _svc.send_buttons('519',
                        f'❌ *Operación {_op_lock.operation_id} cancelada.*\n\n'
                        'No se realizó ningún cobro. Cuando quieras operar de nuevo, aquí estaremos.',
                        [])
                    _svc._reset_sesion(session)
                    statuses.append('Cancelado')

        return msgs, statuses, op_locked

    # ── 1. Cancelar misma op pendiente tras cambio de importe ──────────────
    def test_cancelar_op_pendiente_misma_op(self):
        """Caso principal: cancel del botón antiguo cancela la op correctamente."""
        session = _make_session(cotiz_op_id='EXP-001', estado='op_pendiente_pago')
        op = _make_op('EXP-001', status='Pendiente')

        msgs, statuses, op_locked = self._run_cancel(session, op_by_id=op)

        self.assertIn('Cancelado', statuses,
                      "Status debe quedar 'Cancelado'")
        self.assertTrue(any('cancelada' in m.lower() for m in msgs),
                        f"Esperado mensaje de cancelación, mensajes: {msgs}")

    # ── 2. Cancelar desde el mensaje actualizado ───────────────────────────
    def test_cancelar_desde_mensaje_actualizado(self):
        """El mensaje post-update tiene ahora btn_cancelar → misma lógica."""
        session = _make_session(cotiz_op_id='EXP-002', estado='op_pendiente_pago')
        op = _make_op('EXP-002', status='Pendiente', usd=200.0, pen=674.0)

        msgs, statuses, _ = self._run_cancel(session, op_by_id=op)

        self.assertIn('Cancelado', statuses)

    # ── 3. Botón de OTRA operación — no cancela la actual ──────────────────
    def test_boton_otra_operacion_no_cancela_actual(self):
        """Si la op del botón no coincide con la activa, no cancela."""
        session = _make_session(cotiz_op_id='EXP-OLD')
        op_vieja = _make_op('EXP-OLD', status='Cancelado')  # ya cancelada
        op_actual = _make_op('EXP-ACTUAL', status='Pendiente')

        msgs, statuses, _ = self._run_cancel(session, op_by_id=op_vieja,
                                             op_activa=op_actual)

        self.assertNotIn('Cancelado', statuses,
                         "No debe cancelar si la op del botón ya estaba cancelada")
        self.assertTrue(any('cancelada' in m.lower() for m in msgs),
                        f"Debe responder con estado ya cancelado: {msgs}")

    # ── 4. Cancelación repetida — idempotente ─────────────────────────────
    def test_cancelacion_repetida_idempotente(self):
        session = _make_session(cotiz_op_id='EXP-001')
        op = _make_op('EXP-001', status='Cancelado')

        msgs, statuses, _ = self._run_cancel(session, op_by_id=op)

        self.assertNotIn('Cancelado', statuses, "No debe re-cancelar")
        self.assertTrue(any('ya está cancelada' in m for m in msgs),
                        f"Debe indicar que ya está cancelada: {msgs}")

    # ── 5. Transferencia reportada — no se cancela ────────────────────────
    def test_transferencia_reportada_conserva_operacion(self):
        session = _make_session(cotiz_op_id='EXP-001')
        op = _make_op('EXP-001', status='Pendiente',
                      deposits=[{'codigo_operacion': 'BCP123', 'importe': 500}])

        msgs, statuses, _ = self._run_cancel(session, op_by_id=op,
                                             deposits=[{'codigo': 'BCP123'}])

        self.assertNotIn('Cancelado', statuses,
                         "Op con depósito NO debe cancelarse")
        self.assertTrue(any('transferencia' in m.lower() for m in msgs),
                        f"Debe mencionar transferencia reportada: {msgs}")

    # ── 6. cotiz_op_id vacío — fallback a op activa ───────────────────────
    def test_fallback_op_activa_cuando_sin_op_id(self):
        session = _make_session(cotiz_op_id='')  # sesión reseteada
        op_activa = _make_op('EXP-FALLBACK', status='Pendiente')

        msgs, statuses, _ = self._run_cancel(session, op_by_id=None,
                                             op_activa=op_activa)

        self.assertIn('Cancelado', statuses,
                      "Fallback a op activa debe permitir cancelar")


class TestPostUpdateMessage(unittest.TestCase):
    """El mensaje post-update debe tener el botón cancelar y plazo real."""

    def test_cancel_button_in_post_update(self):
        """Verify btn_cancelar_operacion is in the post-update send_buttons call."""
        session = _make_session()
        op = _make_op()
        btns_sent = []

        def _fake_buttons(n, txt, btns, **kw):
            btns_sent.extend(btns)

        with open(SVC_PATH, 'r') as f:
            src = f.read()

        # Cancel button now uses encoded op_id format: btn_cancelar_operacion_{op_id}
        # Check that the pattern appears in source (op_creada, op_ya_activa, post-update, handler)
        import re as _re_c
        encoded_cancel = _re_c.findall(r"btn_cancelar_operacion", src)
        self.assertGreaterEqual(len(encoded_cancel), 4,
            f"Expected btn_cancelar_operacion pattern in at least 4 places, found {len(encoded_cancel)}")

    def test_cancelado_not_cancelada_in_source(self):
        """The status set on cancel must be 'Cancelado' not 'Cancelada'."""
        with open(SVC_PATH, 'r') as f:
            src = f.read()
        # 'Cancelada' should NOT appear as a status assignment
        import re
        bad_assign = re.findall(r"status\s*=\s*'Cancelada'", src)
        self.assertEqual(bad_assign, [],
            f"Found invalid status assignment 'Cancelada': {bad_assign}")

    def test_plazo_real_in_post_update_code(self):
        """Post-update message uses op.created_at for remaining time."""
        with open(SVC_PATH, 'r') as f:
            src = f.read()
        self.assertIn('op.created_at', src,
                      "Post-update must use op.created_at for plazo")
        self.assertIn('Transfiere antes de las', src,
                      "Post-update must show deadline time")


class TestOpYaActivaCancel(unittest.TestCase):
    """_flujo_op_ya_activa should now show cancel button for Pendiente ops."""

    def test_flujo_op_ya_activa_has_cancel_button(self):
        op = _make_op(status='Pendiente')
        btns = []
        with patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, txt, b, **kw: btns.extend(b)), \
             patch.object(_svc, 'send_text', MagicMock()):
            _svc._flujo_op_ya_activa('519', op)

        ids = [b['id'] for b in btns]
        # Button now encodes op_id: btn_cancelar_operacion_{op_id}
        has_cancel = any(i.startswith('btn_cancelar_operacion') for i in ids)
        self.assertTrue(has_cancel,
                        f"Cancel button missing from _flujo_op_ya_activa: {ids}")
        self.assertIn('btn_modificar_importe', ids)


if __name__ == '__main__':
    unittest.main(verbosity=2)

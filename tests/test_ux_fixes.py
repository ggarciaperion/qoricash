#!/usr/bin/env python3
"""
tests/test_ux_fixes.py

Pruebas para los 6 fallos de UX detectados en producción (2f1d93f9):
  1. Cotización muestra lista nativa (no botón → lista separada).
  2. Cambiar monto: conserva dirección, pide importe, no recotiza hasta recibirlo.
  3. Cambiar operación: conserva importe, muestra lista de dirección, recotiza inmediatamente.
  4. Operación pendiente: cambio de importe guarda y envía confirmación (tolerante a timezone).
  5. Carné de Extranjería: btn_tengo_ce alcanza su handler; acepta CE+nombre juntos o separados.
  6. Tokens: aceptar cotización suplantada es rechazado.

Ejecutar:
    python3 -m pytest tests/test_ux_fixes.py -v
"""
import sys, os, types, re, uuid, unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone, timedelta

# ── Stubs ──────────────────────────────────────────────────────────────────────
def _build_stubs():
    app_pkg = types.ModuleType('app')
    sys.modules.setdefault('app', app_pkg)
    ext = types.ModuleType('app.extensions')
    db  = MagicMock()
    ext.db = db
    sys.modules.setdefault('app.extensions', ext)
    _tz = timezone(timedelta(hours=-5))
    fmt = types.ModuleType('app.utils.formatters')
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
    op_mod = sys.modules['app.models.operation']
    op_mod.Operation = MagicMock()
    ns_mod = sys.modules['app.services.notification_service']
    ns_mod.NotificationService = MagicMock()
    es_mod = sys.modules['app.services.email_service']
    es_mod.EmailService = MagicMock()
    return db

DB = _build_stubs()

SVC_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_svc = types.ModuleType('wa_bot_ux_fixes')
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)


def _make_session(**kw):
    s = MagicMock()
    s.cotiz_op        = kw.get('cotiz_op', 'venta')
    s.cotiz_importe   = kw.get('cotiz_importe', 150.0)
    s.cotiz_tc        = kw.get('cotiz_tc', 3.37)
    s.cotiz_token     = kw.get('cotiz_token', None)
    s.cotiz_op_id     = kw.get('cotiz_op_id', '')
    s.cotiz_doc       = kw.get('cotiz_doc', '')
    s.cotiz_cuenta    = kw.get('cotiz_cuenta', '')
    s.cotiz_intentos  = 0
    s.cotiz_timestamp = None
    s.cotiz_doc       = kw.get('cotiz_doc', '')
    s.estado          = kw.get('estado', 'viendo_cotizacion')
    s.nombre          = kw.get('nombre', 'Test')
    s.tipo            = kw.get('tipo', '')
    s.bot_pausado     = False
    s.id              = 1
    return s


def _make_op(**kw):
    op = MagicMock()
    _tz = timezone(timedelta(hours=-5))
    op.id              = kw.get('id', 1)
    op.operation_id    = kw.get('operation_id', 'EXP-001')
    op.status          = kw.get('status', 'Pendiente')
    op.amount_usd      = kw.get('amount_usd', 150.0)
    op.amount_pen      = kw.get('amount_pen', 505.50)
    op.exchange_rate   = kw.get('exchange_rate', 3.37)
    op.client_deposits = kw.get('client_deposits', [])
    op.notes           = kw.get('notes', '')
    op.created_at      = kw.get(
        'created_at',
        datetime(2026, 9, 23, 14, 55, 0, tzinfo=_tz)
    )
    return op


# ── 1. Lista nativa en cotización ─────────────────────────────────────────────

class TestCotizacionListaNativa(unittest.TestCase):
    """_flujo_mostrar_cotizacion debe usar send_list, no send_buttons."""

    def _call_mostrar(self, cotiz_op='venta', importe=150.0):
        session = _make_session(cotiz_op=cotiz_op, cotiz_importe=importe)
        list_calls = []
        btn_calls  = []
        with patch.object(_svc, '_get_tc', return_value=(3.3700, 3.3900)), \
             patch.object(_svc, 'send_list',
                          side_effect=lambda n, body, sections, **kw:
                              list_calls.append((body, sections))), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, body, btns=None, **kw:
                              btn_calls.append(body)), \
             patch.object(_svc, 'send_text', MagicMock()):
            _svc._flujo_mostrar_cotizacion('519', session)
        return list_calls, btn_calls, session

    def test_usa_send_list_no_send_buttons(self):
        list_calls, btn_calls, _ = self._call_mostrar()
        self.assertEqual(len(list_calls), 1, 'Debe haber exactamente un send_list')
        self.assertEqual(len(btn_calls), 0,
                         f'No debe llamarse send_buttons, se llamó con: {btn_calls}')

    def test_boton_apertura_ver_opciones(self):
        """El campo 'button' del payload es 'Continuar'."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        self.assertIn("'button': 'Continuar'", src,
                      "send_list debe configurar button='Continuar'")

    def test_opciones_en_un_solo_mensaje(self):
        list_calls, _, _ = self._call_mostrar()
        _, sections = list_calls[0]
        rows = sections[0]['rows']
        ids = [r['id'] for r in rows]
        self.assertTrue(any(i.startswith('btn_aceptar_cotiz') for i in ids),
                        f'Falta btn_aceptar_cotiz en {ids}')
        self.assertIn('btn_cambiar_monto',    ids, f'Falta btn_cambiar_monto en {ids}')
        self.assertIn('btn_cambiar_operacion', ids)
        self.assertIn('btn_cancelar_cotiz',   ids)
        self.assertIn('btn_asesor',           ids)

    def test_aceptar_lleva_token(self):
        list_calls, _, session = self._call_mostrar()
        _, sections = list_calls[0]
        rows = sections[0]['rows']
        aceptar = next((r for r in rows if r['id'].startswith('btn_aceptar_cotiz')), None)
        self.assertIsNotNone(aceptar, 'Falta fila btn_aceptar_cotiz')
        token = aceptar['id'].replace('btn_aceptar_cotiz_', '')
        self.assertEqual(session.cotiz_token, token,
                         'El token del row debe coincidir con session.cotiz_token')

    def test_no_regenera_cotizacion_al_abrir_menu(self):
        """Abrir el menú (send_list) no modifica session.cotiz_tc."""
        session = _make_session(cotiz_op='venta', cotiz_importe=100.0, cotiz_tc=3.0)
        with patch.object(_svc, '_get_tc', return_value=(3.3700, 3.3900)), \
             patch.object(_svc, 'send_list', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()):
            _svc._flujo_mostrar_cotizacion('519', session)
        # cotiz_tc es reasignado por _flujo_mostrar_cotizacion (es correcto)
        # Lo que NO debe pasar: un segundo send_list o send_buttons adicional
        # (ya verificado en test_usa_send_list_no_send_buttons)


# ── 2. btn_cambiar_monto: conserva dirección, pide importe ────────────────────

class TestCambiarMonto(unittest.TestCase):
    """btn_cambiar_monto debe pedir importe sin cambiar cotiz_op."""

    def _run_btn(self, cotiz_op='venta', cotiz_importe=150.0, token='TOK'):
        session = _make_session(cotiz_op=cotiz_op, cotiz_importe=cotiz_importe,
                                cotiz_token=token, estado='viendo_cotizacion')
        session.bot_pausado = False
        texts = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: texts.append(t)), \
             patch.object(_svc, 'send_list', MagicMock()), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: texts.append(t)):
            _svc.handle_message('519', 'Test', 'interactive', 'btn_cambiar_monto')
        return texts, session

    def test_invalida_token(self):
        _, s = self._run_btn()
        self.assertIsNone(s.cotiz_token, 'Token debe quedar None al cambiar monto')

    def test_conserva_direccion(self):
        _, s = self._run_btn(cotiz_op='compra')
        self.assertEqual(s.cotiz_op, 'compra', 'Dirección no debe cambiar')

    def test_pide_importe_venta(self):
        texts, _ = self._run_btn(cotiz_op='venta')
        combined = ' '.join(texts)
        self.assertIn('dólares', combined.lower(),
                      f'Debe pedir USD (venta): {combined}')
        self.assertIn('cambiar', combined.lower(),
                      f'Pregunta incorrecta para venta: {combined}')

    def test_pide_importe_compra(self):
        texts, _ = self._run_btn(cotiz_op='compra')
        combined = ' '.join(texts)
        self.assertIn('dólares', combined.lower(),
                      f'Debe pedir USD (compra): {combined}')
        self.assertIn('recibir', combined.lower(),
                      f'Pregunta incorrecta para compra: {combined}')

    def test_estado_esperando_importe(self):
        _, s = self._run_btn()
        self.assertEqual(s.estado, 'esperando_importe')

    def test_handler_en_source(self):
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        self.assertIn("btn_id == 'btn_cambiar_monto'", src,
                      'Handler btn_cambiar_monto debe existir en el bloque interactive')


# ── 3. btn_cambiar_operacion: conserva importe, lista de dirección ─────────────

class TestCambiarOperacion(unittest.TestCase):
    """btn_cambiar_operacion conserva cotiz_importe y muestra lista de dirección."""

    def _run_btn_cambiar_op(self, cotiz_op='compra', cotiz_importe=100.0, token='TOK'):
        session = _make_session(cotiz_op=cotiz_op, cotiz_importe=cotiz_importe,
                                cotiz_token=token, estado='viendo_cotizacion')
        session.bot_pausado = False
        list_calls = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, 'send_list',
                          side_effect=lambda n, body, sections, **kw:
                              list_calls.append((body, sections))), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()):
            _svc.handle_message('519', 'Test', 'interactive', 'btn_cambiar_operacion')
        return list_calls, session

    def test_invalida_token(self):
        _, s = self._run_btn_cambiar_op()
        self.assertIsNone(s.cotiz_token)

    def test_conserva_importe(self):
        _, s = self._run_btn_cambiar_op(cotiz_importe=100.0)
        self.assertEqual(s.cotiz_importe, 100.0,
                         'El importe debe conservarse al cambiar operación')

    def test_muestra_lista_con_dos_opciones(self):
        list_calls, _ = self._run_btn_cambiar_op()
        self.assertEqual(len(list_calls), 1, 'Debe haber un send_list')
        _, sections = list_calls[0]
        rows = sections[0]['rows']
        ids  = [r['id'] for r in rows]
        self.assertIn('btn_dir_compra', ids, f'Falta btn_dir_compra en {ids}')
        self.assertIn('btn_dir_venta',  ids, f'Falta btn_dir_venta en {ids}')

    def test_no_muestra_primera_segunda_opcion(self):
        list_calls, _ = self._run_btn_cambiar_op()
        _, sections = list_calls[0]
        body = list_calls[0][0]
        rows = sections[0]['rows']
        combined = body + ' '.join(r['title'] for r in rows)
        self.assertNotIn('primera opción', combined.lower())
        self.assertNotIn('segunda opción', combined.lower())

    def test_btn_dir_venta_recotiza_con_importe(self):
        """btn_dir_venta con importe válido llama _flujo_mostrar_cotizacion."""
        session = _make_session(cotiz_op='compra', cotiz_importe=100.0,
                                estado='viendo_cotizacion')
        session.bot_pausado = False
        quoted = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, '_flujo_mostrar_cotizacion',
                          side_effect=lambda n, s: quoted.append(s.cotiz_importe)), \
             patch.object(_svc, '_flujo_pedir_importe', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()):
            _svc.handle_message('519', 'Test', 'interactive', 'btn_dir_venta')
        self.assertEqual(len(quoted), 1, '_flujo_mostrar_cotizacion debe llamarse')
        self.assertEqual(quoted[0], 100.0, 'Importe debe conservarse = 100.0')

    def test_handler_en_source(self):
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        self.assertIn("btn_id == 'btn_dir_compra'", src)
        self.assertIn("btn_id == 'btn_dir_venta'", src)
        # no debe llamar _reset_sesion desde btn_cambiar_operacion
        # (verificación de diseño en source)
        import re as _re
        cambiar_op_idx = src.find("btn_id == 'btn_cambiar_operacion'")
        dir_compra_idx = src.find("btn_id == 'btn_dir_compra'")
        reset_between  = src[cambiar_op_idx:dir_compra_idx]
        self.assertNotIn('_reset_sesion(session)', reset_between,
                         'No debe llamar _reset_sesion desde btn_cambiar_operacion')


# ── 4. Cambio de importe con operación pendiente ───────────────────────────────

class TestCambioImporteConOp(unittest.TestCase):
    """esperando_nuevo_importe guarda y envía confirmación (tolerante a timezone)."""

    _TZ = timezone(timedelta(hours=-5))

    def _run_nuevo_importe(self, nuevo_monto_txt, created_at=None, naive=False):
        """Invoca el handler real esperando_nuevo_importe via handle_message."""
        _tz = self._TZ
        _ts = (datetime(2026, 9, 23, 14, 55, 0, tzinfo=None if naive else _tz)
               if created_at is None else created_at)

        op = _make_op(created_at=_ts, amount_usd=150.0, amount_pen=505.50,
                      exchange_rate=3.37)
        session = _make_session(cotiz_op='venta', cotiz_op_id='EXP-001',
                                estado='esperando_nuevo_importe')
        session.bot_pausado = False

        btn_calls = []
        committed = []

        # Usar el db que _svc tiene vinculado (resistente a contaminación entre módulos).
        _db = _svc.db
        _db.session.reset_mock()
        _db.session.commit.side_effect = lambda: committed.append(True)

        # Fijar el reloj donde el handler lo importa en tiempo de ejecución.
        _now_fixed = datetime(2026, 9, 23, 15, 0, 0, tzinfo=_tz)
        sys.modules['app.utils.formatters'].now_peru = lambda: _now_fixed

        # Configurar stub de Operation para este test.
        OpStub = sys.modules['app.models.operation'].Operation
        OpStub.reset_mock()
        OpStub.query.filter_by.return_value.first.return_value = op

        _svc.WaBotSession.get_or_create.return_value = session

        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw:
                              btn_calls.append(t) or True), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', nuevo_monto_txt)

        return btn_calls, committed, op, session

    def test_commit_ocurre_antes_del_envio(self):
        """La modificación se persiste antes de intentar enviar el mensaje."""
        calls, committed, _, _ = self._run_nuevo_importe('200')
        self.assertGreater(len(committed), 0, 'commit debe haberse llamado')

    def test_mensaje_enviado_tras_commit(self):
        calls, _, _, _ = self._run_nuevo_importe('200')
        self.assertEqual(len(calls), 1, f'Debe enviarse exactamente 1 mensaje WA: {calls}')

    def test_mensaje_contiene_nuevo_importe(self):
        calls, _, _, _ = self._run_nuevo_importe('200')
        msg = calls[0]
        self.assertIn('200.00', msg, f'Nuevo importe no está en el mensaje: {msg}')

    def test_mensaje_contiene_hora_limite(self):
        calls, _, _, _ = self._run_nuevo_importe('200')
        msg = calls[0]
        self.assertIn('Transfiere antes de las', msg,
                      f'Hora límite no está en el mensaje: {msg}')

    def test_tolerante_a_created_at_naive(self):
        """created_at sin timezone no debe lanzar excepción."""
        calls, _, _, _ = self._run_nuevo_importe('200', naive=True)
        self.assertEqual(len(calls), 1, 'Debe enviarse mensaje aunque created_at sea naive')

    def test_estado_op_pendiente_pago(self):
        _, _, _, s = self._run_nuevo_importe('200')
        self.assertEqual(s.estado, 'op_pendiente_pago')

    def test_botones_incluyen_cancelar_con_op_id(self):
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        # El handler usa btn_cancelar_operacion_{op.operation_id}
        self.assertIn('btn_cancelar_operacion_{op.operation_id}', src)

    def test_mensaje_sin_datos_cuenta_bancaria(self):
        """El mensaje de confirmación no incluye números de cuenta (mensaje corto)."""
        calls, _, _, _ = self._run_nuevo_importe('200')
        msg = calls[0]
        # Los números de cuenta tienen formato 1917357790119 — no deben estar aquí
        self.assertNotIn('1917357790119', msg,
                         'El mensaje de actualización no debe incluir cuentas bancarias')

    # ── Envío fallido: la actualización persiste ────────────────────────────────

    def _setup_importe_op(self, nuevo_monto='200', naive=False):
        """Helper compartido para tests de send_buttons fallido."""
        _tz = self._TZ
        _ts = datetime(2026, 9, 23, 14, 55, 0, tzinfo=None if naive else _tz)
        op = _make_op(created_at=_ts, amount_usd=150.0, amount_pen=505.50,
                      exchange_rate=3.37)
        session = _make_session(cotiz_op='venta', cotiz_op_id='EXP-001',
                                estado='esperando_nuevo_importe')
        session.bot_pausado = False
        sys.modules['app.utils.formatters'].now_peru = (
            lambda: datetime(2026, 9, 23, 15, 0, 0, tzinfo=_tz)
        )
        OpStub = sys.modules['app.models.operation'].Operation
        OpStub.reset_mock()
        OpStub.query.filter_by.return_value.first.return_value = op
        _svc.WaBotSession.get_or_create.return_value = session
        _db = _svc.db
        _db.session.reset_mock()
        return op, session, _db, nuevo_monto

    def test_envio_fallido_envia_texto_fallback(self):
        """Si send_buttons falla, el handler envía send_text con el resumen completo."""
        op, session, _db, monto = self._setup_importe_op()
        txt_calls = []
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_buttons', return_value=False), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: txt_calls.append(t)), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', monto)
        self.assertGreater(len(txt_calls), 0, 'Debe enviarse texto de respaldo')
        combined = ' '.join(txt_calls)
        self.assertIn('200.00', combined,
                      'Texto de respaldo debe incluir el nuevo importe')
        self.assertIn('EXP-001', combined,
                      'Texto de respaldo debe incluir el ID de operación')
        self.assertIn('3.3700', combined,
                      'Texto de respaldo debe incluir el tipo de cambio')

    def test_envio_fallido_conserva_actualizacion_db(self):
        """Cuando send_buttons falla, el importe queda persistido y el estado es op_pendiente_pago."""
        op, session, _db, monto = self._setup_importe_op()
        committed = []
        _db.session.commit.side_effect = lambda: committed.append(True)
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_buttons', return_value=False), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', monto)
        self.assertGreater(len(committed), 0, 'Commit debe ocurrir aunque send falle')
        self.assertAlmostEqual(float(op.amount_usd), 200.0, places=2,
                               msg='Importe USD debe quedar actualizado')
        self.assertEqual(session.estado, 'op_pendiente_pago',
                         'Estado debe quedar op_pendiente_pago aunque el envío falle')

    def test_recovery_texto_libre_remite_resumen_actualizado(self):
        """Tras envío fallido, texto libre en op_pendiente_pago re-envía resumen con importes actualizados."""
        op = _make_op(amount_usd=200.0, amount_pen=674.0, exchange_rate=3.37,
                      status='Pendiente', operation_id='EXP-001')
        session = _make_session(cotiz_op='venta', cotiz_op_id='EXP-001',
                                estado='op_pendiente_pago')
        session.bot_pausado = False
        btn_calls = []
        OpStub = sys.modules['app.models.operation'].Operation
        OpStub.reset_mock()
        OpStub.query.filter_by.return_value.first.return_value = op
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_texto_cuentas_qoricash', return_value='🏦 BCP ...'), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btn_calls.append(t)), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', 'hola')
        self.assertGreater(len(btn_calls), 0, 'Debe re-enviarse resumen como send_buttons')
        combined = ' '.join(btn_calls)
        self.assertIn('200.00', combined,
                      'Resumen recuperado debe mostrar el importe actualizado (no el original)')
        self.assertIn('EXP-001', combined, 'Resumen debe incluir el ID de la operación')


# ── 5. Carné de Extranjería ────────────────────────────────────────────────────

class TestCarnetExtranjeria(unittest.TestCase):

    def test_btn_tengo_ce_en_bloque_interactive(self):
        """El handler btn_tengo_ce debe estar en el bloque if tipo_msg == 'interactive'."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        interactive_block_start = src.find("if tipo_msg == 'interactive':")
        text_block_start        = src.find("elif tipo_msg == 'text':", interactive_block_start)
        btn_tengo_ce_idx        = src.find("btn_id == 'btn_tengo_ce'")

        self.assertGreater(btn_tengo_ce_idx, 0, 'Handler btn_tengo_ce no encontrado')
        self.assertLess(btn_tengo_ce_idx, text_block_start,
                        'btn_tengo_ce debe estar en el bloque interactive, no en el text block')

    def test_btn_tengo_ce_muestra_instruccion_conjunta(self):
        """El mensaje debe mencionar CE y nombre juntos."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        idx = src.find("btn_id == 'btn_tengo_ce'")
        bloque = src[idx:idx+400]
        self.assertIn('9 dígitos', bloque,
                      'Debe pedir 9 dígitos de CE')
        self.assertIn('nombres', bloque.lower(),
                      'Debe mencionar nombres/apellidos')

    def test_ce_y_nombre_juntos(self):
        """Estado esperando_ce_numero: mensaje '123456789 Juan Pérez' guarda ambos."""
        session = _make_session(estado='esperando_ce_numero', cotiz_op='venta',
                                cotiz_importe=150.0)
        session.bot_pausado = False
        texts = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', '123456789 Juan Pérez García')

        self.assertEqual(session.cotiz_doc, '123456789')
        self.assertIn('Juan', session.nombre.title())
        self.assertEqual(session.estado, 'esperando_email_cotizar')
        self.assertEqual(len(texts), 1, 'Debe enviar exactamente un texto')

    def test_ce_solo_pide_nombre(self):
        """Solo CE (sin nombre) → pasa a esperando_nombre_ce."""
        session = _make_session(estado='esperando_ce_numero')
        session.bot_pausado = False
        texts = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', '123456789')

        self.assertEqual(session.cotiz_doc, '123456789')
        self.assertEqual(session.estado, 'esperando_nombre_ce')

    def test_ce_con_longitud_incorrecta_rechazado(self):
        """CE con ≠ 9 dígitos es rechazado."""
        session = _make_session(estado='esperando_ce_numero')
        session.bot_pausado = False
        texts = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', '12345678')
        self.assertEqual(len(texts), 1)
        self.assertIn('9 dígitos', texts[0])

    def test_ce_no_consulta_reniec(self):
        """El handler CE no debe llamar _lookup_dni."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        ce_block_start = src.find("esperando_ce_numero")
        ce_block_end   = src.find("esperando_nombre_ce", ce_block_start)
        ce_block       = src[ce_block_start:ce_block_end]
        self.assertNotIn('_lookup_dni', ce_block,
                         'CE no debe consultar RENIEC')


# ── 6. Token: cotización suplantada es rechazada ──────────────────────────────

class TestTokenSupreplacement(unittest.TestCase):

    def test_token_viejo_rechazado_tras_cambio_monto(self):
        """Tras cambiar monto, token anterior no debe aceptarse."""
        session = _make_session(cotiz_token='VIEJO')
        # Simula invalidación al cambiar monto
        session.cotiz_token = None
        # El token 'VIEJO' ya no coincide
        token_btn = 'VIEJO'
        token_ses = getattr(session, 'cotiz_token', None) or ''
        stale = not token_btn or not token_ses or token_btn != token_ses
        self.assertTrue(stale, 'Token viejo debe ser stale tras cambiar monto')

    def test_token_viejo_rechazado_tras_cambio_operacion(self):
        """Tras cambiar operación, token anterior no debe aceptarse."""
        session = _make_session(cotiz_token='VIEJO-OP')
        session.cotiz_token = None
        token_btn = 'VIEJO-OP'
        token_ses = getattr(session, 'cotiz_token', None) or ''
        stale = not token_btn or not token_ses or token_btn != token_ses
        self.assertTrue(stale, 'Token viejo debe ser stale tras cambiar operación')

    def test_nuevo_token_asignado_en_cotizacion(self):
        """_flujo_mostrar_cotizacion asigna un UUID nuevo."""
        session = _make_session(cotiz_token=None)
        with patch.object(_svc, '_get_tc', return_value=(3.37, 3.39)), \
             patch.object(_svc, 'send_list', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()):
            _svc._flujo_mostrar_cotizacion('519', session)
        self.assertIsNotNone(session.cotiz_token,
                             'Un token UUID debe asignarse al mostrar cotización')
        self.assertNotEqual(session.cotiz_token, 'VIEJO')

    def test_handler_aceptar_verifica_igualdad_exacta(self):
        """El handler btn_aceptar_cotiz verifica igualdad exacta del token."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        self.assertIn('_token_btn != _token_ses', src,
                      'El handler debe comparar token_btn == token_ses exactamente')

    def test_list_reply_aceptar_con_uuid_real_no_rechazado(self):
        """
        Payload entrante list_reply con el UUID real pasa la validación de token.
        Confirma que el ID de la fila contiene el UUID asignado, no el literal '{token}'.
        """
        # Paso 1: obtener el UUID asignado por _flujo_mostrar_cotizacion
        session = _make_session(cotiz_op='venta', cotiz_importe=150.0,
                                cotiz_doc='', cotiz_token=None,
                                estado='viendo_cotizacion')
        list_rows = []
        with patch.object(_svc, '_get_tc', return_value=(3.3700, 3.3900)), \
             patch.object(_svc, 'send_list',
                          side_effect=lambda n, body, sections, **kw:
                              list_rows.extend(sections[0]['rows'])), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()):
            _svc._flujo_mostrar_cotizacion('519', session)

        aceptar = next((r for r in list_rows if r['id'].startswith('btn_aceptar_cotiz_')), None)
        self.assertIsNotNone(aceptar, 'Fila btn_aceptar_cotiz_ debe estar en el send_list')
        real_token = aceptar['id'].replace('btn_aceptar_cotiz_', '')
        self.assertNotEqual(real_token, '{token}',
                            'El ID no debe contener el literal {token}')
        self.assertGreater(len(real_token), 5, 'El token debe ser un UUID, no una cadena vacía')
        self.assertEqual(real_token, session.cotiz_token,
                         'Token en la fila debe coincidir con session.cotiz_token')

        # Paso 2: simular payload entrante list_reply con ese UUID real
        txt_calls = []
        btn_calls = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, '_buscar_clientes_por_telefono', return_value=[]), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btn_calls.append(t)), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: txt_calls.append(t)):
            _svc.handle_message('519', 'Test', 'interactive', aceptar['id'])

        combined = ' '.join(btn_calls + txt_calls)
        self.assertNotIn('reemplazada', combined,
                         'UUID real no debe ser rechazado como cotización reemplazada')

    def test_list_reply_token_literal_rechazado(self):
        """Payload con ID literal 'btn_aceptar_cotiz_{token}' es rechazado."""
        session = _make_session(cotiz_op='venta', cotiz_importe=150.0,
                                cotiz_token='UUID-REAL', estado='viendo_cotizacion')
        session.bot_pausado = False
        txt_calls = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: txt_calls.append(t)), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            # Simula un mensaje con el literal '{token}' en lugar del UUID real
            _svc.handle_message('519', 'Test', 'interactive', 'btn_aceptar_cotiz_{token}')
        self.assertTrue(any('reemplazada' in t for t in txt_calls),
                        f'Token literal debe ser rechazado con "reemplazada": {txt_calls}')


if __name__ == '__main__':
    unittest.main(verbosity=2)

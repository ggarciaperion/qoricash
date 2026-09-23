#!/usr/bin/env python3
"""
tests/test_frictionless_tc.py

Pruebas para el flujo de consulta de TC sin fricción (identificación diferida).

Regla central: cualquier persona puede consultar el TC y cotizar sin ingresar
documentos. La identificación se solicita únicamente al aceptar una cotización.

Ejecutar:
    python3 -m pytest tests/test_frictionless_tc.py -v
"""
import sys, os, types, re, unittest
from unittest.mock import MagicMock, patch
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
    sys.modules['app.models.wa_bot_session'].WaBotSession = MagicMock()
    sys.modules['app.models.wa_message'].WaMessage = MagicMock()
    sys.modules['app.models.operation'].Operation = MagicMock()
    sys.modules['app.services.notification_service'].NotificationService = MagicMock()
    sys.modules['app.services.email_service'].EmailService = MagicMock()
    # requests stub with HTTPError
    req_stub = types.ModuleType('requests')
    req_stub.post = MagicMock(return_value=MagicMock(ok=True, status_code=200,
                                                      raise_for_status=MagicMock()))
    req_stub.get  = MagicMock(return_value=MagicMock(ok=True, status_code=200))
    class _HTTPError(Exception): pass
    req_stub.HTTPError = _HTTPError
    req_exc = types.ModuleType('requests.exceptions')
    req_exc.HTTPError = _HTTPError
    req_stub.exceptions = req_exc
    sys.modules['requests.exceptions'] = req_exc
    sys.modules['requests'] = req_stub
    return db

DB = _build_stubs()

SVC_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_svc = types.ModuleType('wa_bot_frictionless')
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)

_TZ = timezone(timedelta(hours=-5))
TC_COMPRA = 3.3700
TC_VENTA  = 3.3900


def _make_session(**kw):
    s = MagicMock()
    s.cotiz_op        = kw.get('cotiz_op', '')
    s.cotiz_importe   = kw.get('cotiz_importe', 0.0)
    s.cotiz_tc        = kw.get('cotiz_tc', 0.0)
    s.cotiz_doc       = kw.get('cotiz_doc', '')
    s.cotiz_email     = kw.get('cotiz_email', '')
    s.cotiz_op_id     = kw.get('cotiz_op_id', '')
    s.cotiz_cuenta    = kw.get('cotiz_cuenta', '')
    s.cotiz_token     = kw.get('cotiz_token', None)
    s.cotiz_intentos  = 0
    s.cotiz_timestamp = None
    s.estado          = kw.get('estado', 'inicio')
    s.nombre          = kw.get('nombre', '')
    s.tipo            = kw.get('tipo', '')
    s.bot_pausado     = kw.get('bot_pausado', False)
    s.updated_at      = datetime(2026, 9, 23, 14, 0, 0, tzinfo=_TZ)
    s.id              = 1
    return s


def _make_op(**kw):
    op = MagicMock()
    op.id           = 42
    op.operation_id = kw.get('operation_id', 'EXP-001')
    op.status       = kw.get('status', 'Pendiente')
    op.amount_usd   = kw.get('amount_usd', 500.0)
    op.amount_pen   = kw.get('amount_pen', 1685.0)
    op.exchange_rate= kw.get('exchange_rate', 3.3700)
    op.client_deposits = kw.get('deposits', [])
    op.notes        = ''
    op.created_at   = datetime(2026, 9, 23, 14, 55, 0, tzinfo=_TZ)
    return op


def _run(session, msg_type, texto, *, tc=(TC_COMPRA, TC_VENTA),
         op_activa=None, clientes_tel=None):
    """Invoca handle_message y devuelve (btn_calls, txt_calls, list_calls)."""
    btn_calls  = []
    txt_calls  = []
    list_calls = []

    _svc.WaBotSession.get_or_create.return_value = session
    sys.modules['app.utils.formatters'].now_peru = (
        lambda: datetime(2026, 9, 23, 15, 0, 0, tzinfo=_TZ)
    )

    with patch.object(_svc, '_get_tc', return_value=tc), \
         patch.object(_svc, '_typing', MagicMock()), \
         patch.object(_svc, '_sesion_inactiva', return_value=False), \
         patch.object(_svc, '_operacion_activa_cliente', return_value=op_activa), \
         patch.object(_svc, '_buscar_clientes_por_telefono',
                      return_value=clientes_tel if clientes_tel is not None else []), \
         patch.object(_svc, '_buscar_cliente', return_value=None), \
         patch.object(_svc, 'send_buttons',
                      side_effect=lambda n, t, b=None, **kw: btn_calls.append(t)), \
         patch.object(_svc, 'send_buttons_image',
                      side_effect=lambda n, u, t, b, **kw: btn_calls.append(t)), \
         patch.object(_svc, 'send_text',
                      side_effect=lambda n, t: txt_calls.append(t)), \
         patch.object(_svc, 'send_list',
                      side_effect=lambda n, t, s, **kw: list_calls.append(t)):
        _svc.handle_message('519', 'Test', msg_type, texto)

    return btn_calls, txt_calls, list_calls


# ──────────────────────────────────────────────────────────────────────────────
class TestTCPublicSinFriccion(unittest.TestCase):
    """El TC público se muestra sin pedir documentos."""

    def test_inactividad_consulta_tc_muestra_tasas_sin_documentos(self):
        """Cierre por inactividad → 'cuanto esta la cotizacion' → TC público, sin ID."""
        session = _make_session(estado='inicio')
        btn, txt, lst = _run(session, 'text', 'cuanto esta la cotizacion')

        combined = ' '.join(btn + txt + lst)
        # TC disponible en la respuesta
        self.assertIn('3.3700', combined,
                      'Debe mostrar TC compra sin pedir documentos')
        self.assertIn('3.3900', combined,
                      'Debe mostrar TC venta sin pedir documentos')
        # No pide documento
        self.assertFalse(
            any('dni' in m.lower() or 'ruc' in m.lower() or 'documento' in m.lower()
                for m in btn + txt + lst),
            f'No debe pedir DNI/RUC/documento al consultar TC. Respuestas: {btn + txt}'
        )
        # Estado correcto para elegir dirección
        self.assertEqual(session.estado, 'eligiendo_operacion')

    def test_texto_tc_sin_cuenta(self):
        """'¿a cuánto está el dólar?' desde estado inicio → TC público."""
        session = _make_session(estado='inicio')
        btn, txt, lst = _run(session, 'text', 'a cuanto esta el dolar')

        combined = ' '.join(btn + txt + lst)
        self.assertIn('3.3700', combined)
        self.assertFalse(
            any('dni' in m.lower() for m in btn + txt + lst),
            'No debe pedir DNI'
        )

    def test_tc_literal_sin_cuenta(self):
        """'TC' o 'precio del dólar' → TC público."""
        session = _make_session(estado='inicio')
        btn, txt, lst = _run(session, 'text', 'TC')

        combined = ' '.join(btn + txt + lst)
        self.assertIn('3.37', combined)

    def test_btn_cotizar_muestra_tc(self):
        """Botón 'Ver tipo de cambio' debe mostrar TC + dirección."""
        session = _make_session(estado='menu_mostrado')
        btn, txt, lst = _run(session, 'interactive', 'btn_cotizar')

        combined = ' '.join(btn + txt + lst)
        self.assertIn('3.3700', combined,
                      'btn_cotizar debe mostrar TC público')
        self.assertEqual(session.estado, 'eligiendo_operacion')

    def test_tc_no_disponible_no_muestra_cero(self):
        """Cuando TC no está disponible → mensaje claro, nunca '0.0000'."""
        session = _make_session(estado='inicio')
        btn, txt, lst = _run(session, 'text', 'cuanto esta el dolar', tc=(0, 0))

        combined = ' '.join(btn + txt + lst)
        self.assertNotIn('0.0000', combined,
                         'No debe mostrar tasa cero')
        self.assertNotIn('S/ 0', combined,
                         'No debe mostrar S/ 0')
        # Debe informar que no está disponible
        self.assertTrue(
            any('disponible' in m.lower() or 'momento' in m.lower()
                for m in btn + txt + lst),
            f'Debe informar que TC no está disponible. Resp: {btn + txt}'
        )


# ──────────────────────────────────────────────────────────────────────────────
class TestSaludoConTC(unittest.TestCase):
    """El saludo inicial incluye TC público."""

    def test_hola_nuevo_cliente_incluye_tc(self):
        """'Hola' de cliente nuevo → mensaje con tasas compra y venta."""
        session = _make_session(estado='inicio')
        btn, txt, lst = _run(session, 'text', 'hola')

        combined = ' '.join(btn + txt + lst)
        self.assertIn('3.3700', combined,
                      'Saludo debe incluir TC compra')
        self.assertIn('3.3900', combined,
                      'Saludo debe incluir TC venta')
        self.assertEqual(session.estado, 'menu_mostrado')

    def test_hola_cliente_conocido_incluye_tc(self):
        """'Hola' de cliente reconocido por teléfono → TC en el saludo."""
        from unittest.mock import MagicMock as _MM
        c = _MM()
        c.nombres = 'Juan Perez'
        c.razon_social = ''
        c.dni = '12345678'
        c.status = 'Activo'

        session = _make_session(estado='inicio')
        btn, txt, lst = _run(session, 'text', 'hola', clientes_tel=[c])

        combined = ' '.join(btn + txt + lst)
        self.assertIn('3.3700', combined)

    def test_hola_tc_no_disponible_no_muestra_cero(self):
        """Si TC no disponible, saludo no muestra ceros."""
        session = _make_session(estado='inicio')
        btn, txt, lst = _run(session, 'text', 'hola', tc=(0, 0))

        combined = ' '.join(btn + txt + lst)
        self.assertNotIn('0.0000', combined)
        self.assertNotIn('S/ 0', combined)


# ──────────────────────────────────────────────────────────────────────────────
class TestCotizacionDirectaSinID(unittest.TestCase):
    """Cliente con dirección+importe → cotización directa sin pedir ID."""

    def test_importe_y_direccion_completos_cotiza_directo(self):
        """'Tengo 500 dolares y quiero soles' → cotización sin pedir doc."""
        session = _make_session(estado='inicio')
        btn, txt, lst = _run(session, 'text', 'tengo 500 dolares y quiero soles')

        combined = ' '.join(btn + txt + lst)
        # Debe mostrar cotización (send_list recibe el resumen)
        self.assertTrue(
            any('500' in m for m in btn + txt + lst),
            f'Debe cotizar 500 USD. Resp: {btn + txt + lst}'
        )
        self.assertFalse(
            any('dni' in m.lower() or 'documento' in m.lower()
                for m in btn + txt + lst),
            'No debe pedir documento antes de mostrar cotización'
        )
        self.assertEqual(session.estado, 'viendo_cotizacion')

    def test_importe_en_sesion_cotiza_directo(self):
        """Sesión con cotiz_op y cotiz_importe → ruta P3 muestra cotización."""
        session = _make_session(
            estado='inicio', cotiz_op='venta', cotiz_importe=300.0
        )
        # Simular _identificar_y_cotizar_directo directamente
        list_calls = []
        btn_calls  = []
        with patch.object(_svc, '_get_tc', return_value=(TC_COMPRA, TC_VENTA)), \
             patch.object(_svc, '_buscar_cliente', return_value=None), \
             patch.object(_svc, '_buscar_clientes_por_telefono', return_value=[]), \
             patch.object(_svc, 'send_list',
                          side_effect=lambda n, t, s, **kw: list_calls.append(t)), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btn_calls.append(t)):
            _svc._identificar_y_cotizar_directo('519', session)

        combined = ' '.join(btn_calls + list_calls)
        self.assertFalse(
            any('dni' in m.lower() or 'documento' in m.lower()
                for m in btn_calls + list_calls),
            f'P3 no debe pedir doc con dirección+importe conocidos. Resp: {btn_calls + list_calls}'
        )
        self.assertEqual(session.estado, 'viendo_cotizacion')


# ──────────────────────────────────────────────────────────────────────────────
class TestIdentificacionAlAceptar(unittest.TestCase):
    """La identificación se solicita al aceptar, no antes."""

    def test_aceptar_cotizacion_sin_doc_pide_identificacion(self):
        """Cliente sin cotiz_doc que acepta la cotización → flujo de ID."""
        import uuid
        _token = str(uuid.uuid4())
        session = _make_session(
            estado='viendo_cotizacion',
            cotiz_op='venta', cotiz_importe=500.0, cotiz_tc=3.3700,
            cotiz_doc='',  # sin identificar
            cotiz_token=_token,
        )
        # cotiz_timestamp = None haría expirar la cotización; se parchea _cotiz_expirada
        _svc.WaBotSession.get_or_create.return_value = session
        sys.modules['app.utils.formatters'].now_peru = (
            lambda: datetime(2026, 9, 23, 15, 0, 0, tzinfo=_TZ)
        )
        btn_calls = []
        txt_calls = []
        with patch.object(_svc, '_get_tc', return_value=(TC_COMPRA, TC_VENTA)), \
             patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, '_operacion_activa_cliente', return_value=None), \
             patch.object(_svc, '_buscar_clientes_por_telefono', return_value=[]), \
             patch.object(_svc, '_buscar_cliente', return_value=None), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btn_calls.append(t)), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: txt_calls.append(t)), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'interactive', f'btn_aceptar_cotiz_{_token}')
        btn = btn_calls
        txt = txt_calls
        lst = []

        combined = ' '.join(btn + txt + lst)
        # Debe preguntar si ya es cliente o quiere registrarse
        self.assertTrue(
            any('cliente' in m.lower() or 'registr' in m.lower() or
                'dni' in m.lower() or 'documento' in m.lower()
                for m in btn + txt + lst),
            f'Debe solicitar identificación al aceptar. Resp: {btn + txt + lst}'
        )

    def test_consulta_tc_no_crea_operacion(self):
        """Consultar TC no debe cambiar estado a uno que crea operación."""
        session = _make_session(estado='inicio')
        _run(session, 'text', 'cuanto esta el dolar')

        self.assertNotEqual(session.estado, 'op_pendiente_pago',
                            'Solo consultar TC no debe crear operación')
        self.assertNotEqual(session.estado, 'confirmando_operacion',
                            'Solo consultar TC no debe llegar a confirmación')


# ──────────────────────────────────────────────────────────────────────────────
class TestTCConOperacionActiva(unittest.TestCase):
    """Cliente con op_pendiente_pago que consulta TC → operación intacta."""

    def _run_op_activa_tc(self, pregunta, tc=(TC_COMPRA, TC_VENTA)):
        op = _make_op(operation_id='EXP-009', status='Pendiente',
                      amount_usd=500.0, amount_pen=1685.0, exchange_rate=3.3700)
        session = _make_session(
            estado='op_pendiente_pago',
            cotiz_op='venta', cotiz_op_id='EXP-009',
            cotiz_tc=3.3700,
        )
        OpStub = sys.modules['app.models.operation'].Operation
        OpStub.query.filter_by.return_value.first.return_value = op

        btn, txt, lst = _run(session, 'text', pregunta,
                             tc=tc, op_activa=op)
        return session, btn, txt, lst, op

    def test_consulta_tc_no_modifica_estado_op_pendiente(self):
        """'¿cuánto está el dólar?' con op activa → estado sigue op_pendiente_pago."""
        session, btn, txt, lst, op = self._run_op_activa_tc(
            'cuanto esta el dolar'
        )
        self.assertEqual(session.estado, 'op_pendiente_pago',
                         'Estado no debe cambiar al consultar TC con op activa')

    def test_consulta_tc_muestra_tasa_vigente(self):
        """Consulta de TC con op activa → muestra TC vigente."""
        session, btn, txt, lst, op = self._run_op_activa_tc(
            'tipo de cambio'
        )
        combined = ' '.join(btn + txt + lst)
        self.assertIn('3.3700', combined,
                      'Debe mostrar TC vigente aunque haya op activa')

    def test_consulta_tc_distingue_tc_pactado_si_difiere(self):
        """Cuando TC vigente difiere del pactado, debe mencionarlo."""
        session = _make_session(
            estado='op_pendiente_pago',
            cotiz_op='venta', cotiz_op_id='EXP-009',
            cotiz_tc=3.3500,  # TC pactado distinto al vigente
        )
        op = _make_op(operation_id='EXP-009', status='Pendiente',
                      exchange_rate=3.3500)
        OpStub = sys.modules['app.models.operation'].Operation
        OpStub.query.filter_by.return_value.first.return_value = op

        btn, txt, lst = _run(session, 'text', 'cuanto esta el dolar',
                             tc=(TC_COMPRA, TC_VENTA), op_activa=op)
        combined = ' '.join(btn + txt + lst)
        # Debe mencionar el TC pactado
        self.assertIn('3.3500', combined,
                      'Debe distinguir TC vigente del TC pactado cuando difieren')

    def test_consulta_tc_no_disponible_con_op_activa(self):
        """TC no disponible con op activa → mensaje claro sin ceros ni reinicio."""
        session, btn, txt, lst, op = self._run_op_activa_tc(
            'cuanto esta el dolar', tc=(0, 0)
        )
        combined = ' '.join(btn + txt + lst)
        self.assertNotIn('0.0000', combined)
        self.assertEqual(session.estado, 'op_pendiente_pago',
                         'Estado no debe cambiar si TC no disponible')

    def test_codigo_voucher_no_confundido_con_consulta_tc(self):
        """Voucher alfanumérico no debe activar respuesta de TC."""
        session = _make_session(
            estado='op_pendiente_pago', cotiz_op='venta', cotiz_op_id='EXP-009'
        )
        op = _make_op(operation_id='EXP-009', status='Pendiente')
        OpStub = sys.modules['app.models.operation'].Operation
        OpStub.query.filter_by.return_value.first.return_value = op

        btn, txt, lst = _run(session, 'text', 'BCP123456',
                             tc=(TC_COMPRA, TC_VENTA), op_activa=op)
        combined = ' '.join(btn + txt + lst)
        # No debe mostrar mensaje de TC
        self.assertFalse(
            any('vigente' in m.lower() and 'tc' in m.lower()
                for m in btn + txt + lst),
            'Un código de voucher no debe activar respuesta de TC'
        )


# ──────────────────────────────────────────────────────────────────────────────
class TestInterpretacionSolicitudes(unittest.TestCase):
    """_interpretar_solicitud detecta dirección e importe correctamente."""

    def _interp(self, texto, cotiz_op=''):
        s = _make_session(cotiz_op=cotiz_op)
        return _svc._interpretar_solicitud(texto, s)

    def test_quiero_comprar_dolares_detecta_compra(self):
        r = self._interp('quiero comprar dolares')
        self.assertEqual(r['tipo'], 'compra')

    def test_tengo_dolares_detecta_venta(self):
        r = self._interp('tengo dolares y quiero soles')
        self.assertEqual(r['tipo'], 'venta')

    def test_500_dolares_extrae_importe(self):
        r = self._interp('tengo 500 dolares y quiero soles')
        self.assertEqual(r['tipo'], 'venta')
        self.assertAlmostEqual(r['importe'], 500.0)

    def test_consulta_pura_no_tiene_tipo_ni_importe(self):
        """'cuanto esta la cotizacion' → tipo y importe None."""
        r = self._interp('cuanto esta la cotizacion')
        self.assertIsNone(r['tipo'])
        self.assertIsNone(r['importe'])

    def test_flujo_tc_publico_disponible(self):
        """_flujo_tc_publico existe y llama send_buttons con TC."""
        btn_calls = []
        with patch.object(_svc, '_get_tc', return_value=(TC_COMPRA, TC_VENTA)), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btn_calls.append(t)):
            result = _svc._flujo_tc_publico('519')

        self.assertTrue(result, '_flujo_tc_publico debe devolver True cuando TC disponible')
        combined = ' '.join(btn_calls)
        self.assertIn('3.3700', combined)
        self.assertIn('3.3900', combined)

    def test_flujo_tc_publico_no_disponible(self):
        """_flujo_tc_publico devuelve False cuando TC no disponible."""
        btn_calls = []
        with patch.object(_svc, '_get_tc', return_value=(0, 0)), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btn_calls.append(t)):
            result = _svc._flujo_tc_publico('519')

        self.assertFalse(result)
        combined = ' '.join(btn_calls)
        self.assertNotIn('0.0000', combined)


# ──────────────────────────────────────────────────────────────────────────────
class TestAceptarSinPasoIntermedio(unittest.TestCase):
    """Aceptar cotización lleva directo a doc/cuenta, sin '¿Ya eres cliente?'."""

    def _aceptar_cotizacion(self, session, clientes_tel=None):
        """Envía btn_aceptar_cotiz con el token correcto y devuelve respuestas."""
        import uuid
        _token = str(uuid.uuid4())
        session.cotiz_token = _token
        session.estado = 'viendo_cotizacion'
        btn, txt, lst = _run(session, 'interactive', f'btn_aceptar_cotiz_{_token}',
                             clientes_tel=clientes_tel)
        return btn, txt, lst

    def test_sin_id_pide_documento_directo_sin_pregunta_cliente(self):
        """P3: sin cotiz_doc, sin match de teléfono → pide doc, sin '¿Ya eres cliente?'."""
        session = _make_session(
            cotiz_op='venta', cotiz_importe=500.0, cotiz_tc=TC_COMPRA,
            cotiz_doc='',
        )
        with patch.object(_svc, '_cotiz_expirada', return_value=False):
            btn, txt, lst = self._aceptar_cotizacion(session)

        combined = ' '.join(btn + txt + lst)
        # No debe aparecer la pregunta intermedia eliminada
        self.assertFalse(
            any('ya eres cliente' in m.lower() for m in btn + txt + lst),
            f'No debe preguntar "¿Ya eres cliente?". Resp: {btn}'
        )
        # Sí debe pedir documento (el texto directo)
        self.assertTrue(
            any('dni' in m.lower() or 'continuar' in m.lower()
                for m in btn + txt + lst),
            f'Debe pedir DNI directamente. Resp: {btn}'
        )
        self.assertEqual(session.estado, 'esperando_id_cotizar')

    def test_con_id_en_sesion_no_vuelve_a_pedir_documento(self):
        """P1: cotiz_doc ya fijado + cliente activo → no pide doc otra vez."""
        from unittest.mock import MagicMock as _MM
        client_mock = _MM()
        client_mock.status = 'Activo'
        client_mock.nombres = 'Maria'
        client_mock.razon_social = ''
        client_mock.bank_accounts = []

        session = _make_session(
            cotiz_op='venta', cotiz_importe=500.0, cotiz_tc=TC_COMPRA,
            cotiz_doc='12345678',
        )
        btn, txt, lst = [], [], []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_operacion_activa_cliente', return_value=None), \
             patch.object(_svc, '_buscar_cliente', return_value=client_mock), \
             patch.object(_svc, '_buscar_clientes_por_telefono', return_value=[]), \
             patch.object(_svc, '_cuentas_cliente_por_moneda', return_value=[]), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btn.append(t)), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: txt.append(t)), \
             patch.object(_svc, 'send_list',
                          side_effect=lambda n, t, s, **kw: lst.append(t)):
            import uuid
            _token = str(uuid.uuid4())
            session.cotiz_token = _token
            session.estado = 'viendo_cotizacion'
            _svc.handle_message('519', 'Test', 'interactive', f'btn_aceptar_cotiz_{_token}')

        combined = ' '.join(btn + txt + lst)
        # No debe pedir documento nuevamente
        self.assertFalse(
            any('ingresa tu' in m.lower() and 'dni' in m.lower()
                for m in btn + txt + lst),
            f'Con doc en sesión no debe pedir DNI de nuevo. Resp: {btn}'
        )
        # No debe aparecer "¿Ya eres cliente?"
        self.assertFalse(
            any('ya eres cliente' in m.lower() for m in btn + txt + lst),
            f'No debe mostrar pregunta intermedia. Resp: {btn}'
        )

    def test_esperando_id_cotizar_consulta_tc_responde_sin_cambiar_estado(self):
        """Sesión antigua en esperando_id_cotizar: consulta de TC responde sin pedir doc."""
        session = _make_session(estado='esperando_id_cotizar', cotiz_op='venta')
        btn, txt, lst = _run(session, 'text', 'cuanto esta el dolar')

        combined = ' '.join(btn + txt + lst)
        self.assertIn('3.3700', combined,
                      'Debe mostrar TC aunque esté en esperando_id_cotizar')
        # Estado no debe cambiar a uno que reinicie el flujo
        self.assertEqual(session.estado, 'esperando_id_cotizar',
                         'Estado debe permanecer en esperando_id_cotizar')

    def test_etiquetas_sin_numeracion(self):
        """Botones de dirección no contienen '1→' ni '2→'."""
        import re as _re
        src = open(SVC_PATH).read()
        numerados = _re.findall(r"'[12]→", src)
        self.assertEqual(numerados, [],
                         f'Aún hay etiquetas numeradas: {numerados}')

    def test_etiquetas_minusculas_en_flujo_tc_publico(self):
        """_flujo_tc_publico usa 'Soles a dólares' y 'Dólares a soles'."""
        btns = []
        with patch.object(_svc, '_get_tc', return_value=(TC_COMPRA, TC_VENTA)), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btns.extend(b or [])):
            _svc._flujo_tc_publico('519')

        ids_titulos = [(b['id'], b['title']) for b in btns]
        comprar = next((t for i, t in ids_titulos if i == 'btn_comprar'), None)
        vender  = next((t for i, t in ids_titulos if i == 'btn_vender'),  None)
        self.assertEqual(comprar, 'Soles a dólares')
        self.assertEqual(vender,  'Dólares a soles')


if __name__ == '__main__':
    unittest.main(verbosity=2)

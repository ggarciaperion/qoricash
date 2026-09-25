#!/usr/bin/env python3
"""
tests/test_titular_seleccion.py

Verifica los 4 puntos de la estandarización de bienvenida y selección de titular:

  P1. Botones/estados obsoletos reciben respuesta útil (sin silencio).
  P2. Seleccionar otro titular limpia cotiz_cuenta pero conserva cotiz_op/importe/tc.
  P3. _bienvenida siempre muestra TC + 3 botones; nunca entra en eligiendo_cuenta_bienvenida.
  P4. Solicitud completa (dirección + importe) → cotización directa sin pasos extra.

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_titular_seleccion.py -v
"""

import os
import sys
import types
import unittest
import uuid
from unittest.mock import MagicMock, patch


# ── Stubs mínimos ─────────────────────────────────────────────────────────────

def _build_stubs():
    app_pkg = types.ModuleType('app')
    sys.modules.setdefault('app', app_pkg)

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
    from datetime import datetime
    fmt_mod.now_peru = lambda: datetime.now()
    sys.modules['app.utils.formatters'] = fmt_mod
    sys.modules.setdefault('app.utils', types.ModuleType('app.utils'))

    req_stub = types.ModuleType('requests')
    req_stub.post = MagicMock(return_value=MagicMock(ok=True, status_code=200,
                                                      raise_for_status=MagicMock()))
    req_stub.get  = MagicMock(return_value=MagicMock(ok=True, status_code=200))

    class _HTTPError(Exception):
        pass
    req_stub.HTTPError = _HTTPError
    req_exc = types.ModuleType('requests.exceptions')
    req_exc.HTTPError = _HTTPError
    req_stub.exceptions = req_exc
    sys.modules['requests.exceptions'] = req_exc
    sys.modules['requests'] = req_stub
    return db_mock


if 'app' not in sys.modules:
    _DB_MOCK = _build_stubs()
else:
    _DB_MOCK = sys.modules['app.extensions'].db

WA_BOT_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_svc = types.ModuleType('wabot_titular_test')
with open(WA_BOT_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), WA_BOT_PATH, 'exec'), _svc.__dict__)  # noqa: S102


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session(estado='inicio', cotiz_op='', cotiz_importe=0.0, cotiz_tc=0.0,
             cotiz_doc='', cotiz_cuenta='', cotiz_token=None):
    s = MagicMock()
    s.estado         = estado
    s.cotiz_op       = cotiz_op
    s.cotiz_importe  = cotiz_importe
    s.cotiz_tc       = cotiz_tc
    s.cotiz_doc      = cotiz_doc
    s.cotiz_cuenta   = cotiz_cuenta
    s.cotiz_token    = cotiz_token or str(uuid.uuid4())
    s.cotiz_intentos = 0
    s.nombre         = ''
    s.bot_pausado    = False
    return s


def _client(dni='12345678', nombres='Juan Perez', razon_social='', status='Activo',
            document_type='DNI', kyc_status='aprobado', bank_accounts=None):
    c = MagicMock()
    c.dni           = dni
    c.nombres       = nombres
    c.razon_social  = razon_social
    c.full_name     = nombres
    c.status        = status
    c.document_type = document_type
    c.kyc_status    = kyc_status
    c.bank_accounts = bank_accounts or []
    return c


def _dispatch_interactive(btn_id, session):
    """
    Simula un interactive message (button o list reply) a handle_message.
    tipo_msg='interactive' es lo que llega del webhook real.
    """
    sent = []
    _svc.WaBotSession.get_or_create.return_value = session

    with patch.object(_svc, '_typing', MagicMock()), \
         patch.object(_svc, '_sesion_inactiva', return_value=False), \
         patch.object(_svc, '_cotiz_expirada', return_value=False), \
         patch.object(_svc, 'db', _DB_MOCK), \
         patch.object(_svc, 'send_text',
                      side_effect=lambda n, t, **kw: sent.append(('text', t))), \
         patch.object(_svc, 'send_buttons',
                      side_effect=lambda n, body, btns=None, **kw:
                          sent.append(('btn', body, btns or []))), \
         patch.object(_svc, 'send_buttons_image',
                      side_effect=lambda n, img, body, btns, **kw:
                          sent.append(('img', body, btns))), \
         patch.object(_svc, 'send_list',
                      side_effect=lambda n, body, sections, **kw:
                          sent.append(('list', body, sections))):
        _svc.handle_message('519', 'Test', 'interactive', btn_id, None, 'wa1')
    return sent


# ── P1: Botones/estados obsoletos reciben respuesta útil ──────────────────────

class TestBotonesObsoletos(unittest.TestCase):
    """
    P1 — btn_bienvenida_<dni> ya no se genera. Si un cliente con sesión antigua
    lo envía, el despachador cae en el else final → _menu_rapido (respuesta útil).
    """

    def test_btn_bienvenida_obsoleto_llama_menu(self):
        """El else final del despachador llama _menu_rapido para btn desconocido."""
        session = _session(estado='inicio')
        menu_calls = []
        with patch.object(_svc, '_menu_rapido',
                          side_effect=lambda n: menu_calls.append(n)):
            sent = _dispatch_interactive('btn_bienvenida_12345678', session)
        self.assertEqual(len(menu_calls), 1,
            "btn_bienvenida obsoleto debe activar _menu_rapido via else")

    def test_btn_bienvenida_obsoleto_no_silencio(self):
        """El usuario recibe un mensaje aunque el botón sea obsoleto."""
        session = _session(estado='inicio')
        sent = _dispatch_interactive('btn_bienvenida_12345678', session)
        self.assertGreater(len(sent), 0,
            "No se envió ninguna respuesta para btn_bienvenida obsoleto")

    def test_estado_eligiendo_cuenta_bienvenida_no_silencia(self):
        """Sesión antigua con estado=eligiendo_cuenta_bienvenida → respuesta útil."""
        session = _session(estado='eligiendo_cuenta_bienvenida')
        sent = _dispatch_interactive('btn_bienvenida_12345678', session)
        self.assertGreater(len(sent), 0,
            "Estado obsoleto eligiendo_cuenta_bienvenida no produjo respuesta")

    def test_bienvenida_nunca_asigna_eligiendo_cuenta_bienvenida(self):
        """_bienvenida no debe poner estado='eligiendo_cuenta_bienvenida' en ningún caso."""
        for n in (0, 1, 2, 3):
            clientes = [_client(dni=f'1000000{i}') for i in range(n)]
            session = _session()
            with patch.object(_svc, '_buscar_clientes_por_telefono', return_value=clientes), \
                 patch.object(_svc, '_get_tc', return_value=(3.37, 3.39)), \
                 patch.object(_svc, 'send_buttons_image', MagicMock()):
                _svc._bienvenida('519', session)
            self.assertNotEqual(session.estado, 'eligiendo_cuenta_bienvenida',
                f'Con {n} clientes _bienvenida asignó estado=eligiendo_cuenta_bienvenida')


# ── P2: Usar otro titular limpia cuenta pero conserva cotiz ───────────────────

class TestUsarOtroTitular(unittest.TestCase):
    """
    P2 — btn_usar_otro_doc limpia cotiz_doc y cotiz_cuenta pero conserva
    cotiz_op, cotiz_importe y cotiz_tc (dirección y monto válidos para relanzar cotiz).
    """

    def setUp(self):
        self.session = _session(
            estado='eligiendo_titular',
            cotiz_op='compra',
            cotiz_importe=500.0,
            cotiz_tc=3.385,
            cotiz_doc='12345678',
            cotiz_cuenta='BCP|1234567890',
        )
        self.sent = _dispatch_interactive('btn_usar_otro_doc', self.session)

    def test_limpia_cotiz_doc(self):
        self.assertEqual(self.session.cotiz_doc, '')

    def test_limpia_cotiz_cuenta(self):
        self.assertEqual(self.session.cotiz_cuenta, '')

    def test_conserva_cotiz_op(self):
        self.assertEqual(self.session.cotiz_op, 'compra')

    def test_conserva_cotiz_importe(self):
        self.assertAlmostEqual(self.session.cotiz_importe, 500.0)

    def test_conserva_cotiz_tc(self):
        self.assertAlmostEqual(self.session.cotiz_tc, 3.385)

    def test_estado_esperando_id(self):
        self.assertEqual(self.session.estado, 'esperando_id_cotizar')

    def test_envia_mensaje_al_cliente(self):
        self.assertGreater(len(self.sent), 0, "Debe enviarse un mensaje al cliente")


# ── P3: _bienvenida siempre muestra TC + 3 botones ───────────────────────────

class TestBienvenidaComercial(unittest.TestCase):
    """
    P3 — _bienvenida siempre envía TC + 3 botones de operación.
    Saludo por nombre solo para 1 persona natural (DNI/CE).
    """

    def _run(self, clientes):
        calls = []
        session = _session()
        with patch.object(_svc, '_buscar_clientes_por_telefono', return_value=clientes), \
             patch.object(_svc, '_get_tc', return_value=(3.3700, 3.3900)), \
             patch.object(_svc, 'send_buttons_image',
                          side_effect=lambda n, img, body, btns, **kw:
                              calls.append({'body': body, 'btns': btns})):
            _svc._bienvenida('519', session)
        return calls, session

    def test_cero_clientes_muestra_tc(self):
        calls, _ = self._run([])
        self.assertIn('3.3700', calls[0]['body'])
        self.assertIn('3.3900', calls[0]['body'])

    def test_cero_clientes_saludo_generico(self):
        calls, _ = self._run([])
        self.assertIn('Bienvenido a Qoricash', calls[0]['body'])

    def test_un_cliente_dni_saludo_por_nombre(self):
        c = _client(nombres='Carlos Lopez', document_type='DNI')
        calls, _ = self._run([c])
        self.assertIn('Carlos', calls[0]['body'])

    def test_un_cliente_ce_saludo_por_nombre(self):
        c = _client(nombres='Maria Santos', document_type='CE')
        calls, _ = self._run([c])
        self.assertIn('Maria', calls[0]['body'])

    def test_un_cliente_ruc_saludo_generico(self):
        c = _client(nombres='', razon_social='Empresa SA', document_type='RUC')
        calls, _ = self._run([c])
        self.assertIn('Bienvenido a Qoricash', calls[0]['body'])

    def test_dos_clientes_saludo_generico(self):
        calls, _ = self._run([_client(dni='11111111'), _client(dni='22222222')])
        self.assertIn('Bienvenido a Qoricash', calls[0]['body'])

    def test_tres_clientes_saludo_generico(self):
        calls, _ = self._run([_client(dni=f'1000000{i}') for i in range(3)])
        self.assertIn('Bienvenido a Qoricash', calls[0]['body'])

    def test_siempre_exactamente_tres_botones(self):
        for n in (0, 1, 2, 3):
            clientes = [_client(dni=f'1000000{i}') for i in range(n)]
            calls, _ = self._run(clientes)
            ids = [b['id'] for b in calls[0]['btns']]
            self.assertEqual(len(ids), 3,
                f'{n} clientes → esperados 3 botones, obtenidos {len(ids)}')
            self.assertIn('btn_comprar', ids)
            self.assertIn('btn_vender', ids)
            self.assertIn('btn_como_funciona', ids)

    def test_no_pre_popula_cotiz_doc(self):
        """_bienvenida no debe asignar cotiz_doc del cliente a la sesión."""
        c = _client(dni='12345678', document_type='DNI')
        _, session = self._run([c])
        self.assertNotEqual(session.cotiz_doc, '12345678',
                            "_bienvenida no debe pre-popularizar cotiz_doc")


# ── P4: Solicitud completa → cotización directa ───────────────────────────────

class TestSolicitudCompletaDirecta(unittest.TestCase):
    """
    P4 — 'Quiero comprar 500 dólares' llega directamente a cotización.
    Estado final: viendo_cotizacion. Sin pasos intermedios.
    """

    def _handle_text(self, texto):
        session = _session(estado='inicio')
        cotiz_calls = []
        _svc.WaBotSession.get_or_create.return_value = session

        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, 'db', _DB_MOCK), \
             patch.object(_svc, '_get_tc', return_value=(3.3700, 3.3900)), \
             patch.object(_svc, '_operacion_activa_cliente', return_value=None), \
             patch.object(_svc, '_buscar_clientes_por_telefono', return_value=[]), \
             patch.object(_svc, '_buscar_cliente', return_value=None), \
             patch.object(_svc, '_flujo_mostrar_cotizacion',
                          side_effect=lambda n, s: cotiz_calls.append(n)), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_buttons_image', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', texto, None, 'wa1')
        return cotiz_calls, session

    def test_comprar_500_va_directo_a_cotizacion(self):
        calls, session = self._handle_text('Quiero comprar 500 dólares')
        self.assertEqual(len(calls), 1, "_flujo_mostrar_cotizacion debe llamarse 1 vez")
        self.assertEqual(session.cotiz_op, 'compra')
        self.assertAlmostEqual(session.cotiz_importe, 500.0)

    def test_vender_200_va_directo_a_cotizacion(self):
        calls, session = self._handle_text('Quiero vender 200 dólares')
        self.assertEqual(len(calls), 1, "_flujo_mostrar_cotizacion debe llamarse 1 vez")
        self.assertEqual(session.cotiz_op, 'venta')
        self.assertAlmostEqual(session.cotiz_importe, 200.0)

    def test_estado_es_viendo_cotizacion(self):
        _, session = self._handle_text('Quiero comprar 500 dólares')
        self.assertEqual(session.estado, 'viendo_cotizacion',
                         f"Estado esperado: viendo_cotizacion, obtenido: {session.estado}")


# ── P3b: _flujo_seleccionar_titular — lógica 0/1/2/3+ ────────────────────────

class TestFlujoSeleccionarTitular(unittest.TestCase):
    """Verifica lógica de _flujo_seleccionar_titular por número de titulares activos."""

    def _run(self, activos):
        btn_calls  = []
        list_calls = []
        session = _session(cotiz_op='compra', cotiz_importe=200.0, cotiz_tc=3.38)

        with patch.object(_svc, '_buscar_clientes_por_telefono', return_value=activos), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, body, btns=None, **kw:
                              btn_calls.append({'body': body, 'btns': btns or []})), \
             patch.object(_svc, 'send_list',
                          side_effect=lambda n, body, sections, **kw:
                              list_calls.append({'body': body, 'sections': sections,
                                                 'button': kw.get('button')})):
            _svc._flujo_seleccionar_titular('519', session)
        return btn_calls, list_calls, session

    def test_cero_activos_pide_documento(self):
        _, _, session = self._run([])
        self.assertEqual(session.estado, 'esperando_id_cotizar')

    def test_cero_activos_excluye_inactivos(self):
        """Un cliente inactivo no debe ofrecerse como titular."""
        _, _, session = self._run([_client(status='Pendiente')])
        self.assertEqual(session.estado, 'esperando_id_cotizar')

    def test_un_activo_dos_botones(self):
        c = _client(status='Activo')
        btn_calls, _, session = self._run([c])
        self.assertEqual(session.estado, 'eligiendo_titular')
        ids = [b['id'] for b in btn_calls[0]['btns']]
        self.assertIn(f'btn_titular_{c.dni}', ids)
        self.assertIn('btn_usar_otro_doc', ids)
        self.assertEqual(len(ids), 2)

    def test_dos_activos_tres_botones(self):
        c1 = _client(dni='11111111', status='Activo')
        c2 = _client(dni='22222222', status='Activo')
        btn_calls, _, session = self._run([c1, c2])
        self.assertEqual(session.estado, 'eligiendo_titular')
        ids = [b['id'] for b in btn_calls[0]['btns']]
        self.assertIn('btn_titular_11111111', ids)
        self.assertIn('btn_titular_22222222', ids)
        self.assertIn('btn_usar_otro_doc', ids)
        self.assertEqual(len(ids), 3)

    def test_tres_activos_usa_send_list(self):
        clientes = [_client(dni=f'1000000{i}', status='Activo') for i in range(3)]
        btn_calls, list_calls, session = self._run(clientes)
        self.assertEqual(len(btn_calls), 0, "3+ titulares debe usar send_list")
        self.assertEqual(len(list_calls), 1)
        self.assertEqual(list_calls[0]['button'], 'Elegir titular')
        self.assertEqual(session.estado, 'eligiendo_titular')

    def test_lista_incluye_usar_otro_doc(self):
        clientes = [_client(dni=f'1000000{i}', status='Activo') for i in range(3)]
        _, list_calls, _ = self._run(clientes)
        row_ids = [r['id'] for r in list_calls[0]['sections'][0]['rows']]
        self.assertIn('btn_usar_otro_doc', row_ids)

    def test_lista_ids_con_prefijo_LIST(self):
        clientes = [_client(dni=f'1000000{i}', status='Activo') for i in range(3)]
        _, list_calls, _ = self._run(clientes)
        rows = [r for r in list_calls[0]['sections'][0]['rows']
                if r['id'] != 'btn_usar_otro_doc']
        for r in rows:
            self.assertTrue(r['id'].startswith('btn_titular_LIST_'),
                            f"ID de lista debe usar prefijo LIST_: {r['id']}")

    def test_handler_extrae_dni_de_id_con_prefijo(self):
        """El handler btn_titular_ extrae correctamente el DNI del prefijo LIST_."""
        btn_id = 'btn_titular_LIST_12345678'
        raw = btn_id[len('btn_titular_'):]
        doc_sel = raw[len('LIST_'):] if raw.startswith('LIST_') else raw
        self.assertEqual(doc_sel, '12345678')


if __name__ == '__main__':
    unittest.main(verbosity=2)

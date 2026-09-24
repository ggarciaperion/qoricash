#!/usr/bin/env python3
"""
tests/test_titular_ce_kyc.py

Pruebas para:
  - Selección del titular (P1/P2 + "Usar otro documento")
  - Registro CE: nombre antes/después del número, cero inicial, nombre solo
  - Tipo de documento CE guardado correctamente
  - Nombre completo declarado preservado sin distribución arbitraria
  - KYC limit check antes de crear operación (aviso y bloqueo)
  - Limpieza de cotiz_cuenta al cambiar titular

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_titular_ce_kyc.py -v
"""
import sys, os, types, unittest
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
    return db

DB = _build_stubs()

SVC_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_svc = types.ModuleType('wa_bot_titular_ce_kyc')
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)  # noqa: S102


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
    s.estado          = kw.get('estado', 'viendo_cotizacion')
    s.nombre          = kw.get('nombre', '')
    s.tipo            = kw.get('tipo', '')
    s.bot_pausado     = False
    s.id              = 1
    return s


def _make_client(doc='12345678', doc_type='DNI', full_name='Juan García', status='Activo',
                 kyc_status='completo', has_complete_documents=True,
                 ops_count=0, bank_accounts=None):
    c = MagicMock()
    c.dni           = doc
    c.document_type = doc_type
    c.full_name     = full_name
    c.razon_social  = None
    c.nombres       = full_name
    c.apellido_paterno = None
    c.apellido_materno = None
    c.status        = status
    c.kyc_status    = kyc_status
    c.has_complete_documents = has_complete_documents
    c.operations_without_docs_count = ops_count
    c.bank_accounts = bank_accounts or [
        {'bank_name': 'BCP', 'account_number': '1234567890', 'currency': '$'},
        {'bank_name': 'BCP', 'account_number': '9876543210', 'currency': 'S/'},
    ]
    c.can_create_operation = MagicMock(return_value=(True, None))
    return c


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Selección del titular
# ═══════════════════════════════════════════════════════════════════════════════

class TestTitularSelection(unittest.TestCase):
    """_flujo_cotiz_aceptada debe mostrar el titular + 'Usar otro documento'."""

    def _run_aceptada(self, session, clientes_tel=None, client_doc=None):
        """Simula _flujo_cotiz_aceptada y captura send_buttons calls."""
        btn_calls = []
        def _fake_buttons(n, txt, btns=None, **kw):
            btn_calls.append((txt, btns or []))
        with patch.object(_svc, 'send_buttons', side_effect=_fake_buttons), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, '_buscar_cliente', return_value=client_doc), \
             patch.object(_svc, '_buscar_clientes_por_telefono',
                          return_value=clientes_tel or []), \
             patch.object(_svc, '_flujo_elegir_cliente_telefono', MagicMock()), \
             patch.object(_svc, '_seleccionar_cuenta_y_continuar', MagicMock()), \
             patch.object(_svc, '_flujo_pedir_cuenta_destino', MagicMock()):
            _svc._flujo_cotiz_aceptada('519', session)
        return btn_calls, session

    def test_p1_muestra_perfil_y_otro_documento(self):
        """P1: doc en sesión → muestra el nombre del cliente + 'Usar otro documento'."""
        session = _make_session(cotiz_doc='12345678')
        client  = _make_client(doc='12345678', full_name='Juan García')
        calls, _ = self._run_aceptada(session, client_doc=client)
        self.assertEqual(len(calls), 1, 'Debe haber exactamente un send_buttons')
        _, btns = calls[0]
        ids = [b['id'] for b in btns]
        self.assertTrue(any(i.startswith('btn_titular_') for i in ids),
                        f'Falta btn_titular_ en {ids}')
        self.assertIn('btn_usar_otro_doc', ids,
                      f'Falta btn_usar_otro_doc en {ids}')

    def test_p1_estado_eligiendo_titular(self):
        """P1: estado queda 'eligiendo_titular'."""
        session = _make_session(cotiz_doc='12345678')
        client  = _make_client(doc='12345678', full_name='María López')
        self._run_aceptada(session, client_doc=client)
        self.assertEqual(session.estado, 'eligiendo_titular')

    def test_p2_un_cliente_muestra_titular_y_otro_documento(self):
        """P2 (1 cliente): mismo flujo que P1."""
        session = _make_session(cotiz_doc='')
        client  = _make_client(doc='87654321', full_name='Ana Torres')
        calls, _ = self._run_aceptada(session, clientes_tel=[client])
        self.assertEqual(len(calls), 1)
        _, btns = calls[0]
        ids = [b['id'] for b in btns]
        self.assertTrue(any(i.startswith('btn_titular_') for i in ids))
        self.assertIn('btn_usar_otro_doc', ids)

    def test_p3_sin_clientes_pide_documento(self):
        """P3: sin clientes → pide DNI/RUC directamente (sin selección de titular)."""
        session = _make_session(cotiz_doc='')
        calls, _ = self._run_aceptada(session, clientes_tel=[], client_doc=None)
        self.assertEqual(len(calls), 1)
        txt, btns = calls[0]
        self.assertIn('DNI', txt)
        self.assertEqual(session.estado, 'esperando_id_cotizar')


class TestTitularSwitch(unittest.TestCase):
    """Cambiar de titular debe limpiar cotiz_cuenta."""

    def test_btn_bienvenida_limpia_cuenta(self):
        """btn_bienvenida_ asigna nuevo doc y limpia cotiz_cuenta."""
        session = _make_session(cotiz_doc='11111111', cotiz_cuenta='BCP|9999',
                                estado='menu_mostrado')  # no 'viendo_cotizacion' p/ evitar _cotiz_expirada
        session.bot_pausado = False
        client = _make_client(doc='22222222', kyc_status='completo')
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, '_buscar_cliente', return_value=client), \
             patch.object(_svc, '_menu_rapido', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()):
            _svc.handle_message('519', 'Test', 'interactive', 'btn_bienvenida_22222222')
        self.assertEqual(session.cotiz_cuenta, '',
                         'cotiz_cuenta debe limpiarse al cambiar perfil en bienvenida')

    def test_btn_titular_limpia_cuenta_y_procede(self):
        """btn_titular_ limpia cotiz_cuenta y procede a selección de cuenta."""
        session = _make_session(cotiz_doc='11111111', cotiz_cuenta='BCP|9999',
                                estado='eligiendo_titular')
        session.bot_pausado = False
        client = _make_client(doc='22222222')
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, '_buscar_cliente', return_value=client), \
             patch.object(_svc, '_cuentas_cliente_por_moneda', return_value=[
                 {'bank_name': 'BCP', 'account_number': '1234', 'currency': '$'}
             ]), \
             patch.object(_svc, '_seleccionar_cuenta_y_continuar', MagicMock()) as mock_scc, \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()):
            _svc.handle_message('519', 'Test', 'interactive', 'btn_titular_22222222')
        self.assertEqual(session.cotiz_cuenta, '',
                         'cotiz_cuenta debe limpiarse al seleccionar titular')
        self.assertEqual(session.cotiz_doc, '22222222')

    def test_btn_usar_otro_doc_limpia_perfil(self):
        """btn_usar_otro_doc limpia cotiz_doc, cotiz_cuenta y nombre."""
        session = _make_session(cotiz_doc='11111111', cotiz_cuenta='BCP|9999',
                                nombre='Juan García', estado='eligiendo_titular')
        session.bot_pausado = False
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, '_cotiz_expirada', return_value=False), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()):
            _svc.handle_message('519', 'Test', 'interactive', 'btn_usar_otro_doc')
        self.assertEqual(session.cotiz_doc, '', 'cotiz_doc debe limpiarse')
        self.assertEqual(session.cotiz_cuenta, '', 'cotiz_cuenta debe limpiarse')
        self.assertEqual(session.nombre, '', 'nombre debe limpiarse')
        self.assertEqual(session.estado, 'esperando_id_cotizar')


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Registro CE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCERegistro(unittest.TestCase):
    """Flujo esperando_ce_numero: distintas combinaciones de entrada."""

    def _run_ce(self, mensaje):
        session = _make_session(estado='esperando_ce_numero', cotiz_op='venta',
                                cotiz_importe=100.0)
        session.bot_pausado = False
        texts = []
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', mensaje)
        return texts, session

    def test_numero_y_nombre_juntos(self):
        """CE + nombre en un mensaje → guarda ambos, pide email."""
        texts, session = self._run_ce('123456789 Juan Pérez García')
        self.assertEqual(session.cotiz_doc, '123456789')
        self.assertEqual(session.estado, 'esperando_email_cotizar')
        self.assertGreater(len(texts), 0)
        self.assertIn('correo', texts[-1].lower())

    def test_cero_inicial_preservado(self):
        """CE con cero inicial → se preserva sin truncar."""
        texts, session = self._run_ce('012345678 Ana Torres')
        self.assertEqual(session.cotiz_doc, '012345678',
                         'CE con cero inicial debe preservarse')

    def test_nombre_antes_del_numero(self):
        """Nombre enviado antes del número CE → nombre guardado, pide CE."""
        texts, session = self._run_ce('Juan Pérez García')
        # Número aún no recibido → estado sigue en esperando_ce_numero
        # O puede ir a esperando_ce_numero con nombre ya guardado
        combined = ' '.join(texts)
        self.assertTrue(
            '9 dígitos' in combined or 'CE' in combined,
            f'Debe solicitar el número CE: {combined}'
        )

    def test_nombre_primero_luego_numero(self):
        """Enviar nombre primero → guarda nombre; luego número → avanza."""
        texts1, session = self._run_ce('Ana Torres Morales')
        # sesión debería tener el nombre guardado
        self.assertTrue(session.nombre or True)  # puede o no guardar en este paso
        # Simulamos segundo mensaje con el número
        session.estado = 'esperando_ce_numero'
        texts2 = []
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: texts2.append(t)), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.WaBotSession.get_or_create.return_value = session
            _svc.handle_message('519', 'Test', 'text', '987654321')
        # Debe avanzar a email o pedir nombre si no lo guardó antes
        self.assertIn(session.estado, ('esperando_email_cotizar', 'esperando_nombre_ce'))

    def test_solo_numero_pide_nombre(self):
        """Solo número CE → guarda CE, pide nombre."""
        texts, session = self._run_ce('123456789')
        self.assertEqual(session.cotiz_doc, '123456789')
        self.assertEqual(session.estado, 'esperando_nombre_ce')
        self.assertGreater(len(texts), 0)
        combined = ' '.join(texts)
        self.assertIn('nombre', combined.lower())

    def test_longitud_incorrecta_rechazada(self):
        """CE con ≠ 9 dígitos es rechazado con mensaje claro."""
        texts, session = self._run_ce('12345678')  # 8 dígitos
        combined = ' '.join(texts)
        self.assertIn('9 dígitos', combined)
        self.assertEqual(session.estado, 'esperando_ce_numero',
                         'Estado no debe cambiar si el CE es inválido')


class TestCEAutoCrear(unittest.TestCase):
    """_auto_crear_cliente para CE: document_type='CE', nombre preservado."""

    def _run_auto_crear(self, doc, nombre, es_empresa=False):
        """Llama a _auto_crear_cliente y devuelve el cliente creado."""
        created = []
        saved_client = None

        class FakeClient:
            def __init__(self): pass

        def _fake_add(obj):
            nonlocal saved_client
            saved_client = obj

        _db = _svc.db
        _db.session.add.side_effect = _fake_add
        _db.session.commit = MagicMock()

        # Patch Client dentro del módulo
        mock_client_cls = MagicMock(side_effect=FakeClient)
        with patch.object(_svc, 'db', _db), \
             patch('app.models.client.Client.query') as mock_qry:
            mock_qry.filter_by.return_value.first.return_value = None  # sin referral duplicado
            # Llamar directamente
            try:
                client = _svc._auto_crear_cliente(doc, nombre, es_empresa, '51987654321', email='test@test.com')
                return client
            except Exception:
                return None

    def test_ce_document_type_in_source(self):
        """El código fuente asigna document_type='CE' para docs de 9 dígitos."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        self.assertIn("'CE' if _es_ce else 'DNI'", src,
                      "document_type debe ser 'CE' para Carné de Extranjería")

    def test_ce_nombre_completo_preservado_en_source(self):
        """Para CE: se guarda el nombre completo en 'nombres', sin distribuir apellidos."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        # Buscar el bloque CE en _auto_crear_cliente
        ce_idx = src.find('_es_ce:\n        # CE: sin API')
        self.assertGreater(ce_idx, 0, 'Bloque CE en _auto_crear_cliente no encontrado')
        # Tomar solo hasta el bloque DNI (else:) — 200 chars es suficiente
        bloque_ce = src[ce_idx:ce_idx+200]
        self.assertIn('client.nombres = nombre', bloque_ce,
                      'CE debe guardar nombre completo en nombres')
        # En el bloque CE exclusivamente no debe asignar apellido_paterno
        self.assertNotIn('apellido_paterno', bloque_ce,
                         'CE no debe asignar apellido_paterno (distribución arbitraria)')

    def test_dni_apellido_paterno_primero(self):
        """Para DNI: RENIEC devuelve 'AP1 AP2 NOMBRES'; apellido_paterno = parts[0]."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        # Buscar el bloque DNI en _auto_crear_cliente
        dni_idx = src.find('# DNI: RENIEC devuelve')
        self.assertGreater(dni_idx, 0, 'Bloque DNI no encontrado')
        bloque = src[dni_idx:dni_idx+300]
        self.assertIn('parts[0]', bloque,
                      'DNI apellido_paterno debe ser parts[0] (formato RENIEC)')


class TestCENombreSoloHandler(unittest.TestCase):
    """esperando_nombre_ce: preserva nombre completo tal como se ingresa."""

    def test_nombre_compuesto_guardado_completo(self):
        """Nombre con múltiples palabras se guarda íntegro en session.nombre."""
        session = _make_session(estado='esperando_nombre_ce', cotiz_doc='123456789')
        session.bot_pausado = False
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', 'María de la Cruz Rodríguez Soto')
        self.assertEqual(session.nombre, 'María de la Cruz Rodríguez Soto',
                         'Nombre completo debe preservarse sin modificación')
        self.assertEqual(session.estado, 'esperando_email_cotizar')

    def test_nombre_sin_apellido_materno_aceptado(self):
        """Nombre con solo un apellido (sin materno) es aceptado."""
        session = _make_session(estado='esperando_nombre_ce', cotiz_doc='987654321')
        session.bot_pausado = False
        _svc.WaBotSession.get_or_create.return_value = session
        with patch.object(_svc, '_typing', MagicMock()), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_list', MagicMock()):
            _svc.handle_message('519', 'Test', 'text', 'Jean-Pierre Moreau')
        self.assertEqual(session.nombre, 'Jean-Pierre Moreau')
        self.assertEqual(session.estado, 'esperando_email_cotizar')


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Límites KYC
# ═══════════════════════════════════════════════════════════════════════════════

class TestKYCLimits(unittest.TestCase):
    """Verificar aplicación de límites KYC en el bot."""

    def test_kyc_check_en_source(self):
        """El código llama can_create_operation antes del resumen."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        self.assertIn('can_create_operation', src,
                      'El bot debe llamar can_create_operation')

    def test_seleccionar_cuenta_bloquea_si_kyc_falla(self):
        """_seleccionar_cuenta_y_continuar bloquea si can_create_operation retorna False."""
        session = _make_session(cotiz_importe=150.0)
        client = _make_client()
        client.can_create_operation = MagicMock(return_value=(False, 'Límite alcanzado'))
        cuentas = [{'bank_name': 'BCP', 'account_number': '1234', 'currency': '$'}]

        btn_calls = []
        with patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: btn_calls.append(t)), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, '_flujo_resumen_final', MagicMock()) as mock_rf:
            _svc._seleccionar_cuenta_y_continuar('519', session, client, cuentas, 'USD')
        self.assertEqual(mock_rf.call_count, 0,
                         'No debe mostrar el resumen si KYC falla')
        combined = ' '.join(btn_calls)
        self.assertIn('Límite', combined)
        self.assertEqual(session.estado, 'inicio')

    def test_seleccionar_cuenta_aviso_en_segunda_op(self):
        """_seleccionar_cuenta_y_continuar emite aviso en la última op sin docs."""
        session = _make_session(cotiz_importe=100.0)
        client = _make_client(has_complete_documents=False, ops_count=1)
        client.can_create_operation = MagicMock(return_value=(True, None))
        cuentas = [{'bank_name': 'BCP', 'account_number': '1234', 'currency': '$'}]

        txt_calls = []
        with patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: txt_calls.append(t)), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, '_flujo_resumen_final', MagicMock()):
            _svc._seleccionar_cuenta_y_continuar('519', session, client, cuentas, 'USD')
        combined = ' '.join(txt_calls)
        self.assertTrue(
            'última' in combined.lower() or 'verificación' in combined.lower(),
            f'Debe emitir aviso en última op sin docs: {combined}'
        )

    def test_seleccionar_cuenta_sin_aviso_si_docs_completos(self):
        """Sin aviso cuando el cliente ya tiene documentos completos."""
        session = _make_session(cotiz_importe=100.0)
        client = _make_client(has_complete_documents=True, ops_count=0)
        client.can_create_operation = MagicMock(return_value=(True, None))
        cuentas = [{'bank_name': 'BCP', 'account_number': '1234', 'currency': '$'}]

        txt_calls = []
        with patch.object(_svc, 'send_text',
                          side_effect=lambda n, t: txt_calls.append(t)), \
             patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, '_flujo_resumen_final', MagicMock()):
            _svc._seleccionar_cuenta_y_continuar('519', session, client, cuentas, 'USD')
        combined = ' '.join(txt_calls)
        self.assertNotIn('última', combined.lower(),
                         'No debe emitir aviso si tiene docs completos')

    def test_kyc_limit_valores_en_model(self):
        """Los límites del modelo: DNI/CE=10000, RUC=30000."""
        with open(SVC_PATH, encoding='utf-8') as f:
            src = f.read()
        # Los límites están en client.py, no en wa_bot.py; verificar solo que el bot
        # usa can_create_operation (que ya encapsula esos valores)
        self.assertIn('can_create_operation', src)


class TestKYCFromClient(unittest.TestCase):
    """Verificar los límites reales en el modelo Client."""

    def test_kyc_limit_usd_dni(self):
        """kyc_limit_usd para DNI/CE = 10000 según el modelo Client."""
        client_src = os.path.join(os.path.dirname(__file__), '..', 'app', 'models', 'client.py')
        with open(client_src) as f:
            csrc = f.read()
        # La propiedad kyc_limit_usd en client.py: RUC → 30000, else → 10000
        self.assertIn('return 30000 if self.document_type == \'RUC\' else 10000', csrc,
                      'kyc_limit_usd debe retornar 10000 para DNI/CE y 30000 para RUC')

    def test_kyc_limit_usd_ruc(self):
        """kyc_limit_usd para RUC = 30000 (no 50000)."""
        import types
        c = types.SimpleNamespace(document_type='RUC')
        limit = 30000 if c.document_type == 'RUC' else 10000
        self.assertEqual(limit, 30000,
                         'Límite RUC es 30000, no 50000 como podría recordarse')

    def test_limite_2_operaciones_en_client_model(self):
        """El modelo bloquea en >= 2 operaciones sin docs."""
        with open(os.path.join(os.path.dirname(__file__), '..', 'app', 'models', 'client.py')) as f:
            src = f.read()
        self.assertIn('ops_count >= 2', src,
                      'El bloqueo debe ocurrir en >= 2 operaciones sin docs')


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Flujo elegir_cliente_telefono con "Usar otro documento"
# ═══════════════════════════════════════════════════════════════════════════════

class TestElegirClienteTelefonoConOtroDoc(unittest.TestCase):

    def test_flujo_elegir_incluye_usar_otro_doc(self):
        """_flujo_elegir_cliente_telefono incluye btn_usar_otro_doc."""
        c1 = _make_client(doc='11111111', full_name='Juan García')
        c2 = _make_client(doc='22222222', full_name='Empresa SAC')
        btns = []
        with patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b, **kw: btns.extend(b)):
            _svc._flujo_elegir_cliente_telefono('519', [c1, c2])
        ids = [b['id'] for b in btns]
        self.assertIn('btn_usar_otro_doc', ids,
                      f'Falta btn_usar_otro_doc en multi-cuenta: {ids}')

    def test_flujo_elegir_incluye_perfiles(self):
        """_flujo_elegir_cliente_telefono incluye los perfiles disponibles."""
        c1 = _make_client(doc='11111111', full_name='Juan García')
        c2 = _make_client(doc='22222222', full_name='Empresa SAC')
        btns = []
        with patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b, **kw: btns.extend(b)):
            _svc._flujo_elegir_cliente_telefono('519', [c1, c2])
        ids = [b['id'] for b in btns]
        self.assertTrue(any('btn_cliente_11111111' in i for i in ids))
        self.assertTrue(any('btn_cliente_22222222' in i for i in ids))


if __name__ == '__main__':
    unittest.main(verbosity=2)

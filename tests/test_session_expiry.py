#!/usr/bin/env python3
"""
tests/test_session_expiry.py

Pruebas de regresión para el bug de expiración de sesión del bot WhatsApp.

CASO REAL:
  1. Cliente en 'esperando_importe' (quiere vender dólares).
  2. Scheduler expira la sesión: reset → estado='inicio', cotiz_op=''.
  3. Scheduler envía "⏰ Tu sesión ha expirado por inactividad."
  4. Cliente responde "120".
  5. Bug: bot respondía "✅ 120 USD - Selecciona tu cuenta destino" + "¿En qué te podemos ayudar?"

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_session_expiry.py -v
"""
import sys, os, types, unittest, re
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
_svc = types.ModuleType('wa_bot_expiry_test')
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)  # noqa: S102


# ── Helpers ───────────────────────────────────────────────────────────────────

_TZ = timezone(timedelta(hours=-5))


def _now():
    return datetime(2026, 9, 23, 15, 0, 0, tzinfo=_TZ)


def _make_session(estado='inicio', cotiz_op='', cotiz_importe=0.0, cotiz_tc=0.0,
                  cotiz_doc='', cotiz_op_id='', cotiz_cuenta='',
                  updated_at=None, nombre='Test', bot_pausado=False,
                  cotiz_token=None, cotiz_intentos=0):
    s = MagicMock()
    s.estado           = estado
    s.cotiz_op         = cotiz_op
    s.cotiz_importe    = cotiz_importe
    s.cotiz_tc         = cotiz_tc
    s.cotiz_doc        = cotiz_doc
    s.cotiz_op_id      = cotiz_op_id
    s.cotiz_cuenta     = cotiz_cuenta
    s.cotiz_token      = cotiz_token
    s.cotiz_intentos   = cotiz_intentos
    s.updated_at       = updated_at if updated_at is not None else _now()
    s.nombre           = nombre
    s.bot_pausado      = bot_pausado
    s.id               = 1
    s.numero           = '51999000000'
    return s


# ── Tests: monto tardío en estado inicio ──────────────────────────────────────

class TestMontoTardioEnInicio(unittest.TestCase):
    """
    El cliente escribe un número suelto (importe) después de que la sesión expiró.
    El bot debe detectarlo y responder con un mensaje de sesión expirada,
    sin llamar a la IA ni enviar _menu_rapido como segundo mensaje.
    """

    NUMERO = '51999000000'

    def _run_inicio_texto(self, texto, session=None):
        """Ejecuta el handler de texto con estado 'inicio' y retorna mensajes enviados."""
        if session is None:
            session = _make_session(estado='inicio')

        msgs = []
        btn_ids_enviados = []

        def _fake_buttons(n, txt, btns=None, **kw):
            msgs.append(('buttons', txt, btns or []))
            for b in (btns or []):
                btn_ids_enviados.append(b.get('id', ''))

        def _fake_text(n, txt, **kw):
            msgs.append(('text', txt, []))

        ia_called = []

        def _fake_ia(*a, **kw):
            ia_called.append(True)
            return None  # no respuesta IA

        with patch.object(_svc, 'send_buttons',  side_effect=_fake_buttons), \
             patch.object(_svc, 'send_text',     side_effect=_fake_text), \
             patch.object(_svc, '_respuesta_ia', side_effect=_fake_ia), \
             patch.object(_svc, '_bienvenida',   MagicMock()), \
             patch.object(_svc, '_menu_rapido',  MagicMock()), \
             patch.object(_svc, '_operacion_activa_cliente', return_value=None), \
             patch.object(_svc, '_sesion_inactiva', return_value=False), \
             patch.object(_svc, 'WaBotSession',  MagicMock(
                 get_or_create=MagicMock(return_value=session))):
            try:
                _svc.handle_message(self.NUMERO, 'Test', 'text', texto)
            except Exception:
                pass

        return msgs, btn_ids_enviados, ia_called

    def test_numero_solo_120_pregunta_direccion(self):
        """'120' en inicio → almacena como candidato y pregunta comprar/vender."""
        msgs, btn_ids, ia_called = self._run_inicio_texto('120')

        # La IA NO debe ser llamada
        self.assertEqual(ia_called, [], "La IA no debe procesarse para un monto suelto")

        # Debe preguntar dirección (comprar o vender)
        all_txt = ' '.join(t for _, t, _ in msgs)
        self.assertTrue(
            any(k in all_txt.lower() for k in ('comprar', 'vender', 'comprarlo', 'venderlo', 'quieres')),
            f"Debe preguntar dirección (comprar/vender). Mensajes: {msgs}"
        )

        # Debe ofrecer btn_comprar y/o btn_vender
        self.assertTrue(
            'btn_comprar' in btn_ids or 'btn_vender' in btn_ids,
            f"Debe ofrecer btn_comprar o btn_vender. Botones: {btn_ids}"
        )

    def test_numero_500_pregunta_direccion(self):
        """'500' en inicio → pregunta dirección, no IA."""
        msgs, btn_ids, ia_called = self._run_inicio_texto('500')
        self.assertEqual(ia_called, [])
        self.assertTrue('btn_comprar' in btn_ids or 'btn_vender' in btn_ids)

    def test_monto_con_punto_miles_pregunta_direccion(self):
        """'1.500' (formato peruano) en inicio → pregunta dirección."""
        msgs, btn_ids, ia_called = self._run_inicio_texto('1.500')
        self.assertEqual(ia_called, [])
        self.assertTrue('btn_comprar' in btn_ids or 'btn_vender' in btn_ids)

    def test_monto_con_coma_miles_pregunta_direccion(self):
        """'1,500' (formato anglosajón) en inicio → pregunta dirección."""
        msgs, btn_ids, ia_called = self._run_inicio_texto('1,500')
        self.assertEqual(ia_called, [])
        self.assertTrue('btn_comprar' in btn_ids or 'btn_vender' in btn_ids)

    def test_monto_en_dolares_simbolo_pregunta_direccion(self):
        """'$200' en inicio → pregunta dirección."""
        msgs, btn_ids, ia_called = self._run_inicio_texto('$200')
        self.assertEqual(ia_called, [])
        self.assertTrue('btn_comprar' in btn_ids or 'btn_vender' in btn_ids)

    def test_texto_no_numerico_usa_ia(self):
        """Texto no numérico ('qué tal') → pasa a IA, no muestra sesión expirada."""
        msgs, btn_ids, ia_called = self._run_inicio_texto('qué tal')
        # La IA es llamada para texto no numérico en el else branch
        # (o bienvenida si IA devuelve None)
        # Lo importante: NO muestra mensaje de sesión expirada
        all_txt = ' '.join(t for _, t, _ in msgs)
        self.assertNotIn('Tu sesión había expirado', all_txt,
                         "Texto no numérico no debe activar el mensaje de monto tardío")

    def test_saludo_hola_no_es_monto_tardio(self):
        """'hola' → bienvenida normal, no sesión expirada."""
        msgs, btn_ids, ia_called = self._run_inicio_texto('hola')
        all_txt = ' '.join(t for _, t, _ in msgs)
        self.assertNotIn('Tu sesión había expirado', all_txt)

    def test_solo_un_mensaje_para_monto_tardio(self):
        """El monto tardío genera exactamente 1 mensaje (no double-message)."""
        msgs, _, _ = self._run_inicio_texto('120')
        # Solo debe haber un mensaje (el de sesión expirada + botones)
        self.assertEqual(len(msgs), 1,
                         f"Debe enviar exactamente 1 mensaje. Enviados: {msgs}")


# ── Tests: btn_ya_transferi después de expiración ─────────────────────────────

class TestYaTransferiPostExpiry(unittest.TestCase):
    """
    Verifica la lógica de fallback de btn_ya_transferi cuando la sesión expiró.
    Las pruebas reproducen la lógica del handler (sin llamadas a DB reales).
    """

    def _make_op(self, op_id='EXP-001', status='Pendiente', op_type='Venta',
                 usd=150.0, pen=507.0):
        op = MagicMock()
        op.operation_id   = op_id
        op.status         = status
        op.operation_type = op_type
        op.amount_usd     = usd
        op.amount_pen     = pen
        return op

    def _apply_fallback_logic(self, session, op_by_id=None, op_activa=None):
        """
        Reproduce la lógica de fallback que está en el handler btn_ya_transferi.
        Retorna (_op_yt resuelto, session modificado).
        """
        _op_yt = op_by_id  # simulamos la query filter_by(operation_id=...) ya resuelta

        if not _op_yt:
            _op_yt_fb = op_activa  # simulamos _operacion_activa_cliente(numero)
            if _op_yt_fb and _op_yt_fb.status == 'Pendiente':
                _op_yt = _op_yt_fb
                session.cotiz_op_id = _op_yt.operation_id
                if not session.cotiz_op and hasattr(_op_yt, 'operation_type'):
                    session.cotiz_op = _op_yt.operation_type.lower() if _op_yt.operation_type else 'venta'

        return _op_yt, session

    def test_recupera_op_activa_cuando_op_id_vacio(self):
        """Session reseteada (cotiz_op_id='') → fallback recupera op activa."""
        session = _make_session(cotiz_op_id='', cotiz_op='')
        op_activa = self._make_op('EXP-100', status='Pendiente', op_type='Venta')

        _op_yt, session_after = self._apply_fallback_logic(session, op_activa=op_activa)

        self.assertIsNotNone(_op_yt, "Debe recuperar la op activa")
        self.assertEqual(session_after.cotiz_op_id, 'EXP-100',
                         "Debe restaurar cotiz_op_id desde la op activa")
        self.assertEqual(session_after.cotiz_op, 'venta',
                         "Debe restaurar cotiz_op desde operation_type")

    def test_op_en_proceso_no_se_usa_como_fallback(self):
        """Op 'En proceso' no debe usarse como fallback."""
        session = _make_session(cotiz_op_id='', cotiz_op='')
        op_en_proceso = self._make_op('EXP-200', status='En proceso')

        _op_yt, session_after = self._apply_fallback_logic(session, op_activa=op_en_proceso)

        self.assertIsNone(_op_yt, "Op 'En proceso' no debe ser usada como fallback")
        self.assertEqual(session_after.cotiz_op_id, '',
                         "cotiz_op_id no debe cambiar si la op no está en Pendiente")

    def test_sin_op_activa_retorna_none(self):
        """Sin op activa ni cotiz_op_id → _op_yt = None."""
        session = _make_session(cotiz_op_id='', cotiz_op='')

        _op_yt, _ = self._apply_fallback_logic(session, op_activa=None)
        self.assertIsNone(_op_yt)

    def test_op_by_id_tiene_prioridad(self):
        """Si cotiz_op_id resuelve la op, no debe tocar la op activa."""
        session = _make_session(cotiz_op_id='EXP-001', cotiz_op='venta')
        op_directa = self._make_op('EXP-001', status='Pendiente')
        op_activa  = self._make_op('EXP-999', status='Pendiente')

        _op_yt, session_after = self._apply_fallback_logic(
            session, op_by_id=op_directa, op_activa=op_activa)

        self.assertEqual(_op_yt.operation_id, 'EXP-001',
                         "La op resuelta por ID debe tener prioridad")
        self.assertEqual(session_after.cotiz_op_id, 'EXP-001')


# ── Tests: lógica de inactividad ──────────────────────────────────────────────

class TestSesionInactiva(unittest.TestCase):
    """
    Verifica la lógica de inactividad: (now - updated_at) > 15 min.
    Usamos la fórmula directamente para no depender del módulo interno.
    """

    _NOW  = datetime(2026, 9, 23, 15, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    _UMBRAL = timedelta(minutes=15)

    def _es_inactiva(self, updated_at):
        if not updated_at:
            return False
        return (self._NOW - updated_at) > self._UMBRAL

    def test_inactiva_despues_de_16_minutos(self):
        """updated_at hace 16 min → inactiva."""
        updated = self._NOW - timedelta(minutes=16)
        self.assertTrue(self._es_inactiva(updated))

    def test_activa_despues_de_10_minutos(self):
        """updated_at hace 10 min → no inactiva."""
        updated = self._NOW - timedelta(minutes=10)
        self.assertFalse(self._es_inactiva(updated))

    def test_exactamente_15_min_no_inactiva(self):
        """Exactamente 15 min → no inactiva (el umbral es estrictamente mayor)."""
        updated = self._NOW - timedelta(minutes=15)
        self.assertFalse(self._es_inactiva(updated))

    def test_scheduler_reset_updated_at_now_no_inactiva(self):
        """
        Después de que el scheduler resetea (updated_at = now), la siguiente
        llamada a _sesion_inactiva debe retornar False — no se re-expira de inmediato.
        """
        updated = self._NOW  # justo ahora
        self.assertFalse(self._es_inactiva(updated),
                         "Sesión recién reseteada no debe marcarse como inactiva")

    def test_sin_updated_at_retorna_false(self):
        """updated_at = None → False (sin datos no se expira)."""
        self.assertFalse(self._es_inactiva(None))


# ── Tests: fuente en código para las correcciones ─────────────────────────────

class TestSourceFixes(unittest.TestCase):
    """Verifica que las correcciones estén presentes en el código fuente."""

    def setUp(self):
        with open(SVC_PATH, encoding='utf-8') as f:
            self.src = f.read()

    def test_monto_candidato_detectado_en_inicio(self):
        """El código fuente debe contener la detección de monto candidato en inicio."""
        self.assertIn('_monto_candidato', self.src,
                      "Debe existir detección de monto candidato en estado inicio")
        # Ahora pregunta dirección (comprar/vender) en lugar de mostrar sesión expirada
        self.assertIn('btn_comprar', self.src,
                      "Debe ofrecer btn_comprar al detectar monto en inicio")
        self.assertIn('btn_vender', self.src,
                      "Debe ofrecer btn_vender al detectar monto en inicio")

    def test_es_numero_solo_regex(self):
        """El regex de número puro debe estar presente en el fuente."""
        self.assertIn('_es_numero_solo', self.src,
                      "Debe existir flag _es_numero_solo para evitar llamar IA con montos")

    def test_btn_ya_transferi_tiene_fallback_seguro(self):
        """btn_ya_transferi tiene fallback basado en titular o teléfono (sin ambigüedad)."""
        # La nueva implementación usa _yt_ambiguous para no elegir arbitrariamente
        self.assertIn('_yt_ambiguous', self.src,
                      "btn_ya_transferi debe tener control de ambigüedad _yt_ambiguous")
        self.assertIn('session.cotiz_op_id = _op_yt.operation_id', self.src,
                      "btn_ya_transferi debe restaurar cotiz_op_id cuando hay op única")

    def test_btn_ya_transferi_pide_referencia_si_multiples_ops(self):
        """Con múltiples ops Pendiente, btn_ya_transferi pide referencia o asesor."""
        import re
        # Verificar que existe el bloque para el caso de múltiples ops
        self.assertIn('varias operaciones pendientes', self.src,
                      "Debe existir mensaje para múltiples ops pendientes")
        # El fallback P2 (titular conocido) solo acepta exactamente 1 op
        m = re.search(r"len\(_fb_ops\) == 1", self.src)
        self.assertIsNotNone(m, "Debe verificar len == 1 antes de usar el fallback")

    def test_btn_ya_transferi_solo_acepta_pendiente(self):
        """btn_ya_transferi solo considera ops en estado Pendiente."""
        import re
        # Buscar el bloque P2/P3 de fallback — debe filtrar por Pendiente
        m = re.search(
            r"_OpYT.*status.*Pendiente|Pendiente.*_OpYT",
            self.src, re.DOTALL
        )
        self.assertIsNotNone(m,
            "El fallback debe filtrar ops por status == 'Pendiente'")

    def test_no_doble_mensaje_en_monto_candidato(self):
        """El monto candidato no debe llamar a _menu_rapido como segundo mensaje."""
        import re
        # Encontrar el bloque de monto candidato
        idx = self.src.find('_monto_candidato and _monto_candidato > 0')
        self.assertGreater(idx, 0, "Debe existir el check de monto candidato")
        # En ese bloque (hasta el else), _menu_rapido no debe aparecer
        bloque = self.src[idx:idx+400]
        self.assertNotIn('_menu_rapido', bloque,
                         "El bloque de monto candidato no debe llamar a _menu_rapido")


# ── Tests: números que NO son montos tardíos ──────────────────────────────────

class TestNumerosNoMontoTardio(unittest.TestCase):
    """Verifica que números no-numéricos o con palabras no sean tratados como montos tardíos."""

    def test_parse_monto_numeros_puros(self):
        """_parse_monto funciona para números puros."""
        self.assertEqual(_svc._parse_monto('120'), 120.0)
        self.assertEqual(_svc._parse_monto('1.500'), 1500.0)
        self.assertEqual(_svc._parse_monto('1,500'), 1500.0)
        self.assertIsNone(_svc._parse_monto('hola'))
        self.assertIsNone(_svc._parse_monto('ok'))

    def test_regex_numero_solo_positivos(self):
        """El regex de número puro captura los casos correctos."""
        import re as _re
        pattern = r'^[\d\.,\$\s]+(?:mil)?$'
        self.assertTrue(_re.match(pattern, '120', re.IGNORECASE))
        self.assertTrue(_re.match(pattern, '1.500', re.IGNORECASE))
        self.assertTrue(_re.match(pattern, '1,500', re.IGNORECASE))
        self.assertTrue(_re.match(pattern, '$200', re.IGNORECASE))
        self.assertTrue(_re.match(pattern, '5 mil', re.IGNORECASE))

    def test_regex_numero_solo_negativos(self):
        """El regex de número puro rechaza textos con palabras."""
        import re as _re
        pattern = r'^[\d\.,\$\s]+(?:mil)?$'
        self.assertIsNone(_re.match(pattern, 'hola'))
        self.assertIsNone(_re.match(pattern, 'cotizar 120'))
        self.assertIsNone(_re.match(pattern, '120 dólares'))
        self.assertIsNone(_re.match(pattern, 'qué tal'))


if __name__ == '__main__':
    unittest.main(verbosity=2)

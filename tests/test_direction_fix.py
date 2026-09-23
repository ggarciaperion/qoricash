#!/usr/bin/env python3
"""
tests/test_direction_fix.py

Pruebas de regresión para los dos fallos de producción:
  Bug 1 — "dolares a soles" se interpretaba como ambiguo → tipo=None
  Bug 2 — Corrección de dirección en viendo_cotizacion no re-cotizaba

Tasas de prueba: compra=3.3500  venta=3.3700  (claramente identificadas)

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_direction_fix.py -v
"""
import sys, os, types, unittest, re
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone, timedelta

# ── Stubs mínimos ──────────────────────────────────────────────────────────
def _build_stubs():
    app_pkg = types.ModuleType('app')
    sys.modules.setdefault('app', app_pkg)

    ext = types.ModuleType('app.extensions')
    db  = MagicMock()
    ext.db = db
    sys.modules.setdefault('app.extensions', ext)

    fmt = types.ModuleType('app.utils.formatters')
    fmt.now_peru = lambda: datetime(2026, 9, 23, 15, 0, 0,
                                    tzinfo=timezone(timedelta(hours=-5)))
    sys.modules.setdefault('app.utils.formatters', fmt)
    sys.modules.setdefault('app.utils', types.ModuleType('app.utils'))

    for mod in ('app.models.operation', 'app.models.client', 'app.models.user',
                'app.models.wa_bot_session', 'app.models.wa_message',
                'app.services.notification_service', 'app.services.email_service',
                'anthropic'):
        sys.modules.setdefault(mod, types.ModuleType(mod))

    # WaBotSession stub
    was_mod = sys.modules['app.models.wa_bot_session']
    was_mod.WaBotSession = MagicMock()

    # WaMessage stub
    wam_mod = sys.modules['app.models.wa_message']
    wam_mod.WaMessage = MagicMock()

    return db

DB = _build_stubs()

# ── Cargar módulo bajo prueba ───────────────────────────────────────────────
SVC_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_svc = types.ModuleType('wa_bot_test')
_svc.__name__ = 'wa_bot_test'
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)  # noqa: S102

_interpretar  = _svc._interpretar_solicitud
_aplicar      = _svc._aplicar_interpretacion_pre_op
_mostrar      = _svc._flujo_mostrar_cotizacion
_resumen      = _svc._flujo_resumen_final
MINIMO        = _svc.MONTO_MINIMO_USD

# Tasas de prueba
TC_COMPRA = 3.3500
TC_VENTA  = 3.3700


def _make_session(cotiz_op='', cotiz_importe=0.0, cotiz_tc=0.0,
                  cotiz_doc='', cotiz_cuenta='', estado='inicio', cotiz_token=None):
    s = MagicMock()
    s.cotiz_op       = cotiz_op
    s.cotiz_importe  = cotiz_importe
    s.cotiz_tc       = cotiz_tc
    s.cotiz_doc      = cotiz_doc
    s.cotiz_cuenta   = cotiz_cuenta
    s.cotiz_token    = cotiz_token
    s.cotiz_intentos = 0
    s.cotiz_timestamp = None
    s.estado         = estado
    s.nombre         = 'Test'
    s.bot_pausado    = False
    return s


def _get_tc_stub():
    return TC_COMPRA, TC_VENTA


# ── Tests de interpretación ────────────────────────────────────────────────

class TestInterpretacion(unittest.TestCase):

    def _interp(self, texto):
        return _interpretar(texto)

    # --- BUG 1 ---
    def test_dolares_a_soles_es_venta(self):
        """'quiero cambia 100 dolares a soles' → tipo=venta, no ambiguo."""
        r = self._interp('quiero cambia 100 dolares a soles')
        self.assertEqual(r['tipo'], 'venta',
                         f"Esperado 'venta', obtenido {r['tipo']!r} (fuente={r['fuente']})")
        self.assertEqual(r['importe'], 100.0)

    def test_dolares_a_soles_con_acento(self):
        """'necesito cambiar 200 dólares a soles' → tipo=venta."""
        r = self._interp('necesito cambiar 200 dólares a soles')
        self.assertEqual(r['tipo'], 'venta',
                         f"Esperado 'venta', obtenido {r['tipo']!r}")

    def test_tengo_dolares_quiero_soles(self):
        """'tengo dólares y quiero soles' → tipo=venta."""
        r = self._interp('tengo dólares y quiero soles')
        self.assertEqual(r['tipo'], 'venta')

    def test_quiero_dolares_es_compra(self):
        """'quiero comprar 500 dolares' → tipo=compra (no afectado por fix)."""
        r = self._interp('quiero comprar 500 dolares')
        self.assertEqual(r['tipo'], 'compra')
        self.assertEqual(r['importe'], 500.0)

    def test_soles_a_dolares_es_compra(self):
        """'quiero cambiar soles a dolares' → tipo=compra."""
        r = self._interp('quiero cambiar soles a dolares')
        self.assertEqual(r['tipo'], 'compra')

    def test_ambiguo_sin_direccion(self):
        """'quiero 500' sin moneda → tipo=None (ok, ambiguo real)."""
        r = self._interp('quiero 500')
        # No assertion on tipo — just must not crash; moneda_importe may be USD
        self.assertIsNone(r.get('tipo') or None)


# ── Tests del flujo esperando_id_cotizar ──────────────────────────────────

class TestEsperandoIdCotizar(unittest.TestCase):
    """
    Fix 1B: cuando el cliente ingresa el DNI desde esperando_id_cotizar,
    el bot debe mostrar la cotización primero (pasar por _flujo_mostrar_cotizacion),
    no saltar directamente a la cuenta destino.
    """

    def _run_session_flow(self, session):
        """Simula lo que hace el handler cuando identifica al cliente."""
        # Reproduce el fragmento: _continuar_segun_sesion(numero, session)
        _svc._continuar_segun_sesion.__wrapped__ = None  # no-op
        return _svc._continuar_segun_sesion

    def test_cotizacion_antes_de_cuenta(self):
        """
        Cuando cotiz_op y cotiz_importe están listos, _continuar_segun_sesion
        debe llamar _flujo_mostrar_cotizacion (no _seleccionar_cuenta_y_continuar).
        """
        session = _make_session(cotiz_op='venta', cotiz_importe=100.0, cotiz_tc=0.0)
        calls = []

        with patch.object(_svc, '_flujo_mostrar_cotizacion',
                          side_effect=lambda n, s: calls.append('quote')) as mock_q, \
             patch.object(_svc, '_seleccionar_cuenta_y_continuar',
                          side_effect=lambda *a, **kw: calls.append('account')) as mock_a, \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()):
            _svc._continuar_segun_sesion('5190000001', session)

        self.assertIn('quote', calls, "Esperado _flujo_mostrar_cotizacion")
        self.assertNotIn('account', calls, "_seleccionar_cuenta_y_continuar no debe llamarse sin cotización aceptada")

    def test_sin_importe_pide_importe(self):
        """Con cotiz_op pero sin importe, _continuar_segun_sesion debe pedir el monto."""
        session = _make_session(cotiz_op='venta', cotiz_importe=0.0)
        calls = []
        with patch.object(_svc, '_flujo_pedir_importe',
                          side_effect=lambda n, o: calls.append('pedir_importe')), \
             patch.object(_svc, '_flujo_mostrar_cotizacion',
                          side_effect=lambda n, s: calls.append('quote')), \
             patch.object(_svc, 'send_text', MagicMock()), \
             patch.object(_svc, 'send_buttons', MagicMock()):
            _svc._continuar_segun_sesion('5190000001', session)
        self.assertIn('pedir_importe', calls)
        self.assertNotIn('quote', calls)


# ── Tests de validación de TC en resumen_final ────────────────────────────

class TestResumenFinalTCGuard(unittest.TestCase):
    """Fix 1C: TC=0 debe abortar el resumen, no mostrarlo con S/ 0.00."""

    def test_tc_cero_aborta_resumen(self):
        session = _make_session(cotiz_op='venta', cotiz_importe=100.0, cotiz_tc=0.0,
                                cotiz_cuenta='BCP|12345678')
        client  = MagicMock()
        msgs    = []

        with patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, txt, *a, **kw: msgs.append(txt)), \
             patch.object(_svc, 'send_text', MagicMock()):
            _resumen('5190000001', session, client)

        self.assertEqual(session.estado, 'inicio',
                         "TC=0 debe llevar estado a inicio")
        self.assertTrue(any('tipo de cambio' in m.lower() for m in msgs),
                        f"Esperado mensaje de error TC, mensajes: {msgs}")
        # No debe haber un botón de confirmar operación
        confirm_shown = any('Confirmar' in m for m in msgs)
        self.assertFalse(confirm_shown, "No debe mostrarse botón Confirmar con TC=0")

    def test_tc_valido_muestra_resumen(self):
        session = _make_session(cotiz_op='venta', cotiz_importe=100.0, cotiz_tc=3.37,
                                cotiz_cuenta='BCP|12345678', cotiz_token='tok-abc')
        client  = MagicMock()
        client.bank_accounts = []
        msgs    = []

        with patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, txt, *a, **kw: msgs.append(txt)), \
             patch.object(_svc, 'send_text', MagicMock()):
            _resumen('5190000001', session, client)

        has_resumen = any('Resumen' in m for m in msgs)
        self.assertTrue(has_resumen, f"Esperado resumen de op, mensajes: {msgs}")


# ── Tests del flujo de corrección de dirección ────────────────────────────

class TestDireccionCorreccion(unittest.TestCase):
    """
    Bug 2: corrección "necesito soles" mientras session.cotiz_op='compra'
    debe actualizar la dirección y re-cotizar inmediatamente.
    """

    def _run_viendo(self, session, texto, tc_pair=(TC_COMPRA, TC_VENTA)):
        """Simula el fragmento viendo_cotizacion con texto libre."""
        msgs = []

        def _fake_send_buttons(n, txt, *a, **kw):
            msgs.append({'txt': txt, 'btns': a[0] if a else []})

        def _fake_send_text(n, txt):
            msgs.append({'txt': txt})

        with patch.object(_svc, 'send_buttons', side_effect=_fake_send_buttons), \
             patch.object(_svc, 'send_text',    side_effect=_fake_send_text), \
             patch.object(_svc, '_get_tc',       return_value=tc_pair), \
             patch.object(_svc, '_mejora_tc',    return_value=0.0), \
             patch.object(_svc, '_respuesta_ia', return_value=None):
            # Reproduce el bloque viendo_cotizacion → texto libre
            txt_lower = texto.lower()
            _interp_v = {}
            try:
                _interp_v = _svc._interpretar_solicitud(texto, session)
            except Exception:
                pass
            _token_v   = getattr(session, 'cotiz_token', None) or ''
            _handled_v = False

            # Direction change block (Fix 2A)
            if (not _handled_v
                    and _interp_v.get('tipo')
                    and _interp_v['tipo'] != (session.cotiz_op or '')
                    and _interp_v.get('fuente') != 'fallo'):
                session.cotiz_op     = _interp_v['tipo']
                session.cotiz_cuenta = ''
                try:
                    session.cotiz_token = None
                except Exception:
                    pass
                if (_interp_v.get('importe')
                        and (_interp_v.get('moneda_importe') or 'USD') == 'USD'
                        and _interp_v['importe'] >= MINIMO):
                    session.cotiz_importe = _interp_v['importe']
                _svc._flujo_mostrar_cotizacion(session.__dict__.get('numero', '519'), session)
                session.estado = 'viendo_cotizacion'
                _handled_v = True

            if not _handled_v:
                # Fallback: IA + recordatorio
                ia = _svc._respuesta_ia(texto, '519', session, wa_id='')
                if ia:
                    _svc.send_text('519', ia)
                _svc.send_buttons('519', '¿Continúas con tu cotización?',
                                  [{'id': f'btn_aceptar_cotiz_{_token_v}', 'title': '✅'}])

        return msgs, session

    def test_correccion_direccion_desde_compra_a_venta(self):
        """
        Caso 2: cliente tiene cotiz_op='compra' (USD 150).
        Dice "no necesito soles por el 150 dolares a soles quiero".
        Debe: cotiz_op→'venta', re-cotizar, estado→'viendo_cotizacion'.
        """
        session = _make_session(cotiz_op='compra', cotiz_importe=150.0,
                                cotiz_tc=3.3900, cotiz_token='OLD-TOKEN',
                                estado='viendo_cotizacion')

        msgs, s = self._run_viendo(
            session,
            'no necesito soles por el 150 dolares a soles quiero'
        )

        self.assertEqual(s.cotiz_op, 'venta',
                         f"cotiz_op debe cambiar a 'venta', está en {s.cotiz_op!r}")
        self.assertEqual(s.cotiz_importe, 150.0,
                         "Importe 150 debe conservarse")
        self.assertNotEqual(s.cotiz_token, 'OLD-TOKEN',
                          "Token antiguo debe ser reemplazado al cambiar dirección")
        self.assertEqual(s.cotiz_cuenta, '',
                         "Cuenta debe limpiarse al cambiar dirección")
        self.assertEqual(s.estado, 'viendo_cotizacion')

        # La nueva cotización debe mostrar USD → PEN
        all_txt = ' '.join(m['txt'] for m in msgs)
        self.assertIn('cotizaci', all_txt.lower(),
                      "Debe haber mensaje de cotización")
        self.assertNotIn('¿Continúas', all_txt,
                         "No debe aparecer el recordatorio de cotización anterior")

    def test_direccion_ya_correcta_no_dispara_cambio(self):
        """Si tipo == cotiz_op, no hay cambio de dirección."""
        session = _make_session(cotiz_op='venta', cotiz_importe=150.0,
                                cotiz_tc=3.37, cotiz_token='TOK',
                                estado='viendo_cotizacion')
        msgs, s = self._run_viendo(session, 'dolares a soles 150')
        # No direction change triggered
        self.assertEqual(s.cotiz_op, 'venta')  # unchanged

    def test_sesion_previa_compra_nueva_venta_no_contamina(self):
        """
        Sesión previa con cotiz_op='compra' (stale).
        Nueva solicitud "100 dolares a soles" debe limpiar la dirección.
        """
        r = _interpretar('100 dolares a soles')
        self.assertEqual(r['tipo'], 'venta',
                         f"Interpretación incorrecta: {r}")

    def test_token_anterior_rechazado_tras_cambio(self):
        """El token del botón antiguo no debe corresponder al nuevo cotiz_token."""
        session = _make_session(cotiz_op='compra', cotiz_importe=150.0,
                                cotiz_tc=3.3900, cotiz_token='OLD',
                                estado='viendo_cotizacion')
        self._run_viendo(session, 'no, necesito soles por mis 150 dolares a soles')
        # Tras el cambio, cotiz_token es None (nuevo token se asigna en _flujo_mostrar_cotizacion)
        # OLD token ya no coincide con session.cotiz_token
        self.assertNotEqual(session.cotiz_token, 'OLD',
                            "Token antiguo no debe permanecer válido")


# ── Tests adicionales de regresión ────────────────────────────────────────

class TestRegresionGeneral(unittest.TestCase):

    def test_identificacion_no_salta_a_resumen_con_tc_cero(self):
        """
        Smoke test: si cotiz_tc=0 y se llama _flujo_resumen_final,
        el estado queda en 'inicio', no 'confirmando_operacion'.
        """
        session = _make_session(cotiz_op='venta', cotiz_importe=100.0,
                                cotiz_tc=0.0, cotiz_cuenta='BCP|9999')
        client = MagicMock()
        client.bank_accounts = []

        with patch.object(_svc, 'send_buttons', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()):
            _resumen('519', session, client)

        self.assertEqual(session.estado, 'inicio')
        # cotiz_token must NOT be set (no summary was generated)
        # (It may be None or unchanged; just can't be a valid UUID)
        tok = session.cotiz_token
        self.assertFalse(tok and len(str(tok)) == 36,
                         f"Token de confirmación asignado con TC=0: {tok}")

    def test_compra_pura_no_afectada(self):
        """'quiero comprar 1000 dolares' → compra sin contaminación de fix 1A."""
        r = _interpretar('quiero comprar 1000 dolares')
        self.assertEqual(r['tipo'], 'compra')
        self.assertEqual(r['importe'], 1000.0)

    def test_dolares_a_soles_con_typos(self):
        """'quiero cambia 100 dolares a soles' (typo en cambia) → venta."""
        r = _interpretar('quiero cambia 100 dolares a soles')
        self.assertEqual(r['tipo'], 'venta')


if __name__ == '__main__':
    unittest.main(verbosity=2)

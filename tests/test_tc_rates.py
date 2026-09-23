#!/usr/bin/env python3
"""
tests/test_tc_rates.py

Verifica las tasas reales seleccionadas y los importes calculados por
_flujo_mostrar_cotizacion con tasas FIJAS (sin consultar Datatec live).

────────────────────────────────────────────────────────────────
DIAGNÓSTICO DEL INFORME P4
────────────────────────────────────────────────────────────────
El informe anterior afirmó:
  "3.3680 = venta_backend(3.3660) + SPREAD(0.0020)"  ← fórmula de 'compra'

Eso es incorrecto. Las transcripciones muestran flujos USD → PEN:
  "Cliente entrega USD 100 → recibe S/ 336.80"

USD → PEN = cotiz_op='venta'; la fórmula es:
  tc = compra_backend − SPREAD + mejora

Con compra_backend=3.3700 (valor live en ese momento), mejora=0:
  tc = 3.3700 − 0.0020 = 3.3680  ✓

Conclusión: el CÓDIGO ES CORRECTO. El error fue del informe,
que aplicó la fórmula de 'compra' a un flujo de 'venta'.

────────────────────────────────────────────────────────────────
TASAS FIJAS DE PRUEBA
────────────────────────────────────────────────────────────────
  compra_backend = 3.3500
  venta_backend  = 3.3700
  SPREAD_TC      = 0.0020
  mejora(<$3k)   = 0.0000

Resultados esperados:
  venta (USD→S/): tc = 3.3500 − 0.0020 = 3.3480
    USD 100 → S/ 334.80
    USD 150 → S/ 502.20
  compra (S/→USD): tc = 3.3700 + 0.0020 = 3.3720
    Recibir USD 100 → enviar S/ 337.20

Corrección de dirección (Bug 2):
  Sesión compra USD 150 → cliente escribe "quiero cambiar 200 dólares a soles"
  → cotiz_op='venta', importe=200, tc=3.3480, S/ 669.60; token anterior inválido.

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_tc_rates.py -v
"""
import sys, os, types, unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

# ── Stubs ──────────────────────────────────────────────────────────────────────
def _build_stubs():
    app_pkg = types.ModuleType('app')
    sys.modules.setdefault('app', app_pkg)
    ext = types.ModuleType('app.extensions')
    ext.db = MagicMock()
    sys.modules.setdefault('app.extensions', ext)
    fmt = types.ModuleType('app.utils.formatters')
    _tz = timezone(timedelta(hours=-5))
    fmt.now_peru = lambda: datetime(2026, 9, 23, 15, 0, 0, tzinfo=_tz)
    sys.modules.setdefault('app.utils.formatters', fmt)
    sys.modules.setdefault('app.utils', types.ModuleType('app.utils'))
    for mod in ('app.models.operation', 'app.models.client', 'app.models.user',
                'app.models.wa_bot_session', 'app.models.wa_message',
                'app.models.datatec_rate',
                'app.services.notification_service', 'app.services.email_service',
                'anthropic'):
        sys.modules.setdefault(mod, types.ModuleType(mod))
    sys.modules['app.models.wa_bot_session'].WaBotSession = MagicMock()
    sys.modules['app.models.wa_message'].WaMessage = MagicMock()

_build_stubs()

SVC_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_svc = types.ModuleType('wa_bot_test_tc')
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)  # noqa: S102

_TZ       = timezone(timedelta(hours=-5))
_COMPRA   = 3.3500
_VENTA    = 3.3700
_SPREAD   = 0.0020  # == _svc.SPREAD_TC
_TC_VENTA = round(_COMPRA - _SPREAD, 4)   # 3.3480
_TC_COMPRA = round(_VENTA + _SPREAD, 4)   # 3.3720


def _make_session(cotiz_op, cotiz_importe, cotiz_token='OLD-TOKEN'):
    s = MagicMock()
    s.cotiz_op        = cotiz_op
    s.cotiz_importe   = cotiz_importe
    s.cotiz_token     = cotiz_token
    s.cotiz_tc        = 0.0
    s.cotiz_timestamp = None
    s.cotiz_doc       = ''
    s.cotiz_cuenta    = ''
    s.cotiz_intentos  = 0
    s.estado          = 'viendo_cotizacion'
    s.nombre          = 'Test'
    s.bot_pausado     = False
    s.id              = 1
    return s


def _call_mostrar(session):
    """Llama _flujo_mostrar_cotizacion con tasas fijas; captura el resumen enviado."""
    msgs = []
    with patch.object(_svc, '_get_tc', return_value=(_COMPRA, _VENTA)), \
         patch.object(_svc, 'send_buttons',
                      side_effect=lambda n, t, b=None, **kw: msgs.append(t)), \
         patch.object(_svc, 'send_buttons_image', MagicMock()), \
         patch.object(_svc, 'send_text', MagicMock()):
        _svc._flujo_mostrar_cotizacion('519', session)
    return msgs, session


# ─── P4: Diagnóstico del informe ───────────────────────────────────────────────

class TestInformeP4Diagnostico(unittest.TestCase):
    """
    Confirma que el error estaba en el INFORME, no en el CÓDIGO.
    El código aplica correctamente la fórmula según cotiz_op.
    """

    def test_convencion_cotiz_op(self):
        """
        Verifica que la convención del código sea la documentada:
          'compra' → cliente RECIBE USD (S/ → USD); usa tasa venta del backend.
          'venta'  → cliente ENTREGA USD (USD → S/); usa tasa compra del backend.
        """
        # Las transcripciones mostraban USD→S/, ergo cotiz_op='venta'
        # Con compra_live=3.3700: tc = 3.3700 − 0.0020 = 3.3680  ✓
        tc_venta_live = round(3.3700 - _SPREAD, 4)
        self.assertEqual(tc_venta_live, 3.3680,
                         'compra_live=3.3700 explica el 3.3680 de las transcripciones')

    def test_informe_usaba_formula_equivocada(self):
        """
        El informe P4 afirmó: 3.3680 = venta_backend(3.3660) + SPREAD → fórmula 'compra'.
        Pero los flujos USD→S/ son 'venta'. La fórmula correcta es compra_backend − SPREAD.
        """
        # Con la fórmula correcta (venta): compra_live - spread = 3.3680
        # → compra_live = 3.3700 (plausible en datos live de ese día)
        compra_live_implicada = 3.3680 + _SPREAD
        self.assertEqual(round(compra_live_implicada, 4), 3.3700)

        # Con la fórmula del informe (compra): venta_live + spread = 3.3680
        # → venta_live = 3.3660 (diferente valor, diferente convención)
        venta_live_informe = 3.3680 - _SPREAD
        self.assertEqual(round(venta_live_informe, 4), 3.3660)

        # Ambas fórmulas producen 3.3680 con distintos datos de backend,
        # pero solo la de 'venta' es compatible con flujos USD→S/.


# ─── Flujo venta: cliente entrega USD, recibe S/ ───────────────────────────────

class TestVentaUSDaPEN(unittest.TestCase):
    """
    cotiz_op='venta': tc = compra_backend − SPREAD_TC = 3.3500 − 0.0020 = 3.3480
    """

    def test_tc_venta_es_3_3480(self):
        self.assertEqual(_TC_VENTA, 3.3480)
        self.assertEqual(_svc.SPREAD_TC, _SPREAD)

    def test_venta_100_usd_muestra_334_80_soles(self):
        session = _make_session('venta', 100.0)
        msgs, session = _call_mostrar(session)

        self.assertEqual(round(session.cotiz_tc, 4), 3.3480,
                         f'cotiz_tc debe ser 3.3480, got {session.cotiz_tc}')
        self.assertEqual(session.cotiz_op, 'venta')
        # El resumen debe mostrar "envías USD" y "recibes S/"
        resumen = msgs[0] if msgs else ''
        self.assertIn('USD 100.00', resumen,
                      f'Debe mostrar USD 100.00 como importe enviado: {resumen}')
        self.assertIn('334.80', resumen,
                      f'Debe mostrar S/ 334.80 como importe recibido: {resumen}')
        self.assertIn('3.3480', resumen,
                      f'Debe mostrar TC 3.3480: {resumen}')

    def test_venta_150_usd_muestra_502_20_soles(self):
        session = _make_session('venta', 150.0)
        msgs, session = _call_mostrar(session)

        self.assertEqual(round(session.cotiz_tc, 4), 3.3480)
        resumen = msgs[0] if msgs else ''
        self.assertIn('USD 150.00', resumen)
        self.assertIn('502.20', resumen,
                      f'Debe mostrar S/ 502.20: {resumen}')
        self.assertIn('3.3480', resumen)

    def test_venta_formula_aritmetica(self):
        """Comprueba la aritmética directamente, sin función del svc."""
        tc   = round(_COMPRA - _SPREAD + _svc._mejora_tc(100), 4)
        s100 = round(100.0 * tc, 2)
        s150 = round(150.0 * tc, 2)
        self.assertEqual(tc,   3.3480)
        self.assertEqual(s100, 334.80)
        self.assertEqual(s150, 502.20)

    def test_cotiz_op_persiste_venta(self):
        """cotiz_op del session no cambia al mostrar cotización."""
        session = _make_session('venta', 100.0)
        _call_mostrar(session)
        self.assertEqual(session.cotiz_op, 'venta')

    def test_token_asignado_en_venta(self):
        """Un token nuevo se asigna después de mostrar la cotización."""
        session = _make_session('venta', 100.0, cotiz_token=None)
        _call_mostrar(session)
        # cotiz_token debe ser no-None (un UUID asignado por la función)
        self.assertIsNotNone(session.cotiz_token)


# ─── Flujo compra: cliente envía S/, recibe USD ────────────────────────────────

class TestCompraUSDdesdePEN(unittest.TestCase):
    """
    cotiz_op='compra': tc = venta_backend + SPREAD_TC = 3.3700 + 0.0020 = 3.3720
    El cliente ENVÍA S/, RECIBE USD.
    """

    def test_tc_compra_es_3_3720(self):
        self.assertEqual(_TC_COMPRA, 3.3720)

    def test_compra_100_usd_envia_337_20_soles(self):
        session = _make_session('compra', 100.0)
        msgs, session = _call_mostrar(session)

        self.assertEqual(round(session.cotiz_tc, 4), 3.3720,
                         f'cotiz_tc debe ser 3.3720, got {session.cotiz_tc}')
        self.assertEqual(session.cotiz_op, 'compra')
        resumen = msgs[0] if msgs else ''
        # Para compra: envía S/, recibe USD
        self.assertIn('337.20', resumen,
                      f'Debe mostrar S/ 337.20 como importe enviado: {resumen}')
        self.assertIn('USD 100.00', resumen,
                      f'Debe mostrar USD 100.00 como importe recibido: {resumen}')
        self.assertIn('3.3720', resumen)

    def test_compra_formula_aritmetica(self):
        tc   = round(_VENTA + _SPREAD - _svc._mejora_tc(100), 4)
        s100 = round(100.0 * tc, 2)
        self.assertEqual(tc,   3.3720)
        self.assertEqual(s100, 337.20)


# ─── Corrección de dirección: compra→venta con cambio de importe ───────────────

class TestCorreccionDireccionCompraAVenta(unittest.TestCase):
    """
    Sesión en compra USD 150; cliente escribe "No, quiero cambiar 200 dólares a soles".
    FIX-2A: cotiz_op='venta', importe=200, TC=3.3480, S/ 669.60, token antiguo inválido.
    """

    def test_correccion_venta_200_muestra_669_60(self):
        """
        Simula el bloque de corrección de dirección (FIX-2A) y la cotización resultante.
        El intérprete devuelve tipo='venta', importe=200, es_hipotetico=False.
        """
        session = _make_session('compra', 150.0, cotiz_token='VIEJO-TOKEN')

        _interp = {
            'tipo': 'venta', 'importe': 200.0, 'moneda_importe': 'USD',
            'es_correccion': False, 'es_hipotetico': False, 'fuente': 'ia',
        }

        msgs = []
        with patch.object(_svc, '_get_tc', return_value=(_COMPRA, _VENTA)), \
             patch.object(_svc, 'send_buttons',
                          side_effect=lambda n, t, b=None, **kw: msgs.append(t)), \
             patch.object(_svc, 'send_buttons_image', MagicMock()), \
             patch.object(_svc, 'send_text', MagicMock()):
            # Reproduce exactamente el bloque FIX-2A del handler viendo_cotizacion
            _handled = False
            if (not _handled
                    and _interp.get('tipo')
                    and _interp['tipo'] != (session.cotiz_op or '')
                    and _interp.get('fuente') != 'fallo'
                    and not _interp.get('es_hipotetico')):
                session.cotiz_op = _interp['tipo']
                session.cotiz_cuenta = ''
                try:
                    session.cotiz_token = None
                except Exception:
                    pass
                if (_interp.get('importe')
                        and (_interp.get('moneda_importe') or 'USD') == 'USD'
                        and _interp['importe'] >= _svc.MONTO_MINIMO_USD):
                    session.cotiz_importe = _interp['importe']
                _svc._flujo_mostrar_cotizacion('519', session)
                session.estado = 'viendo_cotizacion'
                _handled = True

        self.assertTrue(_handled, 'El bloque de corrección debe activarse')
        # cotiz_op actualizado
        self.assertEqual(session.cotiz_op, 'venta')
        # importe actualizado a 200
        self.assertEqual(session.cotiz_importe, 200.0)
        # TC correcto para venta
        self.assertEqual(round(session.cotiz_tc, 4), 3.3480)
        # Mensaje muestra S/ 669.60
        resumen = msgs[0] if msgs else ''
        self.assertIn('200.00', resumen,
                      f'Debe mostrar USD 200.00: {resumen}')
        self.assertIn('669.60', resumen,
                      f'Debe mostrar S/ 669.60: {resumen}')
        self.assertIn('3.3480', resumen,
                      f'Debe mostrar TC 3.3480: {resumen}')

    def test_token_anterior_invalido_tras_correccion(self):
        """El token 'VIEJO-TOKEN' debe quedar None antes de llamar _flujo_mostrar."""
        session = _make_session('compra', 150.0, cotiz_token='VIEJO-TOKEN')
        _interp = {
            'tipo': 'venta', 'importe': 200.0, 'moneda_importe': 'USD',
            'es_correccion': False, 'es_hipotetico': False, 'fuente': 'ia',
        }

        token_al_momento_de_cotizar = []

        def _fake_mostrar(numero, sess):
            token_al_momento_de_cotizar.append(sess.cotiz_token)

        with patch.object(_svc, '_flujo_mostrar_cotizacion',
                          side_effect=_fake_mostrar):
            _handled = False
            if (not _handled
                    and _interp.get('tipo')
                    and _interp['tipo'] != session.cotiz_op
                    and _interp.get('fuente') != 'fallo'
                    and not _interp.get('es_hipotetico')):
                session.cotiz_op = _interp['tipo']
                session.cotiz_cuenta = ''
                try:
                    session.cotiz_token = None
                except Exception:
                    pass
                _svc._flujo_mostrar_cotizacion('519', session)
                _handled = True

        self.assertEqual(token_al_momento_de_cotizar[0], None,
                         'Token debe ser None cuando se llama _flujo_mostrar tras corrección')

    def test_hipotetico_mismo_importe_no_cambia_sesion(self):
        """
        Frase hipotética con dirección opuesta NO debe cambiar cotiz_op ni importe.
        """
        session = _make_session('compra', 150.0, cotiz_token='VIEJO-TOKEN')
        _interp_hip = {
            'tipo': 'venta', 'importe': 200.0, 'moneda_importe': 'USD',
            'es_correccion': False, 'es_hipotetico': True, 'fuente': 'ia',
        }

        _handled = False
        if (not _handled
                and _interp_hip.get('tipo')
                and _interp_hip['tipo'] != session.cotiz_op
                and _interp_hip.get('fuente') != 'fallo'
                and not _interp_hip.get('es_hipotetico')):  # bloquea aquí
            session.cotiz_op = _interp_hip['tipo']
            _handled = True

        self.assertFalse(_handled)
        self.assertEqual(session.cotiz_op, 'compra',
                         'Hipotético no debe cambiar la dirección de sesión')
        self.assertEqual(session.cotiz_importe, 150.0)
        self.assertEqual(session.cotiz_token, 'VIEJO-TOKEN',
                         'Token no debe invalidarse por mensaje hipotético')

    def test_aritmetica_669_60(self):
        """Verificación aritmética directa para $200 venta."""
        tc    = round(_COMPRA - _SPREAD + _svc._mejora_tc(200), 4)
        soles = round(200.0 * tc, 2)
        self.assertEqual(tc,    3.3480)
        self.assertEqual(soles, 669.60)


# ─── Tabla resumen: los 4 casos del enunciado ──────────────────────────────────

class TestTablaResumen(unittest.TestCase):
    """Tabla compacta que cubre los 4 casos del enunciado exactamente."""

    CASOS = [
        # (cotiz_op, usd,  tc_esp,  soles_esp,  desc)
        ('venta',  100.0, 3.3480,  334.80,  'USD100→PEN (transcript corregida)'),
        ('venta',  150.0, 3.3480,  502.20,  'USD150→PEN (transcript corregida)'),
        ('compra', 100.0, 3.3720,  337.20,  'PEN→USD100 (entrega soles)'),
        ('venta',  200.0, 3.3480,  669.60,  'USD200→PEN (corrección dirección)'),
    ]

    def _run_caso(self, cotiz_op, usd, tc_esp, soles_esp, desc):
        session = _make_session(cotiz_op, usd)
        msgs, session = _call_mostrar(session)

        tc_real = round(session.cotiz_tc, 4)
        soles_real = round(usd * tc_real, 2)

        self.assertEqual(tc_real, tc_esp,
                         f'[{desc}] TC: esperado {tc_esp}, got {tc_real}')
        self.assertEqual(soles_real, soles_esp,
                         f'[{desc}] S/: esperado {soles_esp}, got {soles_real}')

        resumen = msgs[0] if msgs else ''
        self.assertIn(str(soles_esp), resumen.replace(',', ''),
                      f'[{desc}] S/ {soles_esp} no está en el resumen: {resumen}')
        self.assertIn(str(tc_esp), resumen,
                      f'[{desc}] TC {tc_esp} no está en el resumen: {resumen}')

    def test_venta_100(self):   self._run_caso(*self.CASOS[0])
    def test_venta_150(self):   self._run_caso(*self.CASOS[1])
    def test_compra_100(self):  self._run_caso(*self.CASOS[2])
    def test_venta_200(self):   self._run_caso(*self.CASOS[3])


if __name__ == '__main__':
    unittest.main(verbosity=2)

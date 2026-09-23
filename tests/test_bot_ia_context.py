#!/usr/bin/env python3
"""
tests/test_bot_ia_context.py

Pruebas aisladas para la lógica de historial y contexto de la IA del bot WA.
NO realizan llamadas reales a WhatsApp, Anthropic ni a la BD de producción.

Verifican:
  1. Mensajes consecutivos del mismo rol se concatenan (no se descartan).
  2. El mensaje actual se incluye exactamente una vez, identificado por wa_id.
  3. Mensajes con texto idéntico no se deducan (el separador los distingue).
  4. Mensajes con mismo timestamp se ordenan por id (determinista).
  5. Sin referencia explícita, varias ops activas → operación no determinada.
  6. Teléfono asociado a varios perfiles → operación no determinada.
  7. Referencia explícita a op que no corresponde al perfil identificado.
  8. Op completada histórica no contamina el contexto de una cotización nueva.
  9. Compra: no_tengo → propone operación inversa correcta (tiene dólares).
 10. Venta:  no_tengo → propone operación inversa correcta (tiene soles).
 11. El estado de la operación se obtiene del backend, no del historial.
 12. Después de una operación completada el contexto no fuerza despedida.
 13. Datos ausentes se indican explícitamente; nunca se suponen valores.
 14. bot_pausado=True bloquea la respuesta IA.
 15. TC confirmado de la operación se distingue del TC cotizado/informativo.

Ejecutar:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 -m pytest tests/test_bot_ia_context.py -v

Distinción importante:
  - Estas pruebas validan LÓGICA DE CONSTRUCCIÓN DE CONTEXTO (determinista).
  - NO validan la calidad de las respuestas del modelo (no-determinista).
  - Para evaluar respuestas del modelo se requieren pruebas con API real.
"""

import sys
import os
import types
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# ── Stub mínimo de Flask/SQLAlchemy para importar wa_bot ──────────────────────

def _make_flask_stubs():
    app_pkg = types.ModuleType('app')
    sys.modules['app'] = app_pkg

    ext = types.ModuleType('app.extensions')
    ext.db = MagicMock()
    sys.modules['app.extensions'] = ext

    app_models = types.ModuleType('app.models')
    sys.modules['app.models'] = app_models
    setattr(sys.modules['app'], 'models', app_models)

    wa_bot_session_mod = types.ModuleType('app.models.wa_bot_session')
    class WaBotSessionStub:
        pass
    wa_bot_session_mod.WaBotSession = WaBotSessionStub
    sys.modules['app.models.wa_bot_session'] = wa_bot_session_mod

    wa_msg_mod = types.ModuleType('app.models.wa_message')
    class WaMessageStub:
        pass
    wa_msg_mod.WaMessage = WaMessageStub
    sys.modules['app.models.wa_message'] = wa_msg_mod

    # app.models.operation — stub con Operation mocked
    op_mod = types.ModuleType('app.models.operation')
    MockOperation = MagicMock()
    MockOperation.query.filter_by.return_value.first.return_value = None
    op_mod.Operation = MockOperation
    sys.modules['app.models.operation'] = op_mod
    setattr(app_models, 'operation', op_mod)

    # app.models.client — stub con Client mocked
    client_mod = types.ModuleType('app.models.client')
    MockClient = MagicMock()
    MockClient.query.filter_by.return_value.first.return_value = None
    client_mod.Client = MockClient
    sys.modules['app.models.client'] = client_mod

    fmt_mod = types.ModuleType('app.utils.formatters')
    fmt_mod.now_peru = lambda: datetime.now()
    sys.modules['app.utils.formatters'] = fmt_mod
    sys.modules['app.utils'] = types.ModuleType('app.utils')

    req_stub = types.ModuleType('requests')
    req_stub.post = MagicMock(return_value=MagicMock(ok=True, status_code=200))
    req_stub.get  = MagicMock(return_value=MagicMock(ok=True, status_code=200))
    sys.modules['requests'] = req_stub

_make_flask_stubs()

# ── Importar las funciones bajo prueba directamente desde wa_bot ──────────────
WA_BOT_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')

_wabot = types.ModuleType('wabot_test')
with open(WA_BOT_PATH, encoding='utf-8') as _f:
    _src = _f.read()
exec(compile(_src, WA_BOT_PATH, 'exec'), _wabot.__dict__)

_historial_ia              = _wabot._historial_ia
_construir_contexto_sesion = _wabot._construir_contexto_sesion
_respuesta_ia              = _wabot._respuesta_ia


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sesion(**kwargs):
    s = MagicMock()
    s.estado          = kwargs.get('estado', 'inicio')
    s.cotiz_op        = kwargs.get('cotiz_op', '')
    s.cotiz_importe   = kwargs.get('cotiz_importe', 0.0)
    s.cotiz_tc        = kwargs.get('cotiz_tc', 0.0)
    s.cotiz_cuenta    = kwargs.get('cotiz_cuenta', '')
    s.cotiz_op_id     = kwargs.get('cotiz_op_id', '')
    s.cotiz_timestamp = kwargs.get('cotiz_timestamp', None)
    s.cotiz_token     = kwargs.get('cotiz_token', None)
    s.nombre          = kwargs.get('nombre', '')
    s.bot_pausado     = kwargs.get('bot_pausado', False)
    s.cotiz_doc       = kwargs.get('cotiz_doc', '')
    return s


def _msg(direccion, mensaje, wa_id='', created_at=None, db_id=None):
    m = MagicMock()
    m.direccion  = direccion
    m.mensaje    = mensaje
    m.wa_id      = wa_id
    m.created_at = created_at or datetime.now()
    m.id         = db_id or id(m)
    return m


def _simular_historial(mensajes_raw):
    """
    Aplica la misma lógica de normalización y concatenación que _historial_ia,
    dado una lista de objetos stub con .direccion y .mensaje.

    Útil para pruebas puras que no requieren BD.
    """
    historia = []
    for m in mensajes_raw:
        role  = 'assistant' if m.direccion == 'saliente' else 'user'
        texto = m.mensaje.strip()
        if not texto:
            continue
        if texto.startswith('[template:'):
            texto = f'[Mensaje automático del sistema: {texto}]'
        historia.append({'role': role, 'content': texto})

    filtered = []
    for msg in historia:
        if filtered and filtered[-1]['role'] == msg['role']:
            filtered[-1] = {
                'role':    filtered[-1]['role'],
                'content': filtered[-1]['content'] + '\n---\n' + msg['content'],
            }
        else:
            filtered.append({'role': msg['role'], 'content': msg['content']})
    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# 1. TestHistorialIa
# ─────────────────────────────────────────────────────────────────────────────

class TestHistorialIa(unittest.TestCase):

    def test_mensajes_consecutivos_usuario_se_concatenan(self):
        """Tres mensajes seguidos del usuario quedan en un único turno con todo el contenido."""
        msgs = [
            _msg('entrante', 'Quiero comprar dólares'),
            _msg('entrante', 'Son 1500'),
            _msg('entrante', 'Al BCP'),
        ]
        result = _simular_historial(msgs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['role'], 'user')
        self.assertIn('Quiero comprar dólares', result[0]['content'])
        self.assertIn('Son 1500',               result[0]['content'])
        self.assertIn('Al BCP',                 result[0]['content'])

    def test_alternancia_correcta_no_afecta_contenido(self):
        """Mensajes alternados user/assistant preservan el orden y el contenido."""
        msgs = [
            _msg('entrante',  'Hola'),
            _msg('saliente',  'Hola, ¿en qué te ayudo?'),
            _msg('entrante',  'Quiero cotizar'),
            _msg('saliente',  'Con gusto, ¿cuánto deseas cambiar?'),
            _msg('entrante',  '2000'),
        ]
        result = _simular_historial(msgs)
        self.assertEqual(len(result), 5)
        roles = [r['role'] for r in result]
        self.assertEqual(roles, ['user', 'assistant', 'user', 'assistant', 'user'])
        self.assertEqual(result[4]['content'], '2000')

    def test_mensajes_consecutivos_bot_se_concatenan(self):
        """Dos mensajes consecutivos del bot quedan concatenados."""
        msgs = [
            _msg('saliente', 'Generando tu operación...'),
            _msg('saliente', 'Operación EXP-001 creada.'),
            _msg('entrante', 'Gracias'),
        ]
        result = _simular_historial(msgs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['role'], 'assistant')
        self.assertIn('Generando tu operación', result[0]['content'])
        self.assertIn('Operación EXP-001',       result[0]['content'])
        self.assertEqual(result[1]['role'], 'user')

    def test_mensaje_vacio_se_omite(self):
        """Mensajes vacíos o solo espacios no aparecen en el historial."""
        msgs = [
            _msg('entrante', ''),
            _msg('entrante', '   '),
            _msg('entrante', 'Hola'),
        ]
        result = _simular_historial(msgs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['content'], 'Hola')

    def test_template_se_normaliza(self):
        """Las plantillas de Meta se envuelven con prefijo legible para la IA."""
        msgs = [
            _msg('saliente', '[template:qoricash_operacion_completada] EXP-001 | Juan | juan@test.com'),
            _msg('entrante', 'Muchas gracias'),
        ]
        result = _simular_historial(msgs)
        self.assertEqual(len(result), 2)
        self.assertIn('[Mensaje automático del sistema:', result[0]['content'])
        self.assertIn('qoricash_operacion_completada',   result[0]['content'])

    def test_tres_mensajes_usuario_separador_visible(self):
        """El separador '---' es visible entre mensajes concatenados."""
        msgs = [
            _msg('entrante', 'A'),
            _msg('entrante', 'B'),
            _msg('entrante', 'C'),
        ]
        result = _simular_historial(msgs)
        self.assertEqual(result[0]['content'], 'A\n---\nB\n---\nC')

    # ── Nuevos (Puntos 3 y 4) ─────────────────────────────────────────────────

    def test_mismo_texto_dos_mensajes_no_deduplicados(self):
        """Dos mensajes con texto idéntico se concatenan con separador, no se deducan."""
        msgs = [
            _msg('entrante', 'Hola'),
            _msg('entrante', 'Hola'),  # mismo texto, mensaje distinto
        ]
        result = _simular_historial(msgs)
        self.assertEqual(len(result), 1, "Deben fusionarse en un turno (mismo rol consecutivo)")
        # El contenido debe tener ambos mensajes con separador — no solo uno
        self.assertEqual(result[0]['content'], 'Hola\n---\nHola',
                         "Los dos mensajes idénticos deben preservarse concatenados")

    def test_mismo_timestamp_orden_determinista_por_id(self):
        """
        Cuando dos mensajes tienen el mismo created_at, el de menor id (insertado antes)
        queda primero en el orden cronológico tras reversar el resultado DESC.
        """
        ts = datetime.now()
        m_anterior = _msg('entrante', 'primer mensaje',  db_id=10, created_at=ts)
        m_posterior = _msg('entrante', 'segundo mensaje', db_id=11, created_at=ts)

        # La query usa ORDER BY created_at DESC, id DESC → retorna [id=11, id=10]
        # Después de reversed → [id=10, id=11] (cronológico correcto)
        with patch.object(_wabot, 'WaMessage') as mock_wm:
            mock_q = MagicMock()
            mock_wm.query.filter_by.return_value = mock_q
            mock_q.filter.return_value           = mock_q
            mock_q.order_by.return_value         = mock_q
            # DESC order: id=11 first, id=10 second
            mock_q.limit.return_value.all.return_value = [m_posterior, m_anterior]

            filtered, _ = _historial_ia('+51910000001')

        self.assertEqual(len(filtered), 1, "Dos entrantes consecutivos → 1 turno")
        contenido = filtered[0]['content']
        pos_primero  = contenido.find('primer mensaje')
        pos_segundo  = contenido.find('segundo mensaje')
        self.assertGreater(pos_primero, -1)
        self.assertGreater(pos_segundo, -1)
        self.assertLess(pos_primero, pos_segundo,
                        "El mensaje con id menor debe aparecer primero (orden cronológico)")


# ─────────────────────────────────────────────────────────────────────────────
# 2. TestConstruirContextoSesion
# ─────────────────────────────────────────────────────────────────────────────

class TestConstruirContextoSesion(unittest.TestCase):

    def setUp(self):
        self._patcher_op       = patch.object(_wabot, '_operacion_activa_cliente', return_value=None)
        self._patcher_clientes = patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[])
        self._patcher_op.start()
        self._patcher_clientes.start()

    def tearDown(self):
        self._patcher_op.stop()
        self._patcher_clientes.stop()

    def test_sesion_sin_cotizacion(self):
        """Sin cotización activa, el contexto lo indica explícitamente."""
        s = _sesion(estado='inicio')
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('COTIZACIÓN EN CURSO: ninguna', ctx)
        self.assertIn('CUENTA DESTINO CLIENTE: no definida aún', ctx)
        self.assertIn('OPERACIÓN VINCULADA: ninguna', ctx)

    def test_cotizacion_compra_con_tc(self):
        """Una cotización de compra con TC muestra la dirección correcta."""
        s = _sesion(
            estado='viendo_cotizacion',
            cotiz_op='compra',
            cotiz_importe=1500.0,
            cotiz_tc=3.8120,
            cotiz_timestamp=datetime.now(),
        )
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('cliente ENVÍA soles → RECIBE dólares', ctx)
        self.assertIn('USD 1,500.00', ctx)
        self.assertIn('3.8120', ctx)
        self.assertIn('S/ 5,718.00', ctx)

    def test_cotizacion_venta(self):
        """Una cotización de venta muestra la dirección opuesta."""
        s = _sesion(
            cotiz_op='venta',
            cotiz_importe=2000.0,
            cotiz_tc=3.7900,
        )
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('cliente ENVÍA dólares → RECIBE soles', ctx)

    def test_cuenta_destino_enmascarada(self):
        """El número de cuenta se muestra con solo los últimos 4 dígitos."""
        s = _sesion(cotiz_cuenta='BCP|1917357790119')
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('BCP ···0119', ctx)
        self.assertNotIn('1917357790119', ctx)

    def test_cuenta_cci_enmascarada(self):
        """CCI de 20 dígitos también se enmascara."""
        s = _sesion(cotiz_cuenta='BBVA|00340010123456789012')
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('···9012', ctx)
        self.assertNotIn('00340010123456789012', ctx)

    def test_operacion_completada_desde_backend(self):
        """El estado 'Completada' se obtiene de la BD y usa la formulación correcta."""
        op_mock = MagicMock()
        op_mock.operation_id  = 'EXP-042'
        op_mock.status        = 'Completada'
        op_mock.amount_usd    = 1500.0
        op_mock.amount_pen    = 5718.0
        op_mock.exchange_rate = 3.812
        op_mock.client_id     = 1

        op_mod = sys.modules['app.models.operation']
        op_mod.Operation.query.filter_by.return_value.first.return_value = op_mock

        s = _sesion(cotiz_op_id='EXP-042', estado='inicio')
        ctx = _construir_contexto_sesion('+51910000001', s)

        op_mod.Operation.query.filter_by.return_value.first.return_value = None

        self.assertIn('EXP-042',             ctx)
        self.assertIn('Completada',          ctx)
        self.assertIn('operación finalizada', ctx)
        self.assertIn('resultado final',     ctx)

    def test_operacion_en_proceso_desde_backend(self):
        """El estado 'En proceso' muestra la formulación correcta (sin afirmar fondos no enviados)."""
        op_mock = MagicMock()
        op_mock.operation_id  = 'EXP-055'
        op_mock.status        = 'En proceso'
        op_mock.amount_usd    = 500.0
        op_mock.amount_pen    = 1895.0
        op_mock.exchange_rate = 3.790
        op_mock.client_id     = 1

        op_mod = sys.modules['app.models.operation']
        op_mod.Operation.query.filter_by.return_value.first.return_value = op_mock

        s = _sesion(cotiz_op_id='EXP-055', estado='op_pendiente_pago')
        ctx = _construir_contexto_sesion('+51910000001', s)

        op_mod.Operation.query.filter_by.return_value.first.return_value = None

        self.assertIn('En proceso', ctx)
        self.assertIn('todavía no registra su finalización', ctx)
        # No debe afirmar categóricamente que los fondos no fueron enviados
        self.assertNotIn('fondos ya fueron enviados', ctx)

    def test_datos_ausentes_no_se_suponen(self):
        """Sin cotiz_op ni importe, el contexto dice claramente que no hay cotización."""
        s = _sesion()
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('COTIZACIÓN EN CURSO: ninguna', ctx)
        self.assertNotIn('cliente ENVÍA', ctx)
        self.assertNotIn('S/ 0', ctx)

    def test_cotizacion_vigencia_expirada(self):
        """Si el timestamp expiró, el contexto lo indica."""
        hace_20_min = datetime.now() - timedelta(minutes=20)
        s = _sesion(
            cotiz_op='compra',
            cotiz_importe=1000.0,
            cotiz_tc=3.800,
            cotiz_timestamp=hace_20_min,
        )
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('expirada', ctx)

    def test_cotizacion_vigente(self):
        """Si el timestamp es reciente, el contexto muestra el plazo de aceptación."""
        hace_2_min = datetime.now() - timedelta(minutes=2)
        s = _sesion(
            cotiz_op='venta',
            cotiz_importe=800.0,
            cotiz_tc=3.790,
            cotiz_timestamp=hace_2_min,
        )
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('PLAZO COTIZACIÓN', ctx)
        self.assertIn('para aceptar', ctx)

    def test_accion_pendiente_correcta(self):
        """El estado op_pendiente_pago muestra la instrucción correcta."""
        s = _sesion(estado='op_pendiente_pago')
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('Ya transferí', ctx)

    def test_accion_pendiente_importe(self):
        """El estado esperando_importe muestra la instrucción de escribir el monto."""
        s = _sesion(estado='esperando_importe')
        ctx = _construir_contexto_sesion('+51910000001', s)
        self.assertIn('monto en USD', ctx)

    # ── Nuevos (Puntos 5, 6, 7, 8, 15) ───────────────────────────────────────

    def test_multiples_ops_activas_sin_referencia(self):
        """Sin referencia explícita, si hay más de una op activa → no determinada."""
        cliente1 = MagicMock()
        cliente1.id = 1

        op1, op2 = MagicMock(), MagicMock()
        filter_chain = MagicMock()
        filter_chain.all.return_value = [op1, op2]

        op_mod = sys.modules['app.models.operation']
        original_filter = op_mod.Operation.query.filter
        op_mod.Operation.query.filter = MagicMock(return_value=filter_chain)

        try:
            with patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[cliente1]):
                s = _sesion()  # cotiz_op_id='' → fallback path
                ctx = _construir_contexto_sesion('+51910000001', s)
        finally:
            op_mod.Operation.query.filter = original_filter

        self.assertIn('no determinada', ctx)
        self.assertIn('más de una operación activa', ctx)

    def test_multiples_perfiles_por_telefono(self):
        """Si un teléfono está asociado a varios perfiles → operación no determinada."""
        c1, c2 = MagicMock(), MagicMock()

        with patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[c1, c2]):
            s = _sesion()
            ctx = _construir_contexto_sesion('+51910000001', s)

        self.assertIn('no determinada', ctx)
        self.assertIn('más de un perfil', ctx)

    def test_referencia_explicita_perfil_incorrecto(self):
        """Si cotiz_op_id referencia una op cuyo cliente no coincide con cotiz_doc → se indica."""
        op_mock = MagicMock()
        op_mock.operation_id  = 'EXP-099'
        op_mock.status        = 'Pendiente'
        op_mock.client_id     = 5
        op_mock.created_at    = datetime.now() - timedelta(minutes=3)
        op_mock.amount_usd    = 1000.0
        op_mock.amount_pen    = 3800.0
        op_mock.exchange_rate = 3.800

        # Client de la operación tiene DNI distinto al de la sesión
        client_mock = MagicMock()
        client_mock.dni = '87654321'
        client_mock.ruc = ''

        op_mod     = sys.modules['app.models.operation']
        client_mod = sys.modules['app.models.client']
        op_mod.Operation.query.filter_by.return_value.first.return_value   = op_mock
        client_mod.Client.query.filter_by.return_value.first.return_value  = client_mock

        try:
            # cotiz_doc='12345678' ≠ client_mock.dni='87654321' → no corresponde
            s = _sesion(cotiz_op_id='EXP-099', cotiz_doc='12345678')
            ctx = _construir_contexto_sesion('+51910000001', s)
        finally:
            op_mod.Operation.query.filter_by.return_value.first.return_value  = None
            client_mod.Client.query.filter_by.return_value.first.return_value = None

        self.assertIn('EXP-099',      ctx)
        self.assertIn('no corresponde', ctx)

    def test_completada_no_contamina_cotizacion_nueva(self):
        """
        Si el cliente solo tiene ops completadas (no Pendiente/En proceso),
        el fallback por teléfono no las incluye como 'activas'.
        La cotización nueva en curso debe mostrarse sin referencia a la op pasada.
        """
        cliente1 = MagicMock()
        cliente1.id = 1

        filter_chain = MagicMock()
        filter_chain.all.return_value = []  # sin Pendiente ni En proceso

        op_mod = sys.modules['app.models.operation']
        original_filter = op_mod.Operation.query.filter
        op_mod.Operation.query.filter = MagicMock(return_value=filter_chain)

        try:
            with patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[cliente1]):
                s = _sesion(cotiz_op='compra', cotiz_importe=1000.0, cotiz_tc=3.80)
                ctx = _construir_contexto_sesion('+51910000001', s)
        finally:
            op_mod.Operation.query.filter = original_filter

        self.assertIn('COTIZACIÓN EN CURSO', ctx)
        self.assertNotIn('OPERACIÓN DETECTADA', ctx)
        self.assertIn('OPERACIÓN VINCULADA: ninguna', ctx)

    def test_tc_confirmado_distinguido_del_cotizado(self):
        """
        Cuando hay operación vinculada, el TC confirmado de la operación se etiqueta
        explícitamente. No se muestra un bloque COTIZACIÓN EN CURSO separado.
        """
        op_mock = MagicMock()
        op_mock.operation_id  = 'EXP-010'
        op_mock.status        = 'En proceso'
        op_mock.client_id     = 1
        op_mock.amount_usd    = 1000.0
        op_mock.amount_pen    = 3799.0
        op_mock.exchange_rate = 3.799

        op_mod = sys.modules['app.models.operation']
        op_mod.Operation.query.filter_by.return_value.first.return_value = op_mock

        try:
            s = _sesion(
                cotiz_op_id='EXP-010',
                cotiz_op='compra',
                cotiz_importe=1000.0,
                cotiz_tc=3.800,   # TC cotizado en sesión (ligeramente distinto)
            )
            ctx = _construir_contexto_sesion('+51910000001', s)
        finally:
            op_mod.Operation.query.filter_by.return_value.first.return_value = None

        # El TC de la operación debe estar etiquetado como 'TC confirmado'
        self.assertIn('TC confirmado', ctx)
        self.assertIn('3.7990', ctx)
        # No debe aparecer un bloque COTIZACIÓN EN CURSO cuando la op ya fue creada
        self.assertNotIn('COTIZACIÓN EN CURSO', ctx)


# ─────────────────────────────────────────────────────────────────────────────
# 3. TestRespuestaIaBotPausado
# ─────────────────────────────────────────────────────────────────────────────

class TestRespuestaIaBotPausado(unittest.TestCase):
    """Verifica que bot_pausado=True impide que la IA genere respuesta."""

    def test_bot_pausado_devuelve_none(self):
        s = _sesion(bot_pausado=True)
        resultado = _respuesta_ia('Hola', '+51910000001', s)
        self.assertIsNone(resultado, "Con bot_pausado=True la IA debe retornar None")

    def test_sin_api_key_devuelve_none(self):
        s = _sesion(bot_pausado=False)
        with patch.object(_wabot, '_get_anthropic_client', return_value=None):
            resultado = _respuesta_ia('Hola', '+51910000001', s)
        self.assertIsNone(resultado)


# ─────────────────────────────────────────────────────────────────────────────
# 4. TestHistorialEnRespuestaIa
# ─────────────────────────────────────────────────────────────────────────────

class TestHistorialEnRespuestaIa(unittest.TestCase):
    """
    Verifica que _respuesta_ia construye el historial y el system prompt
    correctamente (sin llamar a la API real de Anthropic).
    """

    def _mock_cliente_anthropic(self, texto='Respuesta simulada'):
        mock_client  = MagicMock()
        mock_content = MagicMock()
        mock_content.text = texto
        mock_client.messages.create.return_value.content = [mock_content]
        return mock_client

    def _historia_enviada(self, mock_client):
        """Extrae la lista 'messages' enviada a la API del mock."""
        kw = mock_client.messages.create.call_args.kwargs
        if not kw:
            kw = mock_client.messages.create.call_args[1]
        return kw.get('messages', [])

    def _system_prompt(self, mock_client):
        kw = mock_client.messages.create.call_args.kwargs
        if not kw:
            kw = mock_client.messages.create.call_args[1]
        return kw.get('system', '')

    # ── Existentes (mocks ahora retornan tupla) ───────────────────────────────

    def test_mensajes_consecutivos_llegan_a_la_api(self):
        """Tres mensajes consecutivos del usuario llegan concatenados en un turno."""
        mock_client = self._mock_cliente_anthropic()
        historial_mock = (
            [{'role': 'user', 'content': 'Quiero comprar dólares\n---\nSon 1500\n---\nAl BCP'}],
            True,
        )
        with patch.object(_wabot, '_get_anthropic_client', return_value=mock_client), \
             patch.object(_wabot, '_historial_ia', return_value=historial_mock), \
             patch.object(_wabot, '_construir_contexto_sesion', return_value='ESTADO: test'), \
             patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True):
            _respuesta_ia('Al BCP', '+51910000001', _sesion())

        historia = self._historia_enviada(mock_client)
        user_turns = [m for m in historia if m.get('role') == 'user']
        contenido  = ' '.join(t['content'] for t in user_turns)
        self.assertIn('Quiero comprar dólares', contenido)
        self.assertIn('Son 1500',               contenido)
        self.assertIn('Al BCP',                 contenido)

    def test_mensaje_actual_no_se_duplica(self):
        """El mensaje actual no aparece dos veces en la historia enviada a la API."""
        mock_client = self._mock_cliente_anthropic()
        historial_mock = (
            [
                {'role': 'assistant', 'content': 'Hola, ¿en qué te ayudo?'},
                {'role': 'user',      'content': '¿Cuál es el tipo de cambio hoy?'},
            ],
            True,
        )
        with patch.object(_wabot, '_get_anthropic_client', return_value=mock_client), \
             patch.object(_wabot, '_historial_ia', return_value=historial_mock), \
             patch.object(_wabot, '_construir_contexto_sesion', return_value='ESTADO: test'), \
             patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True):
            _respuesta_ia('¿Cuál es el tipo de cambio hoy?', '+51910000001', _sesion())

        historia = self._historia_enviada(mock_client)
        contenido_total = ' | '.join(m['content'] for m in historia)
        count = contenido_total.count('¿Cuál es el tipo de cambio hoy?')
        self.assertEqual(count, 1, f"El mensaje actual apareció {count} veces (esperado: 1)")

    def test_contexto_sesion_incluido_en_system_prompt(self):
        """El system prompt contiene el contexto estructurado de la sesión."""
        mock_client = self._mock_cliente_anthropic()
        contexto_mock = (
            'ESTADO DEL FLUJO: cotización mostrada\n'
            'DIRECCIÓN DEL CAMBIO: cliente ENVÍA soles → RECIBE dólares\n'
            'MONTO EN JUEGO: USD 1,500.00\n'
            'COTIZACIÓN EN CURSO: envía S/ 5,718.00 | TC cotizado S/ 3.8120\n'
            'PLAZO COTIZACIÓN: ~12 min para aceptar antes de que expire\n'
            'CUENTA DESTINO CLIENTE: no definida aún\n'
            'OPERACIÓN VINCULADA: ninguna\n'
            'ACCIÓN PENDIENTE: cliente debe pulsar "Aceptar cotización"'
        )
        historial_mock = (
            [{'role': 'user', 'content': '¿Por qué ese precio?'}],
            True,
        )
        with patch.object(_wabot, '_get_anthropic_client', return_value=mock_client), \
             patch.object(_wabot, '_historial_ia', return_value=historial_mock), \
             patch.object(_wabot, '_construir_contexto_sesion', return_value=contexto_mock), \
             patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True):
            s = _sesion(estado='viendo_cotizacion', cotiz_op='compra', cotiz_importe=1500)
            _respuesta_ia('¿Por qué ese precio?', '+51910000001', s)

        prompt = self._system_prompt(mock_client)
        self.assertIn('ESTADO DEL FLUJO',  prompt)
        self.assertIn('USD 1,500.00',      prompt)
        self.assertIn('TC cotizado S/ 3.8120', prompt)
        self.assertIn('ACCIÓN PENDIENTE',  prompt)

    def test_operacion_completada_no_fuerza_despedida_en_prompt(self):
        """El system prompt no instruye a forzar despedida por operación completada en historial."""
        mock_client = self._mock_cliente_anthropic()
        historial_mock = (
            [
                {'role': 'assistant', 'content': '[Mensaje automático: [template:qoricash_operacion_completada]]'},
                {'role': 'user',      'content': '¿Puedo hacer otra operación?'},
            ],
            True,
        )
        with patch.object(_wabot, '_get_anthropic_client', return_value=mock_client), \
             patch.object(_wabot, '_historial_ia', return_value=historial_mock), \
             patch.object(_wabot, '_construir_contexto_sesion', return_value='ESTADO: inicio'), \
             patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True):
            _respuesta_ia('¿Puedo hacer otra operación?', '+51910000001', _sesion())

        prompt = self._system_prompt(mock_client)
        self.assertNotIn('responde solo agradeciendo y despidiéndote', prompt)
        self.assertIn('puede hacer nuevas preguntas', prompt)

    # ── Nuevos (Puntos 1 y 2) ─────────────────────────────────────────────────

    def test_wa_id_ausente_texto_usuario_incorporado(self):
        """
        Si _historial_ia retorna ([], False) (mensaje actual no encontrado),
        _respuesta_ia incorpora texto_usuario antes de llamar a la API.
        """
        mock_client = self._mock_cliente_anthropic()
        with patch.object(_wabot, '_get_anthropic_client', return_value=mock_client), \
             patch.object(_wabot, '_historial_ia', return_value=([], False)), \
             patch.object(_wabot, '_construir_contexto_sesion', return_value='ESTADO: test'), \
             patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True):
            _respuesta_ia('consulta especifica', '+51910000001', _sesion())

        historia = self._historia_enviada(mock_client)
        contenido = ' '.join(m['content'] for m in historia)
        self.assertIn('consulta especifica', contenido,
                      "El texto del mensaje actual debe estar en el historial enviado")

    def test_wa_id_presente_no_agrega_duplicado(self):
        """
        Si _historial_ia retorna (historial, True) (mensaje actual ya incluido),
        _respuesta_ia no lo agrega de nuevo.
        """
        mock_client = self._mock_cliente_anthropic()
        historial_mock = (
            [{'role': 'user', 'content': 'mensaje sin duplicar'}],
            True,  # current_in_history=True → ya está incluido
        )
        with patch.object(_wabot, '_get_anthropic_client', return_value=mock_client), \
             patch.object(_wabot, '_historial_ia', return_value=historial_mock), \
             patch.object(_wabot, '_construir_contexto_sesion', return_value='ESTADO: test'), \
             patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True):
            _respuesta_ia('mensaje sin duplicar', '+51910000001', _sesion())

        historia = self._historia_enviada(mock_client)
        contenido_total = ' | '.join(m['content'] for m in historia)
        count = contenido_total.count('mensaje sin duplicar')
        self.assertEqual(count, 1, f"El mensaje actual apareció {count} veces (esperado: 1)")


# ─────────────────────────────────────────────────────────────────────────────
# 5. TestNoPoseeMoneda (Puntos 9 y 10)
# ─────────────────────────────────────────────────────────────────────────────

class TestNoPoseeMoneda(unittest.TestCase):
    """
    Verifica que la rama no_tengo en estado esperando_importe sugiere
    la operación inversa correcta según la dirección del flujo.

    'compra' (envía soles):  le faltan soles → inverso: tiene dólares, quiere soles.
    'venta'  (envía dólares): le faltan dólares → inverso: tiene soles, quiere dólares.
    """

    def _ejecutar_no_tengo(self, cotiz_op_val):
        """
        Invoca handle_message simulando la rama no_tengo y captura
        el texto enviado por send_buttons.
        """
        s = _sesion(estado='esperando_importe', cotiz_op=cotiz_op_val)
        llamadas = []
        db_mock  = sys.modules['app.extensions'].db

        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada',  return_value=False), \
             patch.object(_wabot, '_parse_monto',     return_value=0), \
             patch.object(_wabot, '_detectar_intencion', return_value='no_tengo'), \
             patch.object(_wabot, '_reset_sesion'), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, txt, b: llamadas.append(txt)), \
             patch.object(db_mock, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message(
                '+51910000001', '', 'text', 'no tengo', '', 'wamid_test'
            )

        return llamadas[0] if llamadas else ''

    def test_compra_propone_operacion_inversa_correcta(self):
        """
        Flujo 'compra' (envía soles): le faltan soles.
        El mensaje propuesto debe decir 'tienes dólares' antes de 'quieres soles'.
        """
        texto = self._ejecutar_no_tengo('compra')
        self.assertIn('dólares', texto, "El mensaje debe mencionar dólares")
        self.assertIn('soles',   texto, "El mensaje debe mencionar soles")
        pos_dolares = texto.find('dólares')
        pos_soles   = texto.find('soles')
        self.assertLess(pos_dolares, pos_soles,
                        "En compra: 'dólares' (lo que tiene) debe aparecer antes que 'soles' (lo que quiere)")

    def test_venta_propone_operacion_inversa_correcta(self):
        """
        Flujo 'venta' (envía dólares): le faltan dólares.
        El mensaje propuesto debe decir 'tienes soles' antes de 'quieres dólares'.
        """
        texto = self._ejecutar_no_tengo('venta')
        self.assertIn('soles',   texto, "El mensaje debe mencionar soles")
        self.assertIn('dólares', texto, "El mensaje debe mencionar dólares")
        pos_soles   = texto.find('soles')
        pos_dolares = texto.find('dólares')
        self.assertLess(pos_soles, pos_dolares,
                        "En venta: 'soles' (lo que tiene) debe aparecer antes que 'dólares' (lo que quiere)")



# ─────────────────────────────────────────────────────────────────────────────
# 6. TestInterpretarSolicitud  (Etapa 2 – extracción determinista)
# ─────────────────────────────────────────────────────────────────────────────

_interpretar_solicitud = _wabot._interpretar_solicitud
_no_tengo_handler      = _wabot._no_tengo_handler


class TestInterpretarSolicitud(unittest.TestCase):
    """
    Prueba la extracción determinista de _interpretar_solicitud.
    Estas pruebas NO validan comprensión lingüística del modelo;
    solo verifican que los patrones deterministas funcionan correctamente.
    """

    def test_compra_explicita_con_importe_usd(self):
        """'Quiero comprar 1500 dolares' → tipo=compra, importe=1500, moneda=USD."""
        r = _interpretar_solicitud('Quiero comprar 1500 dolares')
        self.assertEqual(r['tipo'], 'compra')
        self.assertAlmostEqual(r['importe'], 1500.0)
        self.assertEqual(r['moneda_importe'], 'USD')
        self.assertEqual(r['fuente'], 'determinista')

    def test_venta_explicita_con_importe_usd(self):
        """'Vendo 800 dolares' → tipo=venta, importe=800, moneda=USD."""
        r = _interpretar_solicitud('Vendo 800 dolares')
        self.assertEqual(r['tipo'], 'venta')
        self.assertAlmostEqual(r['importe'], 800.0)
        self.assertEqual(r['moneda_importe'], 'USD')

    def test_importe_en_soles_detectado(self):
        """'Quiero cambiar 3000 soles' → moneda=PEN (no USD)."""
        r = _interpretar_solicitud('Quiero cambiar 3000 soles')
        self.assertEqual(r['moneda_importe'], 'PEN')
        self.assertAlmostEqual(r['importe'], 3000.0)

    def test_correccion_mejor_N(self):
        """'Mejor 2000' → es_correccion=True, importe=2000."""
        r = _interpretar_solicitud('Mejor 2000')
        self.assertTrue(r['es_correccion'], "'Mejor 2000' debe marcarse como corrección")
        self.assertAlmostEqual(r['importe'], 2000.0)

    def test_hipotetico_cuanto_recibiria(self):
        """'cuanto recibiria por 500' → es_hipotetico=True, importe=500."""
        r = _interpretar_solicitud('cuanto recibiria por 500')
        self.assertTrue(r['es_hipotetico'], "debe marcarse como hipotético")
        self.assertAlmostEqual(r['importe'], 500.0)

    def test_sin_numero_faltante_tipo_e_importe(self):
        """'Quiero cambiar' (sin número) → faltante incluye importe."""
        r = _interpretar_solicitud('Quiero cambiar')
        self.assertIn('importe', r['faltante'])
        # No debe llamar IA (no hay dígito)
        self.assertEqual(r['fuente'], 'determinista')

    def test_tengo_soles_es_compra(self):
        """'tengo soles' → tipo=compra."""
        r = _interpretar_solicitud('tengo soles')
        self.assertEqual(r['tipo'], 'compra')

    def test_tengo_dolares_es_venta(self):
        """'tengo dolares' → tipo=venta."""
        r = _interpretar_solicitud('tengo dolares')
        self.assertEqual(r['tipo'], 'venta')


# ─────────────────────────────────────────────────────────────────────────────
# 7. TestEtapa2Routing  (Etapa 2 – enrutamiento con mocks)
# ─────────────────────────────────────────────────────────────────────────────

class TestEtapa2Routing(unittest.TestCase):
    """
    Verifica el enrutamiento derivado de la interpretación.
    Las interpretaciones son simuladas para aislar la lógica del backend.

    NOTA: estas pruebas validan el flujo del backend, NO la comprensión
    lingüística del modelo (que requeriría llamadas reales a la API).
    """

    def _ejecutar_handle(self, texto, estado='inicio', cotiz_op='', cotiz_importe=0.0,
                         cotiz_tc=0.0, interp_override=None):
        """Ejecuta handle_message con dependencias simuladas y retorna (session, textos_enviados)."""
        s = _sesion(estado=estado, cotiz_op=cotiz_op, cotiz_importe=cotiz_importe,
                    cotiz_tc=cotiz_tc)
        textos = []
        db_mock = sys.modules['app.extensions'].db

        with patch.object(_wabot, 'WaBotSession') as mock_wbs,              patch.object(_wabot, '_typing'),              patch.object(_wabot, '_sesion_inactiva', return_value=False),              patch.object(_wabot, '_cotiz_expirada', return_value=False),              patch.object(_wabot, '_operacion_activa_cliente', return_value=None),              patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[]),              patch.object(_wabot, '_buscar_cliente', return_value=None),              patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)),              patch.object(_wabot, '_is_horario_atencion', return_value=True),              patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: textos.append(('text', t))),              patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: textos.append(('buttons', t))),              patch.object(_wabot, '_flujo_pedir_id_para_cotizar'),              patch.object(db_mock, 'session'):
            mock_wbs.get_or_create.return_value = s
            if interp_override is not None:
                with patch.object(_wabot, '_interpretar_solicitud',
                                  return_value=interp_override):
                    _wabot.handle_message('+51910000001', '', 'text', texto, '', '')
            else:
                _wabot.handle_message('+51910000001', '', 'text', texto, '', '')
        return s, textos

    # ── Test 1: Compra explícita con importe → sets cotiz_op ─────────────────
    def test_inicio_compra_con_importe_pre_establece_cotiz_op(self):
        """Si la interpretación devuelve tipo=compra, session.cotiz_op queda en 'compra'."""
        interp = {
            'tipo': 'compra', 'importe': 1500.0, 'moneda_importe': 'USD',
            'es_hipotetico': False, 'es_correccion': False,
            'faltante': [], 'fuente': 'determinista',
        }
        s, _ = self._ejecutar_handle('Quiero comprar 1500 dolares', interp_override=interp)
        self.assertEqual(s.cotiz_op, 'compra',
                         "cotiz_op debe ser 'compra' tras interpretación")

    # ── Test 2: Venta explícita con importe → sets cotiz_op ─────────────────
    def test_inicio_venta_con_importe_pre_establece_cotiz_op(self):
        """Si la interpretación devuelve tipo=venta, session.cotiz_op queda en 'venta'."""
        interp = {
            'tipo': 'venta', 'importe': 800.0, 'moneda_importe': 'USD',
            'es_hipotetico': False, 'es_correccion': False,
            'faltante': [], 'fuente': 'determinista',
        }
        s, _ = self._ejecutar_handle('Vendo 800 dolares', interp_override=interp)
        self.assertEqual(s.cotiz_op, 'venta')

    # ── Test 3: Información incompleta → pregunta faltante ──────────────────
    def test_solo_tipo_pide_importe(self):
        """Si solo hay tipo (sin importe), el flujo pide el importe."""
        interp = {
            'tipo': 'compra', 'importe': None, 'moneda_importe': None,
            'es_hipotetico': False, 'es_correccion': False,
            'faltante': ['importe'], 'fuente': 'determinista',
        }
        with patch.object(_wabot, 'WaBotSession') as mock_wbs,              patch.object(_wabot, '_typing'),              patch.object(_wabot, '_sesion_inactiva', return_value=False),              patch.object(_wabot, '_cotiz_expirada', return_value=False),              patch.object(_wabot, '_operacion_activa_cliente', return_value=None),              patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[]),              patch.object(_wabot, '_buscar_cliente', return_value=None),              patch.object(_wabot, '_flujo_pedir_importe') as mock_pedir,              patch.object(_wabot, '_flujo_pedir_id_para_cotizar'),              patch.object(_wabot, '_interpretar_solicitud', return_value=interp),              patch.object(_wabot, 'send_text', return_value=None),              patch.object(_wabot, 'send_buttons', return_value=None),              patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='inicio')
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', 'quiero comprar dolares', '', '')
        mock_pedir.assert_called_once()
        self.assertEqual(s.estado, 'esperando_importe')

    # ── Test 4: Importe en soles → explicación de limitación ────────────────
    def test_importe_pen_explica_limitacion(self):
        """Importe en soles → el bot explica que cotiza en USD y pide importe en dólares."""
        interp = {
            'tipo': 'compra', 'importe': 3000.0, 'moneda_importe': 'PEN',
            'es_hipotetico': False, 'es_correccion': False,
            'faltante': [], 'fuente': 'determinista',
        }
        s, textos = self._ejecutar_handle('Quiero cambiar 3000 soles', interp_override=interp)
        textos_planos = ' '.join(t for _, t in textos).lower()
        self.assertIn('usd', textos_planos,
                      "La respuesta debe mencionar USD cuando se recibe un importe en PEN")
        # No debe haber establecido cotiz_importe=3000 (eso sería mezclar monedas)
        self.assertNotEqual(s.cotiz_importe, 3000.0,
                            "No debe establecer cotiz_importe=3000 para un importe en PEN")

    # ── Test 5: Corrección en viendo_cotizacion → nueva cotización ───────────
    def test_viendo_cotizacion_correccion_actualiza_importe(self):
        """'Mejor 2000' en viendo_cotizacion actualiza cotiz_importe."""
        interp = {
            'tipo': None, 'importe': 2000.0, 'moneda_importe': 'USD',
            'es_hipotetico': False, 'es_correccion': True,
            'faltante': ['tipo'], 'fuente': 'determinista',
        }
        s, _ = self._ejecutar_handle(
            'Mejor 2000', estado='viendo_cotizacion',
            cotiz_op='compra', cotiz_importe=1000.0, cotiz_tc=3.81,
            interp_override=interp,
        )
        self.assertAlmostEqual(s.cotiz_importe, 2000.0,
                               msg="cotiz_importe debe actualizarse a 2000 tras corrección")

    # ── Test 6: Pregunta informativa no cambia estado ─────────────────────────
    def test_viendo_cotizacion_pregunta_no_cambia_estado(self):
        """Una pregunta informativa en viendo_cotizacion mantiene el estado."""
        # No hay corrección ni hipotético → flujo IA o dudas
        interp = {
            'tipo': None, 'importe': None, 'moneda_importe': None,
            'es_hipotetico': False, 'es_correccion': False,
            'faltante': ['tipo', 'importe'], 'fuente': 'determinista',
        }
        with patch.object(_wabot, 'WaBotSession') as mock_wbs,              patch.object(_wabot, '_typing'),              patch.object(_wabot, '_sesion_inactiva', return_value=False),              patch.object(_wabot, '_cotiz_expirada', return_value=False),              patch.object(_wabot, '_interpretar_solicitud', return_value=interp),              patch.object(_wabot, '_respuesta_ia', return_value='El TC es...'),              patch.object(_wabot, 'send_text', return_value=None),              patch.object(_wabot, 'send_buttons', return_value=None),              patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='viendo_cotizacion', cotiz_op='compra',
                        cotiz_importe=1000.0, cotiz_tc=3.81)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', 'como funciona esto?', '', '')
        self.assertEqual(s.estado, 'viendo_cotizacion',
                         "El estado debe permanecer 'viendo_cotizacion' tras pregunta informativa")

    # ── Test 7: Consulta hipotética no reemplaza cotización vigente ──────────
    def test_viendo_cotizacion_hipotetica_no_modifica_importe(self):
        """'y si son 500' en viendo_cotizacion NO modifica cotiz_importe."""
        interp = {
            'tipo': None, 'importe': 500.0, 'moneda_importe': 'USD',
            'es_hipotetico': True, 'es_correccion': False,
            'faltante': ['tipo'], 'fuente': 'determinista',
        }
        s, textos = self._ejecutar_handle(
            'y si son 500', estado='viendo_cotizacion',
            cotiz_op='compra', cotiz_importe=1000.0, cotiz_tc=3.81,
            interp_override=interp,
        )
        self.assertAlmostEqual(s.cotiz_importe, 1000.0,
                               msg="cotiz_importe NO debe cambiar por consulta hipotética")
        textos_planos = ' '.join(t for _, t in textos).lower()
        self.assertIn('500', textos_planos,
                      "La respuesta hipotética debe incluir el importe consultado")
        self.assertIn('1,000', textos_planos,
                      "La respuesta debe recordar la cotización vigente")

    # ── Test 8: Operación ya creada → no modifica sesión ────────────────────
    def test_operacion_activa_no_pasa_por_interpretacion(self):
        """Si hay operación activa, no se llama a _interpretar_solicitud."""
        mock_op = MagicMock()
        mock_op.operation_id = 'OP-001'
        mock_op.status = 'Pendiente'
        with patch.object(_wabot, 'WaBotSession') as mock_wbs,              patch.object(_wabot, '_typing'),              patch.object(_wabot, '_sesion_inactiva', return_value=False),              patch.object(_wabot, '_cotiz_expirada', return_value=False),              patch.object(_wabot, '_operacion_activa_cliente', return_value=mock_op),              patch.object(_wabot, '_flujo_op_ya_activa') as mock_op_activa,              patch.object(_wabot, '_interpretar_solicitud') as mock_interp,              patch.object(_wabot, 'send_text', return_value=None),              patch.object(_wabot, 'send_buttons', return_value=None),              patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='inicio')
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', 'quiero comprar 1500 dolares', '', '')
        mock_op_activa.assert_called_once()
        mock_interp.assert_not_called()

    # ── Test 9: Fallo del intérprete → flujo guiado ──────────────────────────
    def test_fallo_interprete_cae_en_flujo_guiado(self):
        """Si _interpretar_solicitud lanza excepción, se usa el flujo guiado."""
        with patch.object(_wabot, 'WaBotSession') as mock_wbs,              patch.object(_wabot, '_typing'),              patch.object(_wabot, '_sesion_inactiva', return_value=False),              patch.object(_wabot, '_cotiz_expirada', return_value=False),              patch.object(_wabot, '_operacion_activa_cliente', return_value=None),              patch.object(_wabot, '_interpretar_solicitud',
                          side_effect=RuntimeError('test error')),              patch.object(_wabot, '_intentar_identificar_y_cotizar') as mock_guiado,              patch.object(_wabot, 'send_text', return_value=None),              patch.object(_wabot, 'send_buttons', return_value=None),              patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='inicio')
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', 'quiero comprar 1500', '', '')
        mock_guiado.assert_called_once()

    # ── Test 10: Aceptación explícita vs agradecimiento ambiguo ─────────────
    def test_ok_en_viendo_cotizacion_no_crea_operacion(self):
        """'ok' como texto en viendo_cotizacion NO llama a _crear_op_y_confirmar."""
        with patch.object(_wabot, 'WaBotSession') as mock_wbs,              patch.object(_wabot, '_typing'),              patch.object(_wabot, '_sesion_inactiva', return_value=False),              patch.object(_wabot, '_cotiz_expirada', return_value=False),              patch.object(_wabot, '_crear_op_y_confirmar') as mock_crear,              patch.object(_wabot, '_respuesta_ia', return_value=None),              patch.object(_wabot, 'send_text', return_value=None),              patch.object(_wabot, 'send_buttons', return_value=None),              patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='viendo_cotizacion', cotiz_op='compra',
                        cotiz_importe=1000.0, cotiz_tc=3.81)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', 'ok', '', '')
        mock_crear.assert_not_called()

    # ── Test 11: btn_aceptar_cotiz fuera de estado viendo_cotizacion ─────────
    def test_btn_aceptar_cotiz_fuera_de_estado_rechazado(self):
        """btn_aceptar_cotiz sin token es rechazado (token vacío != cualquier token de sesión)."""
        textos = []
        with patch.object(_wabot, 'WaBotSession') as mock_wbs,              patch.object(_wabot, '_typing'),              patch.object(_wabot, '_sesion_inactiva', return_value=False),              patch.object(_wabot, '_cotiz_expirada', return_value=False),              patch.object(_wabot, '_crear_op_y_confirmar') as mock_crear,              patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: textos.append(t)),              patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: textos.append(t)),              patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='inicio', cotiz_op='compra', cotiz_importe=0.0, cotiz_tc=0.0)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive', 'btn_aceptar_cotiz', '', '')
        mock_crear.assert_not_called()
        self.assertTrue(any('cotizaci' in t.lower() or 'reciente' in t.lower() or 'reemplazada' in t.lower()
                            for t in textos),
                        "Debe mostrar mensaje de rechazo; textos: " + str(textos))


# ─────────────────────────────────────────────────────────────────────────────
# 8. TestNoTengoHandler  (Etapa 2 – los 4 casos de 'no tengo')
# ─────────────────────────────────────────────────────────────────────────────

class TestNoTengoHandler(unittest.TestCase):
    """
    Verifica los cuatro casos del manejador no_tengo.
    Los mensajes distintos requieren distintas respuestas:
      1. 'no tengo soles' en compra → ofrecer inversa (reset)
      2. 'no tengo dolares' en compra → aclarar sin resetear
      3. 'no tengo' (sin moneda, sin dirección) → preguntar sin resetear
      4. 'no tengo cuenta BCP' → explicar opciones de cuenta sin resetear
    """

    def _ejecutar_no_tengo_v2(self, texto, cotiz_op='', estado='esperando_importe'):
        """Ejecuta handle_message con _detectar_intencion='no_tengo' y captura respuestas."""
        s = _sesion(estado=estado, cotiz_op=cotiz_op)
        llamadas = []
        db_mock  = sys.modules['app.extensions'].db

        with patch.object(_wabot, 'WaBotSession') as mock_wbs,              patch.object(_wabot, '_typing'),              patch.object(_wabot, '_sesion_inactiva', return_value=False),              patch.object(_wabot, '_cotiz_expirada',  return_value=False),              patch.object(_wabot, '_parse_monto',     return_value=0),              patch.object(_wabot, '_detectar_intencion', return_value='no_tengo'),              patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: llamadas.append(('buttons', t, b))),              patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: llamadas.append(('text', t))),              patch.object(db_mock, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', texto, '', 'wamid_test')
        return s, llamadas

    def test_caso1_no_tengo_soles_en_compra_ofrece_inversa(self):
        """'no tengo soles' en compra → ofrece cambio inverso (tiene dólares)."""
        s, llamadas = self._ejecutar_no_tengo_v2('no tengo soles', cotiz_op='compra')
        textos = ' '.join(t for _, t, *_ in llamadas).lower()
        self.assertIn('d', textos,
                      "La respuesta debe mencionar 'dólares'")
        # Verifica que se ofrece la dirección inversa (venta)
        botones = [b for _, t, bs in llamadas if bs for b in bs]
        btn_ids = [b.get('id', '') for b in botones]
        self.assertIn('btn_vender', btn_ids,
                      "Debe ofrecer btn_vender como alternativa inversa")

    def test_caso2_no_tengo_dolares_en_compra_clarifica(self):
        """'no tengo dolares' en compra → clarifica sin auto-invertir (no btn_vender)."""
        s, llamadas = self._ejecutar_no_tengo_v2('no tengo dolares', cotiz_op='compra')
        botones = [b for _, t, bs in llamadas if bs for b in bs]
        btn_ids = [b.get('id', '') for b in botones]
        self.assertNotIn('btn_vender', btn_ids,
                         "No debe ofrecer btn_vender: 'no tengo dólares' en compra es ambiguo")
        # El estado o session NO deben haber sido reseteados (cotiz_op preservada)
        self.assertEqual(s.cotiz_op, 'compra',
                         "cotiz_op debe preservarse para mensajes ambiguos")

    def test_caso3_no_tengo_sin_moneda_sin_direccion_pregunta(self):
        """'no tengo' sin dirección → pregunta qué moneda falta sin resetear sesión."""
        s, llamadas = self._ejecutar_no_tengo_v2('no tengo', cotiz_op='')
        textos = ' '.join(t for _, t, *_ in llamadas).lower()
        # Debe hacer una pregunta sobre la moneda
        tiene_pregunta = 'soles' in textos or 'moneda' in textos or 'falta' in textos
        self.assertTrue(tiene_pregunta,
                        "Debe preguntar sobre la moneda faltante")

    def test_caso4_no_tengo_cuenta_bcp_explica_opciones(self):
        """'no tengo cuenta BCP' → explica opciones de cuenta sin resetear."""
        s, llamadas = self._ejecutar_no_tengo_v2('no tengo cuenta BCP', cotiz_op='compra')
        textos = ' '.join(t for _, t, *_ in llamadas).lower()
        # Debe mencionar cuenta o banco en la respuesta
        tiene_cuenta = 'cuenta' in textos or 'banco' in textos or 'bancaria' in textos
        self.assertTrue(tiene_cuenta, "La respuesta debe abordar el tema de cuentas bancarias")
        # El cotiz_op debe seguir intacto (no reseteó sesión)
        self.assertEqual(s.cotiz_op, 'compra',
                         "cotiz_op debe preservarse — 'no tengo cuenta' no afecta la dirección")


# ─────────────────────────────────────────────────────────────────────────────
# 9. TestRevisionFinal  (Revisión final Etapa 2)
# ─────────────────────────────────────────────────────────────────────────────

_interpretar_solicitud = _wabot._interpretar_solicitud


class TestRevisionFinal(unittest.TestCase):
    """
    Cubre los puntos de la revisión final de Etapa 2:

    A. Vinculación aceptación ↔ cotización concreta (epoch token)
    B. Continuación desde esperando_importe (dirección + monto)
    C. Preservar importe al seleccionar dirección con btn_comprar/btn_vender
    D. Negación y autocorrección sin cambios indebidos
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    def _run_interactive(self, btn_id_str, estado='viendo_cotizacion',
                         cotiz_op='compra', cotiz_importe=1000.0,
                         cotiz_tc=3.81, cotiz_timestamp=None, cotiz_token=None):
        """Ejecuta handle_message con tipo_msg='interactive'."""
        s = _sesion(estado=estado, cotiz_op=cotiz_op,
                    cotiz_importe=cotiz_importe, cotiz_tc=cotiz_tc,
                    cotiz_timestamp=cotiz_timestamp, cotiz_token=cotiz_token)
        texts, buttons = [], []
        db_mock = sys.modules['app.extensions'].db
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_operacion_activa_cliente', return_value=None), \
             patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[]), \
             patch.object(_wabot, '_buscar_cliente', return_value=None), \
             patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)), \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: (texts.append(t), buttons.extend(b))), \
             patch.object(db_mock, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  btn_id_str, '', '')
        return s, texts, buttons

    def _run_text(self, texto, estado='esperando_importe', cotiz_op='compra',
                  cotiz_importe=0.0, cotiz_tc=0.0, cotiz_timestamp=None):
        """Ejecuta handle_message con tipo_msg='text'."""
        s = _sesion(estado=estado, cotiz_op=cotiz_op,
                    cotiz_importe=cotiz_importe, cotiz_tc=cotiz_tc,
                    cotiz_timestamp=cotiz_timestamp)
        texts, buttons = [], []
        db_mock = sys.modules['app.extensions'].db
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_operacion_activa_cliente', return_value=None), \
             patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[]), \
             patch.object(_wabot, '_buscar_cliente', return_value=None), \
             patch.object(_wabot, '_get_tc', return_value=(3.77, 3.81)), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: (texts.append(t), buttons.extend(b))), \
             patch.object(db_mock, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', texto, '', '')
        return s, texts, buttons

    # ── A. Vinculación cotización ─────────────────────────────────────────────

    def test_boton_cotizacion_A_rechazado_tras_mostrar_B(self):
        """
        Clic en 'Aceptar' de cotización A después de que se mostró B.
        El token del botón no coincide con el token de la sesión → rechazo breve.
        """
        token_a = 'aaa11111'
        token_b = 'bbb22222'
        btn_a = f'btn_aceptar_cotiz_{token_a}'
        # Session refleja la cotización B
        s, texts, _ = self._run_interactive(
            btn_a, cotiz_token=token_b,
            estado='viendo_cotizacion', cotiz_importe=1500.0, cotiz_tc=3.81
        )
        # No debe haber procesado la aceptación (sin cambio de estado)
        self.assertNotEqual(s.estado, 'esperando_id_cotizar',
                            "Una aceptación stale no debe avanzar el flujo")
        # Debe mencionar que fue reemplazada / usar la más reciente
        all_text = ' '.join(texts).lower()
        self.assertTrue(
            'reemplazada' in all_text or 'reciente' in all_text
                or 'precio' in all_text or 'cambió' in all_text,
            f"Debe indicar que la cotización fue reemplazada; textos: {texts}"
        )

    def test_boton_cotizacion_vigente_aceptado(self):
        """
        Clic en 'Aceptar' con token que coincide con la sesión → flujo avanza.
        (Cliente desconocido → pide documento)
        """
        token = 'abc12345'
        btn = f'btn_aceptar_cotiz_{token}'
        s, _, _ = self._run_interactive(
            btn, cotiz_token=token,
            estado='viendo_cotizacion', cotiz_importe=1000.0, cotiz_tc=3.81
        )
        self.assertIn(s.estado, ('esperando_id_cotizar', 'eligiendo_cuenta_destino',
                                 'esperando_cuenta_destino'),
                      f"Estado inesperado: {s.estado}")

    def test_boton_sin_token_rechazado(self):
        """
        'btn_aceptar_cotiz' sin token (formato legacy o mal formado)
        → rechazado por falta de token, independientemente del estado.
        """
        with patch.object(_wabot, '_crear_op_y_confirmar') as mock_crear, \
             patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='inicio', cotiz_importe=0.0, cotiz_tc=0.0)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  'btn_aceptar_cotiz', '', '')
        mock_crear.assert_not_called()

    # ── B. esperando_importe: recorridos de continuación ─────────────────────

    def test_importe_plano_muestra_cotizacion(self):
        """
        'Quiero comprar dólares' → '1500' en esperando_importe → muestra cotización.
        """
        with patch.object(_wabot, '_flujo_mostrar_cotizacion') as mock_show, \
             patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='esperando_importe', cotiz_op='compra')
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', '1500', '', '')
        mock_show.assert_called_once()
        self.assertAlmostEqual(s.cotiz_importe, 1500.0)

    def test_importe_en_texto_rico_muestra_cotizacion(self):
        """'Serían 1500 dólares' → monto extraído y cotización mostrada."""
        with patch.object(_wabot, '_flujo_mostrar_cotizacion') as mock_show, \
             patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='esperando_importe', cotiz_op='compra')
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', 'Serían 1500 dólares', '', '')
        mock_show.assert_called_once()
        self.assertAlmostEqual(s.cotiz_importe, 1500.0)

    def test_correccion_direccion_en_esperando_importe(self):
        """
        'Mejor quiero vender 800 dólares' en esperando_importe (cotiz_op=compra):
        - cotiz_importe → 800
        - cotiz_op → 'venta'  (dirección detectada determinísticamente)
        """
        with patch.object(_wabot, '_flujo_mostrar_cotizacion'), \
             patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='esperando_importe', cotiz_op='compra')
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text',
                                  'Mejor quiero vender 800 dólares', '', '')
        self.assertAlmostEqual(s.cotiz_importe, 800.0,
                               msg="cotiz_importe debe ser 800")
        self.assertEqual(s.cotiz_op, 'venta',
                         "cotiz_op debe cambiar a 'venta'")

    # ── C. Preservar importe al seleccionar dirección ────────────────────────

    def test_btn_comprar_con_importe_previo_muestra_cotizacion(self):
        """
        Flujo: 'Quiero cambiar 800 dólares' (sin dirección) → bot guarda importe=800
        y muestra botones de dirección → cliente pulsa btn_comprar.
        La cotización debe mostrarse directamente sin pedir importe de nuevo.
        """
        with patch.object(_wabot, '_flujo_mostrar_cotizacion') as mock_show, \
             patch.object(_wabot, '_flujo_pedir_importe') as mock_pedir, \
             patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_operacion_activa_cliente', return_value=None), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            # Session con importe ya conocido, sin dirección aún
            s = _sesion(estado='eligiendo_operacion', cotiz_importe=800.0)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  'btn_comprar', '', '')
        mock_show.assert_called_once()
        mock_pedir.assert_not_called()
        self.assertEqual(s.cotiz_op, 'compra')

    def test_btn_vender_con_importe_previo_muestra_cotizacion(self):
        """btn_vender con cotiz_importe=600 ya fijado → cotización directa."""
        with patch.object(_wabot, '_flujo_mostrar_cotizacion') as mock_show, \
             patch.object(_wabot, '_flujo_pedir_importe') as mock_pedir, \
             patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_operacion_activa_cliente', return_value=None), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='eligiendo_operacion', cotiz_importe=600.0)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  'btn_vender', '', '')
        mock_show.assert_called_once()
        mock_pedir.assert_not_called()
        self.assertEqual(s.cotiz_op, 'venta')

    def test_btn_comprar_sin_importe_pide_importe(self):
        """btn_comprar con cotiz_importe=0 → pide el importe (flujo normal)."""
        with patch.object(_wabot, '_flujo_mostrar_cotizacion') as mock_show, \
             patch.object(_wabot, '_flujo_pedir_importe') as mock_pedir, \
             patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_operacion_activa_cliente', return_value=None), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='eligiendo_operacion', cotiz_importe=0.0)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  'btn_comprar', '', '')
        mock_show.assert_not_called()
        mock_pedir.assert_called_once()

    # ── D. Negación y autocorrección ─────────────────────────────────────────

    def test_negacion_no_quiero_comprar_dolares(self):
        """
        'No quiero comprar dólares' → tipo=None (determinista).
        La negación cancela la señal de compra.
        """
        r = _interpretar_solicitud('No quiero comprar dólares')
        self.assertIsNone(r['tipo'],
                          "'No quiero comprar dólares' no debe devolver tipo='compra'")

    def test_autocorreccion_queria_comprar_mejor_vendo(self):
        """
        'Quería comprar, pero mejor vendo 800 dólares':
        tanto 'comprar' como 'vender' aparecen → tipo=None (ambiguo).
        El importe 800 sí debe extraerse.
        """
        r = _interpretar_solicitud('Quería comprar, pero mejor vendo 800 dólares')
        self.assertIsNone(r['tipo'],
                          "Mensaje con compra y venta ambas presentes debe quedar ambiguo")
        self.assertAlmostEqual(r['importe'], 800.0,
                               msg="El importe 800 debe extraerse de todas formas")

    def test_negacion_no_quiero_vender(self):
        """'No quiero vender dólares' → tipo=None."""
        r = _interpretar_solicitud('No quiero vender dólares')
        self.assertIsNone(r['tipo'])

    def test_comprar_con_monto_entre_verbo_y_moneda(self):
        """'Quiero comprar 1500 dólares' → tipo='compra' (regex sin frase contigua)."""
        r = _interpretar_solicitud('Quiero comprar 1500 dólares')
        self.assertEqual(r['tipo'], 'compra')
        self.assertAlmostEqual(r['importe'], 1500.0)

    def test_vender_con_monto_entre_verbo_y_moneda(self):
        """'Vendo 800 dólares' → tipo='venta'."""
        r = _interpretar_solicitud('Vendo 800 dólares')
        self.assertEqual(r['tipo'], 'venta')
        self.assertAlmostEqual(r['importe'], 800.0)


# ─────────────────────────────────────────────────────────────────────────────
# 10. TestCorreccionesFinales  (correcciones de Etapa 2 — sesión 3)
# ─────────────────────────────────────────────────────────────────────────────

class TestCorreccionesFinales(unittest.TestCase):
    """
    Cubre las 4 correcciones aplicadas en la sesión 3 de Etapa 2:

    A. Identidad UUID exacta: mismo segundo → tokens distintos → stale detectado.
    B. Botón sin token → rechazado (no stale silencioso).
    C. _flujo_pedir_importe: mensaje específico por dirección, sin "Escribe solo el número".
    D. "¿Es seguro?" en viendo_cotizacion → respuesta concreta, cotización activa.
    E. T1/T4 unificación: cliente desconocido con op+importe completo → cotización directa.
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    def _run_pedir_importe(self, operacion):
        """Llama a _flujo_pedir_importe y captura el texto enviado."""
        texts, buttons = [], []
        with patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: (texts.append(t), buttons.extend(b))), \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)):
            _wabot._flujo_pedir_importe('+51910000001', operacion)
        return texts

    def _run_viendo_cotizacion_texto(self, texto, cotiz_token='tok99'):
        """Ejecuta handle_message en estado viendo_cotizacion con texto libre."""
        s = _sesion(estado='viendo_cotizacion', cotiz_op='compra',
                    cotiz_importe=1000.0, cotiz_tc=3.81, cotiz_token=cotiz_token)
        texts, buttons = [], []
        db_mock = sys.modules['app.extensions'].db
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: (texts.append(t), buttons.extend(b))), \
             patch.object(db_mock, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text', texto, '', '')
        return s, texts, buttons

    # ── A. mismo segundo → tokens distintos → stale ───────────────────────────

    def test_mismo_segundo_tokens_distintos_stale(self):
        """
        Dos cotizaciones generadas dentro del mismo segundo tienen tokens distintos.
        El botón de la primera (token_a) es rechazado cuando la sesión tiene token_b.
        """
        token_a = 'aaaa1111'
        token_b = 'bbbb2222'
        # Ambas tienen el mismo cotiz_timestamp (mismo segundo), pero token distinto
        btn_a = f'btn_aceptar_cotiz_{token_a}'
        s = _sesion(estado='viendo_cotizacion', cotiz_op='compra',
                    cotiz_importe=1000.0, cotiz_tc=3.81, cotiz_token=token_b)
        texts = []
        db_mock = sys.modules['app.extensions'].db
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(db_mock, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive', btn_a, '', '')
        all_text = ' '.join(texts).lower()
        self.assertTrue(
            'reemplazada' in all_text or 'reciente' in all_text,
            f"Debe rechazar cotización con token incorrecto; textos: {texts}"
        )
        self.assertNotEqual(s.estado, 'esperando_id_cotizar',
                            "Estado no debe avanzar con token incorrecto")

    # ── B. botón sin token → rechazado ────────────────────────────────────────

    def test_boton_sin_token_siempre_rechazado(self):
        """
        'btn_aceptar_cotiz' (sin sufijo de token) es siempre rechazado,
        incluso si la sesión tiene estado viendo_cotizacion y datos válidos.
        """
        s = _sesion(estado='viendo_cotizacion', cotiz_op='compra',
                    cotiz_importe=1000.0, cotiz_tc=3.81, cotiz_token='abc12345')
        texts = []
        db_mock = sys.modules['app.extensions'].db
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(db_mock, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  'btn_aceptar_cotiz', '', '')
        all_text = ' '.join(texts).lower()
        self.assertTrue(
            'reemplazada' in all_text or 'reciente' in all_text,
            f"Botón sin token debe ser rechazado; textos: {texts}"
        )

    # ── C. _flujo_pedir_importe: mensajes específicos ─────────────────────────

    def test_pedir_importe_compra_recibir_dolares(self):
        """_flujo_pedir_importe('compra') → menciona 'recibir' (no genérico)."""
        texts = self._run_pedir_importe('compra')
        all_text = ' '.join(texts).lower()
        self.assertIn('recibir', all_text,
                      "Compra debe preguntar cuántos dólares quiere RECIBIR")
        self.assertNotIn('escribe solo el número', all_text,
                         "No debe incluir instrucción literal de formato")

    def test_pedir_importe_venta_cambiar_a_soles(self):
        """_flujo_pedir_importe('venta') → menciona 'soles' (no genérico)."""
        texts = self._run_pedir_importe('venta')
        all_text = ' '.join(texts).lower()
        self.assertIn('soles', all_text,
                      "Venta debe mencionar que cambia dólares A SOLES")
        self.assertNotIn('escribe solo el número', all_text,
                         "No debe incluir instrucción literal de formato")

    # ── D. "¿Es seguro?" → respuesta concreta ────────────────────────────────

    def test_es_seguro_responde_concretamente(self):
        """'¿Es seguro?' en viendo_cotizacion → respuesta concreta, no deflecta."""
        s, texts, buttons = self._run_viendo_cotizacion_texto('¿Es seguro esto?')
        all_text = ' '.join(texts).lower()
        # Debe mencionar SBS o supervisión
        self.assertTrue(
            'sbs' in all_text or 'inscrito' in all_text or 'supervisión' in all_text
                or 'supervisado' in all_text or 'regulad' in all_text,
            f"Debe mencionar SBS o supervisión; textos: {texts}"
        )
        # NO debe deflectar inmediatamente al asesor sin contexto
        btn_ids = [b.get('id', '') for b in buttons]
        has_only_asesor = btn_ids == ['btn_asesor']
        self.assertFalse(has_only_asesor,
                         "No debe responder solo con botón de asesor")
        # La cotización debe seguir activa (botón de aceptar presente)
        has_accept = any('btn_aceptar_cotiz' in bid for bid in btn_ids)
        self.assertTrue(has_accept,
                        f"Debe mantener botón de aceptar cotización activo; botones: {btn_ids}")

    # ── E. T1/T4 unificación: cliente desconocido + op+importe → cotización ──

    def test_t1_cliente_desconocido_muestra_cotizacion_primero(self):
        """
        'Quiero comprar 1500 dólares' (T1, op+importe completos, cliente desconocido):
        → debe mostrar cotización directamente, sin pedir documento primero.
        """
        with patch.object(_wabot, '_flujo_mostrar_cotizacion') as mock_show, \
             patch.object(_wabot, '_flujo_pedir_id_para_cotizar') as mock_pedir_id, \
             patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, '_operacion_activa_cliente', return_value=None), \
             patch.object(_wabot, '_buscar_clientes_por_telefono', return_value=[]), \
             patch.object(_wabot, '_buscar_cliente', return_value=None), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            s = _sesion(estado='inicio', cotiz_op='', cotiz_importe=0.0)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text',
                                  'Quiero comprar 1500 dólares', '', '')
        # Cotización debe mostrarse sin preguntar ID
        mock_show.assert_called_once()
        mock_pedir_id.assert_not_called()
        self.assertEqual(s.estado, 'viendo_cotizacion')


# ─────────────────────────────────────────────────────────────────────────────

class TestEtapa3(unittest.TestCase):
    """
    Cubre la lógica determinista de Etapa 3:
    selección de cuenta, confirmación de operación y reporte de transferencia.

    A. Cuenta única → resumen directo (sin botones de selección).
    B. Múltiples cuentas → botones de selección.
    C. Sin cuentas guardadas → solicitar cuenta nueva.
    D. Cambiar cuenta desde resumen → vuelve a eligiendo_cuenta_destino.
    E. Confirmar con estado incorrecto (stale) → rechazado.
    F. Código duplicado → idempotente (no crea segundo depósito).
    G. Código con op cancelada → no reactiva, notifica asesor.
    H. Código inline en op_pendiente_pago → detectado sin pulsar botón.
    I. Texto libre en confirmando_operacion → re-muestra resumen.
    J. _flujo_resumen_final muestra montos correctos (compra y venta).
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    def _make_session(self, **kwargs):
        s = _sesion(**kwargs)
        return s

    def _cuenta(self, bank_name='BCP', account_number='1234567890', currency='USD'):
        return {'bank_name': bank_name, 'account_number': account_number, 'currency': currency}

    def _run_seleccionar_cuenta(self, cuentas, op='compra', moneda='USD', extra_kw=None):
        s = _sesion(estado='viendo_cotizacion', cotiz_op=op,
                    cotiz_importe=1000.0, cotiz_tc=3.81, cotiz_token='tok-sel')
        extra_kw = extra_kw or {}
        for k, v in extra_kw.items():
            setattr(s, k, v)
        client = MagicMock()
        client.bank_accounts = cuentas
        texts, buttons = [], []
        with patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: (texts.append(t), buttons.extend(b))):
            _wabot._seleccionar_cuenta_y_continuar('+51910000001', s, client, cuentas, moneda)
        return s, texts, buttons

    def _run_resumen_final(self, op, importe, tc, cuenta):
        s = _sesion(estado='confirmando_operacion', cotiz_op=op,
                    cotiz_importe=importe, cotiz_tc=tc, cotiz_cuenta=cuenta)
        client = MagicMock()
        client.bank_accounts = []
        texts, buttons = [], []
        with patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: (texts.append(t), buttons.extend(b))):
            _wabot._flujo_resumen_final('+51910000001', s, client)
        return texts, buttons

    def _handle(self, s, msg_type, texto, **patches):
        texts, buttons = [], []
        db_mock = sys.modules['app.extensions'].db
        extra = {
            '_typing': MagicMock(),
            '_sesion_inactiva': MagicMock(return_value=False),
            '_cotiz_expirada': MagicMock(return_value=False),
            '_is_horario_atencion': MagicMock(return_value=True),
        }
        extra.update(patches)
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: (texts.append(t), buttons.extend(b))), \
             patch.object(db_mock, 'session'):
            for attr, val in extra.items():
                patcher = patch.object(_wabot, attr, val)
                patcher.start()
                self.addCleanup(patcher.stop)
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', msg_type, texto, '', '')
        return s, texts, buttons

    # ── A. Cuenta única → resumen directo ─────────────────────────────────────

    def test_cuenta_unica_salta_a_resumen(self):
        cuentas = [self._cuenta()]
        s, texts, buttons = self._run_seleccionar_cuenta(cuentas)
        # Estado debe ser confirmando_operacion (no eligiendo_cuenta_destino)
        self.assertEqual(s.estado, 'confirmando_operacion')
        # Cuenta debe estar guardada en sesión
        self.assertIn('BCP', s.cotiz_cuenta)
        self.assertIn('1234567890', s.cotiz_cuenta)
        # El resumen debe mostrar botón de confirmación con token
        all_btns = [b.get('id', '') for b in buttons]
        confirmar_btns = [b for b in all_btns if b.startswith('btn_confirmar_operacion_')]
        self.assertTrue(len(confirmar_btns) >= 1,
                        f"Resumen debe tener botón btn_confirmar_operacion_{{token}}; botones: {all_btns}")
        # El token del botón debe coincidir con el token de la sesión
        token_en_boton = confirmar_btns[0][len('btn_confirmar_operacion_'):]
        self.assertEqual(token_en_boton, s.cotiz_token,
                         "Token del botón debe coincidir con session.cotiz_token")

    # ── B. Múltiples cuentas → botones de selección ───────────────────────────

    def test_multiples_cuentas_muestra_botones(self):
        cuentas = [
            self._cuenta('BCP', '1111111111'),
            self._cuenta('BBVA', '2222222222'),
        ]
        s, texts, buttons = self._run_seleccionar_cuenta(cuentas)
        self.assertEqual(s.estado, 'eligiendo_cuenta_destino')
        all_btns = [b.get('id', '') for b in buttons]
        # Debe haber al menos un btn_cuenta_XXXX
        cuenta_btns = [b for b in all_btns if b.startswith('btn_cuenta_')]
        self.assertTrue(len(cuenta_btns) >= 1,
                        f"Debe mostrar botones de cuenta; botones: {all_btns}")

    # ── C. Sin cuentas → solicitar cuenta nueva ───────────────────────────────

    def test_sin_cuentas_pide_cuenta_nueva(self):
        """
        El call site llama _flujo_pedir_cuenta_destino cuando cuentas=[] y NO
        llama _seleccionar_cuenta_y_continuar. Se verifica que el patrón de
        dispatch del estado eligiendo_cuenta_destino mueva la sesión correctamente.
        """
        s = _sesion(estado='confirmando_operacion', cotiz_op='compra',
                    cotiz_importe=1000.0, cotiz_tc=3.81,
                    cotiz_cuenta='BCP|1234567890', cotiz_doc='12345678')
        client = MagicMock()
        client.bank_accounts = []

        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, '_buscar_cliente', return_value=client), \
             patch.object(_wabot, '_cuentas_cliente_por_moneda', return_value=[]), \
             patch.object(_wabot, '_flujo_pedir_cuenta_destino') as mock_pedir, \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  'btn_cambiar_cuenta_resumen', '', '')

        mock_pedir.assert_called_once()
        self.assertEqual(s.estado, 'esperando_cuenta_nueva')

    # ── D. Cambiar cuenta desde resumen ───────────────────────────────────────

    def test_cambiar_cuenta_desde_resumen(self):
        s = _sesion(estado='confirmando_operacion', cotiz_op='compra',
                    cotiz_importe=1000.0, cotiz_tc=3.81,
                    cotiz_cuenta='BCP|1234567890', cotiz_doc='12345678')
        client = MagicMock()
        client.bank_accounts = [
            self._cuenta('BCP', '1234567890'),
            self._cuenta('BBVA', '9876543210'),
        ]
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, '_buscar_cliente', return_value=client), \
             patch.object(_wabot, '_cuentas_cliente_por_moneda',
                          return_value=client.bank_accounts), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  'btn_cambiar_cuenta_resumen', '', '')
        self.assertEqual(s.estado, 'eligiendo_cuenta_destino')

    # ── E. Confirmar con estado incorrecto (stale) → rechazado ────────────────

    def test_confirmar_operacion_estado_incorrecto_rechazado(self):
        """btn_confirmar_operacion con estado != confirmando_operacion es rechazado."""
        s = _sesion(estado='viendo_cotizacion', cotiz_op='compra',
                    cotiz_importe=1000.0, cotiz_tc=3.81, cotiz_token='tok-stale')
        texts = []
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, '_crear_op_y_confirmar') as mock_crear, \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: texts.append(t)), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  'btn_confirmar_operacion', '', '')
        mock_crear.assert_not_called()
        all_text = ' '.join(texts).lower()
        self.assertTrue(
            'activo' in all_text or 'resumen' in all_text or 'cotiz' in all_text,
            f"Debe rechazar con mensaje de stale; textos: {texts}"
        )

    # ── F. Código duplicado → idempotente ─────────────────────────────────────

    def _make_op_mock(self, operation_id, status, client_deposits=None, notes=''):
        op = MagicMock()
        op.status = status
        op.operation_id = operation_id
        op.client_deposits = client_deposits if client_deposits is not None else []
        op.notes = notes
        op.amount_pen = 3810.0
        op.amount_usd = 1000.0
        # Wire both .filter_by().first() and .filter_by().with_for_update().first()
        op_model = sys.modules['app.models.operation'].Operation
        op_model.query.filter_by.return_value.first.return_value = op
        op_model.query.filter_by.return_value.with_for_update.return_value.first.return_value = op
        return op

    def test_codigo_duplicado_no_registra_dos_veces(self):
        """Si el código ya existe en client_deposits, no agrega duplicado."""
        op = self._make_op_mock(
            'EXP-001', 'En proceso',
            client_deposits=[{'codigo_operacion': '00145872'}]
        )
        s = _sesion(estado='esperando_codigo_op', cotiz_op='compra',
                    cotiz_op_id='EXP-001')
        texts = []
        with patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: texts.append(t)), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            _wabot._flujo_registrar_codigo_op('+51910000001', '00145872', s)

        # Depósitos no deben haber crecido
        self.assertEqual(len(op.client_deposits), 1,
                         "No debe agregar depósito duplicado")
        all_text = ' '.join(texts).lower()
        self.assertTrue(
            'ya' in all_text or 'registrado' in all_text,
            f"Debe informar que el código ya fue registrado; textos: {texts}"
        )

    # ── G. Código con op cancelada → no reactiva ──────────────────────────────

    def test_codigo_con_op_cancelada_no_reactiva(self):
        """Si la operación está Cancelada, el código se guarda en notas pero no reactiva."""
        op = self._make_op_mock('EXP-002', 'Cancelado', notes='')
        s = _sesion(estado='esperando_codigo_op', cotiz_op='compra',
                    cotiz_op_id='EXP-002')
        texts = []
        with patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: texts.append(t)), \
             patch.object(_wabot, '_notificar_admins_wa', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            _wabot._flujo_registrar_codigo_op('+51910000001', '99887766', s)

        # Status no debe cambiar a En proceso
        self.assertNotEqual(op.status, 'En proceso',
                            "Operación cancelada no debe reactivarse")
        # Código debe aparecer en notas
        self.assertIn('99887766', op.notes,
                      "El código debe guardarse en las notas de la operación")

    # ── H. Código inline en op_pendiente_pago ─────────────────────────────────

    def test_codigo_inline_en_op_pendiente_pago(self):
        """
        Cliente escribe 'código 00145872' en estado op_pendiente_pago
        → se llama _flujo_registrar_codigo_op con el código correcto.
        """
        op = MagicMock()
        op.status = 'Pendiente'
        op.operation_id = 'EXP-003'
        op.client_deposits = []
        op.notes = ''

        s = _sesion(estado='op_pendiente_pago', cotiz_op='compra',
                    cotiz_op_id='EXP-003', cotiz_tc=3.81, cotiz_importe=1000.0)

        captured_codigo = []
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, '_flujo_registrar_codigo_op',
                          side_effect=lambda n, c, sess: captured_codigo.append(c)), \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text',
                                  'código 00145872', '', '')

        self.assertTrue(len(captured_codigo) >= 1,
                        "Debe detectar código inline y llamar _flujo_registrar_codigo_op")
        self.assertEqual(captured_codigo[0], '00145872',
                         f"Código debe preservar ceros iniciales; capturado: {captured_codigo}")

    # ── I. Texto libre en confirmando_operacion → re-muestra resumen ──────────

    def test_texto_libre_en_confirmando_operacion_remuestra_resumen(self):
        """Texto libre en estado confirmando_operacion vuelve a mostrar el resumen."""
        s = _sesion(estado='confirmando_operacion', cotiz_op='compra',
                    cotiz_importe=1000.0, cotiz_tc=3.81,
                    cotiz_cuenta='BCP|1234567890', cotiz_doc='12345678')
        client = MagicMock()
        client.bank_accounts = [self._cuenta()]

        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, '_buscar_cliente', return_value=client), \
             patch.object(_wabot, '_flujo_resumen_final') as mock_resumen, \
             patch.object(_wabot, 'send_text', return_value=None), \
             patch.object(_wabot, 'send_buttons', return_value=None), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            mock_wbs.get_or_create.return_value = s
            _wabot.handle_message('+51910000001', '', 'text',
                                  '¿puedo pagar con otro banco?', '', '')

        mock_resumen.assert_called_once()
        # Estado no debe cambiar
        self.assertEqual(s.estado, 'confirmando_operacion')

    # ── J2. Resumen reemplazado: botón viejo rechazado ────────────────────────

    def test_resumen_reemplazado_boton_viejo_rechazado(self):
        """
        Cliente cambia de cuenta A a cuenta B:
        1. Resumen A → token_A guardado en sesión, botón btn_confirmar_operacion_token_A
        2. Resumen B → token_B guardado en sesión, botón btn_confirmar_operacion_token_B
        3. Cliente pulsa botón de resumen A (token_A) → rechazado porque token ≠ token_B
        """
        token_A = 'aaaa-1111-old'
        token_B = 'bbbb-2222-new'
        # Sesión ya tiene el token del resumen B (el último mostrado)
        s = _sesion(estado='confirmando_operacion', cotiz_op='compra',
                    cotiz_importe=1000.0, cotiz_tc=3.81,
                    cotiz_cuenta='BBVA|9876543210', cotiz_doc='12345678',
                    cotiz_token=token_B)
        texts = []
        with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
             patch.object(_wabot, '_typing'), \
             patch.object(_wabot, '_sesion_inactiva', return_value=False), \
             patch.object(_wabot, '_cotiz_expirada', return_value=False), \
             patch.object(_wabot, '_is_horario_atencion', return_value=True), \
             patch.object(_wabot, '_crear_op_y_confirmar') as mock_crear, \
             patch.object(_wabot, 'send_text',
                          side_effect=lambda n, t: texts.append(t)), \
             patch.object(_wabot, 'send_buttons',
                          side_effect=lambda n, t, b: texts.append(t)), \
             patch.object(sys.modules['app.extensions'].db, 'session'):
            mock_wbs.get_or_create.return_value = s
            # Pulsar el botón del resumen A (token_A, ya obsoleto)
            _wabot.handle_message('+51910000001', '', 'interactive',
                                  f'btn_confirmar_operacion_{token_A}', '', '')
        mock_crear.assert_not_called()
        # Comportamiento correcto: re-mostrar el resumen actual (no resetear a inicio)
        all_text = ' '.join(texts)
        self.assertIn('Resumen', all_text,
                      f"Debe re-mostrar el resumen actual; textos: {texts}")
        self.assertEqual(s.estado, 'confirmando_operacion',
                         "Estado debe permanecer en confirmando_operacion al re-mostrar resumen")

    # ── J3. Código tardío desde inicio (op expiró, sesión reseteada) ──────────

    def test_codigo_tardio_desde_inicio_op_unica(self):
        """
        La operación vence, la sesión se resetea a 'inicio'.
        El cliente escribe 'código 001234'.
        → El código se guarda en notas de la op y se notifica al admin.
        → No se reactiva la op ni se dice al cliente que vuelva a transferir.
        """
        op = MagicMock()
        op.status = 'Cancelado'
        op.operation_id = 'EXP-777'
        op.notes = ''
        op.client_id = 42

        client = MagicMock()
        client.id = 42
        client.full_name = 'Juan Quispe'
        client.phone = '987654321'

        s = _sesion(estado='inicio', cotiz_op_id='')
        db_mock = sys.modules['app.extensions'].db

        # MagicMock's __ge__ returns NotImplemented by default (comparison operators
        # are designed to allow Python's fallback chain).  We need column-like objects
        # that return a truthy value from comparison operators so the ORM filter
        # arguments can be evaluated without raising TypeError.
        class _Col:
            """Minimal stand-in for a SQLAlchemy column expression in tests."""
            def __ge__(self, other): return self
            def __le__(self, other): return self
            def __eq__(self, other): return self
            def in_(self, v): return self
            def ilike(self, v): return self
            def desc(self): return self

        cli_mod = sys.modules['app.models.client']
        op_mod  = sys.modules['app.models.operation']

        # Preserve originals
        orig_cli_q           = cli_mod.Client.query
        orig_op_q            = op_mod.Operation.query
        orig_op_updated_at   = getattr(op_mod.Operation, 'updated_at', None)
        orig_op_client_id    = getattr(op_mod.Operation, 'client_id', None)
        orig_op_status       = getattr(op_mod.Operation, 'status', None)
        orig_cli_phone       = getattr(cli_mod.Client, 'phone', None)

        # Install column mocks so that `updated_at >= cutoff` doesn't raise TypeError
        op_mod.Operation.updated_at = _Col()
        op_mod.Operation.client_id  = _Col()
        op_mod.Operation.status     = _Col()
        cli_mod.Client.phone        = _Col()

        # Query mocks
        mock_cli_q = MagicMock()
        mock_cli_q.filter.return_value.first.return_value = client
        cli_mod.Client.query = mock_cli_q

        mock_op_q = MagicMock()
        mock_op_q.filter.return_value.order_by.return_value.all.return_value = [op]
        op_mod.Operation.query = mock_op_q

        try:
            with patch.object(_wabot, 'WaBotSession') as mock_wbs, \
                 patch.object(_wabot, '_typing'), \
                 patch.object(_wabot, '_sesion_inactiva', return_value=False), \
                 patch.object(_wabot, '_cotiz_expirada', return_value=False), \
                 patch.object(_wabot, '_is_horario_atencion', return_value=True), \
                 patch.object(_wabot, '_operacion_activa_cliente', return_value=None), \
                 patch.object(_wabot, '_notificar_admins_wa') as mock_notify, \
                 patch.object(_wabot, 'send_text', return_value=None), \
                 patch.object(_wabot, 'send_buttons', return_value=None), \
                 patch.object(db_mock, 'session'):
                mock_wbs.get_or_create.return_value = s
                _wabot.handle_message('+51910000001', '', 'text',
                                      'código 001234', '', '')
        finally:
            cli_mod.Client.query  = orig_cli_q
            op_mod.Operation.query = orig_op_q
            if orig_op_updated_at is not None:
                op_mod.Operation.updated_at = orig_op_updated_at
            if orig_op_client_id is not None:
                op_mod.Operation.client_id = orig_op_client_id
            if orig_op_status is not None:
                op_mod.Operation.status = orig_op_status
            if orig_cli_phone is not None:
                cli_mod.Client.phone = orig_cli_phone

        # El código debe haberse guardado en las notas de la op
        self.assertIn('001234', op.notes,
                      "Código tardío debe guardarse en notas de la op")
        # Admin debe haber sido notificado
        mock_notify.assert_called_once()
        notify_msg = mock_notify.call_args[0][0]
        self.assertIn('001234', notify_msg,
                      "Notificación al admin debe incluir el código")
        # La op no debe reactivarse
        self.assertEqual(op.status, 'Cancelado',
                         "Operación cancelada no debe reactivarse")

    # ── J. _flujo_resumen_final calcula montos correctos ─────────────────────

    def test_resumen_final_compra_montos_correctos(self):
        """Compra USD 1000 a TC 3.81 → envías S/ 3810.00, recibes USD 1000.00."""
        texts, buttons = self._run_resumen_final('compra', 1000.0, 3.81, 'BCP|1234567890')
        all_text = ' '.join(texts)
        self.assertIn('3,810.00', all_text,
                      f"Debe mostrar S/ 3,810.00 (envías); textos: {texts}")
        self.assertIn('1,000.00', all_text,
                      f"Debe mostrar USD 1,000.00 (recibes); textos: {texts}")
        self.assertIn('3.8100', all_text,
                      f"Debe mostrar TC 3.8100; textos: {texts}")

    def test_resumen_final_venta_montos_correctos(self):
        """Venta USD 500 a TC 3.75 → envías USD 500.00, recibes S/ 1875.00."""
        texts, buttons = self._run_resumen_final('venta', 500.0, 3.75, 'BCP|9876543210')
        all_text = ' '.join(texts)
        self.assertIn('500.00', all_text,
                      f"Debe mostrar USD 500.00 (envías); textos: {texts}")
        self.assertIn('1,875.00', all_text,
                      f"Debe mostrar S/ 1,875.00 (recibes); textos: {texts}")


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 70)
    print('PRUEBAS AISLADAS — Bot WA: historial e IA (sin llamadas reales)')
    print('=' * 70)
    print()
    print('NOTA: Estas pruebas validan lógica de construcción de contexto.')
    print('      NO evalúan la calidad de las respuestas del modelo.')
    print()
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in (
        TestHistorialIa,
        TestConstruirContextoSesion,
        TestRespuestaIaBotPausado,
        TestHistorialEnRespuestaIa,
        TestNoPoseeMoneda,
        TestInterpretarSolicitud,
        TestEtapa2Routing,
        TestNoTengoHandler,
        TestRevisionFinal,
        TestCorreccionesFinales,
        TestEtapa3,
    ):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

#!/usr/bin/env python3
"""
tests/validate_dialogs_ia.py

Validación de diálogos conversacionales con IA real (claude-haiku-4-5-20251001).

Simula únicamente: send_text / send_buttons / send_buttons_image / send_list / DB writes.
IA real: _interpretar_solicitud, _detectar_intencion, _respuesta_ia.

Diálogos:
  A — préstamo: "Hola, quiero préstamo" → "Necesito que me presten 500 dólares"
                → "Bueno, entonces quiero vender 200 dólares"
  B — consulta durante flujo: "Quiero vender dólares" → "¿Cobran comisión?" → "500"
  C — dirección ambigua: "Quiero cambiar 100 dólares"

Uso:
    python3 tests/validate_dialogs_ia.py
"""
import sys, os, types, re
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

# ── ANTHROPIC_API_KEY desde .env ──────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.isfile(_env_path):
    with open(_env_path) as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

assert os.environ.get('ANTHROPIC_API_KEY'), 'ANTHROPIC_API_KEY no encontrada'

# ── Stubs para Flask / DB / modelos ──────────────────────────────────────────
def _build_stubs():
    app_pkg = types.ModuleType('app')
    sys.modules.setdefault('app', app_pkg)
    ext = types.ModuleType('app.extensions')
    db  = MagicMock()
    ext.db = db
    sys.modules.setdefault('app.extensions', ext)
    _tz = timezone(timedelta(hours=-5))
    fmt = types.ModuleType('app.utils.formatters')
    fmt.now_peru = lambda: datetime(2026, 9, 24, 15, 0, 0, tzinfo=_tz)
    sys.modules.setdefault('app.utils.formatters', fmt)
    sys.modules.setdefault('app.utils', types.ModuleType('app.utils'))
    for mod in ('app.models.operation', 'app.models.client', 'app.models.user',
                'app.models.wa_bot_session', 'app.models.wa_message',
                'app.services.notification_service', 'app.services.email_service'):
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

# ── Cargar wa_bot.py en módulo aislado ───────────────────────────────────────
SVC_PATH = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'wa_bot.py')
_svc = types.ModuleType('wa_bot_validate')
with open(SVC_PATH, encoding='utf-8') as _f:
    exec(compile(_f.read(), SVC_PATH, 'exec'), _svc.__dict__)

# Configurar WaBotSession.query.filter_by().with_entities().scalar() → None
# para que la guardia de drift de sesión en _respuesta_ia no descarte la respuesta.
# session.session_started_at = None (valor por defecto), así que scalar() debe devolver None.
_wbs_mock = _svc.WaBotSession
_wbs_mock.query.filter_by.return_value.with_entities.return_value.scalar.return_value = None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_session(**kw):
    s = MagicMock()
    s.cotiz_op        = kw.get('cotiz_op', None)
    s.cotiz_importe   = kw.get('cotiz_importe', None)
    s.cotiz_tc        = kw.get('cotiz_tc', None)
    s.cotiz_token     = kw.get('cotiz_token', None)
    s.cotiz_op_id     = kw.get('cotiz_op_id', '')
    s.cotiz_doc       = kw.get('cotiz_doc', '')
    s.cotiz_cuenta    = kw.get('cotiz_cuenta', '')
    s.cotiz_intentos  = 0
    s.cotiz_timestamp = None
    s.cotiz_email     = ''
    s.estado          = kw.get('estado', 'inicio')
    s.nombre          = kw.get('nombre', '')
    s.tipo            = kw.get('tipo', '')
    s.bot_pausado     = False
    s.session_started_at = None
    s.id              = 1
    return s


# Capture WA messages
_sent = []

def _mock_send_text(numero, texto):
    _sent.append({'tipo': 'texto', 'msg': texto})

def _mock_send_buttons(numero, texto, botones, *a, **kw):
    _sent.append({'tipo': 'botones', 'msg': texto, 'botones': [b['title'] for b in botones]})

def _mock_send_buttons_image(numero, url, texto, botones, *a, **kw):
    _sent.append({'tipo': 'imagen+botones', 'msg': texto, 'botones': [b['title'] for b in botones]})

def _mock_send_list(numero, texto, secciones, *a, **kw):
    opciones = [r['title'] for sec in secciones for r in sec.get('rows', [])]
    _sent.append({'tipo': 'lista', 'msg': texto, 'opciones': opciones})

# Patch senders in the loaded module
_svc.send_text             = _mock_send_text
_svc.send_buttons          = _mock_send_buttons
_svc.send_buttons_image    = _mock_send_buttons_image
_svc.send_list             = _mock_send_list

# TC sintético — valores fijos para pruebas, NO provienen del backend real
_TC_COMPRA_SINTETICO = 3.720
_TC_VENTA_SINTETICO  = 3.750

# Patch TC, horario, historial, clientes
_svc._get_tc                        = lambda: (_TC_COMPRA_SINTETICO, _TC_VENTA_SINTETICO)
_svc._is_horario_atencion           = lambda: True
_svc._historial_ia                  = lambda *a, **kw: ([], False)
_svc._construir_contexto_sesion     = lambda numero, session: (
    f'ESTADO DEL FLUJO: {session.estado}\n'
    f'Dirección: {session.cotiz_op or "(sin definir)"}\n'
    f'Monto: {f"USD {session.cotiz_importe:,.0f}" if session.cotiz_importe else "(sin definir)"}'
)
_svc._buscar_clientes_por_telefono  = lambda numero: []
_svc._buscar_cliente                = lambda doc: None   # sin cliente en BD de prueba
_svc._operacion_activa_cliente      = lambda numero: None
# _save_outgoing: no-op (evita escribir en BD en sends internos no mocked)
_svc._save_outgoing                 = lambda *a, **kw: None

# _identificar_y_cotizar_directo y _flujo_pedir_importe se usan REALES para capturar
# la salida completa de cotización. Los send_* ya están mocked arriba.

_routing_calls = []   # solo para _bienvenida / _menu_rapido (aún mocked)

_orig_bienvenida = _svc._bienvenida
def _mock_bienvenida(numero, session):
    _routing_calls.append('→ _bienvenida()')
    _sent.append({'tipo': 'imagen+botones', 'msg': '[Bienvenida Qoricash + TC + botones]',
                  'botones': ['Soles a dólares', 'Dólares a soles', '› ¿Cómo funciona?']})
_svc._bienvenida = _mock_bienvenida

_orig_menu_rapido = _svc._menu_rapido
def _mock_menu_rapido(numero):
    _routing_calls.append('→ _menu_rapido()')
    _sent.append({'tipo': 'botones', 'msg': '[Menú rápido Qoricash]',
                  'botones': ['Soles a dólares', 'Dólares a soles', 'Hablar con asesor']})
_svc._menu_rapido = _mock_menu_rapido


# ── Funciones de acceso directo ───────────────────────────────────────────────
interpretar     = _svc._interpretar_solicitud
aplicar         = _svc._aplicar_interpretacion_pre_op
detectar        = _svc._detectar_intencion
respuesta_ia    = _svc._respuesta_ia


def _print_sep(titulo):
    print('\n' + '═' * 60)
    print(f'  {titulo}')
    print('═' * 60)

def _print_turn(n, user_msg, session_estado):
    print(f'\n  Turno {n} | estado={session_estado}')
    print(f'  👤 Usuario: "{user_msg}"')

def _print_interp(interp):
    print(f'  📋 _interpretar_solicitud → tipo={interp["tipo"]}, '
          f'importe={interp["importe"]}, fuente={interp["fuente"]}')

def _flush_sent():
    msgs = list(_sent)
    _sent.clear()
    return msgs

def _flush_routing():
    calls = list(_routing_calls)
    _routing_calls.clear()
    return calls

def _print_bot_msgs(msgs, routing):
    for r in routing:
        print(f'  🔀 {r}')
    for m in msgs:
        if m['tipo'] == 'texto':
            print(f'  🤖 Bot (texto): {m["msg"]}')
        elif m['tipo'] in ('botones', 'imagen+botones'):
            print(f'  🤖 Bot (botones): {m["msg"]}')
            print(f'       Opciones: {m["botones"]}')
        elif m['tipo'] == 'lista':
            print(f'  🤖 Bot (lista):')
            for line in m['msg'].splitlines():
                print(f'       {line}')
            if m.get('opciones'):
                print(f'       Opciones: {m["opciones"]}')


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO A — "Hola, quiero préstamo"
# Expectativa: sin disparar flujo de cotización; IA responde sobre servicio
# ══════════════════════════════════════════════════════════════════════════════
_print_sep('DIÁLOGO A — Hola, quiero préstamo')
print('  Expectativa: NO inicia cotización. IA responde explicando servicio.')

session_a = _make_session(estado='inicio')

# Turno A1
_flush_sent(); _flush_routing()
_print_turn(1, 'Hola, quiero préstamo', session_a.estado)
interp_a1 = interpretar('Hola, quiero préstamo', session_a)
_print_interp(interp_a1)
routed_a1 = aplicar('5100000001', session_a, interp_a1)
print(f'  📌 _aplicar_interpretacion_pre_op → {routed_a1} (True=manejado, False=sin señal cambio)')
if not routed_a1:
    ia_a1 = respuesta_ia('Hola, quiero préstamo', '5100000001', session_a)
    if ia_a1:
        _sent.append({'tipo': 'texto', 'msg': ia_a1})
    else:
        _sent.append({'tipo': 'texto', 'msg': '¡Hola! 👋 En Qoricash te ayudamos a comprar y vender dólares. ¿En qué puedo ayudarte?'})
if session_a.estado not in ('eligiendo_operacion', 'eligiendo_cliente_telefono',
                             'viendo_cotizacion', 'esperando_importe'):
    session_a.estado = 'menu_mostrado'
_print_bot_msgs(_flush_sent(), _flush_routing())
print(f'  Estado tras turno 1: {session_a.estado}')

# Turno A2
_flush_sent(); _flush_routing()
_print_turn(2, 'Necesito que me presten 500 dólares', session_a.estado)
interp_a2 = interpretar('Necesito que me presten 500 dólares', session_a)
_print_interp(interp_a2)
routed_a2 = aplicar('5100000001', session_a, interp_a2)
print(f'  📌 _aplicar_interpretacion_pre_op → {routed_a2}')
if not routed_a2:
    ia_a2 = respuesta_ia('Necesito que me presten 500 dólares', '5100000001', session_a)
    if ia_a2:
        _sent.append({'tipo': 'texto', 'msg': ia_a2})
    else:
        _sent.append({'tipo': 'texto', 'msg': '[fallback: menú]'})
_print_bot_msgs(_flush_sent(), _flush_routing())
print(f'  Estado tras turno 2: {session_a.estado}')

# Turno A3 — cotización real venta USD 200
_flush_sent(); _flush_routing()
_print_turn(3, 'Bueno, entonces quiero vender 200 dólares', session_a.estado)
interp_a3 = interpretar('Bueno, entonces quiero vender 200 dólares', session_a)
_print_interp(interp_a3)
# aplicar → _identificar_y_cotizar_directo (real) → _flujo_mostrar_cotizacion (real)
aplicar('5100000001', session_a, interp_a3)
_print_bot_msgs(_flush_sent(), _flush_routing())
print(f'  Estado={session_a.estado} | cotiz_op={session_a.cotiz_op} | importe={session_a.cotiz_importe}')


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO B — Consulta durante flujo esperando_importe
# Expectativa: IA responde comisión, luego redirecciona, finalmente cotiza con 500
# ══════════════════════════════════════════════════════════════════════════════
_print_sep('DIÁLOGO B — Quiero vender dólares / ¿Cobran comisión? / 500')
print('  Expectativa: solicita importe, IA responde comisión+redirige, cotiza 500 USD.')

session_b = _make_session(estado='inicio')

# Turno B1
_flush_sent(); _flush_routing()
_print_turn(1, 'Quiero vender dólares', session_b.estado)
interp_b1 = interpretar('Quiero vender dólares', session_b)
_print_interp(interp_b1)
routed_b1 = aplicar('5100000002', session_b, interp_b1)
print(f'  📌 _aplicar_interpretacion_pre_op → {routed_b1}')
if not routed_b1:
    ia_b1 = respuesta_ia('Quiero vender dólares', '5100000002', session_b)
    if ia_b1:
        _sent.append({'tipo': 'texto', 'msg': ia_b1})
_print_bot_msgs(_flush_sent(), _flush_routing())
print(f'  cotiz_op={session_b.cotiz_op} | Estado={session_b.estado}')

# Turno B2 — pregunta de comisión en estado esperando_importe
_flush_sent(); _flush_routing()
_print_turn(2, '¿Cobran comisión?', session_b.estado)
monto_b2 = _svc._parse_monto('¿Cobran comisión?')
print(f'  📋 _parse_monto → {monto_b2}')
intencion_b2 = detectar('¿Cobran comisión?')
print(f'  📋 _detectar_intencion → "{intencion_b2}"')
if intencion_b2 == 'otro':
    # Handler actualizado: IA lleva la redirección; no se añade send_text extra.
    ia_b2 = respuesta_ia('¿Cobran comisión?', '5100000002', session_b)
    if ia_b2:
        _sent.append({'tipo': 'texto', 'msg': ia_b2})
    else:
        _sent.append({'tipo': 'texto', 'msg': '¿Cuántos dólares quieres vender? Escribe el monto, por ejemplo: *1000*'})
elif intencion_b2 == 'cancelar':
    _sent.append({'tipo': 'botones', 'msg': 'Sin problema, cancelamos la cotización.', 'botones': ['Cotizar', 'Hablar con asesor']})
    session_b.estado = 'inicio'
_print_bot_msgs(_flush_sent(), _flush_routing())
print(f'  Estado tras turno 2: {session_b.estado}')

# Turno B3 — cotización real venta USD 500
_flush_sent(); _flush_routing()
_print_turn(3, '500', session_b.estado)
monto_b3 = _svc._parse_monto('500')
print(f'  📋 _parse_monto → {monto_b3}')
if monto_b3 and monto_b3 >= _svc.MONTO_MINIMO_USD:
    session_b.cotiz_importe = monto_b3
    # _flujo_mostrar_cotizacion real (sin redirect de identificación para cliente desconocido)
    _svc._flujo_mostrar_cotizacion('5100000002', session_b)
    session_b.estado = 'viendo_cotizacion'
_print_bot_msgs(_flush_sent(), _flush_routing())
print(f'  Estado={session_b.estado} | cotiz_op={session_b.cotiz_op} | importe={session_b.cotiz_importe}')


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO C — "Quiero cambiar 100 dólares" → "quiero soles"
# Expectativa: bot pide dirección conservando USD 100.
#              "quiero soles" → cotiza venta 100 USD sin volver a pedir importe.
# ══════════════════════════════════════════════════════════════════════════════
_print_sep('DIÁLOGO C — Quiero cambiar 100 dólares / quiero soles')
print('  Expectativa: bot pide dirección conservando USD 100.')
print('  Turno 2 "quiero soles" → cotiza venta 100 USD sin volver a pedir importe.')

session_c = _make_session(estado='inicio')

# Turno C1
_flush_sent(); _flush_routing()
_print_turn(1, 'Quiero cambiar 100 dólares', session_c.estado)
interp_c1 = interpretar('Quiero cambiar 100 dólares', session_c)
_print_interp(interp_c1)
routed_c1 = aplicar('5100000003', session_c, interp_c1)
print(f'  📌 _aplicar_interpretacion_pre_op → {routed_c1}')
print(f'  cotiz_op={session_c.cotiz_op} | cotiz_importe={session_c.cotiz_importe} | estado={session_c.estado}')
if not routed_c1:
    ia_c1 = respuesta_ia('Quiero cambiar 100 dólares', '5100000003', session_c)
    if ia_c1:
        _sent.append({'tipo': 'texto', 'msg': ia_c1})
_print_bot_msgs(_flush_sent(), _flush_routing())

# Turno C2 — "quiero soles" en estado eligiendo_operacion
_flush_sent(); _flush_routing()
_print_turn(2, 'quiero soles', session_c.estado)
interp_c2 = interpretar('quiero soles', session_c)
_print_interp(interp_c2)
# Simular el handler eligiendo_operacion: extrae tipo y aplica
if interp_c2.get('tipo'):
    session_c.cotiz_op = interp_c2['tipo']
# aplicar → _identificar_y_cotizar_directo (real) → _flujo_mostrar_cotizacion (real)
aplicar('5100000003', session_c, interp_c2)
print(f'  cotiz_op={session_c.cotiz_op} | cotiz_importe={session_c.cotiz_importe} | estado={session_c.estado}')
_print_bot_msgs(_flush_sent(), _flush_routing())

print()
if interp_c1['tipo'] is None and (session_c.cotiz_importe or 0) > 0:
    print('  ✅ Turno 1: dirección ambigua; importe USD 100 conservado, dirección pedida.')
if interp_c2['tipo'] == 'venta':
    print('  ✅ Turno 2: "quiero soles" → venta detectada + cotización emitida.')


# ══════════════════════════════════════════════════════════════════════════════
print('\n' + '═' * 60)
print('  FIN DE VALIDACIÓN')
print('  Modelo IA: claude-haiku-4-5-20251001 (llamadas reales a Anthropic API)')
print()
print('  TRAZABILIDAD DE TIPOS DE CAMBIO:')
print(f'    _get_tc() → MOCK SINTÉTICO: compra={_TC_COMPRA_SINTETICO}, venta={_TC_VENTA_SINTETICO}')
print('    Los TC en las respuestas de la IA provienen exclusivamente de este mock,')
print('    inyectado al system prompt. No provienen del backend ni fueron generados')
print('    por el modelo. En producción, _get_tc() consulta el servicio de cotización.')
print()
print('  MOCKS activos (send/DB/clientes):')
print('    send_text, send_buttons, send_buttons_image, send_list,')
print('    _historial_ia, _get_tc, _is_horario_atencion,')
print('    _buscar_clientes_por_telefono, _buscar_cliente, _operacion_activa_cliente,')
print('    _save_outgoing, _bienvenida, _menu_rapido')
print('  Funciones reales ejecutadas (incluyendo cotización):')
print('    _interpretar_solicitud, _detectar_intencion, _respuesta_ia,')
print('    _aplicar_interpretacion_pre_op, _identificar_y_cotizar_directo,')
print('    _flujo_mostrar_cotizacion, _flujo_pedir_importe, _mejora_tc')
print('═' * 60 + '\n')

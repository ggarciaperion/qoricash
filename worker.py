"""
Background Worker — Agentes IA QoriCash
Entry point para el servicio Background Worker de Render.
Ejecuta exclusivamente el ecosistema de agentes IA sin servidor HTTP,
liberando al web service (qoricash-trading) del peso de los greenlets.

Render Start Command: python worker.py
"""
# CRITICO: monkey_patch de eventlet DEBE ir PRIMERO
import eventlet
eventlet.monkey_patch(os=True, select=True, socket=True, thread=True, time=True)

try:
    from psycogreen.eventlet import patch_psycopg
    patch_psycopg()
    print("[WORKER] psycopg2 patched con psycogreen")
except ImportError:
    print("[WORKER] WARNING: psycogreen no disponible — continuando sin patch")

import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Asegurar zona horaria Lima
os.environ.setdefault('TZ', 'America/Lima')
try:
    import time as _time
    _time.tzset()
except AttributeError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)
_log = logging.getLogger('qoricash.worker')

# Crear app Flask (sin greenlets de agentes — QORI_MODE no es 'web' aqui,
# pero tampoco queremos arrancar agentes dos veces si create_app() los inicia).
# La variable QORI_MODE=worker hace que __init__.py NO llame start_all_agents().
# Los llamamos nosotros aqui, una sola vez, de forma controlada.
os.environ['QORI_MODE'] = 'web'   # evita que create_app() arranque los agentes
from app import create_app

app = create_app()
_log.info('[Worker] App Flask inicializada')

# Ahora si arrancamos los agentes en este proceso
os.environ['QORI_MODE'] = 'worker'  # restaurar para claridad de logs

with app.app_context():
    from app.models import inteligencia as _m_intel   # noqa
    from app.models import prospecto as _m_prosp      # noqa

from app.services.agents.orchestrator import start_all_agents
start_all_agents(app)

_log.info('[Worker] Todos los agentes corriendo — proceso en idle loop')

# Mantener el proceso vivo.
# Los greenlets de eventlet siguen ejecutandose mientras el proceso este activo.
while True:
    eventlet.sleep(60)
    _log.debug('[Worker] heartbeat — agentes activos')

"""
campaign_sink.py — Sink de eventos de campaña para el sistema QoriCash.

Reemplaza la escritura de archivos .log en ~/Desktop como mecanismo de registro.
Los eventos se envían directamente al endpoint Flask autenticado. Si el servidor
no está disponible, el evento se encola en ~/Library/Application Support/qoricash/queue/
para reintento posterior por el sincronizador.

Solo se conserva la cola de reintentos (archivos pequeños, transitories).
Los eventos confirmados por el servidor NO se guardan localmente.

Uso en campaña:
    from campaign_sink import send_evento

    send_evento({
        'email':        'contacto@empresa.com',
        'empresa':      'Empresa S.A.',
        'bandeja':      'ggarcia@qoricash.pe',
        'proceso':      'campana_150',          # nombre estable del proceso
        'enviado_at':   '2026-10-25 09:30:00',  # datetime.now().strftime(...)
        'resultado_log': 'OK',                  # 'OK' o 'FAIL'
        'fuente_archivo': 'campana_150_2026-10-25.log',  # mantiene hash compatible
    })
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
APPDIR    = Path.home() / 'Library' / 'Application Support' / 'qoricash'
QUEUE_DIR = APPDIR / 'queue'
_KEY_FILE = Path.home() / '.config' / 'qoricash' / 'sync_key'
_URL_FILE = Path.home() / '.config' / 'qoricash' / 'sync_url'

DEFAULT_URL = 'http://localhost:5002/agentes/api/prospeccion/sync-evento'
# ─────────────────────────────────────────────────────────────────────────────

_api_key_cache: str = ''
_api_url_cache: str = ''


def _api_key() -> str:
    global _api_key_cache
    if _api_key_cache:
        return _api_key_cache
    k = os.environ.get('SYNC_API_KEY', '').strip()
    if not k and _KEY_FILE.exists():
        k = _KEY_FILE.read_text().strip()
    _api_key_cache = k
    return k


def _api_url() -> str:
    global _api_url_cache
    if _api_url_cache:
        return _api_url_cache
    u = os.environ.get('QORI_SYNC_URL', '').strip()
    if not u and _URL_FILE.exists():
        u = _URL_FILE.read_text().strip()
    _api_url_cache = u or DEFAULT_URL
    return _api_url_cache


def _ensure_queue():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def _enqueue(record: dict):
    """Escribe el evento en la cola de reintentos (Application Support)."""
    _ensure_queue()
    ts = time.strftime('%Y%m%d_%H%M%S')
    micro = f'{time.time_ns() % 1_000_000:06d}'
    fname = f'evt_{ts}_{micro}.json'
    path = QUEUE_DIR / fname
    try:
        path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass   # no se puede encolar — se pierde silenciosamente


def _try_post(eventos: list) -> bool:
    """POST al endpoint Flask. Retorna True si el servidor confirmó (2xx)."""
    key = _api_key()
    if not key:
        return False  # sin clave → encolar

    body = json.dumps({'eventos': eventos}).encode('utf-8')
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Length': str(len(body)),
        'X-Sync-Client': 'campaign_sink/1.0',
        'X-Sync-Key': key,   # nunca aparece en logs
    }
    try:
        req = urllib.request.Request(_api_url(), data=body, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status < 300
    except Exception:
        return False


def send_evento(record: dict) -> bool:
    """
    Envía un evento de campaña al servidor.
    - Si el servidor confirma: no guarda nada localmente.
    - Si falla: encola en Application Support para reintento posterior.
    Retorna True si el servidor confirmó; False si quedó en cola.
    """
    if _try_post([record]):
        return True
    _enqueue(record)
    return False


def send_batch(records: list) -> tuple:
    """
    Envía un lote. Retorna (enviados_al_servidor, encolados).
    Si el POST falla, todos los registros van a la cola.
    """
    if not records:
        return 0, 0
    if _try_post(records):
        return len(records), 0
    for r in records:
        _enqueue(r)
    return 0, len(records)

"""
sincronizador.py — Drainer de cola de eventos de campaña QoriCash.

Lee eventos pendientes de ~/Library/Application Support/qoricash/queue/,
los envía al endpoint Flask autenticado y elimina los confirmados.
No accede a ~/Desktop — no requiere Full Disk Access de macOS.

Cola: un archivo JSON por evento. Solo permanecen los no confirmados.
Log:  rotación automática (500 KB × 3 archivos).

Uso:
    python3 sincronizador.py              # modo normal
    python3 sincronizador.py --dry-run    # muestra pendientes sin enviar
    python3 sincronizador.py --url URL    # apuntar a otro servidor

Automatización: launchd carga pe.qoricash.sincronizador.plist cada 15 min.
"""

import argparse
import json
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────
APPDIR    = Path.home() / 'Library' / 'Application Support' / 'qoricash'
QUEUE_DIR = APPDIR / 'queue'
LOCK_FILE = APPDIR / 'sincronizador.lock'
LOG_FILE  = APPDIR / 'sincronizador.log'
LOG_MAX_BYTES = 500_000   # 500 KB por archivo
LOG_BACKUP_COUNT = 3      # 3 archivos de backup
DEFAULT_URL = 'http://localhost:5002/agentes/api/prospeccion/sync-evento'
BATCH_SIZE  = 100         # eventos por POST
MAX_RETRIES = 3
RETRY_DELAY = 5
_KEY_FILE = Path.home() / '.config' / 'qoricash' / 'sync_key'
# ─────────────────────────────────────────────────────────────────────────────


def _setup_logging():
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler())


_log = logging.getLogger(__name__)


# ── Lock ──────────────────────────────────────────────────────────────────────

def _acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)
            return False   # proceso vivo
        except (ValueError, ProcessLookupError, PermissionError):
            pass           # lock huérfano
    try:
        LOCK_FILE.write_text(str(os.getpid()))
    except OSError as exc:
        _log.warning('No se pudo crear lock: %s', exc)
    return True


def _release_lock():
    try:
        LOCK_FILE.unlink()
    except OSError:
        pass


# ── Autenticación ─────────────────────────────────────────────────────────────

def _load_api_key() -> str:
    k = os.environ.get('SYNC_API_KEY', '').strip()
    if k:
        return k
    if _KEY_FILE.exists():
        v = _KEY_FILE.read_text().strip()
        if v:
            return v
    _log.error('Clave de sincronización no configurada. '
               'Configura SYNC_API_KEY o crea %s', _KEY_FILE)
    sys.exit(2)


# ── Envío ─────────────────────────────────────────────────────────────────────

def _post_batch(eventos: list, url: str, api_key: str) -> bool:
    """Envía un lote al endpoint. Retorna True si el servidor confirmó (2xx)."""
    body = json.dumps({'eventos': eventos}).encode('utf-8')
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Length': str(len(body)),
        'X-Sync-Client': 'sincronizador/2.0',
        'X-Sync-Key': api_key,
    }
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status < 300
        except urllib.error.HTTPError as exc:
            last_exc = exc
            _log.warning('intento %d/%d: HTTP %d', attempt, MAX_RETRIES, exc.code)
        except urllib.error.URLError as exc:
            last_exc = exc
            _log.warning('intento %d/%d: servidor no disponible (%s)',
                         attempt, MAX_RETRIES, exc.reason)
        except Exception as exc:
            last_exc = exc
            _log.warning('intento %d/%d: %s', attempt, MAX_RETRIES, exc)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
    _log.error('Falló tras %d intentos: %s', MAX_RETRIES, last_exc)
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Sincronizador de cola de eventos QoriCash')
    parser.add_argument('--dry-run', action='store_true',
                        help='Mostrar pendientes sin enviar')
    parser.add_argument('--url', default=DEFAULT_URL,
                        help='URL del endpoint Flask')
    args = parser.parse_args()

    APPDIR.mkdir(parents=True, exist_ok=True)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    _setup_logging()

    if not args.dry_run:
        if not _acquire_lock():
            _log.info('Sincronizador: otra instancia en curso. Saliendo.')
            sys.exit(0)

    try:
        _run(args)
    finally:
        if not args.dry_run:
            _release_lock()


def _run(args):
    api_key = '' if args.dry_run else _load_api_key()

    pending = sorted(QUEUE_DIR.glob('evt_*.json'))
    if not pending:
        _log.info('Sincronizador: cola vacía.')
        return

    _log.info('Sincronizador QoriCash — %d eventos pendientes | %s',
              len(pending), args.url)
    if args.dry_run:
        for p in pending:
            _log.info('  [pendiente] %s', p.name)
        return

    total_imp = total_err = 0

    # Procesar en lotes
    for i in range(0, len(pending), BATCH_SIZE):
        lote_paths = pending[i:i + BATCH_SIZE]
        lote_eventos = []
        for path in lote_paths:
            try:
                ev = json.loads(path.read_text(encoding='utf-8'))
                lote_eventos.append(ev)
            except (OSError, json.JSONDecodeError) as exc:
                _log.warning('Cola: no se pudo leer %s: %s', path.name, exc)

        if not lote_eventos:
            continue

        confirmado = _post_batch(lote_eventos, args.url, api_key)
        if confirmado:
            for path in lote_paths:
                try:
                    path.unlink()
                except OSError:
                    pass
            total_imp += len(lote_eventos)
            _log.info('  lote %d-%d: %d confirmados y eliminados de la cola',
                      i + 1, i + len(lote_paths), len(lote_eventos))
        else:
            total_err += len(lote_eventos)
            _log.warning('  lote %d-%d: falló — %d eventos permanecen en cola',
                         i + 1, i + len(lote_paths), len(lote_eventos))

    _log.info('Total confirmados: %d | En cola: %d', total_imp, total_err)
    if total_err:
        sys.exit(1)


if __name__ == '__main__':
    main()

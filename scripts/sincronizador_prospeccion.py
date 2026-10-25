"""
sincronizador_prospeccion.py — Sincroniza logs de campaña con el sistema QoriCash.

Escanea ~/Desktop/Prospeccion/ en busca de archivos .log y _resultado.json
nuevos o modificados y los envía al endpoint Flask local. Solo envía archivos
que aún no han sido procesados con éxito (estado en sincronizador_estado.json).

DEPENDENCIA: requiere que la Mac esté encendida y el servidor Flask corriendo
             en localhost. No puede sincronizar si la Mac está apagada.

AUTENTICACIÓN: requiere clave en SYNC_API_KEY (env var) o en
             ~/.config/qoricash/sync_key. Sin clave configurada, sale con
             error. Nunca expone la clave en logs.

SUPERPOSICIÓN: usa archivo de bloqueo (sincronizador.lock) basado en PID.
             Si ya hay una ejecución activa, la nueva sale sin hacer nada.

DETECCIÓN DE CAMBIOS: compara tamaño + SHA-256 del contenido. Un archivo
             con el mismo tamaño pero diferente hash se re-envía (detección
             de rotación o truncamiento con re-escritura).

Uso:
    python3 sincronizador_prospeccion.py              # modo normal
    python3 sincronizador_prospeccion.py --dry-run    # muestra pendientes sin enviar
    python3 sincronizador_prospeccion.py --reset      # olvida estado y re-envía todo
    python3 sincronizador_prospeccion.py --url URL    # apuntar a otro servidor

Automatización: launchd carga pe.qoricash.sincronizador.plist cada 15 min.
    Activar:   launchctl load ~/Library/LaunchAgents/pe.qoricash.sincronizador.plist
    Detener:   launchctl unload ~/Library/LaunchAgents/pe.qoricash.sincronizador.plist
    Estado:    launchctl list pe.qoricash.sincronizador
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import urllib.request
import urllib.error

# ── Configuración ─────────────────────────────────────────────────────────────
PROSPECCION_DIR = os.path.expanduser('~/Desktop/Prospeccion')
ESTADO_FILE     = os.path.join(PROSPECCION_DIR, 'sincronizador_estado.json')
LOCK_FILE       = os.path.join(PROSPECCION_DIR, 'sincronizador.lock')
DEFAULT_URL     = 'http://localhost:5002/agentes/api/prospeccion/sync-importar'
MAX_RETRIES     = 3
RETRY_DELAY_S   = 5     # segundos entre reintentos
MAX_FILE_MB     = 20    # archivos mayores se omiten con aviso
_KEY_FILE       = os.path.expanduser('~/.config/qoricash/sync_key')
# ─────────────────────────────────────────────────────────────────────────────


# ── Lock ──────────────────────────────────────────────────────────────────────

def _acquire_lock() -> bool:
    """
    Intenta adquirir el lock de ejecución única.
    Retorna True si se adquirió; False si ya hay otra instancia activa.
    Elimina locks huérfanos (proceso que ya no existe).
    """
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)   # signal 0 = check existence only
            return False       # proceso aún vivo → no continuar
        except (ValueError, ProcessLookupError, PermissionError):
            pass               # PID inválido o proceso muerto → lock huérfano
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except OSError as exc:
        print(f'[WARN] No se pudo crear lock: {exc}')
    return True


def _release_lock():
    try:
        os.unlink(LOCK_FILE)
    except OSError:
        pass


# ── Autenticación ─────────────────────────────────────────────────────────────

def _load_api_key() -> str:
    """
    Lee la clave de API desde env var SYNC_API_KEY o desde el archivo de claves.
    Nunca registra ni imprime el valor de la clave.
    Termina con error si no hay clave configurada.
    """
    k = os.environ.get('SYNC_API_KEY', '').strip()
    if k:
        return k
    if os.path.exists(_KEY_FILE):
        try:
            v = Path(_KEY_FILE).read_text().strip()
            if v:
                return v
        except OSError:
            pass
    print('[ERROR] Clave de sincronización no configurada.')
    print(f'  Configura SYNC_API_KEY como variable de entorno')
    print(f'  o crea {_KEY_FILE} con el valor de la clave.')
    sys.exit(2)


# ── Detección de cambios ──────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    """SHA-256 hex del contenido completo del archivo."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


_EXCLUIDOS = {
    'sincronizador.log',        # log propio de este script
    'sincronizador_estado.json', # estado interno
    'sincronizador.lock',       # lock file
}


def _es_archivo_valido(name: str) -> bool:
    """Devuelve True si el archivo debe ser importado."""
    if name in _EXCLUIDOS:
        return False
    nl = name.lower()
    return nl.endswith('.log') or nl.endswith('_resultado.json')


# ── Estado por destino ────────────────────────────────────────────────────────
#
# Formato v2:
#   { "version": 2,
#     "destinos": {
#       "http://localhost:5002/.../sync-importar": { "enviados": { "file.log": {...} } },
#       "https://app.render.com/.../sync-importar": { "enviados": {} }
#     }
#   }
#
# El progreso es independiente por URL de destino:
# archivos enviados a localhost no bloquean el envío a Render.

def _cargar_estado() -> dict:
    raw = {}
    if os.path.exists(ESTADO_FILE):
        try:
            with open(ESTADO_FILE, 'r') as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass

    # Migración v1 → v2: formato antiguo tiene 'enviados' en la raíz
    if 'enviados' in raw and 'destinos' not in raw:
        raw = {
            'version': 2,
            'destinos': {DEFAULT_URL: {'enviados': raw['enviados']}},
        }
        _guardar_estado_raw(raw)

    if 'destinos' not in raw:
        raw = {'version': 2, 'destinos': {}}

    return raw


def _enviados_para(estado: dict, dest_url: str) -> dict:
    """Devuelve el sub-dict 'enviados' para un destino concreto."""
    return estado['destinos'].setdefault(dest_url, {'enviados': {}}).setdefault('enviados', {})


def _guardar_estado_raw(estado: dict):
    try:
        with open(ESTADO_FILE, 'w') as f:
            json.dump(estado, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        print(f'  [WARN] No se pudo guardar estado: {exc}')


def _migrar_sha256(enviados: dict) -> bool:
    """Agrega sha256 a entradas antiguas que solo tienen 'size'. Retorna True si hubo cambios."""
    changed = False
    for fname, entry in enviados.items():
        if 'sha256' not in entry:
            fpath = Path(PROSPECCION_DIR) / fname
            if fpath.exists() and fpath.stat().st_size == entry.get('size', -1):
                try:
                    entry['sha256'] = _sha256(fpath)
                    changed = True
                except OSError:
                    pass
    return changed


def _archivos_pendientes(enviados: dict) -> list:
    """
    Retorna archivos nuevos o modificados para un destino.
    Compara tamaño + SHA-256: detecta rotación, truncamiento y re-escritura.
    """
    directorio = Path(PROSPECCION_DIR)
    pendientes = []
    for p in sorted(directorio.iterdir()):
        if not p.is_file():
            continue
        if not _es_archivo_valido(p.name):
            continue
        size = p.stat().st_size
        if size == 0:
            continue

        prev = enviados.get(p.name)
        if not prev:
            pendientes.append(p)
            continue
        if prev.get('size') != size:
            pendientes.append(p)
            continue
        if 'sha256' not in prev:
            pendientes.append(p)
            continue
        try:
            if _sha256(p) != prev['sha256']:
                pendientes.append(p)
        except OSError:
            continue

    return pendientes


# ── Envío ─────────────────────────────────────────────────────────────────────

def _enviar_archivo(path: Path, url: str, api_key: str) -> dict:
    """
    Envía un archivo al endpoint Flask via multipart/form-data.
    Retorna el dict de respuesta JSON o lanza RuntimeError tras agotar reintentos.
    La clave de API se transmite por header; nunca se registra en logs.
    """
    size_mb = path.stat().st_size / 1_048_576
    if size_mb > MAX_FILE_MB:
        return {'filename': path.name, 'omitido': True,
                'motivo': f'Archivo demasiado grande ({size_mb:.1f} MB > {MAX_FILE_MB} MB)'}

    content = path.read_bytes()
    filename = path.name

    boundary = b'----QoriCashSyncBoundary7x4k'
    body = (
        b'--' + boundary + b'\r\n'
        b'Content-Disposition: form-data; name="files"; filename="' + filename.encode() + b'"\r\n'
        b'Content-Type: application/octet-stream\r\n'
        b'\r\n' +
        content +
        b'\r\n--' + boundary + b'--\r\n'
    )

    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary.decode()}',
        'Content-Length': str(len(body)),
        'X-Sync-Client': 'sincronizador_prospeccion/1.1',
    }
    if api_key:
        headers['X-Sync-Key'] = api_key   # nunca aparece en logs

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
                data = json.loads(raw)
                for r in data.get('resultados', []):
                    if r.get('filename') == filename:
                        return r
                return {
                    'filename': filename,
                    'importados': data.get('total_importados', '?'),
                    'duplicados': data.get('total_duplicados', '?'),
                    'descartados': 0,
                }
        except urllib.error.HTTPError as exc:
            last_exc = exc
            # Lee el cuerpo del error pero no expone headers de auth
            try:
                body_err = exc.read().decode('utf-8', errors='replace')[:200]
            except Exception:
                body_err = str(exc)
            print(f'    intento {attempt}/{MAX_RETRIES}: HTTP {exc.code} — {body_err}')
        except urllib.error.URLError as exc:
            last_exc = exc
            print(f'    intento {attempt}/{MAX_RETRIES}: servidor no disponible ({exc.reason})')
        except Exception as exc:
            last_exc = exc
            print(f'    intento {attempt}/{MAX_RETRIES}: {type(exc).__name__}: {exc}')

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_S)

    raise RuntimeError(f'Falló tras {MAX_RETRIES} intentos: {last_exc}')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Sincronizador de logs de campaña QoriCash')
    parser.add_argument('--dry-run', action='store_true',
                        help='Mostrar archivos pendientes sin enviar nada')
    parser.add_argument('--reset', action='store_true',
                        help='Olvidar estado guardado y re-enviar todos los archivos')
    parser.add_argument('--url', default=DEFAULT_URL,
                        help='URL del endpoint Flask')
    args = parser.parse_args()

    # ── Evitar ejecuciones superpuestas ───────────────────────────────────────
    if not args.dry_run:
        if not _acquire_lock():
            print('Sincronizador: otra instancia está en curso. Saliendo.')
            sys.exit(0)

    try:
        _run(args)
    finally:
        if not args.dry_run:
            _release_lock()


def _run(args):
    # Verificar key antes de cualquier trabajo (falla rápido si no configurada)
    # _load_api_key() llama sys.exit(2) si no hay clave disponible
    api_key = '' if args.dry_run else _load_api_key()
    auth_info = 'con clave' if api_key else 'dry-run'

    if args.reset:
        estado = {'version': 2, 'destinos': {}}
    else:
        estado = _cargar_estado()

    # Estado separado por destino: archivos enviados a localhost no bloquean Render
    enviados = _enviados_para(estado, args.url)

    # Migrar entradas antiguas sin sha256 (primera vez que se abre con v2)
    if _migrar_sha256(enviados):
        _guardar_estado_raw(estado)

    pendientes = _archivos_pendientes(enviados)

    if not pendientes:
        print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Sincronizador: no hay archivos nuevos.')
        return

    print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Sincronizador QoriCash')
    print(f'  Archivos pendientes: {len(pendientes)}')
    print(f'  Endpoint: {args.url}  [{auth_info}]')
    if args.dry_run:
        print('  (dry-run: solo se listan, no se envían)')

    total_imp = 0
    errores   = 0

    for path in pendientes:
        size_kb = path.stat().st_size / 1024
        print(f'  → {path.name} ({size_kb:.0f} KB)', end=' ', flush=True)

        if args.dry_run:
            print('[pendiente]')
            continue

        try:
            resultado = _enviar_archivo(path, args.url, api_key)
        except RuntimeError as exc:
            # Servidor no disponible o error irrecuperable
            # No marcar como enviado → queda pendiente para el próximo ciclo
            print(f'[FALLO] {exc}')
            errores += 1
            continue

        if resultado.get('omitido'):
            print(f'[omitido] {resultado.get("motivo", "")}')
            continue

        if resultado.get('error'):
            # Respuesta del servidor con error de negocio (ej: extensión no permitida)
            print(f'[ERROR servidor] {resultado["error"]}')
            errores += 1
            continue

        # Solo se registra como enviado si la respuesta confirmó la importación
        imp  = resultado.get('importados', 0)
        dup  = resultado.get('duplicados', 0)
        desc = resultado.get('descartados', 0)
        total_imp += int(imp) if imp else 0
        print(f'[OK] {imp} nuevos / {dup} dup / {desc} desc')

        try:
            file_hash = _sha256(path)
        except OSError:
            file_hash = ''

        enviados[path.name] = {
            'size':       path.stat().st_size,
            'sha256':     file_hash,
            'importados': imp,
            'ts':         time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        _guardar_estado_raw(estado)   # guardar después de cada archivo exitoso

    print(f'  Total importados: {total_imp}')
    if errores:
        print(f'  Errores: {errores} archivo(s) no confirmados '
              f'(quedan pendientes para el siguiente ciclo)')
        sys.exit(1)


if __name__ == '__main__':
    main()

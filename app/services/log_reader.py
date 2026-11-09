"""
log_reader.py — Lector de logs de campanas de prospeccion.

Fuente real: archivos .log y _resultado.json en ~/Desktop/Prospeccion/
Acceso: solo lectura local, sin credenciales externas.

Los scripts de campana (campana_qoricash_150.py, campana_prospeccion_nueva_base.py,
campana_nuevos_prospectos.py) NO escriben en PostgreSQL.  Su registro de actividad
vive en estos archivos locales, que esta clase lee y normaliza.

Formatos soportados:
  1. campana_prospeccion_nueva_base: [BANDEJA] [  N/T] OK -> email (empresa)
  2. campana_150:                    [bandeja][N/T] OK  email  empresa
  3. campana_nuevos con bandeja:     [INFO] [bandeja@qoricash.pe] Enviado -> email
  4. campana_nuevos old sin bandeja: INFO [N/T] OK email
  5. campana_prospeccion_precios:    [PROSP-PRECIOS] INFO [N/T] OK  -> email | empresa | ...
"""

import os
import re
import json
import glob
import math
import logging
import time as _time

log = logging.getLogger(__name__)

LOGS_DIR = os.path.expanduser("/Users/gianpierre/Desktop/Prospeccion")

# ── Regexes por formato ────────────────────────────────────────────────────────

RE_PROSP = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+'
    r'\s+\[([A-Z]+)\]\s+\[\s*\d+/\d+\]\s+(OK|FAIL)\s+\u2192\s+(\S+)\s+\((.+)\)\s*$'
)

RE_150 = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+'
    r'\s+\[([a-z]+)\]\[\s*\d+/\d+\]\s+(OK|FAIL)\s+(\S+)\s+(.*?)\s*$'
)

RE_NUEVOS = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+'
    r'\s+\[INFO\]\s+\[([^\]@]+@qoricash\.pe)\]\s+Enviado\s+\u2192\s+(\S+)'
)

RE_NUEVOS_OLD = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+'
    r'\s+INFO\s+\[\s*\d+/\d+\]\s+(OK|FAIL)\s+(\S+)\s*$'
)

RE_PRECIOS = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+'
    r'\s+\[[^\]]+\]\s+INFO\s+\[\s*\d+/\d+\]\s+(OK|FAIL)\s+\u2192\s+(\S+)\s+\|\s+([^|]+)'
)

_BANDEJA_NORM = {
    'ggarcia':  'ggarcia@qoricash.pe',
    'GGARCIA':  'ggarcia@qoricash.pe',
    'gerencia': 'gerencia@qoricash.pe',
    'GERENCIA': 'gerencia@qoricash.pe',
    'info':     'info@qoricash.pe',
    'INFO':     'info@qoricash.pe',
}


def _norm_bandeja(raw):
    if raw in _BANDEJA_NORM:
        return _BANDEJA_NORM[raw]
    if '@' in raw:
        return raw
    return raw.lower() + '@qoricash.pe'


def _bandeja_from_filename(path):
    name = os.path.basename(path).lower()
    if 'gerencia' in name:
        return 'gerencia@qoricash.pe'
    if 'ggarcia' in name:
        return 'ggarcia@qoricash.pe'
    if '_info' in name:
        return 'info@qoricash.pe'
    return None


def _proceso_from_filename(path):
    name = os.path.basename(path)
    if name.startswith('campana_150'):
        return 'campana_150'
    if 'precios' in name:
        return 'campana_precios'
    if name.startswith('campana_prospeccion'):
        return 'campana_prospeccion'
    if name.startswith('campana_nuevos'):
        return 'campana_nuevos'
    return 'campana'


def _parse_log_file(path):
    proceso = _proceso_from_filename(path)
    bandeja_default = _bandeja_from_filename(path)
    records = []

    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.rstrip()

                m = RE_PROSP.match(line)
                if m:
                    ts, bandeja_raw, result, email, empresa = m.groups()
                    records.append({
                        'ts': ts,
                        'email': email.lower().rstrip(','),
                        'empresa': empresa.strip(),
                        'bandeja': _norm_bandeja(bandeja_raw),
                        'resultado': result,
                        'proceso': proceso,
                        'fuente_log': os.path.basename(path),
                    })
                    continue

                m = RE_150.match(line)
                if m:
                    ts, bandeja_raw, result, email, empresa = m.groups()
                    records.append({
                        'ts': ts,
                        'email': email.lower(),
                        'empresa': empresa.strip() or None,
                        'bandeja': _norm_bandeja(bandeja_raw),
                        'resultado': result,
                        'proceso': proceso,
                        'fuente_log': os.path.basename(path),
                    })
                    continue

                m = RE_NUEVOS.match(line)
                if m:
                    ts, bandeja, email = m.groups()
                    records.append({
                        'ts': ts,
                        'email': email.lower().rstrip(','),
                        'empresa': None,
                        'bandeja': bandeja,
                        'resultado': 'OK',
                        'proceso': proceso,
                        'fuente_log': os.path.basename(path),
                    })
                    continue

                m = RE_PRECIOS.match(line)
                if m:
                    ts, result, email, empresa = m.groups()
                    records.append({
                        'ts': ts,
                        'email': email.lower().rstrip(','),
                        'empresa': empresa.strip(),
                        'bandeja': bandeja_default,
                        'resultado': result,
                        'proceso': proceso,
                        'fuente_log': os.path.basename(path),
                    })
                    continue

                m = RE_NUEVOS_OLD.match(line)
                if m:
                    ts, result, email = m.groups()
                    records.append({
                        'ts': ts,
                        'email': email.lower(),
                        'empresa': None,
                        'bandeja': bandeja_default,
                        'resultado': result,
                        'proceso': proceso,
                        'fuente_log': os.path.basename(path),
                    })

    except Exception as exc:
        log.warning("log_reader: error leyendo %s: %s", path, exc)

    return records


# ── Cache en memoria (TTL 5 min) ───────────────────────────────────────────────

_cache = {
    'records': None,
    'bounces': None,
    'loaded_at': 0.0,
    'total_files': 0,
}
_CACHE_TTL = 300


def _ensure_cache():
    now = _time.time()
    if _cache['records'] is not None and (now - _cache['loaded_at']) < _CACHE_TTL:
        return

    patterns = [
        'campana_150_*.log',
        'campana_prospeccion_*.log',
        'campana_nuevos_*.log',
        'campana_nuevos_gerencia*.log',
        'campana_nuevos_ggarcia*.log',
    ]
    all_files = set()
    for pat in patterns:
        all_files.update(glob.glob(os.path.join(LOGS_DIR, pat)))

    all_records = []
    for path in sorted(all_files):
        all_records.extend(_parse_log_file(path))

    all_records.sort(key=lambda r: r['ts'], reverse=True)

    # Deduplicar por (email, ts)
    seen = set()
    deduped = []
    for r in all_records:
        key = (r['email'], r['ts'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # Indice de rebotes
    bounces = {}
    for path in sorted(glob.glob(os.path.join(LOGS_DIR, 'limpiar_bandejas_*_resultado.json'))):
        try:
            d = json.load(open(path, encoding='utf-8'))
            for email, info in (d.get('bounces') or {}).items():
                if isinstance(info, dict):
                    bounces[email.lower()] = {
                        'tipo': info.get('tipo', 'hard'),
                        'motivo': info.get('motivo', ''),
                        'fecha': info.get('fecha', ''),
                        'cuenta': info.get('cuenta', ''),
                    }
        except Exception as exc:
            log.warning("log_reader bounces: %s: %s", path, exc)

    _cache['records'] = deduped
    _cache['bounces'] = bounces
    _cache['loaded_at'] = now
    _cache['total_files'] = len(all_files)
    log.info(
        "log_reader: %d registros, %d rebotes, %d archivos",
        len(deduped), len(bounces), len(all_files)
    )


def disponible():
    return os.path.isdir(LOGS_DIR) and bool(
        glob.glob(os.path.join(LOGS_DIR, 'campana_*.log'))
    )


def get_contactos_page_from_logs(
    page=1,
    per_page=50,
    fecha_desde=None,
    fecha_hasta=None,
    bandeja=None,
    resultado=None,
    busqueda=None,
):
    """Tabla paginada de contactos desde archivos de log locales."""
    if not disponible():
        return {
            'disponible': False,
            'fuente': 'logs_locales',
            'fuente_descripcion': 'Directorio de logs no accesible: ' + LOGS_DIR,
            'rows': [], 'total': 0, 'page': page, 'per_page': per_page, 'pages': 1,
        }

    _ensure_cache()
    rows = list(_cache['records'] or [])
    bounces = _cache['bounces'] or {}

    if fecha_desde:
        rows = [r for r in rows if r['ts'][:10] >= fecha_desde]
    if fecha_hasta:
        rows = [r for r in rows if r['ts'][:10] <= fecha_hasta]
    if bandeja:
        rows = [r for r in rows if bandeja in (r.get('bandeja') or '')]
    if resultado:
        if resultado in ('rebotado', 'bounce'):
            rows = [r for r in rows if r['email'] in bounces]
        elif resultado in ('ok', 'enviado'):
            rows = [r for r in rows if r['resultado'] == 'OK' and r['email'] not in bounces]
        elif resultado in ('fail', 'error'):
            rows = [r for r in rows if r['resultado'] == 'FAIL']
    if busqueda:
        q = busqueda.lower()
        rows = [r for r in rows if q in r['email'] or q in (r.get('empresa') or '').lower()]

    total = len(rows)
    pages = max(1, math.ceil(total / per_page)) if total else 1
    page = min(max(1, page), pages)
    start = (page - 1) * per_page
    page_rows = rows[start:start + per_page]

    out = []
    for r in page_rows:
        rebote = bounces.get(r['email'])
        status = 'rebotado' if rebote else ('enviado' if r['resultado'] == 'OK' else 'error')
        out.append({
            # Nombres compatibles con el schema de DB para que el template los reutilice
            'email':             r['email'],
            'razon_social':      r.get('empresa'),
            'nombre_contacto':   None,
            'bandeja':           r.get('bandeja'),
            'stage':             r.get('proceso'),
            'subject':           None,
            'status':            status,
            'sent_at_lima':      r['ts'],
            'estado_com':        None,
            'resp_clasificacion': ('bounce_' + rebote['tipo']) if rebote else None,
            'resp_snippet':      rebote.get('motivo') if rebote else None,
            'fuente_log':        r.get('fuente_log'),
        })

    return {
        'disponible': True,
        'fuente': 'logs_locales',
        'fuente_descripcion': (
            'Archivos de campana en ~/Desktop/Prospeccion/ '
            '(%d archivos)' % _cache['total_files']
        ),
        'rows':     out,
        'total':    total,
        'page':     page,
        'per_page': per_page,
        'pages':    pages,
    }


def get_contacto_timeline_from_logs(email):
    """Historial completo de un email desde logs de campana y resultados de rebote."""
    email_lower = email.lower()

    if not disponible():
        return {
            'disponible': False, 'fuente': 'logs_locales',
            'email': email_lower, 'envios': [], 'rebote': None,
        }

    _ensure_cache()
    records = _cache['records'] or []
    bounces = _cache['bounces'] or {}

    envios = [r for r in records if r['email'] == email_lower]
    rebote = bounces.get(email_lower)
    empresa = next((r['empresa'] for r in envios if r.get('empresa')), None)

    envios_out = []
    for e in envios:
        envios_out.append({
            'ts':        e['ts'],
            'bandeja':   e.get('bandeja'),
            'stage':     e.get('proceso'),
            'resultado': e['resultado'],
            'fuente':    e.get('fuente_log'),
            'subject':   None,
            'status':    'rebotado' if rebote else ('enviado' if e['resultado'] == 'OK' else 'error'),
            # Compat con template existente
            'sent_at_lima': e['ts'],
            'skip_reason':  None,
            'tc_compra':    None,
            'tc_venta':     None,
            'agent':        None,
        })

    return {
        'disponible': True,
        'fuente': 'logs_locales',
        'email': email_lower,
        'prospecto': {
            'email':        email_lower,
            'razon_social': empresa,
            'ruc':          None,
            'estado_email': 'correo_rebotado' if rebote else None,
            'estado_com':   None,
        },
        'envios':     envios_out,
        'respuestas': [],
        'cambios':    [],
        'rebote':     rebote,
    }

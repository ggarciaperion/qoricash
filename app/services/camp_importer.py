"""
camp_importer.py  —  Importador incremental e idempotente de logs de campana.

Tablas persistentes: camp_envio, camp_rebote, camp_importacion.
Compatible con SQLite (dev) y PostgreSQL (produccion).

Reglas de importacion:
  - Identificador estable: sha256(filename + ts + email)  => nunca duplica la misma linea.
  - Re-importar el mismo archivo es seguro: los registros existentes se cuentan como "duplicados".
  - El rebote se registra separado del envio; la relacion es por email, no por envio especifico.
  - Los archivos se tratan como datos; nunca se ejecutan.
"""

import hashlib
import json
import re
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# ── Regexes identicos a log_reader.py ────────────────────────────────────────

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

_BN = {
    'ggarcia': 'ggarcia@qoricash.pe',   'GGARCIA': 'ggarcia@qoricash.pe',
    'gerencia': 'gerencia@qoricash.pe', 'GERENCIA': 'gerencia@qoricash.pe',
    'info': 'info@qoricash.pe',         'INFO': 'info@qoricash.pe',
}


def _nb(raw):
    return _BN.get(raw, raw if '@' in raw else raw.lower() + '@qoricash.pe')


def _bandeja_from_name(name):
    n = name.lower()
    if 'gerencia' in n: return 'gerencia@qoricash.pe'
    if 'ggarcia' in n:  return 'ggarcia@qoricash.pe'
    return None


def _proceso_from_name(name):
    if name.startswith('campana_150'):       return 'campana_150'
    if 'precios' in name:                   return 'campana_precios'
    if name.startswith('campana_prospeccion'): return 'campana_prospeccion'
    if name.startswith('campana_nuevos'):   return 'campana_nuevos'
    return 'campana'


def _hash32(*parts):
    return hashlib.sha256('|'.join(str(p) for p in parts).encode()).hexdigest()[:32]


# ── DDL: tablas persistentes ──────────────────────────────────────────────────

def init_camp_tables():
    """Crea las tablas camp_* si no existen. Compatible SQLite y PostgreSQL."""
    from app.extensions import db
    dialect = db.engine.dialect.name
    if dialect == 'sqlite':
        pk   = 'id INTEGER PRIMARY KEY AUTOINCREMENT'
    else:
        pk   = 'id BIGSERIAL PRIMARY KEY'

    stmts = [
        f"""CREATE TABLE IF NOT EXISTS camp_envio (
            {pk},
            envio_hash    VARCHAR(32)  NOT NULL,
            email         VARCHAR(200) NOT NULL,
            empresa       VARCHAR(300),
            bandeja       VARCHAR(100),
            proceso       VARCHAR(80),
            enviado_at    TIMESTAMP,
            resultado_log VARCHAR(10),
            fuente_archivo VARCHAR(200),
            importado_at  TIMESTAMP,
            CONSTRAINT uq_camp_envio UNIQUE (envio_hash)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_camp_envio_email ON camp_envio (email)",
        "CREATE INDEX IF NOT EXISTS ix_camp_envio_at    ON camp_envio (enviado_at)",
        f"""CREATE TABLE IF NOT EXISTS camp_rebote (
            {pk},
            rebote_hash      VARCHAR(32)  NOT NULL,
            email            VARCHAR(200) NOT NULL,
            tipo             VARCHAR(20),
            motivo           TEXT,
            detectado_at     TIMESTAMP,
            bandeja_detectora VARCHAR(100),
            msg_id           VARCHAR(200),
            fuente_archivo   VARCHAR(200),
            importado_at     TIMESTAMP,
            CONSTRAINT uq_camp_rebote UNIQUE (rebote_hash)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_camp_rebote_email ON camp_rebote (email)",
        f"""CREATE TABLE IF NOT EXISTS camp_importacion (
            {pk},
            filename          VARCHAR(200) NOT NULL,
            tipo              VARCHAR(20)  NOT NULL,
            importado_at      TIMESTAMP,
            total_parseados   INTEGER DEFAULT 0,
            total_importados  INTEGER DEFAULT 0,
            total_duplicados  INTEGER DEFAULT 0,
            total_descartados INTEGER DEFAULT 0,
            detalle           TEXT
        )""",
        # camp_prospecto: enriquecimiento comercial vinculado por email
        f"""CREATE TABLE IF NOT EXISTS camp_prospecto (
            {pk},
            email            VARCHAR(200) NOT NULL,
            ruc              VARCHAR(20),
            razon_social     VARCHAR(300),
            nombre_contacto  VARCHAR(200),
            cargo            VARCHAR(150),
            telefono         VARCHAR(100),
            rubro            VARCHAR(150),
            provincia        VARCHAR(100),
            fuente           VARCHAR(50),
            actualizado_at   TIMESTAMP,
            CONSTRAINT uq_camp_prospecto_email UNIQUE (email)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_camp_prospecto_email ON camp_prospecto (email)",
        "CREATE INDEX IF NOT EXISTS ix_camp_prospecto_rubro ON camp_prospecto (rubro)",
    ]

    try:
        for stmt in stmts:
            db.session.execute(db.text(stmt))
        db.session.commit()
        log.info("camp_importer: tablas camp_* listas")
    except Exception as exc:
        db.session.rollback()
        log.warning("camp_importer: init_camp_tables: %s", exc)


# ── Upsert enriquecimiento ────────────────────────────────────────────────────

def upsert_prospectos(records: list) -> tuple:
    """
    Inserta o actualiza registros en camp_prospecto de forma idempotente.

    Reglas de actualización (no borrar datos existentes con campos vacíos):
      - Si el campo entrante es NULL/vacío, conserva el valor existente (COALESCE).
      - Solo 'fuente' y 'actualizado_at' se sobreescriben siempre.

    Compatible con SQLite (3.24+, que soporta ON CONFLICT DO UPDATE)
    y PostgreSQL (ON CONFLICT ... DO UPDATE con EXCLUDED).

    Retorna (upserted, skipped, error_list).
    """
    from app.extensions import db
    from datetime import datetime

    _FIELDS = ('email', 'ruc', 'razon_social', 'nombre_contacto',
               'cargo', 'telefono', 'rubro', 'provincia', 'fuente')

    upserted = skipped = 0
    error_list = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # SQL idempotente compatible con SQLite 3.24+ y PostgreSQL.
    # COALESCE(EXCLUDED.x, camp_prospecto.x) conserva el valor existente cuando
    # el campo entrante es NULL.
    sql = db.text("""
        INSERT INTO camp_prospecto
            (email, ruc, razon_social, nombre_contacto, cargo,
             telefono, rubro, provincia, fuente, actualizado_at)
        VALUES
            (:email, :ruc, :razon_social, :nombre_contacto, :cargo,
             :telefono, :rubro, :provincia, :fuente, :actualizado_at)
        ON CONFLICT (email) DO UPDATE SET
            ruc              = COALESCE(EXCLUDED.ruc,             camp_prospecto.ruc),
            razon_social     = COALESCE(EXCLUDED.razon_social,    camp_prospecto.razon_social),
            nombre_contacto  = COALESCE(EXCLUDED.nombre_contacto, camp_prospecto.nombre_contacto),
            cargo            = COALESCE(EXCLUDED.cargo,            camp_prospecto.cargo),
            telefono         = COALESCE(EXCLUDED.telefono,         camp_prospecto.telefono),
            rubro            = COALESCE(EXCLUDED.rubro,            camp_prospecto.rubro),
            provincia        = COALESCE(EXCLUDED.provincia,        camp_prospecto.provincia),
            fuente           = EXCLUDED.fuente,
            actualizado_at   = EXCLUDED.actualizado_at
    """)

    BATCH = 500
    batch_params = []

    def _flush():
        nonlocal upserted
        if not batch_params:
            return
        try:
            db.session.execute(sql, batch_params)
            db.session.commit()
            upserted += len(batch_params)
        except Exception as exc:
            db.session.rollback()
            error_list.append(str(exc)[:120])

    for r in records:
        email = (r.get('email') or '').strip().lower()
        if not email or '@' not in email:
            skipped += 1
            continue

        def _str(v):
            v = (v or '').strip()
            return v if v else None

        batch_params.append({
            'email':           email,
            'ruc':             _str(r.get('ruc')),
            'razon_social':    _str(r.get('razon_social')),
            'nombre_contacto': _str(r.get('nombre_contacto')),
            'cargo':           _str(r.get('cargo')),
            'telefono':        _str(r.get('telefono')),
            'rubro':           _str(r.get('rubro')),
            'provincia':       _str(r.get('provincia')),
            'fuente':          _str(r.get('fuente')) or 'sheets_master',
            'actualizado_at':  now,
        })

        if len(batch_params) >= BATCH:
            _flush()
            batch_params.clear()

    _flush()
    return upserted, skipped, error_list


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_log_content(content, filename):
    """Parsea el contenido de un archivo .log de campana. Retorna lista de dicts."""
    proceso         = _proceso_from_name(filename)
    bandeja_default = _bandeja_from_name(filename)
    records = []
    seen    = set()   # dedup dentro del mismo archivo: (ts, email)

    for line in content.splitlines():
        ts = email = empresa = bandeja = resultado = None

        m = RE_PROSP.match(line)
        if m:
            ts, braw, resultado, email, empresa = m.groups()
            bandeja = _nb(braw)
        else:
            m = RE_150.match(line)
            if m:
                ts, braw, resultado, email, empresa = m.groups()
                bandeja = _nb(braw)
                empresa = empresa.strip() or None
            else:
                m = RE_NUEVOS.match(line)
                if m:
                    ts, bandeja, email = m.groups()
                    resultado = 'OK'
                else:
                    m = RE_PRECIOS.match(line)
                    if m:
                        ts, resultado, email, empresa = m.groups()
                        bandeja  = bandeja_default
                        empresa  = empresa.strip()
                    else:
                        m = RE_NUEVOS_OLD.match(line)
                        if m:
                            ts, resultado, email = m.groups()
                            bandeja = bandeja_default

        if not ts or not email:
            continue

        email = email.lower().rstrip(',')
        if '@' not in email:
            continue

        key = (ts, email)
        if key in seen:
            continue
        seen.add(key)

        records.append({
            'envio_hash':   _hash32(filename, ts, email),
            'email':        email,
            'empresa':      empresa.strip() if empresa else None,
            'bandeja':      bandeja,
            'proceso':      proceso,
            'enviado_at':   ts,
            'resultado_log': resultado or 'OK',
            'fuente_archivo': filename,
        })

    return records


def parse_bounce_content(content, filename):
    """
    Parsea el contenido de un limpiar_bandejas_*_resultado.json.
    Retorna lista de dicts de rebote.
    """
    try:
        d = json.loads(content)
    except Exception as exc:
        log.warning("camp_importer: parse_bounce_content JSON error: %s", exc)
        return []

    records = []
    for email, info in (d.get('bounces') or {}).items():
        if not isinstance(info, dict):
            continue
        el = email.lower()
        records.append({
            'rebote_hash':      _hash32(filename, el),
            'email':            el,
            'tipo':             info.get('tipo', 'hard'),
            'motivo':           info.get('motivo', ''),
            'detectado_at':     info.get('fecha'),
            'bandeja_detectora': info.get('cuenta'),
            'msg_id':           info.get('msg_id'),
            'fuente_archivo':   filename,
        })

    return records


# ── Insercion a DB ────────────────────────────────────────────────────────────

def _existing_hashes(db, table, hash_col, filename):
    """Devuelve el set de hashes ya presentes para este archivo."""
    try:
        rows = db.session.execute(
            db.text(f"SELECT {hash_col} FROM {table} WHERE fuente_archivo = :f"),
            {'f': filename}
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _insert_batch(db, table, cols, rows_params):
    """Inserta filas individuales; retorna (importados, duplicados, descartados)."""
    col_list   = ', '.join(cols)
    param_list = ', '.join(':' + c for c in cols)
    sql = db.text(f"INSERT INTO {table} ({col_list}) VALUES ({param_list})")

    importados = duplicados = descartados = 0
    discard_reasons = []

    for params in rows_params:
        try:
            db.session.execute(sql, params)
            importados += 1
        except Exception as exc:
            msg = str(exc).lower()
            if 'unique' in msg or 'duplicate' in msg:
                duplicados += 1
            else:
                descartados += 1
                if len(discard_reasons) < 5:
                    discard_reasons.append(str(exc)[:80])

    return importados, duplicados, descartados, discard_reasons


# ── Entrada directa (eventos JSON sin archivo) ────────────────────────────────

def import_eventos(eventos: list) -> tuple:
    """
    Inserta eventos de envío recibidos directamente (sin parsear archivos de log).
    Cada evento es un dict con campos:
        email, empresa, bandeja, proceso, enviado_at, resultado_log, fuente_archivo
    El hash se calcula igual que para logs: _hash32(fuente_archivo, enviado_at, email),
    garantizando idempotencia incluso si el mismo evento llega por ambas vías.

    Retorna (importados, duplicados, descartados, error_list).
    """
    from app.extensions import db
    from datetime import datetime

    if not eventos:
        return 0, 0, 0, []

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cols = ['envio_hash', 'email', 'empresa', 'bandeja', 'proceso',
            'enviado_at', 'resultado_log', 'fuente_archivo']

    rows = []
    for ev in eventos:
        email = (ev.get('email') or '').strip().lower()
        if not email or '@' not in email:
            continue
        ts     = (ev.get('enviado_at') or now_str).strip()
        fuente = (ev.get('fuente_archivo') or ev.get('proceso') or 'directo').strip()
        rows.append({
            'envio_hash':    _hash32(fuente, ts, email),
            'email':         email,
            'empresa':       (ev.get('empresa') or '').strip() or None,
            'bandeja':       (ev.get('bandeja') or '').strip() or None,
            'proceso':       (ev.get('proceso') or '').strip() or None,
            'enviado_at':    ts,
            'resultado_log': (ev.get('resultado_log') or 'OK').strip()[:10],
            'fuente_archivo': fuente,
        })

    if not rows:
        return 0, 0, len(eventos), ['Sin emails válidos']

    imp, dup, desc, errs = _insert_batch(db, 'camp_envio', cols, rows)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return 0, 0, len(rows), [str(exc)[:120]]
    return imp, dup, desc, errs


# ── Entrada principal ─────────────────────────────────────────────────────────

def import_file(filename, content):
    """
    Importa el contenido de un archivo (log .log o bounce .json) a la DB.
    Retorna un dict con: filename, tipo, parseados, importados, duplicados,
                         descartados, discard_reasons[].
    Idempotente: llamar dos veces con el mismo archivo produce los mismos
    registros en DB; la segunda vez todo cuenta como 'duplicado'.
    """
    from app.extensions import db

    # Tipo de archivo
    if filename.endswith('.json'):
        tipo    = 'rebotes'
        records = parse_bounce_content(content, filename)
        table   = 'camp_rebote'
        hcol    = 'rebote_hash'
        cols    = ['rebote_hash', 'email', 'tipo', 'motivo', 'detectado_at',
                   'bandeja_detectora', 'msg_id', 'fuente_archivo']
    else:
        tipo    = 'log_envio'
        records = parse_log_content(content, filename)
        table   = 'camp_envio'
        hcol    = 'envio_hash'
        cols    = ['envio_hash', 'email', 'empresa', 'bandeja', 'proceso',
                   'enviado_at', 'resultado_log', 'fuente_archivo']

    parseados = len(records)

    if not records:
        return {
            'filename': filename, 'tipo': tipo,
            'parseados': 0, 'importados': 0, 'duplicados': 0,
            'descartados': 0, 'discard_reasons': ['Sin registros parseados'],
        }

    # Pre-filtrar duplicados por hash (lectura anticipada)
    existing = _existing_hashes(db, table, hcol, filename)
    nuevos   = [r for r in records if r[hcol] not in existing]
    dupes_pre = parseados - len(nuevos)

    importados = duplicados_db = descartados = 0
    discard_reasons = []

    if nuevos:
        importados, duplicados_db, descartados, discard_reasons = _insert_batch(db, table, cols, nuevos)
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            return {
                'filename': filename, 'tipo': tipo, 'parseados': parseados,
                'importados': 0, 'duplicados': dupes_pre, 'descartados': len(nuevos),
                'discard_reasons': [str(exc)[:120]],
            }

    duplicados = dupes_pre + duplicados_db

    # Registro de auditoria (importado_at en hora local Lima)
    try:
        db.session.execute(db.text("""
            INSERT INTO camp_importacion
                (filename, tipo, importado_at, total_parseados, total_importados,
                 total_duplicados, total_descartados, detalle)
            VALUES
                (:fn, :tipo, :ts, :tp, :ti, :td, :tdc, :det)
        """), {
            'fn': filename, 'tipo': tipo,
            'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tp': parseados,
            'ti': importados, 'td': duplicados, 'tdc': descartados,
            'det': json.dumps({'discard_reasons': discard_reasons}),
        })
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        log.warning("camp_importer: audit log falló: %s", exc)

    log.info("camp_importer: %s → %d importados / %d dupes / %d desc",
             filename, importados, duplicados, descartados)

    return {
        'filename': filename, 'tipo': tipo, 'parseados': parseados,
        'importados': importados, 'duplicados': duplicados,
        'descartados': descartados, 'discard_reasons': discard_reasons,
    }

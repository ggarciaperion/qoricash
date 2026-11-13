"""
prospeccion_repo.py — Repositorio Flask para datos del ecosistema de prospección

Lee desde PostgreSQL compartido (las tablas worker: ec_prospectos, agent_runs,
agent_heartbeat, bandeja_estado, runtime_config, metrics, alerts_log, lead_pipeline,
ec_lotes, ec_lote_items).

Reemplaza prospeccion_connector.py (que leía SQLite directamente).
Mantiene la misma interfaz para no romper agentes.py ni mission_control.html.

Fallback: si las tablas worker no existen aún (pre-deploy), retorna datos vacíos
sin lanzar excepción — mismo comportamiento que el connector SQLite offline.

Seguridad:
  - Solo lectura (SELECT). Las escrituras son responsabilidad del worker.
  - No expone credenciales, tokens ni secrets.
  - Todas las queries parametrizadas.

Contrato de semántica canónico (ec_lote_items — ecosistema_db.py T1):
  estado_envio='pendiente'     → seleccionado en lote, aún no intentado
  estado_envio='en_proceso'    → lock tomado, Gmail API no llamada
  estado_envio='en_envio'      → Gmail API en curso (in-flight)
  estado_envio='enviado'       → Gmail API 2xx (proveedor) — no garantiza entrega
  estado_envio='conciliacion'  → resultado incierto; NUNCA reintento automático
  estado_envio='omitido'       → saltado (rate limit, dry_run, etc.)
  estado_envio='rebotado'      → rebote confirmado
  estado_envio='error'         → fallo definitivo, no reintentable
  rebote_motivo IS NOT NULL    → rebote posterior; estado_envio se conserva
  No existe columna dry_run en ec_lotes ni en ec_lote_items.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
import zoneinfo as _zi

from app.extensions import db

log = logging.getLogger(__name__)

# Tiempo máximo sin heartbeat antes de considerar un agente offline
_OFFLINE_THRESHOLD_MIN = 10

# Tiempo máximo sin heartbeat del orchestrator para considerar el worker offline
_WORKER_OFFLINE_THRESHOLD_MIN = 5


def _exec(sql: str, params: tuple = ()) -> list:
    """Ejecuta un SELECT crudo en PG. Retorna lista de Row-like objects."""
    try:
        result = db.session.execute(db.text(sql), dict(enumerate(params)) if params else {})
        return result.fetchall()
    except Exception as e:
        # Puede fallar si las tablas no existen todavía (pre-deploy)
        log.debug(f"[prospeccion_repo] query falló (tablas no disponibles?): {e}")
        return []


def _exec_one(sql: str, params: tuple = ()):
    """Ejecuta un SELECT y retorna la primera fila, o None."""
    rows = _exec(sql, params)
    return rows[0] if rows else None


def _row(sql: str, params: tuple = ()) -> dict:
    """Ejecuta SELECT y retorna la primera fila como dict, o {}."""
    try:
        result = db.session.execute(db.text(sql), _params(params))
        row = result.fetchone()
        return dict(row._mapping) if row else {}
    except Exception as e:
        log.debug(f"[prospeccion_repo] _row falló: {e}")
        return {}


def _rows(sql: str, params: tuple = ()) -> list:
    """Ejecuta SELECT y retorna lista de dicts."""
    try:
        result = db.session.execute(db.text(sql), _params(params))
        return [dict(r._mapping) for r in result.fetchall()]
    except Exception as e:
        log.debug(f"[prospeccion_repo] _rows falló: {e}")
        return []


def _scalar(sql: str, params: tuple = (), default=None):
    """Ejecuta SELECT y retorna el primer valor de la primera fila."""
    try:
        result = db.session.execute(db.text(sql), _params(params))
        row = result.fetchone()
        return row[0] if row else default
    except Exception as e:
        log.debug(f"[prospeccion_repo] _scalar falló: {e}")
        return default


def _params(params: tuple) -> dict:
    """Convierte tuple de params a dict numerado para SQLAlchemy text()."""
    return {str(i): v for i, v in enumerate(params)}


def _today_lima() -> str:
    """Retorna la fecha de hoy en America/Lima como string YYYY-MM-DD."""
    try:
        lima = _zi.ZoneInfo('America/Lima')
        return datetime.now(lima).date().isoformat()
    except Exception:
        return datetime.utcnow().date().isoformat()


# ── Master stats ───────────────────────────────────────────────────────────────

def get_master_stats() -> dict:
    """
    Estadísticas de ec_prospectos desde PostgreSQL.
    Retorna dict vacío con disponible=False si las tablas no están disponibles.
    """
    try:
        stats = _row("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN estado_email = 'valido' THEN 1 ELSE 0 END) AS validos,
                SUM(CASE WHEN estado_email = 'sin_validar' THEN 1 ELSE 0 END) AS sin_validar,
                SUM(CASE WHEN estado_email = 'correo_rebotado' THEN 1 ELSE 0 END) AS rebotados,
                SUM(CASE WHEN estado_com = 'cliente' THEN 1 ELSE 0 END) AS clientes,
                SUM(CASE WHEN prioridad = 'ALTA' THEN 1 ELSE 0 END) AS prioridad_alta
            FROM ec_prospectos
        """)

        if not stats or stats.get('total') is None:
            return {'disponible': False}

        # ready_for_outreach: valido + no bloqueado comercialmente
        _stop = (
            'no_contactar', 'correo_rebotado', 'cliente', 'interesado',
            'solicita_cotizacion', 'solicita_informacion', 'solicita_llamada',
            'solicita_whatsapp', 'no_interesado', 'persona_incorrecta',
            'referido', 'rebotado',
        )
        stop_list = ', '.join(f"'{s}'" for s in _stop)
        ready = _scalar(
            f"SELECT COUNT(*) FROM ec_prospectos "
            f"WHERE estado_email = 'valido' AND estado_com NOT IN ({stop_list})"
        ) or 0

        last_sync = _scalar(
            "SELECT value FROM sync_state WHERE key = 'last_full_sync'"
        )

        return {
            'disponible':         True,
            'total':              int(stats.get('total', 0) or 0),
            'validos':            int(stats.get('validos', 0) or 0),
            'sin_validar':        int(stats.get('sin_validar', 0) or 0),
            'rebotados':          int(stats.get('rebotados', 0) or 0),
            'clientes':           int(stats.get('clientes', 0) or 0),
            'prioridad_alta':     int(stats.get('prioridad_alta', 0) or 0),
            'ready_for_outreach': int(ready),
            'requires_validation': int(stats.get('sin_validar', 0) or 0),
            'last_full_sync':     last_sync,
        }

    except Exception as e:
        log.warning(f"[prospeccion_repo] get_master_stats falló: {e}")
        return {'disponible': False, 'error': str(e)}


# ── Agent runs ─────────────────────────────────────────────────────────────────

def get_agent_runs(limit: int = 20) -> list:
    """Últimas ejecuciones de agentes desde agent_runs."""
    return _rows("""
        SELECT agent, status, started_at, finished_at,
               records_in, records_out, actions_taken, error_msg, triggered_by
        FROM agent_runs
        ORDER BY started_at DESC
        LIMIT :0
    """, (limit,))


# ── Heartbeat / liveness ───────────────────────────────────────────────────────

def get_agent_heartbeats() -> list:
    """
    Estado actual de cada agente desde agent_heartbeat.
    Enriquece con un campo 'is_offline' si last_seen > umbral.
    """
    beats = _rows("""
        SELECT agent, last_seen, status, current_run_id, hostname, updated_at
        FROM agent_heartbeat
        ORDER BY agent
    """)

    now = datetime.utcnow()
    threshold = timedelta(minutes=_OFFLINE_THRESHOLD_MIN)

    for b in beats:
        ls = b.get('last_seen')
        if ls:
            if hasattr(ls, 'replace'):
                age = now - ls.replace(tzinfo=None)
            else:
                age = timedelta(seconds=99999)
            b['is_offline'] = age > threshold
            b['age_seconds'] = int(age.total_seconds())
        else:
            b['is_offline'] = True
            b['age_seconds'] = None

    return beats


def get_scheduler_status() -> dict:
    """
    Estado del scheduler_lotes (proceso operativo acordado).

    threshold: 5 min — el scheduler hace heartbeat cada 60 s.
    Sin señal en 5 min = offline.
    Nunca usa orchestrator ni motor_local.
    """
    _THRESHOLD_MIN = 5  # 5 min (scheduler heartbeat cada 60 s)

    beat = _row("""
        SELECT last_seen, status, hostname
        FROM agent_heartbeat
        WHERE agent = 'scheduler_lotes'
    """)

    if not beat:
        return {'online': False, 'last_seen': None, 'status': 'sin_datos', 'edad_min': None}

    ls = beat.get('last_seen')
    if ls:
        # Convertir a UTC-aware antes de calcular la diferencia.
        # ls puede ser naive (UTC asumido) o aware con offset.
        # ls.replace(tzinfo=None) quitaría el offset sin convertir, inflando
        # la edad en la diferencia UTC/Lima (~5h = 300 min).
        try:
            if hasattr(ls, 'tzinfo') and ls.tzinfo is not None:
                # aware → convertir a UTC naive
                ls_utc = ls.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                ls_utc = ls  # ya naive, asumir UTC
            age = datetime.utcnow() - ls_utc
        except Exception:
            age = timedelta(seconds=99999)
        online   = age < timedelta(minutes=_THRESHOLD_MIN)
        edad_min = int(age.total_seconds() / 60)
    else:
        online   = False
        edad_min = None

    return {
        'online':    online,
        'status':    beat.get('status', 'offline'),
        'last_seen': str(ls) if ls else None,
        'edad_min':  edad_min,
        'hostname':  beat.get('hostname'),
    }


def get_worker_status() -> dict:
    """
    Estado del orchestrator/worker.
    offline=True si el heartbeat del orchestrator es más antiguo que el umbral.
    """
    beat = _row("""
        SELECT last_seen, status, hostname, pid
        FROM agent_heartbeat
        WHERE agent = 'orchestrator'
    """)

    if not beat:
        return {'online': False, 'last_seen': None, 'hostname': None}

    ls = beat.get('last_seen')
    if ls:
        if hasattr(ls, 'replace'):
            age = datetime.utcnow() - ls.replace(tzinfo=None)
        else:
            age = timedelta(seconds=99999)
        online = age < timedelta(minutes=_WORKER_OFFLINE_THRESHOLD_MIN)
    else:
        online = False

    return {
        'online':   online,
        'status':   beat.get('status', 'offline'),
        'last_seen': str(ls) if ls else None,
        'hostname': beat.get('hostname'),
        'pid':      beat.get('pid'),
    }


# ── Runtime config ─────────────────────────────────────────────────────────────

def get_runtime_config() -> dict:
    """Lee todos los valores de runtime_config."""
    rows = _rows("SELECT key, value FROM runtime_config")
    return {r['key']: r['value'] for r in rows}


# ── TC helpers ─────────────────────────────────────────────────────────────────

def get_tc_status() -> dict:
    """Estado del tipo de cambio desde runtime_config."""
    config = get_runtime_config()
    tc_compra = config.get('tc_compra', '')
    tc_venta  = config.get('tc_venta', '')
    tc_ts     = config.get('tc_updated_at', '')

    fresco    = False
    age_min   = None

    if tc_ts:
        try:
            ts  = datetime.fromisoformat(tc_ts)
            age = datetime.now() - ts
            age_min = int(age.total_seconds() / 60)
            fresco  = age < timedelta(hours=3)
        except Exception:
            pass

    return {
        'compra':    tc_compra,
        'venta':     tc_venta,
        'updated_at': tc_ts,
        'fresco':    fresco,
        'age_min':   age_min,
    }


# ── Bandejas ───────────────────────────────────────────────────────────────────

def get_bandeja_estado() -> list:
    """Estado actual de las 3 bandejas Gmail."""
    rows = _rows("""
        SELECT bandeja, enviados_hoy, bounce_count_24h, total_24h,
               pausada_hasta, ultimo_update
        FROM bandeja_estado
        ORDER BY bandeja
    """)
    # Enriquecer con is_pausada
    now = datetime.utcnow()
    for r in rows:
        ph = r.get('pausada_hasta')
        if ph:
            ph_dt = ph.replace(tzinfo=None) if hasattr(ph, 'replace') else None
            r['is_pausada'] = bool(ph_dt and now < ph_dt)
        else:
            r['is_pausada'] = False
    return rows


# ── Outreach today ─────────────────────────────────────────────────────────────

def get_outreach_stats_today() -> dict:
    """Emails enviados hoy (00:00 Lima → ahora)."""
    row = _row("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) AS enviados,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS fallidos
        FROM outreach_attempt
        WHERE DATE(reserved_at AT TIME ZONE 'America/Lima') = CURRENT_DATE
    """)
    return {
        'total':    int(row.get('total', 0) or 0),
        'enviados': int(row.get('enviados', 0) or 0),
        'fallidos': int(row.get('fallidos', 0) or 0),
    }


# ── Alerts ────────────────────────────────────────────────────────────────────

def get_alerts(limit: int = 20) -> list:
    """Alertas recientes del worker."""
    return _rows("""
        SELECT level, component, message, detail, created_at
        FROM alerts_log
        ORDER BY created_at DESC
        LIMIT :0
    """, (limit,))


# ── Lead pipeline ─────────────────────────────────────────────────────────────

def get_lead_pipeline_stats() -> dict:
    """Resumen del pipeline de leads pendientes de pasar al CRM."""
    row = _row("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN notificado = 0 THEN 1 ELSE 0 END) AS pendientes,
            SUM(CASE WHEN webhook_ok = 1 THEN 1 ELSE 0 END) AS en_crm
        FROM lead_pipeline
    """)
    return {
        'total':     int(row.get('total', 0) or 0),
        'pendientes': int(row.get('pendientes', 0) or 0),
        'en_crm':    int(row.get('en_crm', 0) or 0),
    }


# ── Agent Guide Status ─────────────────────────────────────────────────────────

def get_agent_guide_status() -> dict:
    """
    Contadores en tiempo real para la vista 'Agentes de Guía'.

    Lee exclusivamente desde las tablas del worker (ec_prospectos, agent_runs,
    runtime_config). No toca Google Drive, no toca tablas financieras ni
    operaciones de cambio de divisas.

    Retorna:
        leads_nuevo             — Prospectos válidos sin contacto previo
        leads_enviados_paso1    — Primer contacto completado (presentado)
        leads_enviados_paso2    — Segunda etapa (precio enviado / seguimiento)
        leads_interesado        — Respuestas positivas y escalaciones activas
        last_activity_timestamp — ISO timestamp de la última ejecución exitosa
        worker_online           — True si el orchestrator tiene heartbeat reciente
        disponible              — False si las tablas del worker no están presentes
    """
    # ── Contadores de estado en un solo scan ─────────────────────────────────
    counters = _row("""
        SELECT
            SUM(CASE WHEN estado_com = 'nuevo'
                      AND estado_email = 'valido'
                 THEN 1 ELSE 0 END)                             AS leads_nuevo,

            SUM(CASE WHEN estado_com IN ('presentado', 'P1', 'seguimiento')
                 THEN 1 ELSE 0 END)                             AS leads_enviados_paso1,

            SUM(CASE WHEN estado_com IN (
                    'precio_enviado', 'P2', 'seguimiento_precio'
                ) THEN 1 ELSE 0 END)                            AS leads_enviados_paso2,

            SUM(CASE WHEN estado_com IN (
                    'interesado',
                    'solicita_cotizacion',
                    'solicita_informacion',
                    'solicita_llamada',
                    'solicita_whatsapp',
                    'negociando',
                    'negociacion',
                    'P3'
                ) THEN 1 ELSE 0 END)                            AS leads_interesado
        FROM ec_prospectos
    """)

    if not counters or counters.get('leads_nuevo') is None:
        return {
            'disponible':              False,
            'leads_nuevo':             0,
            'leads_enviados_paso1':    0,
            'leads_enviados_paso2':    0,
            'leads_interesado':        0,
            'last_activity_timestamp': None,
            'worker_online':           False,
        }

    # ── Timestamp de última actividad del worker ──────────────────────────────
    last_ts = _scalar("""
        SELECT MAX(COALESCE(finished_at, started_at))
        FROM agent_runs
        WHERE status IN ('ok', 'partial')
    """)

    # ── Estado del worker (heartbeat) ─────────────────────────────────────────
    worker = get_worker_status()

    return {
        'disponible':              True,
        'leads_nuevo':             int(counters.get('leads_nuevo')          or 0),
        'leads_enviados_paso1':    int(counters.get('leads_enviados_paso1') or 0),
        'leads_enviados_paso2':    int(counters.get('leads_enviados_paso2') or 0),
        'leads_interesado':        int(counters.get('leads_interesado')     or 0),
        'last_activity_timestamp': last_ts.isoformat() if last_ts and hasattr(last_ts, 'isoformat') else str(last_ts) if last_ts else None,
        'worker_online':           worker.get('online', False),
    }


# ── Pipeline card stats — ec_lotes / ec_lote_items ────────────────────────────
#
# Contrato de semántica canónico (ecosistema_db.py / ec04_lotes_schema_fix.py):
#   estado_envio IN ('pendiente','en_proceso','en_envio','enviado',
#                    'conciliacion','omitido','rebotado','error')
#   rebote_motivo IS NOT NULL → rebote posterior; historial de envío se conserva
#
# ec_lote_items.lote_id es BIGINT FK → ec_lotes.id (tanto en schema original
# como después de ec04). Todas las queries sobre items usan ese FK entero.
#
# ec_lotes.dry_run = TRUE  → lote fue simulación; nunca contar enviados como reales.
# ec_lotes.dry_run = FALSE → lote real; enviados = correos aceptados por proveedor.
# (dry_run existe desde el schema original ec02; ec04 lo agrega si falta.)
#
# Columnas que solo existen después de ec04 (bandeja_asignada, estado_validacion,
# rebote_motivo, etc.) se consultan con COALESCE / fallback a columna original
# para ser compatibles con DBs donde ec04 aún no fue aplicado.


def _lotes_hoy() -> list[dict]:
    """
    Lotes operativos de hoy (America/Lima), es_prueba=0.
    Cada dict incluye 'id' (BIGINT, FK para items) y 'lote_id' (TEXT).

    Excluye lotes de prueba (es_prueba != 0). Para acceso a lotes de prueba
    usar get_lotes_disponibles(fecha) que retorna todos sin filtro.

    Detecta el schema disponible y ejecuta la query apropiada.
    - Schema post-ec04 (producción): columnas viejas + nuevas coexisten.
    - Schema ec02 puro (instalación fresca): solo columnas canónicas.
    """
    hoy = _today_lima()

    # Detectar si existen las columnas del schema original (pre-ec04)
    # Una sola consulta a information_schema determina la estrategia.
    _tiene_schema_viejo = False
    try:
        result = db.session.execute(db.text("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name='ec_lotes' AND column_name='creado_at'
        """))
        _tiene_schema_viejo = (result.scalar() or 0) > 0
    except Exception:
        pass

    if _tiene_schema_viejo:
        # Schema post-ec04: usar COALESCE con columnas viejas y nuevas
        return _rows("""
            SELECT id,
                   COALESCE(lote_id, 'LOT-' || id::text)          AS lote_id,
                   COALESCE(fuente_sheet_id, fuente, '—')           AS fuente_activa,
                   fuente_tab,
                   COALESCE(fecha_creacion::text, creado_at::text)  AS fecha_ts,
                   estado,
                   dry_run,
                   COALESCE(total_elegibles, total_items, 0)        AS total_elegibles,
                   COALESCE(total_enviados,  items_aceptados, 0)    AS total_enviados,
                   COALESCE(total_candidatos, total_items, 0)       AS total_candidatos,
                   COALESCE(es_prueba, 0)                           AS es_prueba
            FROM ec_lotes
            WHERE DATE(
                COALESCE(fecha_creacion, creado_at)
                AT TIME ZONE 'America/Lima'
            ) = :0
              AND COALESCE(es_prueba, 0) = 0
            ORDER BY id
        """, (hoy,))
    else:
        # Schema ec02 puro (instalación fresca): solo columnas canónicas
        return _rows("""
            SELECT id,
                   COALESCE(lote_id, 'LOT-' || id::text) AS lote_id,
                   COALESCE(fuente_sheet_id, '—')          AS fuente_activa,
                   fuente_tab,
                   fecha_creacion::text                     AS fecha_ts,
                   estado,
                   dry_run,
                   total_elegibles,
                   total_enviados,
                   total_candidatos,
                   COALESCE(es_prueba, 0)                  AS es_prueba
            FROM ec_lotes
            WHERE DATE(fecha_creacion AT TIME ZONE 'America/Lima') = :0
              AND COALESCE(es_prueba, 0) = 0
            ORDER BY id
        """, (hoy,))


def _lote_op_activo() -> list[dict]:
    """
    Lote operativo más reciente con items pendientes (cualquier fecha).

    Criterio espejo del motor: estado IN ('pendiente','en_progreso'), es_prueba=0,
    y al menos un item seleccionado aún pendiente de envío.
    Usado como fallback cuando no hay lotes operativos hoy (America/Lima).
    Retorna lista de 0 ó 1 elemento con el mismo formato que _lotes_hoy().
    """
    _tiene_schema_viejo = False
    try:
        result = db.session.execute(db.text("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name='ec_lotes' AND column_name='creado_at'
        """))
        _tiene_schema_viejo = (result.scalar() or 0) > 0
    except Exception:
        pass

    if _tiene_schema_viejo:
        return _rows("""
            SELECT l.id,
                   COALESCE(l.lote_id, 'LOT-' || l.id::text)        AS lote_id,
                   COALESCE(l.fuente_sheet_id, l.fuente, '—')        AS fuente_activa,
                   l.fuente_tab,
                   COALESCE(l.fecha_creacion, l.creado_at)::text     AS fecha_ts,
                   l.estado,
                   l.dry_run,
                   COALESCE(l.total_elegibles, l.total_items, 0)     AS total_elegibles,
                   COALESCE(l.total_enviados,  l.items_aceptados, 0) AS total_enviados,
                   COALESCE(l.total_candidatos, l.total_items, 0)    AS total_candidatos,
                   COALESCE(l.es_prueba, 0)                          AS es_prueba
            FROM ec_lotes l
            WHERE l.estado IN ('pendiente','en_progreso')
              AND COALESCE(l.es_prueba, 0) = 0
              AND EXISTS (
                  SELECT 1 FROM ec_lote_items li
                  WHERE li.lote_id = l.id
                    AND COALESCE(li.bandeja_asignada, li.bandeja) IS NOT NULL
                    AND li.estado_envio = 'pendiente'
              )
            ORDER BY COALESCE(l.fecha_creacion, l.creado_at) DESC
            LIMIT 1
        """)
    else:
        # Schema ec02 puro: bandeja_asignada es la única columna de bandeja
        # (bandeja no existe — COALESCE causaría error silencioso en _rows)
        return _rows("""
            SELECT l.id,
                   COALESCE(l.lote_id, 'LOT-' || l.id::text) AS lote_id,
                   COALESCE(l.fuente_sheet_id, '—')            AS fuente_activa,
                   l.fuente_tab,
                   l.fecha_creacion::text                       AS fecha_ts,
                   l.estado,
                   l.dry_run,
                   l.total_elegibles,
                   l.total_enviados,
                   l.total_candidatos,
                   COALESCE(l.es_prueba, 0)                   AS es_prueba
            FROM ec_lotes l
            WHERE l.estado IN ('pendiente','en_progreso')
              AND COALESCE(l.es_prueba, 0) = 0
              AND EXISTS (
                  SELECT 1 FROM ec_lote_items li
                  WHERE li.lote_id = l.id
                    AND li.bandeja_asignada IS NOT NULL
                    AND li.estado_envio = 'pendiente'
              )
            ORDER BY l.fecha_creacion DESC
            LIMIT 1
        """)


def get_pipeline_card_stats() -> dict:
    """
    Datos para las 5 cards del panel Agentes IA.

    Cards 1-3 (selección/validación/asignación): usan el lote operativo activo.
      Si hay lotes operativos hoy → se usan.
      Si no hay lotes hoy → se usa el más reciente con pendientes (_lote_op_activo).
    Card 4 (envíos de hoy): siempre scoped a la fecha actual Lima.
    Card 5 (rebotes): acumulado histórico + detectados en lotes de hoy.

    Fallback seguro: si ec_lotes no existe aún, retorna disponible=False.
    Compatible con schema original (ec02) y schema corregido (post-ec04).
    """
    hoy = _today_lima()

    lotes_hoy = _lotes_hoy()
    # Lotes operativos de hoy (excluir pruebas) — para envíos/rebotes de HOY
    lotes_op_hoy = [l for l in lotes_hoy if not l.get('es_prueba')]

    # Lote operativo activo para cards 1-3 (sel/val/asig):
    # Primero hoy; si no hay, el más reciente con pendientes (cualquier fecha).
    if lotes_op_hoy:
        lotes_lote = lotes_op_hoy
        lote_es_hoy = True
    else:
        lotes_lote = _lote_op_activo()
        lote_es_hoy = False

    ids_lote = [l['id'] for l in lotes_lote]       # sel/val/asig

    # Detectar si ec_lote_items tiene columnas del schema original (pre-ec02).
    # Schema ec02 puro solo tiene bandeja_asignada / estado_validacion / fecha_envio.
    # Referenciar columnas viejas inexistentes causa error silencioso en _rows/_row.
    _tiene_schema_items_viejo = (_scalar("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name='ec_lote_items' AND column_name='bandeja'
    """) or 0) > 0
    # Expresión de bandeja: original tiene 'bandeja'; ec02 puro solo 'bandeja_asignada'
    _bq = "COALESCE(bandeja_asignada, bandeja)" if _tiene_schema_items_viejo else "bandeja_asignada"
    # Expresión de validación: original tiene 'estado_email'; ec02 puro solo 'estado_validacion'
    _vq = "COALESCE(estado_validacion, estado_email,'sin_validar')" if _tiene_schema_items_viejo else "COALESCE(estado_validacion,'sin_validar')"
    # Expresión de fecha envío: original tiene 'enviado_at'; ec02 puro solo 'fecha_envio'
    _eq = "COALESCE(li.fecha_envio, li.enviado_at)" if _tiene_schema_items_viejo else "li.fecha_envio"

    if ids_lote:
        ids_lote_sql = ','.join(str(i) for i in ids_lote)  # safe: integers from DB

        # Fuente(s) del lote operativo activo
        fuentes = [l['fuente_activa'] for l in lotes_lote if l.get('fuente_activa') and l['fuente_activa'] != '—']
        fuentes_unicas = list(dict.fromkeys(fuentes))
        tabs = [l.get('fuente_tab') or '' for l in lotes_lote if l.get('fuente_activa') and l['fuente_activa'] != '—']
        tabs_unicas = list(dict.fromkeys(t for t in tabs if t))
        fuente_activa = (
            fuentes_unicas[0]          if len(fuentes_unicas) == 1
            else ', '.join(fuentes_unicas) if fuentes_unicas
            else 'pendiente de conectar'
        )
        fuente_tab = tabs_unicas[0] if len(tabs_unicas) == 1 else ''
        lote_dry_run = any(l.get('dry_run') for l in lotes_lote)

        # ── 1. Selección ──────────────────────────────────────────────────────
        # COALESCE: usa estado_seleccion (post-ec04) o default 'candidato'
        # seleccionados = items asignados a una bandeja (bandeja_asignada IS NOT NULL)
        # Estos son los destinatarios operativos del lote, independientemente de
        # su estado_envio actual (pendiente, enviado, etc.).
        sel = _row(f"""
            SELECT
                COUNT(*)                                                           AS total,
                COUNT(*) FILTER (WHERE COALESCE(estado_seleccion,'candidato')
                                       = 'elegible')                               AS elegibles,
                COUNT(*) FILTER (WHERE COALESCE(estado_seleccion,'candidato')
                                       = 'excluido')                               AS excluidos,
                COUNT(*) FILTER (WHERE COALESCE(estado_seleccion,'candidato')
                                       = 'candidato')                              AS candidatos,
                COUNT(*) FILTER (WHERE estado_envio = 'pendiente'
                                    OR (estado_envio = 'en_lote'
                                        AND estado_envio IS NOT NULL))             AS pendientes,
                COUNT(*) FILTER (WHERE {_bq}
                                       IS NOT NULL)                                AS seleccionados
            FROM ec_lote_items
            WHERE lote_id IN ({ids_lote_sql})
        """)

        # ── 2. Validación ─────────────────────────────────────────────────────
        # COALESCE: estado_validacion (post-ec04) o estado_email (original)
        # Scoped a los seleccionados (bandeja_asignada IS NOT NULL) — 300 reales.
        # El historial completo (2 000) queda disponible en la vista "Ver todos".
        val = _row(f"""
            SELECT
                COUNT(*) FILTER (WHERE {_vq} = 'valido')          AS validos,
                COUNT(*) FILTER (WHERE {_vq} = 'sin_validar')     AS sin_validar,
                COUNT(*) FILTER (WHERE {_vq} = 'no_verificado')   AS no_verificado,
                COUNT(*) FILTER (WHERE {_vq} = 'riesgo')          AS riesgo,
                COUNT(*) FILTER (WHERE {_vq} IN ('invalido','INVALIDO')) AS invalidos
            FROM ec_lote_items
            WHERE lote_id IN ({ids_lote_sql})
              AND {_bq} IS NOT NULL
        """)

        # ── 3. Asignación — distribución por bandeja ──────────────────────────
        # _bq: 'bandeja_asignada' (ec02 puro) o 'COALESCE(bandeja_asignada, bandeja)'
        band_rows = _rows(f"""
            SELECT {_bq} AS bandeja,
                   COUNT(*) AS asignados
            FROM ec_lote_items
            WHERE lote_id IN ({ids_lote_sql})
              AND {_bq} IS NOT NULL
            GROUP BY {_bq}
            ORDER BY 1
        """)

        # ── 4. Envíos de hoy ──────────────────────────────────────────────────
        # Criterio: fecha_envio (o enviado_at) en Lima = hoy.
        # Independiente del lote al que pertenece el item — cubre lotes de días
        # anteriores cuyos envíos ocurren hoy.
        # Solo cuentan como 'enviados reales' los de lotes con dry_run=FALSE.
        # ── 4. Envíos de hoy ──────────────────────────────────────────────────
        # Criterio: fecha_envio (o enviado_at) en Lima = hoy. Sin filtro por lote
        # — cubre lotes de días anteriores cuyos envíos ocurren hoy.
        # "Enviados" = items con fecha_envio set + dry_run=FALSE, independiente de
        # si el estado_envio fue luego marcado como 'rebotado'. El envío ocurrió.
        env = _row(f"""
            SELECT
                COUNT(*) FILTER (WHERE DATE({_eq} AT TIME ZONE 'America/Lima') = :0
                                   AND {_eq} IS NOT NULL
                                   AND l.dry_run = FALSE)                               AS enviados,
                COUNT(*) FILTER (WHERE DATE({_eq} AT TIME ZONE 'America/Lima') = :0
                                   AND {_eq} IS NOT NULL
                                   AND l.dry_run = TRUE)                                AS simulados,
                COUNT(*) FILTER (WHERE DATE({_eq} AT TIME ZONE 'America/Lima') = :0
                                   AND li.estado_envio
                                       IN ('en_proceso','en_envio','reservado'))        AS en_proceso,
                COUNT(*) FILTER (WHERE DATE({_eq} AT TIME ZONE 'America/Lima') = :0
                                   AND li.estado_envio
                                       IN ('conciliacion','incierto'))                  AS conciliacion,
                COUNT(*) FILTER (WHERE DATE({_eq} AT TIME ZONE 'America/Lima') = :0
                                   AND li.estado_envio = 'omitido')                    AS omitidos,
                COUNT(*) FILTER (WHERE DATE({_eq} AT TIME ZONE 'America/Lima') = :0
                                   AND li.estado_envio
                                       IN ('error','fallido','reintentable'))           AS errores
            FROM ec_lote_items li
            JOIN ec_lotes l ON l.id = li.lote_id
            WHERE COALESCE(l.es_prueba, 0) = 0
        """, (hoy,))

        # ── 5. Rebotes de hoy ─────────────────────────────────────────────────
        # Criterio: rebote_detectado_en en Lima = hoy, es_prueba=0.
        # Registros sin rebote_detectado_en (NULL) = desconocido; no se inventan fechas.
        reb_hoy = _scalar("""
            SELECT COUNT(*) FROM ec_lote_items li
            JOIN ec_lotes l ON l.id = li.lote_id
            WHERE li.rebote_detectado_en IS NOT NULL
              AND DATE(li.rebote_detectado_en AT TIME ZONE 'America/Lima') = :0
              AND COALESCE(l.es_prueba, 0) = 0
        """, (hoy,)) or 0

    else:
        sel           = {}
        val           = {}
        band_rows     = []
        env           = {}
        reb_hoy       = 0
        fuente_activa = 'pendiente de conectar'
        fuente_tab    = ''
        lote_dry_run  = False

    # Rebotes históricos acumulados — excluye lotes de prueba
    reb_total = _scalar("""
        SELECT COUNT(*) FROM ec_lote_items li
        JOIN ec_lotes l ON l.id = li.lote_id
        WHERE COALESCE(li.rebote_motivo, li.rebote_tipo) IS NOT NULL
          AND COALESCE(l.es_prueba, 0) = 0
    """) or 0

    # Identificador del lote operativo activo (para enlace de prospectos)
    lote_op = None
    if lotes_lote:
        l0 = lotes_lote[0]
        lote_op = {
            'lote_id': l0.get('lote_id'),
            'fecha':   (l0.get('fecha_ts') or '')[:10],
            'es_hoy':  lote_es_hoy,
        }

    return {
        'disponible':  bool(ids_lote),
        'lotes_hoy':   len(lotes_hoy),
        'fecha':       hoy,
        'dry_run':     lote_dry_run,
        'lote_op':     lote_op,

        'seleccion': {
            'total':         int((sel or {}).get('total', 0) or 0),
            'elegibles':     int((sel or {}).get('elegibles', 0) or 0),
            'excluidos':     int((sel or {}).get('excluidos', 0) or 0),
            'candidatos':    int((sel or {}).get('candidatos', 0) or 0),
            'pendientes':    int((sel or {}).get('pendientes', 0) or 0),
            # seleccionados = asignados a bandeja (operativos del lote).
            # Estable: no cambia cuando el estado_envio avanza de pendiente → enviado.
            'seleccionados': int((sel or {}).get('seleccionados', 0) or 0),
            'fuente_activa': fuente_activa,
            'fuente_tab':    fuente_tab,
        },
        'validacion': {
            'validos':       int((val or {}).get('validos', 0) or 0),
            'sin_validar':   int((val or {}).get('sin_validar', 0) or 0),
            'no_verificado': int((val or {}).get('no_verificado', 0) or 0),
            'riesgo':        int((val or {}).get('riesgo', 0) or 0),
            'invalidos':     int((val or {}).get('invalidos', 0) or 0),
        },
        'asignacion': {
            'bandejas': [
                {'bandeja': r['bandeja'], 'asignados': int(r['asignados'] or 0)}
                for r in band_rows
            ],
            'bandeja_estado': get_bandeja_estado(),
        },
        'envios': {
            # enviados/simulados/etc. = eventos con fecha_envio (Lima) = hoy
            # (incluye items de lotes de días anteriores enviados hoy)
            'total':           int((env or {}).get('intentados', 0) or 0),
            'enviados':        int((env or {}).get('enviados', 0) or 0),
            'simulados':       int((env or {}).get('simulados', 0) or 0),
            'en_proceso':      int((env or {}).get('en_proceso', 0) or 0),
            'conciliacion':    int((env or {}).get('conciliacion', 0) or 0),
            'omitidos':        int((env or {}).get('omitidos', 0) or 0),
            'errores':         int((env or {}).get('errores', 0) or 0),
            # pendientes_lote = items aún por enviar en el lote operativo activo
            'pendientes_lote': int((sel or {}).get('pendientes', 0) or 0),
        },
        'rebotes': {
            'total_acumulado': int(reb_total),
            'detectados_hoy':  int(reb_hoy) if reb_hoy is not None else 0,
        },
    }


def get_lotes_disponibles(fecha: str) -> list:
    """
    Lista de lotes para una fecha dada (YYYY-MM-DD, America/Lima).

    Compatible con schema original (ec02) y corregido (post-ec04).
    """
    return _rows("""
        SELECT
            id,
            COALESCE(lote_id, 'LOT-' || id::text)            AS lote_id,
            COALESCE(fuente_sheet_id, fuente, '—')            AS fuente_sheet_id,
            fuente_tab,
            COALESCE(fecha_creacion, creado_at)::text          AS fecha_creacion,
            creado_por,
            cupo_elegibles,
            COALESCE(total_candidatos, total_items, 0)        AS total_candidatos,
            COALESCE(total_elegibles, 0)                      AS total_elegibles,
            COALESCE(total_excluidos, 0)                      AS total_excluidos,
            COALESCE(total_enviados, items_aceptados, 0)      AS total_enviados,
            estado,
            dry_run,
            COALESCE(items_fallidos, 0)                       AS items_fallidos,
            COALESCE(es_prueba, 0)                            AS es_prueba
        FROM ec_lotes
        WHERE DATE(
            COALESCE(fecha_creacion, creado_at)
            AT TIME ZONE 'America/Lima'
        ) = :0
        ORDER BY id
    """, (fecha,))


def get_lote_prospectos(lote_id: str, limit: int = 500,
                        solo_seleccionados: bool = True) -> dict:
    """
    Items de un lote específico (ec_lote_items JOIN ec_lotes).

    lote_id: identificador TEXT del lote (ej. '2026-11-09-A' o 'LOT-42').
    solo_seleccionados: True (default) → muestra solo los 300 asignados a bandeja.
                        False          → muestra todos (incluye los no seleccionados).
    Compatible con schema original (ec02) y corregido (post-ec04).

    Semántica de dry_run:
      dry_run=TRUE  → nunca mostrar como 'Enviado'; mostrar 'Simulado (DRY RUN)'
      dry_run=FALSE → estado_envio='enviado' confirma aceptación por proveedor

    Por qué bandeja_asignada y no estado_envio='pendiente':
      Cuando el scheduler avanza los envíos, estado_envio cambia a 'enviado',
      'en_proceso', etc. El item sigue siendo parte del lote seleccionado.
      bandeja_asignada IS NOT NULL es el marcador permanente de selección
      (CONTRATO_LOTES.md: "permanente; sobrevive al envío para trazabilidad").

    Limitación — ventana pre-asignación:
      Antes de que el scheduler asigne bandejas, bandeja_asignada = NULL para
      todos los ítems. El panel mostrará 0 seleccionados en esa ventana.
      El contrato no define un campo que identifique los N ítems pre-seleccionados
      antes de la asignación: estado_seleccion='elegible' es el pool completo
      (todos los que pasaron el filtro), no el subconjunto que se enviará.
      Para visibilidad inmediata post-selección sería necesario un campo nuevo
      en el contrato T1 (ej. orden_seleccion o cupo_asignado). No se agrega aquí.
    """
    # Busca por TEXT lote_id (post-ec04) o por id si lote_id tiene formato 'LOT-N'
    lote = _row("""
        SELECT
            l.id,
            COALESCE(l.lote_id, 'LOT-' || l.id::text)        AS lote_id,
            COALESCE(l.fuente_sheet_id, l.fuente, '—')        AS fuente_sheet_id,
            l.fuente_tab,
            COALESCE(l.fecha_creacion, l.creado_at)::text     AS fecha_creacion,
            l.creado_por,
            l.estado,
            l.dry_run,
            COALESCE(l.total_candidatos, l.total_items, 0)   AS total_candidatos,
            COALESCE(l.total_elegibles, 0)                    AS total_elegibles,
            COALESCE(l.total_excluidos, 0)                    AS total_excluidos,
            COALESCE(l.total_enviados, l.items_aceptados, 0) AS total_enviados,
            l.cupo_elegibles
        FROM ec_lotes l
        WHERE COALESCE(l.lote_id, 'LOT-' || l.id::text) = :0
    """, (lote_id,))

    if not lote:
        return {'error': f'Lote {lote_id} no encontrado', 'items': []}

    lote_pk = lote['id']  # BIGINT — FK en ec_lote_items.lote_id

    bandeja_filter = (
        "AND COALESCE(li.bandeja_asignada, li.bandeja) IS NOT NULL"
        if solo_seleccionados else ""
    )
    items = _rows(f"""
        SELECT
            li.id,
            li.email,
            COALESCE(li.razon_social, li.email)              AS razon_social,
            COALESCE(li.rubro, '')                           AS rubro,
            li.sector,
            COALESCE(li.estado_validacion, li.estado_email,
                     'sin_validar')                          AS estado_validacion,
            COALESCE(li.estado_seleccion, 'candidato')       AS estado_seleccion,
            COALESCE(li.bandeja_asignada, li.bandeja)        AS bandeja_asignada,
            li.bloqueado_por,
            li.estado_envio,
            li.skip_reason,
            COALESCE(li.fecha_seleccion,
                     li.agregado_at)::text                   AS fecha_seleccion,
            COALESCE(li.fecha_envio,
                     li.enviado_at)::text                    AS fecha_envio,
            COALESCE(li.rebote_motivo,
                     li.rebote_tipo)                         AS rebote_motivo,
            li.gmail_message_id,
            li.intento_enviado_en::text                      AS intento_enviado_en
        FROM ec_lote_items li
        WHERE li.lote_id = :0
        {bandeja_filter}
        ORDER BY COALESCE(li.bandeja_asignada, li.bandeja) ASC,
                 li.estado_envio     ASC,
                 COALESCE(li.fecha_seleccion, li.agregado_at) ASC
        LIMIT :1
    """, (lote_pk, limit))

    # Normalizar estado_envio: mapear valores del schema original si aún no migrados
    _ESTADO_ENVIO_MAP = {
        'en_lote':     'pendiente',
        'reservado':   'en_proceso',
        'aceptado':    'enviado',
        'fallido':     'error',
        'reintentable': 'error',
        'incierto':    'conciliacion',
    }
    for row in items:
        v = row.get('estado_envio')
        if v in _ESTADO_ENVIO_MAP:
            row['estado_envio'] = _ESTADO_ENVIO_MAP[v]

    # Totales por estado_envio (ya normalizados)
    totales: dict[str, int] = {}
    for row in items:
        k = row.get('estado_envio') or 'pendiente'
        totales[k] = totales.get(k, 0) + 1
    totales['total'] = len(items)
    totales['rebotes'] = sum(1 for r in items if r.get('rebote_motivo'))
    totales['solo_seleccionados'] = solo_seleccionados

    return {
        'lote':    lote,
        'items':   items,
        'totales': totales,
    }


# ── KPIs consolidados ──────────────────────────────────────────────────────────

def get_prospeccion_kpis() -> dict:
    """
    KPIs consolidados del ecosistema de prospección desde PostgreSQL.
    Interfaz idéntica a prospeccion_connector.get_prospeccion_kpis()
    para no romper agentes.py ni mission_control.html.

    No expone credenciales, tokens ni datos sensibles.
    """
    master    = get_master_stats()
    outreach  = get_outreach_stats_today()
    config    = get_runtime_config()
    tc        = get_tc_status()

    dry_run   = config.get('dry_run', 'true').lower() in ('true', '1', 'yes')

    return {
        'master':        master,
        'outreach_hoy':  outreach,
        'dry_run':       dry_run,
        'tc':            tc,
        'db_disponible': master.get('disponible', False),
        # Nuevos campos vs connector:
        'worker':        get_worker_status(),
        'bandejas':      get_bandeja_estado(),
        'leads':         get_lead_pipeline_stats(),
    }

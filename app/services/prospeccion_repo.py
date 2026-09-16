"""
prospeccion_repo.py — Repositorio Flask para datos del ecosistema de prospección

Lee desde PostgreSQL compartido (las tablas worker: ec_prospectos, agent_runs,
agent_heartbeat, bandeja_estado, runtime_config, metrics, alerts_log, lead_pipeline).

Reemplaza prospeccion_connector.py (que leía SQLite directamente).
Mantiene la misma interfaz para no romper agentes.py ni mission_control.html.

Fallback: si las tablas worker no existen aún (pre-deploy), retorna datos vacíos
sin lanzar excepción — mismo comportamiento que el connector SQLite offline.

Seguridad:
  - Solo lectura (SELECT). Las escrituras son responsabilidad del worker.
  - No expone credenciales, tokens ni secrets.
  - Todas las queries parametrizadas.
"""
import logging
from datetime import datetime, timedelta
from typing import Any

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

"""
mc_repo.py — Repositorio de lectura para Mission Control v2

Principios:
  - Cada función retorna un dict con 'source', 'query_at' y datos o 'error'.
  - Sin fallbacks silenciosos entre fuentes. Si una tabla falla → error explícito.
  - ec_prospectos y prospectos (Flask) nunca se suman ni confunden.
  - outreach_log (registros reales enviados) ≠ outreach_attempt (idempotencia).
  - Todas las queries son SELECT parametrizadas; sin escrituras.

Fuentes:
  WORKER  — tablas creadas por ec01_worker_tables.py:
            ec_prospectos, outreach_log, outreach_attempt, response_log,
            agent_runs, agent_heartbeat, bandeja_estado, prospect_state_log,
            lead_pipeline, metrics, alerts_log, runtime_config, sync_state,
            suppression
  FLASK   — tablas ORM del sistema:
            agent_status, agent_logs, agent_metrics, prospectos,
            actividades_prospecto, seguimientos_prospecto
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.extensions import db

log = logging.getLogger(__name__)

# ── Cache simple en memoria ───────────────────────────────────────────────────
# Cada entrada: (timestamp_float, payload_dict)
_cache: Dict[str, tuple] = {}
_RESUMEN_TTL   = 120   # segundos
_AGENTES_TTL   = 30
_HISTORIAL_TTL = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _cache_get(key: str, ttl: int):
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < ttl:
        return entry[1]
    return None


def _cache_set(key: str, value: Any):
    _cache[key] = (time.monotonic(), value)


def _sql(query: str, params: Optional[Dict] = None) -> List[Dict]:
    """SELECT parametrizado → lista de dicts. Lanza excepción si falla."""
    result = db.session.execute(db.text(query), params or {})
    return [dict(r._mapping) for r in result.fetchall()]


def _sql_one(query: str, params: Optional[Dict] = None) -> Optional[Dict]:
    result = db.session.execute(db.text(query), params or {})
    row = result.fetchone()
    return dict(row._mapping) if row else None


def _scalar(query: str, params: Optional[Dict] = None, default=None):
    result = db.session.execute(db.text(query), params or {})
    row = result.fetchone()
    return row[0] if row else default


# ── Helpers de error ──────────────────────────────────────────────────────────

def _err(source: str, exc: Exception) -> dict:
    msg = str(exc)
    # No exponer stack trace ni credenciales en la respuesta JSON
    if 'does not exist' in msg or 'relation' in msg.lower():
        msg = f'tabla no disponible ({source})'
    elif 'connection' in msg.lower() or 'timeout' in msg.lower():
        msg = 'error de conexión a base de datos'
    else:
        msg = 'error de consulta'
    log.warning(f'[mc_repo] {source}: {exc}')
    return {'error': msg, 'source': source}


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — Resumen ejecutivo
# ══════════════════════════════════════════════════════════════════════════════

def get_resumen() -> dict:
    """
    Resumen rápido del estado del ecosistema.
    Cache 120 s. Errores independientes por bloque.
    """
    cached = _cache_get('resumen', _RESUMEN_TTL)
    if cached:
        return {**cached, 'cached': True}

    query_at = _now_iso()
    result = {'query_at': query_at, 'cached': False}

    # ── Worker heartbeat (orchestrator) ──────────────────────────────────────
    try:
        row = _sql_one("""
            SELECT status, last_seen, hostname, pid
            FROM agent_heartbeat
            WHERE agent = 'orchestrator'
        """)
        if row:
            ls = row.get('last_seen')
            ls_iso = ls.isoformat() if hasattr(ls, 'isoformat') else str(ls) if ls else None
            age_s = None
            if ls:
                ls_naive = ls.replace(tzinfo=None) if hasattr(ls, 'replace') else None
                if ls_naive:
                    age_s = int((datetime.utcnow() - ls_naive).total_seconds())
            result['worker'] = {
                'source':    'agent_heartbeat',
                'online':    age_s is not None and age_s < 300,
                'status':    row.get('status'),
                'last_seen': ls_iso,
                'age_s':     age_s,
                'hostname':  row.get('hostname'),
            }
        else:
            result['worker'] = {
                'source': 'agent_heartbeat',
                'online': None,
                'error':  'sin datos de heartbeat',
            }
    except Exception as e:
        result['worker'] = _err('agent_heartbeat', e)

    # ── Tipo de cambio ────────────────────────────────────────────────────────
    try:
        rows = _sql("SELECT key, value, updated_at FROM runtime_config WHERE key IN ('tc_compra','tc_venta','tc_updated_at')")
        cfg = {r['key']: r for r in rows}
        tc_compra = cfg.get('tc_compra', {}).get('value')
        tc_venta  = cfg.get('tc_venta',  {}).get('value')
        tc_ts_row = cfg.get('tc_updated_at', {})
        tc_ts     = tc_ts_row.get('value')
        tc_age_min = None
        fresco = None
        if tc_ts:
            try:
                ts = datetime.fromisoformat(tc_ts.replace('Z', '+00:00'))
                age = datetime.now(timezone.utc) - ts
                tc_age_min = int(age.total_seconds() / 60)
                fresco = tc_age_min < 180
            except Exception:
                pass
        result['tc'] = {
            'source':     'runtime_config',
            'compra':     tc_compra,
            'venta':      tc_venta,
            'updated_at': tc_ts,
            'fresco':     fresco,
            'age_min':    tc_age_min,
        }
    except Exception as e:
        result['tc'] = _err('runtime_config', e)

    # ── DRY RUN ───────────────────────────────────────────────────────────────
    try:
        dry_val = _scalar("SELECT value FROM runtime_config WHERE key = 'dry_run'")
        result['dry_run'] = {
            'source': 'runtime_config',
            'activo': str(dry_val).lower() in ('true', '1', 'yes') if dry_val else True,
        }
    except Exception as e:
        result['dry_run'] = _err('runtime_config', e)

    # ── Emails hoy (outreach_log — registros realmente enviados) ─────────────
    # outreach_log.status = 'enviado' | 'omitido' | etc.
    # outreach_attempt es el guard de idempotencia, no el historial definitivo.
    try:
        row = _sql_one("""
            SELECT
                COUNT(*)                                            AS total,
                COUNT(*) FILTER (WHERE status = 'enviado')         AS enviados,
                COUNT(*) FILTER (WHERE status != 'enviado'
                                   AND status IS NOT NULL
                                   AND status != 'omitido')        AS fallidos
            FROM outreach_log
            WHERE DATE(sent_at AT TIME ZONE 'America/Lima') = CURRENT_DATE
        """)
        result['outreach_hoy'] = {
            'source':       'outreach_log',
            'query_date':   datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'total':        int(row.get('total', 0) or 0) if row else 0,
            'enviados':     int(row.get('enviados', 0) or 0) if row else 0,
            'fallidos':     int(row.get('fallidos', 0) or 0) if row else 0,
        }
    except Exception as e:
        result['outreach_hoy'] = _err('outreach_log', e)

    # ── Bandejas ──────────────────────────────────────────────────────────────
    try:
        rows = _sql("""
            SELECT bandeja, enviados_hoy, bounce_count_24h,
                   total_24h, pausada_hasta, ultimo_update
            FROM bandeja_estado
            ORDER BY bandeja
        """)
        now_utc = datetime.utcnow()
        bandejas = []
        ultimo = None
        for r in rows:
            ph = r.get('pausada_hasta')
            ph_naive = ph.replace(tzinfo=None) if ph and hasattr(ph, 'replace') else None
            uu = r.get('ultimo_update')
            uu_iso = uu.isoformat() if hasattr(uu, 'isoformat') else None
            if uu and (ultimo is None or uu > ultimo):
                ultimo = uu
            bandejas.append({
                'bandeja':        r['bandeja'],
                'enviados_hoy':   r.get('enviados_hoy', 0),
                'bounce_24h':     r.get('bounce_count_24h', 0),
                'total_24h':      r.get('total_24h', 0),
                'pausada':        bool(ph_naive and now_utc < ph_naive),
                'pausada_hasta':  ph.isoformat() if hasattr(ph, 'isoformat') else None,
                'ultimo_update':  uu_iso,
            })
        result['bandejas'] = {
            'source':       'bandeja_estado',
            'ultimo_update': ultimo.isoformat() if hasattr(ultimo, 'isoformat') else None,
            'items':        bandejas,
        }
    except Exception as e:
        result['bandejas'] = _err('bandeja_estado', e)

    # ── Sync state (última sincronización Sheets→DB) ──────────────────────────
    try:
        row = _sql_one("""
            SELECT value, updated_at
            FROM sync_state
            WHERE key = 'last_full_sync'
        """)
        result['sync'] = {
            'source':          'sync_state',
            'last_full_sync':  row['value'] if row else None,
            'sync_updated_at': row['updated_at'].isoformat() if row and hasattr(row.get('updated_at'), 'isoformat') else None,
        }
    except Exception as e:
        result['sync'] = _err('sync_state', e)

    _cache_set('resumen', result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — Agentes
# ══════════════════════════════════════════════════════════════════════════════

def get_agentes() -> dict:
    """
    Estado de agentes del worker (agent_heartbeat + último agent_run por agente)
    y agentes Flask (agent_status ORM).
    Cache 30 s.
    """
    cached = _cache_get('agentes', _AGENTES_TTL)
    if cached:
        return {**cached, 'cached': True}

    query_at = _now_iso()
    result = {'query_at': query_at, 'cached': False}

    # ── Worker: heartbeat + último run ────────────────────────────────────────
    try:
        beats = _sql("""
            SELECT h.agent, h.last_seen, h.status, h.pid, h.hostname,
                   r.started_at   AS last_run_started,
                   r.finished_at  AS last_run_finished,
                   r.status       AS last_run_status,
                   r.actions_taken,
                   r.records_out,
                   r.error_msg    AS last_error
            FROM agent_heartbeat h
            LEFT JOIN LATERAL (
                SELECT started_at, finished_at, status, actions_taken,
                       records_out, error_msg
                FROM agent_runs
                WHERE agent = h.agent
                ORDER BY started_at DESC
                LIMIT 1
            ) r ON true
            ORDER BY h.agent
        """)
        now_utc = datetime.utcnow()
        items = []
        for b in beats:
            ls = b.get('last_seen')
            ls_naive = ls.replace(tzinfo=None) if ls and hasattr(ls, 'replace') else None
            age_s = int((now_utc - ls_naive).total_seconds()) if ls_naive else None
            items.append({
                'agent':              b['agent'],
                'last_seen':          ls.isoformat() if hasattr(ls, 'isoformat') else None,
                'age_s':              age_s,
                'is_offline':         age_s is None or age_s > 600,
                'status':             b.get('status'),
                'last_run_started':   b['last_run_started'].isoformat() if b.get('last_run_started') and hasattr(b['last_run_started'], 'isoformat') else None,
                'last_run_finished':  b['last_run_finished'].isoformat() if b.get('last_run_finished') and hasattr(b['last_run_finished'], 'isoformat') else None,
                'last_run_status':    b.get('last_run_status'),
                'actions_taken':      b.get('actions_taken'),
                'records_out':        b.get('records_out'),
                'last_error':         b.get('last_error'),
            })
        result['worker_agents'] = {
            'source': 'agent_heartbeat + agent_runs',
            'items':  items,
        }
    except Exception as e:
        result['worker_agents'] = _err('agent_heartbeat + agent_runs', e)

    # ── Flask agents (agent_status ORM) ───────────────────────────────────────
    try:
        from app.models.agent import AgentStatus
        agents = AgentStatus.query.order_by(AgentStatus.agent_id).all()
        items_flask = []
        for a in agents:
            items_flask.append({
                'agent_id':     a.agent_id,
                'name':         a.name,
                'status':       a.status,
                'enabled':      a.enabled,
                'last_run':     a.last_run.isoformat() if a.last_run else None,
                'next_run':     a.next_run.isoformat() if a.next_run else None,
                'tasks_today':  a.tasks_today,
                'errors_today': a.errors_today,
                'last_result':  a.last_result,
                'last_error':   a.last_error,
                'run_interval': a.run_interval,
            })
        result['flask_agents'] = {
            'source': 'agent_status',
            'items':  items_flask,
        }
    except Exception as e:
        result['flask_agents'] = _err('agent_status', e)

    _cache_set('agentes', result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — Prospectos (ec_prospectos, paginado)
# ══════════════════════════════════════════════════════════════════════════════

_PER_PAGE_MAX = 100
_PER_PAGE_DEFAULT = 50


def get_prospectos(
    q: str = '',
    estado_email: str = '',
    estado_com: str = '',
    page: int = 1,
    per_page: int = _PER_PAGE_DEFAULT,
) -> dict:
    """
    Búsqueda paginada en ec_prospectos (worker).
    Nunca carga la tabla completa. LIMIT/OFFSET en servidor.
    No mezcla con la tabla Flask 'prospectos'.
    """
    query_at = _now_iso()
    per_page = min(max(1, per_page), _PER_PAGE_MAX)
    offset = (max(1, page) - 1) * per_page

    conditions = []
    params: dict = {'limit': per_page, 'offset': offset}

    if q:
        conditions.append(
            "(razon_social ILIKE :q OR email ILIKE :q OR ruc ILIKE :q OR nombre_contacto ILIKE :q)"
        )
        params['q'] = f'%{q}%'
    if estado_email:
        conditions.append("estado_email = :estado_email")
        params['estado_email'] = estado_email
    if estado_com:
        conditions.append("estado_com = :estado_com")
        params['estado_com'] = estado_com

    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

    try:
        count_row = _sql_one(
            f"SELECT COUNT(*) AS n FROM ec_prospectos {where}",
            {k: v for k, v in params.items() if k not in ('limit', 'offset')}
        )
        total = int(count_row['n']) if count_row else 0

        items = _sql(f"""
            SELECT id, ruc, email, razon_social, nombre_contacto, cargo,
                   provincia, rubro, sector, estado_email, estado_com,
                   score, prioridad, fecha_ult_contacto, synced_at
            FROM ec_prospectos
            {where}
            ORDER BY score DESC, id DESC
            LIMIT :limit OFFSET :offset
        """, params)

        # Serializar timestamps
        for item in items:
            sa = item.get('synced_at')
            item['synced_at'] = sa.isoformat() if hasattr(sa, 'isoformat') else sa

        return {
            'query_at': query_at,
            'source':   'ec_prospectos',
            'page':     page,
            'per_page': per_page,
            'total':    total,
            'pages':    (total + per_page - 1) // per_page if total else 0,
            'items':    items,
        }
    except Exception as e:
        return {
            'query_at': query_at,
            **_err('ec_prospectos', e),
            'page': page, 'per_page': per_page, 'total': None, 'items': None,
        }


def get_prospectos_estados() -> dict:
    """Distribución de estados para filtros del panel. Cache 5 min."""
    cached = _cache_get('prospectos_estados', 300)
    if cached:
        return cached
    try:
        email_estados = _sql(
            "SELECT estado_email, COUNT(*) AS n FROM ec_prospectos GROUP BY estado_email ORDER BY n DESC"
        )
        com_estados = _sql(
            "SELECT estado_com, COUNT(*) AS n FROM ec_prospectos GROUP BY estado_com ORDER BY n DESC"
        )
        result = {
            'source':        'ec_prospectos',
            'estado_email':  [{'value': r['estado_email'], 'count': int(r['n'])} for r in email_estados],
            'estado_com':    [{'value': r['estado_com'],   'count': int(r['n'])} for r in com_estados],
        }
        _cache_set('prospectos_estados', result)
        return result
    except Exception as e:
        return _err('ec_prospectos', e)


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — Historial de ejecuciones (agent_runs)
# ══════════════════════════════════════════════════════════════════════════════

def get_historial_runs(agent: str = '', limit: int = 20) -> dict:
    """
    Últimas ejecuciones del worker desde agent_runs.
    Cache 60 s (sin filtro de agente).
    """
    limit = min(max(1, limit), 200)
    cache_key = f'historial_{agent}_{limit}'

    if not agent:
        cached = _cache_get(cache_key, _HISTORIAL_TTL)
        if cached:
            return {**cached, 'cached': True}

    params: dict = {'limit': limit}
    where = ''
    if agent:
        where = 'WHERE agent = :agent'
        params['agent'] = agent

    try:
        rows = _sql(f"""
            SELECT id, agent, execution_uuid, started_at, finished_at,
                   status, records_in, records_out, actions_taken,
                   actions_skipped, error_msg, triggered_by
            FROM agent_runs
            {where}
            ORDER BY started_at DESC
            LIMIT :limit
        """, params)

        for r in rows:
            for f in ('started_at', 'finished_at'):
                v = r.get(f)
                r[f] = v.isoformat() if hasattr(v, 'isoformat') else v
            # Duración en segundos si tenemos ambos timestamps
            if r.get('started_at') and r.get('finished_at'):
                try:
                    s = datetime.fromisoformat(r['started_at'].replace('Z', '+00:00'))
                    e = datetime.fromisoformat(r['finished_at'].replace('Z', '+00:00'))
                    r['duration_s'] = int((e - s).total_seconds())
                except Exception:
                    r['duration_s'] = None
            else:
                r['duration_s'] = None

        result = {
            'query_at': _now_iso(),
            'source':   'agent_runs',
            'cached':   False,
            'agent':    agent or None,
            'limit':    limit,
            'items':    rows,
        }
        if not agent:
            _cache_set(cache_key, result)
        return result
    except Exception as e:
        return {
            'query_at': _now_iso(),
            **_err('agent_runs', e),
            'items': None,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — Historial por prospecto
# ══════════════════════════════════════════════════════════════════════════════

def get_prospecto_historial(prospecto_id: int) -> dict:
    """
    Historial de envíos y transiciones de estado de un prospecto concreto.
    Fuente: outreach_log + prospect_state_log (worker).
    Sin cache — es una consulta específica de bajo volumen.
    """
    query_at = _now_iso()
    result = {'query_at': query_at, 'prospecto_id': prospecto_id}

    # Verificar que el prospecto existe
    try:
        meta = _sql_one(
            "SELECT id, email, razon_social, nombre_contacto, estado_email, estado_com, score FROM ec_prospectos WHERE id = :id",
            {'id': prospecto_id}
        )
        if not meta:
            return {**result, 'error': 'prospecto no encontrado', 'source': 'ec_prospectos'}
        result['prospecto'] = {'source': 'ec_prospectos', **meta}
    except Exception as e:
        return {**result, **_err('ec_prospectos', e)}

    # Envíos
    try:
        outreach = _sql("""
            SELECT id, bandeja, stage, template_sector, subject,
                   sent_at, status, skip_reason, tc_compra, tc_venta
            FROM outreach_log
            WHERE prospecto_id = :id
            ORDER BY sent_at DESC
            LIMIT 100
        """, {'id': prospecto_id})
        for r in outreach:
            sa = r.get('sent_at')
            r['sent_at'] = sa.isoformat() if hasattr(sa, 'isoformat') else sa
        result['outreach'] = {'source': 'outreach_log', 'items': outreach}
    except Exception as e:
        result['outreach'] = _err('outreach_log', e)

    # Transiciones de estado
    try:
        states = _sql("""
            SELECT id, estado_anterior, estado_nuevo, motivo, agente, created_at
            FROM prospect_state_log
            WHERE prospecto_id = :id
            ORDER BY created_at DESC
            LIMIT 50
        """, {'id': prospecto_id})
        for r in states:
            ca = r.get('created_at')
            r['created_at'] = ca.isoformat() if hasattr(ca, 'isoformat') else ca
        result['state_log'] = {'source': 'prospect_state_log', 'items': states}
    except Exception as e:
        result['state_log'] = _err('prospect_state_log', e)

    # Leads generados por este prospecto
    try:
        leads = _sql("""
            SELECT id, tipo, subject, notificado, webhook_ok, created_at
            FROM lead_pipeline
            WHERE prospecto_id = :id
            ORDER BY created_at DESC
            LIMIT 20
        """, {'id': prospecto_id})
        for r in leads:
            ca = r.get('created_at')
            r['created_at'] = ca.isoformat() if hasattr(ca, 'isoformat') else ca
        result['leads'] = {'source': 'lead_pipeline', 'items': leads}
    except Exception as e:
        result['leads'] = _err('lead_pipeline', e)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6 — Alertas del worker
# ══════════════════════════════════════════════════════════════════════════════

def get_alertas_worker(limit: int = 30) -> dict:
    """Alertas recientes del worker desde alerts_log."""
    try:
        rows = _sql("""
            SELECT level, component, message, detail, agent_run_id, created_at
            FROM alerts_log
            ORDER BY created_at DESC
            LIMIT :limit
        """, {'limit': min(limit, 200)})
        for r in rows:
            ca = r.get('created_at')
            r['created_at'] = ca.isoformat() if hasattr(ca, 'isoformat') else ca
        return {
            'query_at': _now_iso(),
            'source':   'alerts_log',
            'items':    rows,
        }
    except Exception as e:
        return {'query_at': _now_iso(), **_err('alerts_log', e), 'items': None}

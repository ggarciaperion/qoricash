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

Hallazgos del diagnóstico local (terminal 3):
  FIX 1  — env_note en cada respuesta; SQLite local != Render/producción.
  FIX 2  — agent_heartbeat ausente no bloquea agent_runs; fallback explícito.
  FIX 3  — ec_prospectos puede ser VISTA en SQLite; source_note lo documenta.
  FIX 4  — outreach_hoy usa sent_at+Lima, COUNT(DISTINCT id), label parcial.
  FIX 5  — bandeja_estado: data_date vs query_date; data_stale cuando difieren.
  FIX 6  — finished_at nulo → cierre_registrado=False, display_status explícito.
  FIX 7  — origin solo con evidencia; agent_run_id nulo != campaña local.
  FIX 8  — suppression independiente de estado_com; aviso fuente autoritativa.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.extensions import db

log = logging.getLogger(__name__)

_cache: dict[str, tuple[float, Any]] = {}
_RESUMEN_TTL   = 120
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


def _sql(query: str, params=None) -> list[dict]:
    result = db.session.execute(db.text(query), params or {})
    return [dict(r._mapping) for r in result.fetchall()]


def _sql_one(query: str, params=None) -> dict:
    result = db.session.execute(db.text(query), params or {})
    row = result.fetchone()
    return dict(row._mapping) if row else None


def _scalar(query: str, params=None, default=None):
    result = db.session.execute(db.text(query), params or {})
    row = result.fetchone()
    return row[0] if row else default


def _err(source: str, exc: Exception) -> dict:
    msg = str(exc)
    if 'does not exist' in msg or 'relation' in msg.lower():
        msg = f'tabla no disponible ({source})'
    elif 'connection' in msg.lower() or 'timeout' in msg.lower():
        msg = 'error de conexión a base de datos'
    else:
        msg = 'error de consulta'
    log.warning(f'[mc_repo] {source}: {exc}')
    return {'error': msg, 'source': source}


# ── FIX 1: Identificación de entorno ─────────────────────────────────────────

def _detect_env() -> str:
    """
    SQLite local NO acredita estado de Render/producción.
    Las tablas worker pueden no existir en SQLite, o existir como vistas de prueba.
    """
    try:
        dialect = db.engine.dialect.name
        if dialect == 'sqlite':
            return 'SQLite local — no acredita estado de Render/producción'
        if dialect == 'postgresql':
            return 'PostgreSQL (Render)'
        return f'{dialect} (entorno no identificado)'
    except Exception:
        return 'entorno desconocido'


def _lima_today() -> str:
    """Fecha de hoy en America/Lima como YYYY-MM-DD."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('America/Lima')).strftime('%Y-%m-%d')
    except Exception:
        return datetime.utcnow().strftime('%Y-%m-%d')


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — Resumen ejecutivo
# ══════════════════════════════════════════════════════════════════════════════

def get_resumen() -> dict:
    cached = _cache_get('resumen', _RESUMEN_TTL)
    if cached:
        return {**cached, 'cached': True}

    query_at   = _now_iso()
    env_note   = _detect_env()    # FIX 1
    lima_today = _lima_today()    # FIX 4, 5
    result = {'query_at': query_at, 'cached': False, 'env_note': env_note}

    # Worker heartbeat
    try:
        row = _sql_one("""
            SELECT status, last_seen, hostname, pid
            FROM agent_heartbeat WHERE agent = 'orchestrator'
        """)
        if row:
            ls    = row.get('last_seen')
            ls_iso = ls.isoformat() if hasattr(ls, 'isoformat') else str(ls) if ls else None
            age_s  = None
            if ls:
                ls_naive = ls.replace(tzinfo=None) if hasattr(ls, 'replace') else None
                if ls_naive:
                    age_s = int((datetime.utcnow() - ls_naive).total_seconds())
            result['worker'] = {
                'source': 'agent_heartbeat', 'online': age_s is not None and age_s < 300,
                'status': row.get('status'), 'last_seen': ls_iso,
                'age_s': age_s, 'hostname': row.get('hostname'),
            }
        else:
            result['worker'] = {'source': 'agent_heartbeat', 'online': None,
                                 'error': 'sin datos de heartbeat'}
    except Exception as e:
        result['worker'] = _err('agent_heartbeat', e)

    # Tipo de cambio
    try:
        rows = _sql("SELECT key, value, updated_at FROM runtime_config "
                    "WHERE key IN ('tc_compra','tc_venta','tc_updated_at')")
        cfg = {r['key']: r for r in rows}
        tc_compra  = cfg.get('tc_compra', {}).get('value')
        tc_venta   = cfg.get('tc_venta', {}).get('value')
        tc_ts      = cfg.get('tc_updated_at', {}).get('value')
        tc_age_min = None
        fresco     = None
        if tc_ts:
            try:
                ts  = datetime.fromisoformat(tc_ts.replace('Z', '+00:00'))
                age = datetime.now(timezone.utc) - ts
                tc_age_min = int(age.total_seconds() / 60)
                fresco = tc_age_min < 180
            except Exception:
                pass
        result['tc'] = {
            'source': 'runtime_config', 'compra': tc_compra, 'venta': tc_venta,
            'updated_at': tc_ts, 'fresco': fresco, 'age_min': tc_age_min,
        }
    except Exception as e:
        result['tc'] = _err('runtime_config', e)

    # DRY RUN
    try:
        dry_val = _scalar("SELECT value FROM runtime_config WHERE key = 'dry_run'")
        result['dry_run'] = {
            'source': 'runtime_config',
            'activo': str(dry_val).lower() in ('true', '1', 'yes') if dry_val else True,
        }
    except Exception as e:
        result['dry_run'] = _err('runtime_config', e)

    # FIX 4 — Emails hoy desde outreach_log
    # COUNT(DISTINCT id): evita duplicados aunque gmail_message_id sea UNIQUE en PG.
    # query_date (Lima) separado de los datos.
    # label: cobertura parcial por fuente.
    try:
        row = _sql_one("""
            SELECT
                COUNT(DISTINCT id)                                           AS total,
                COUNT(DISTINCT id) FILTER (WHERE status = 'enviado')        AS enviados,
                COUNT(DISTINCT id) FILTER (WHERE status != 'enviado'
                                           AND status IS NOT NULL
                                           AND status != 'omitido')         AS fallidos
            FROM outreach_log
            WHERE DATE(sent_at AT TIME ZONE 'America/Lima') = CURRENT_DATE
        """)
        result['outreach_hoy'] = {
            'source':     'outreach_log',
            'query_date': lima_today,
            'label':      'envíos registrados hoy en esta fuente',
            'total':      int(row.get('total', 0) or 0) if row else 0,
            'enviados':   int(row.get('enviados', 0) or 0) if row else 0,
            'fallidos':   int(row.get('fallidos', 0) or 0) if row else 0,
        }
    except Exception as e:
        result['outreach_hoy'] = _err('outreach_log', e)

    # FIX 5 — Bandejas con data_date vs query_date
    # enviados_hoy puede ser de un día anterior si el worker no actualizó hoy.
    # data_stale = True cuando data_date != lima_today.
    try:
        rows = _sql("""
            SELECT bandeja, enviados_hoy, bounce_count_24h,
                   total_24h, pausada_hasta, ultimo_update
            FROM bandeja_estado ORDER BY bandeja
        """)
        now_utc   = datetime.utcnow()
        bandejas  = []
        ultimo    = None
        for r in rows:
            ph       = r.get('pausada_hasta')
            ph_naive = ph.replace(tzinfo=None) if ph and hasattr(ph, 'replace') else None
            uu       = r.get('ultimo_update')
            uu_iso   = uu.isoformat() if hasattr(uu, 'isoformat') else None
            if uu and (ultimo is None or uu > ultimo):
                ultimo = uu

            data_date  = None
            data_stale = None
            if uu:
                try:
                    from zoneinfo import ZoneInfo
                    uu_aware   = uu if uu.tzinfo else uu.replace(tzinfo=timezone.utc)
                    data_date  = uu_aware.astimezone(ZoneInfo('America/Lima')).strftime('%Y-%m-%d')
                    data_stale = (data_date != lima_today)
                except Exception:
                    pass

            bandejas.append({
                'bandeja':           r['bandeja'],
                'enviados_hoy':      r.get('enviados_hoy', 0),
                'bounce_24h':        r.get('bounce_count_24h', 0),
                'total_24h':         r.get('total_24h', 0),
                'pausada':           bool(ph_naive and now_utc < ph_naive),
                'pausada_hasta':     ph.isoformat() if hasattr(ph, 'isoformat') else None,
                'ultimo_update':     uu_iso,
                'data_date':         data_date,
                'data_stale':        data_stale,
                'enviados_hoy_nota': (
                    f'contador corresponde a {data_date} — no representa hoy ({lima_today})'
                    if data_stale else None
                ),
            })
        result['bandejas'] = {
            'source':        'bandeja_estado',
            'query_date':    lima_today,
            'ultimo_update': ultimo.isoformat() if hasattr(ultimo, 'isoformat') else None,
            'items':         bandejas,
        }
    except Exception as e:
        result['bandejas'] = _err('bandeja_estado', e)

    # Sync state
    try:
        row = _sql_one("SELECT value, updated_at FROM sync_state WHERE key = 'last_full_sync'")
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
    FIX 2: si agent_heartbeat no existe, fallback a agent_runs solo.
    heartbeat_available=False + heartbeat_nota describe la ausencia.
    Las ejecuciones siempre se presentan; no se crea tabla vacía.
    """
    cached = _cache_get('agentes', _AGENTES_TTL)
    if cached:
        return {**cached, 'cached': True}

    query_at = _now_iso()
    env_note = _detect_env()    # FIX 1
    result   = {'query_at': query_at, 'cached': False, 'env_note': env_note}

    try:
        beats = _sql("""
            SELECT h.agent, h.last_seen, h.status, h.pid, h.hostname,
                   r.started_at   AS last_run_started,
                   r.finished_at  AS last_run_finished,
                   r.status       AS last_run_status,
                   r.actions_taken, r.records_out, r.error_msg AS last_error
            FROM agent_heartbeat h
            LEFT JOIN LATERAL (
                SELECT started_at, finished_at, status, actions_taken, records_out, error_msg
                FROM agent_runs WHERE agent = h.agent
                ORDER BY started_at DESC LIMIT 1
            ) r ON true
            ORDER BY h.agent
        """)
        now_utc = datetime.utcnow()
        items   = []
        for b in beats:
            ls      = b.get('last_seen')
            ls_naive = ls.replace(tzinfo=None) if ls and hasattr(ls, 'replace') else None
            age_s   = int((now_utc - ls_naive).total_seconds()) if ls_naive else None
            fa      = b.get('last_run_finished')
            items.append({
                'agent':              b['agent'],
                'last_seen':          ls.isoformat() if hasattr(ls, 'isoformat') else None,
                'age_s':              age_s,
                'is_offline':         age_s is None or age_s > 600,
                'status':             b.get('status'),
                'last_run_started':   b['last_run_started'].isoformat() if b.get('last_run_started') and hasattr(b['last_run_started'], 'isoformat') else None,
                'last_run_finished':  fa.isoformat() if fa and hasattr(fa, 'isoformat') else None,
                'cierre_registrado':  fa is not None,    # FIX 6
                'last_run_status':    b.get('last_run_status'),
                'actions_taken':      b.get('actions_taken'),
                'records_out':        b.get('records_out'),
                'last_error':         b.get('last_error'),
            })
        result['worker_agents'] = {
            'source': 'agent_heartbeat + agent_runs',
            'heartbeat_available': True,
            'items': items,
        }
    except Exception as e1:
        # FIX 2: fallback cuando agent_heartbeat no existe
        err_msg   = str(e1).lower()
        hb_absent = (
            'agent_heartbeat' in err_msg
            or ('relation' in err_msg and 'heartbeat' in err_msg)
        )
        if hb_absent:
            try:
                runs = _sql("""
                    SELECT agent, started_at, finished_at, status,
                           actions_taken, records_out, error_msg
                    FROM agent_runs
                    WHERE (agent, started_at) IN (
                        SELECT agent, MAX(started_at) FROM agent_runs GROUP BY agent
                    )
                    ORDER BY agent
                """)
                items_fb = []
                for r in runs:
                    sa = r.get('started_at')
                    fa = r.get('finished_at')
                    items_fb.append({
                        'agent':              r['agent'],
                        'last_seen':          None,
                        'age_s':              None,
                        'is_offline':         None,     # indeterminado sin heartbeat
                        'status':             None,     # status de heartbeat, no disponible
                        'last_run_started':   sa.isoformat() if hasattr(sa, 'isoformat') else None,
                        'last_run_finished':  fa.isoformat() if hasattr(fa, 'isoformat') else None,
                        'cierre_registrado':  fa is not None,    # FIX 6
                        'last_run_status':    r.get('status'),
                        'actions_taken':      r.get('actions_taken'),
                        'records_out':        r.get('records_out'),
                        'last_error':         r.get('error_msg'),
                    })
                result['worker_agents'] = {
                    'source':              'agent_runs (sin heartbeat)',
                    'heartbeat_available': False,
                    'heartbeat_nota':      'No disponible — tabla agent_heartbeat ausente en este entorno',
                    'items':               items_fb,
                }
            except Exception as e2:
                result['worker_agents'] = _err('agent_runs', e2)
        else:
            result['worker_agents'] = _err('agent_heartbeat + agent_runs', e1)

    # Flask agents
    try:
        from app.models.agent import AgentStatus
        agents = AgentStatus.query.order_by(AgentStatus.agent_id).all()
        result['flask_agents'] = {
            'source': 'agent_status',
            'items': [{
                'agent_id': a.agent_id, 'name': a.name, 'status': a.status,
                'enabled': a.enabled,
                'last_run': a.last_run.isoformat() if a.last_run else None,
                'next_run': a.next_run.isoformat() if a.next_run else None,
                'tasks_today': a.tasks_today, 'errors_today': a.errors_today,
                'last_result': a.last_result, 'last_error': a.last_error,
                'run_interval': a.run_interval,
            } for a in agents],
        }
    except Exception as e:
        result['flask_agents'] = _err('agent_status', e)

    _cache_set('agentes', result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — Prospectos (ec_prospectos, paginado)
# ══════════════════════════════════════════════════════════════════════════════

_PER_PAGE_MAX     = 100
_PER_PAGE_DEFAULT = 50


def get_prospectos(q='', estado_email='', estado_com='',
                   page=1, per_page=_PER_PAGE_DEFAULT) -> dict:
    """
    FIX 3: source_note documenta si ec_prospectos es vista (SQLite) o tabla (PG).
    Nunca mezcla con la tabla prospectos del sistema Flask.
    """
    query_at = _now_iso()
    env_note = _detect_env()
    per_page = min(max(1, per_page), _PER_PAGE_MAX)
    offset   = (max(1, page) - 1) * per_page

    source_note = (
        'ec_prospectos es una vista en SQLite local; esquema puede diferir de Render. '
        'No confundir con la tabla prospectos del sistema Flask.'
        if 'sqlite' in env_note.lower() else
        'ec_prospectos es la tabla worker en PostgreSQL. '
        'Distinta de la tabla prospectos del sistema Flask.'
    )

    conditions = []
    params: dict = {'limit': per_page, 'offset': offset}
    if q:
        conditions.append("(razon_social ILIKE :q OR email ILIKE :q OR ruc ILIKE :q OR nombre_contacto ILIKE :q)")
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
            FROM ec_prospectos {where}
            ORDER BY score DESC, id DESC
            LIMIT :limit OFFSET :offset
        """, params)
        for item in items:
            sa = item.get('synced_at')
            item['synced_at'] = sa.isoformat() if hasattr(sa, 'isoformat') else sa
        return {
            'query_at': query_at, 'source': 'ec_prospectos',
            'source_note': source_note, 'env_note': env_note,
            'page': page, 'per_page': per_page, 'total': total,
            'pages': (total + per_page - 1) // per_page if total else 0,
            'items': items,
        }
    except Exception as e:
        return {
            'query_at': query_at, 'env_note': env_note, 'source_note': source_note,
            **_err('ec_prospectos', e),
            'page': page, 'per_page': per_page, 'total': None, 'items': None,
        }


def get_prospectos_estados() -> dict:
    """Distribución de estados para filtros. Cache 5 min."""
    cached = _cache_get('prospectos_estados', 300)
    if cached:
        return cached
    env_note = _detect_env()
    try:
        result = {
            'source':       'ec_prospectos',
            'env_note':     env_note,
            'estado_email': [{'value': r['estado_email'], 'count': int(r['n'])}
                             for r in _sql("SELECT estado_email, COUNT(*) AS n FROM ec_prospectos GROUP BY estado_email ORDER BY n DESC")],
            'estado_com':   [{'value': r['estado_com'],   'count': int(r['n'])}
                             for r in _sql("SELECT estado_com, COUNT(*) AS n FROM ec_prospectos GROUP BY estado_com ORDER BY n DESC")],
        }
        _cache_set('prospectos_estados', result)
        return result
    except Exception as e:
        return {**_err('ec_prospectos', e), 'env_note': env_note}


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — Historial de ejecuciones (agent_runs)
# ══════════════════════════════════════════════════════════════════════════════

def get_historial_runs(agent='', limit=20) -> dict:
    """
    FIX 6: sin finished_at → cierre_registrado=False, display_status='sin cierre registrado'.
    No se declara activo ni muerto por antigüedad.
    FIX 7: origin de triggered_by; nulo = 'origen no identificado'.
    """
    limit     = min(max(1, limit), 200)
    cache_key = f'historial_{agent}_{limit}'
    if not agent:
        cached = _cache_get(cache_key, _HISTORIAL_TTL)
        if cached:
            return {**cached, 'cached': True}

    env_note = _detect_env()
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
            FROM agent_runs {where}
            ORDER BY started_at DESC LIMIT :limit
        """, params)

        for r in rows:
            for f in ('started_at', 'finished_at'):
                v = r.get(f)
                r[f] = v.isoformat() if hasattr(v, 'isoformat') else v
            # FIX 6
            if r.get('finished_at'):
                r['cierre_registrado'] = True
                try:
                    s = datetime.fromisoformat(r['started_at'].replace('Z', '+00:00'))
                    e = datetime.fromisoformat(r['finished_at'].replace('Z', '+00:00'))
                    r['duration_s'] = int((e - s).total_seconds())
                except Exception:
                    r['duration_s'] = None
            else:
                r['cierre_registrado'] = False
                r['duration_s']        = None
                r['display_status']    = 'sin cierre registrado'
            # FIX 7
            tb = r.get('triggered_by')
            r['origin'] = tb if tb else 'origen no identificado'

        result = {
            'query_at': _now_iso(), 'source': 'agent_runs',
            'env_note': env_note, 'cached': False,
            'agent': agent or None, 'limit': limit, 'items': rows,
        }
        if not agent:
            _cache_set(cache_key, result)
        return result
    except Exception as e:
        return {'query_at': _now_iso(), 'env_note': env_note,
                **_err('agent_runs', e), 'items': None}


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — Historial por prospecto
# ══════════════════════════════════════════════════════════════════════════════

def get_prospecto_historial(prospecto_id: int) -> dict:
    """
    FIX 7: origin por agent_run_id; nulo = 'origen no identificado'.
    FIX 8: suppression independiente de estado_com;
           aviso sobre fuente autoritativa de clientes.
    """
    query_at = _now_iso()
    env_note = _detect_env()
    result   = {'query_at': query_at, 'prospecto_id': prospecto_id, 'env_note': env_note}

    try:
        meta = _sql_one(
            "SELECT id, email, razon_social, nombre_contacto, "
            "estado_email, estado_com, score FROM ec_prospectos WHERE id = :id",
            {'id': prospecto_id}
        )
        if not meta:
            return {**result, 'error': 'prospecto no encontrado', 'source': 'ec_prospectos'}
        result['prospecto'] = {'source': 'ec_prospectos', **meta}
    except Exception as e:
        return {**result, **_err('ec_prospectos', e)}

    # FIX 8: suppression es independiente del estado_com
    try:
        # Schema real: suppression usa tipo/valor/motivo/agregado_at (no email/reason/created_at)
        sup          = _sql_one(
            "SELECT id, motivo, fuente, agregado_at FROM suppression "
            "WHERE tipo = 'email' AND valor = :email",
            {'email': meta.get('email', '')})
        is_sup       = sup is not None
        estado_com   = (meta.get('estado_com') or '').lower()
        ya_excluido  = estado_com in ('no_contactar', 'correo_rebotado', 'no_enviar', 'rebotado')
        conflicto    = is_sup and not ya_excluido
        result['suppression'] = {
            'source':    'suppression',
            'suprimido': is_sup,
            'razon':     sup.get('motivo') if sup else None,
            'fuente':    sup.get('fuente') if sup else None,
            'desde':     sup['agregado_at'].isoformat() if sup and hasattr(sup.get('agregado_at'), 'isoformat') else None,
            'conflicto': conflicto,
            'nota': (
                'El estado comercial permitiría contacto, pero el email está en suppression — NO enviar'
                if conflicto else None
            ),
            'aviso_fuente_clientes': (
                'ec_prospectos.estado_com no es la fuente autoritativa de clientes. '
                'Consultar la tabla clientes del sistema Flask para confirmar.'
            ),
        }
    except Exception as e:
        result['suppression'] = _err('suppression', e)

    # Envíos — FIX 7: agent_run_id en SELECT
    try:
        outreach = _sql("""
            SELECT id, bandeja, stage, template_sector, subject,
                   sent_at, status, skip_reason, tc_compra, tc_venta, agent_run_id
            FROM outreach_log WHERE prospecto_id = :id
            ORDER BY sent_at DESC LIMIT 100
        """, {'id': prospecto_id})
        for r in outreach:
            sa = r.get('sent_at')
            r['sent_at'] = sa.isoformat() if hasattr(sa, 'isoformat') else sa
            r['origin']  = f'run:{r["agent_run_id"]}' if r.get('agent_run_id') else 'origen no identificado'
        result['outreach'] = {'source': 'outreach_log', 'items': outreach}
    except Exception as e:
        result['outreach'] = _err('outreach_log', e)

    # Transiciones de estado — FIX 7
    try:
        states = _sql("""
            SELECT id, estado_anterior, estado_nuevo, motivo, agente,
                   agent_run_id, created_at
            FROM prospect_state_log WHERE prospecto_id = :id
            ORDER BY created_at DESC LIMIT 50
        """, {'id': prospecto_id})
        for r in states:
            ca = r.get('created_at')
            r['created_at'] = ca.isoformat() if hasattr(ca, 'isoformat') else ca
            r['origin']     = f'run:{r["agent_run_id"]}' if r.get('agent_run_id') else 'origen no identificado'
        result['state_log'] = {'source': 'prospect_state_log', 'items': states}
    except Exception as e:
        result['state_log'] = _err('prospect_state_log', e)

    # Leads
    try:
        leads = _sql("""
            SELECT id, tipo, subject, notificado, webhook_ok, created_at
            FROM lead_pipeline WHERE prospecto_id = :id
            ORDER BY created_at DESC LIMIT 20
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

def get_alertas_worker(limit=30) -> dict:
    """
    FIX 7: agent_run_id nulo != campaña local ni origen específico.
    Solo se atribuye origen cuando agent_run_id está presente.
    """
    try:
        rows = _sql("""
            SELECT level, component, message, detail, agent_run_id, created_at
            FROM alerts_log ORDER BY created_at DESC LIMIT :limit
        """, {'limit': min(limit, 200)})
        for r in rows:
            ca = r.get('created_at')
            r['created_at'] = ca.isoformat() if hasattr(ca, 'isoformat') else ca
            r['origin'] = f'run:{r["agent_run_id"]}' if r.get('agent_run_id') else 'origen no identificado'
        return {'query_at': _now_iso(), 'source': 'alerts_log',
                'env_note': _detect_env(), 'items': rows}
    except Exception as e:
        return {'query_at': _now_iso(), 'env_note': _detect_env(),
                **_err('alerts_log', e), 'items': None}

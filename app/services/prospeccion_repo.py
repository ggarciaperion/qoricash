"""
prospeccion_repo.py — Repositorio Flask para datos del ecosistema de prospeccion

Lee desde PostgreSQL compartido (las tablas worker: ec_prospectos, agent_runs,
agent_heartbeat, bandeja_estado, runtime_config, metrics, alerts_log, lead_pipeline).

Reemplaza prospeccion_connector.py (que leia SQLite directamente).
Mantiene la misma interfaz para no romper agentes.py ni mission_control.html.

Fallback: si las tablas worker no existen aun (pre-deploy), retorna datos vacios
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

# ── Contactos realizados (outreach_log paginado, fallback a logs locales) ──────

def get_contactos_page(
    page=1,
    per_page=50,
    fecha_desde=None,
    fecha_hasta=None,
    bandeja=None,
    resultado=None,
    busqueda=None,
):
    """
    Tabla paginada de contactos.
    Fuente 1 (preferida): outreach_log en PostgreSQL (worker Render).
    Fuente 2 (fallback): archivos de log locales en ~/Desktop/Prospeccion/.
    Si ninguna esta disponible: disponible=False.
    """
    where_clauses = ["1=1"]
    params: dict = {}

    if fecha_desde:
        where_clauses.append(
            "ol.sent_at AT TIME ZONE 'America/Lima' >= :fecha_desde ::date"
        )
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        where_clauses.append(
            "ol.sent_at AT TIME ZONE 'America/Lima' < (:fecha_hasta ::date + interval '1 day')"
        )
        params["fecha_hasta"] = fecha_hasta
    if bandeja:
        where_clauses.append("ol.bandeja = :bandeja")
        params["bandeja"] = bandeja
    if resultado:
        where_clauses.append("ol.status = :resultado")
        params["resultado"] = resultado
    if busqueda:
        where_clauses.append(
            "(ol.email ILIKE :busq OR ep.razon_social ILIKE :busq OR ep.nombre_contacto ILIKE :busq)"
        )
        params["busq"] = f"%{busqueda}%"

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * per_page

    count_sql = f"""
        SELECT COUNT(*) FROM outreach_log ol
        LEFT JOIN ec_prospectos ep ON ep.id = ol.prospecto_id
        WHERE {where_sql}
    """
    rows_sql = f"""
        SELECT
            ol.id,
            ol.email,
            ol.bandeja,
            ol.stage,
            ol.subject,
            ol.status,
            ol.skip_reason,
            ol.tc_compra,
            ol.tc_venta,
            ol.sent_at AT TIME ZONE 'America/Lima' AS sent_at_lima,
            ol.gmail_message_id,
            ep.razon_social,
            ep.nombre_contacto,
            ep.cargo,
            ep.ruc,
            ep.estado_email,
            ep.estado_com,
            ep.score,
            rl.clasificacion   AS resp_clasificacion,
            rl.snippet         AS resp_snippet,
            rl.recibido_at AT TIME ZONE 'America/Lima' AS resp_recibido_lima
        FROM outreach_log ol
        LEFT JOIN ec_prospectos ep ON ep.id = ol.prospecto_id
        LEFT JOIN LATERAL (
            SELECT clasificacion, snippet, recibido_at
            FROM response_log
            WHERE email = ol.email
            ORDER BY recibido_at DESC
            LIMIT 1
        ) rl ON TRUE
        WHERE {where_sql}
        ORDER BY ol.sent_at DESC
        LIMIT :limit OFFSET :offset
    """
    params["limit"]  = per_page
    params["offset"] = offset

    try:
        total = _scalar(count_sql, (), default=None)
        if total is None:
            # outreach_log no disponible: intentar logs locales
            from app.services import log_reader
            return log_reader.get_contactos_page_from_logs(
                page=page, per_page=per_page,
                fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
                bandeja=bandeja, resultado=resultado, busqueda=busqueda,
            )

        result = db.session.execute(db.text(rows_sql), params)
        rows = []
        for r in result.fetchall():
            d = dict(r._mapping)
            for k in ("sent_at_lima", "resp_recibido_lima"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].strftime("%Y-%m-%d %H:%M")
            rows.append(d)

        return {
            "disponible": True,
            "fuente": "outreach_log",
            "fuente_descripcion": "outreach_log (worker PostgreSQL)",
            "rows":     rows,
            "total":    int(total),
            "page":     page,
            "per_page": per_page,
            "pages":    max(1, -(-int(total) // per_page)),
        }
    except Exception as e:
        log.warning("[prospeccion_repo] get_contactos_page fallo: %s", e)
        # Intentar logs locales como ultimo recurso
        try:
            from app.services import log_reader
            return log_reader.get_contactos_page_from_logs(
                page=page, per_page=per_page,
                fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
                bandeja=bandeja, resultado=resultado, busqueda=busqueda,
            )
        except Exception as e2:
            log.warning("[prospeccion_repo] log_reader fallback fallo: %s", e2)
            return {"disponible": False, "rows": [], "total": 0, "page": page, "per_page": per_page, "error": str(e)}


def get_contacto_timeline(email):
    """
    Cronologia completa de un contacto: envios, respuestas y cambios de estado.
    Fuente 1: outreach_log + response_log + prospect_state_log (PostgreSQL worker).
    Fuente 2 (fallback): archivos de log locales en ~/Desktop/Prospeccion/.
    No reconstruye el cuerpo del mensaje si no esta almacenado.
    """
    try:
        envios = _rows("""
            SELECT
                ol.id, ol.bandeja, ol.stage, ol.subject, ol.status,
                ol.skip_reason, ol.tc_compra, ol.tc_venta,
                ol.sent_at AT TIME ZONE 'America/Lima' AS sent_at_lima,
                ol.gmail_message_id,
                ar.agent, ar.status AS run_status
            FROM outreach_log ol
            LEFT JOIN agent_runs ar ON ar.id = ol.agent_run_id
            WHERE ol.email = :0
            ORDER BY ol.sent_at DESC
            LIMIT 100
        """, (email,))

        for e in envios:
            if e.get("sent_at_lima") and hasattr(e["sent_at_lima"], "strftime"):
                e["sent_at_lima"] = e["sent_at_lima"].strftime("%Y-%m-%d %H:%M")

        respuestas = _rows("""
            SELECT
                id, bandeja_receptora, clasificacion, bounce_type,
                subject_original, snippet, procesado,
                recibido_at AT TIME ZONE 'America/Lima' AS recibido_lima
            FROM response_log
            WHERE email = :0
            ORDER BY recibido_at DESC
            LIMIT 50
        """, (email,))

        for r in respuestas:
            if r.get("recibido_lima") and hasattr(r["recibido_lima"], "strftime"):
                r["recibido_lima"] = r["recibido_lima"].strftime("%Y-%m-%d %H:%M")

        cambios = _rows("""
            SELECT
                psl.estado_anterior, psl.estado_nuevo, psl.motivo, psl.agente,
                psl.created_at AT TIME ZONE 'America/Lima' AS ts_lima
            FROM prospect_state_log psl
            JOIN ec_prospectos ep ON ep.id = psl.prospecto_id
            WHERE ep.email = :0
            ORDER BY psl.created_at DESC
            LIMIT 50
        """, (email,))

        for c in cambios:
            if c.get("ts_lima") and hasattr(c["ts_lima"], "strftime"):
                c["ts_lima"] = c["ts_lima"].strftime("%Y-%m-%d %H:%M")

        prospecto = _row("""
            SELECT id, ruc, razon_social, nombre_contacto, cargo, telefono,
                   provincia, rubro, sector, estado_email, estado_com,
                   score, prioridad, fecha_ult_contacto
            FROM ec_prospectos
            WHERE email = :0
            LIMIT 1
        """, (email,))

        fuente_final = "outreach_log"
        # Si no hay envios en DB, complementar con logs locales
        if not envios:
            try:
                from app.services import log_reader
                log_data = log_reader.get_contacto_timeline_from_logs(email)
                if log_data.get('envios'):
                    envios = log_data['envios']
                    fuente_final = "logs_locales"
                    if not prospecto:
                        prospecto = log_data.get('prospecto')
                    # Anotar rebote si consta en logs
                    rebote = log_data.get('rebote')
                    if rebote and not respuestas:
                        respuestas = [{
                            'id': None,
                            'bandeja_receptora': rebote.get('cuenta'),
                            'clasificacion': 'bounce_' + rebote.get('tipo', 'hard'),
                            'bounce_type': rebote.get('tipo'),
                            'subject_original': None,
                            'snippet': rebote.get('motivo'),
                            'procesado': 1,
                            'recibido_lima': rebote.get('fecha'),
                            'fuente': 'limpiar_bandejas_resultado.json',
                        }]
            except Exception as e2:
                log.debug("[prospeccion_repo] log_reader timeline fallback: %s", e2)

        return {
            "disponible": True,
            "fuente": fuente_final,
            "email":      email,
            "prospecto":  prospecto,
            "envios":     envios,
            "respuestas": respuestas,
            "cambios":    cambios,
        }
    except Exception as e:
        log.warning("[prospeccion_repo] get_contacto_timeline fallo: %s", e)
        # Fallback completo a logs locales
        try:
            from app.services import log_reader
            return log_reader.get_contacto_timeline_from_logs(email)
        except Exception as e2:
            return {"disponible": False, "email": email, "error": str(e)}


# ── Actividad real de agentes ──────────────────────────────────────────────────

def get_actividad_real() -> list:
    """
    Última ejecución registrada por agente + heartbeat actual.
    No infiere actividad si no hay runs — campo 'sin_registro' indica ausencia real.
    """
    heartbeats = {
        r["agent"]: r for r in _rows(
            "SELECT agent, last_seen, status, pid, hostname FROM agent_heartbeat"
        )
    }

    # Un row por agente con su última ejecución
    runs = _rows("""
        SELECT DISTINCT ON (agent)
            agent, status, started_at, finished_at,
            records_in, records_out, actions_taken, error_msg
        FROM agent_runs
        ORDER BY agent, started_at DESC
    """)

    now = datetime.utcnow()
    result = []

    for r in runs:
        hb = heartbeats.get(r["agent"], {})
        last_seen = hb.get("last_seen")

        # Convertir datetimes
        for field in ("started_at", "finished_at"):
            v = r.get(field)
            if v and hasattr(v, "strftime"):
                r[field] = v.strftime("%Y-%m-%d %H:%M")

        if last_seen and hasattr(last_seen, "replace"):
            age_s = int((now - last_seen.replace(tzinfo=None)).total_seconds())
        else:
            age_s = None

        result.append({
            "agent":         r["agent"],
            "sin_registro":  False,
            "ultima_run":    r,
            "heartbeat_status": hb.get("status", "offline"),
            "age_seconds":   age_s,
            "hostname":      hb.get("hostname"),
            "pid":           hb.get("pid"),
        })

    # Agentes con heartbeat pero sin runs
    agentes_con_run = {r["agent"] for r in runs}
    for agent, hb in heartbeats.items():
        if agent in agentes_con_run or agent == "orchestrator":
            continue
        last_seen = hb.get("last_seen")
        age_s = None
        if last_seen and hasattr(last_seen, "replace"):
            age_s = int((now - last_seen.replace(tzinfo=None)).total_seconds())
        result.append({
            "agent":         agent,
            "sin_registro":  True,
            "ultima_run":    None,
            "heartbeat_status": hb.get("status", "offline"),
            "age_seconds":   age_s,
            "hostname":      hb.get("hostname"),
            "pid":           hb.get("pid"),
        })

    return result


# ── Respuestas y pendientes ────────────────────────────────────────────────────

def get_respuestas_pendientes(limit: int = 50) -> dict:
    """
    Respuestas sin procesar (response_log.procesado = 0) y leads en espera
    (lead_pipeline.notificado = 0). Separados por tipo para atención directa.
    """
    respuestas = _rows("""
        SELECT
            rl.id, rl.email, rl.bandeja_receptora, rl.clasificacion,
            rl.bounce_type, rl.subject_original, rl.snippet, rl.procesado,
            rl.recibido_at AT TIME ZONE 'America/Lima' AS recibido_lima,
            ep.razon_social, ep.nombre_contacto, ep.estado_com
        FROM response_log rl
        LEFT JOIN ec_prospectos ep ON ep.email = rl.email
        WHERE rl.procesado = 0
        ORDER BY rl.recibido_at DESC
        LIMIT :0
    """, (limit,))

    for r in respuestas:
        if r.get("recibido_lima") and hasattr(r["recibido_lima"], "strftime"):
            r["recibido_lima"] = r["recibido_lima"].strftime("%Y-%m-%d %H:%M")

    leads = _rows("""
        SELECT
            lp.id, lp.email, lp.tipo, lp.subject, lp.bandeja_receptora,
            lp.notificado, lp.webhook_ok, lp.notas,
            lp.created_at AT TIME ZONE 'America/Lima' AS ts_lima,
            ep.razon_social, ep.nombre_contacto, ep.estado_com
        FROM lead_pipeline lp
        LEFT JOIN ec_prospectos ep ON ep.id = lp.prospecto_id
        WHERE lp.notificado = 0
        ORDER BY lp.created_at DESC
        LIMIT :0
    """, (limit,))

    for l in leads:
        if l.get("ts_lima") and hasattr(l["ts_lima"], "strftime"):
            l["ts_lima"] = l["ts_lima"].strftime("%Y-%m-%d %H:%M")

    return {
        "disponible":        True,
        "respuestas_sin_procesar": respuestas,
        "leads_pendientes":  leads,
        "total_respuestas":  len(respuestas),
        "total_leads":       len(leads),
    }


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


# ══════════════════════════════════════════════════════════════════════════════
# CAMP_* — Tablas de envios de campana importados manualmente
# Fuente: archivos de log subidos via panel de importacion.
# Prioridad sobre log_reader (local) y outreach_log (worker).
# ══════════════════════════════════════════════════════════════════════════════

def _camp_tables_exist():
    """True si la tabla camp_envio ya existe en la DB."""
    try:
        db.session.execute(db.text("SELECT 1 FROM camp_envio LIMIT 1"))
        return True
    except Exception:
        return False


def _camp_has_data():
    """True si camp_envio tiene al menos un registro."""
    try:
        n = db.session.execute(db.text("SELECT COUNT(*) FROM camp_envio")).scalar()
        return (n or 0) > 0
    except Exception:
        return False


def get_camp_stats():
    """
    KPIs del modulo de campanas importadas.
    Distingue contactos unicos, intentos, rebotes conocidos y ultima importacion.
    """
    try:
        row = db.session.execute(db.text("""
            SELECT
                COUNT(*)                            AS total_intentos,
                COUNT(DISTINCT email)               AS contactos_unicos,
                COUNT(DISTINCT fuente_archivo)      AS archivos_fuente,
                MAX(enviado_at)                     AS ultimo_envio,
                MIN(enviado_at)                     AS primer_envio
            FROM camp_envio
        """)).fetchone()

        rb = db.session.execute(db.text("""
            SELECT
                COUNT(*)              AS total_rebotes,
                COUNT(DISTINCT email) AS emails_rebotados
            FROM camp_rebote
        """)).fetchone()

        imp = db.session.execute(db.text("""
            SELECT importado_at, filename, total_importados
            FROM camp_importacion
            ORDER BY importado_at DESC
            LIMIT 1
        """)).fetchone()

        # Cuantos rebotes tienen al menos un envio registrado
        rebotes_con_envio = 0
        try:
            rebotes_con_envio = db.session.execute(db.text("""
                SELECT COUNT(DISTINCT cr.email)
                FROM camp_rebote cr
                WHERE EXISTS (SELECT 1 FROM camp_envio ce WHERE ce.email = cr.email)
            """)).scalar() or 0
        except Exception:
            pass

        r  = dict(row._mapping)   if row else {}
        rb = dict(rb._mapping)    if rb  else {}
        im = dict(imp._mapping)   if imp else {}

        for k in ('ultimo_envio', 'primer_envio'):
            if r.get(k) and hasattr(r[k], 'strftime'):
                r[k] = r[k].strftime('%Y-%m-%d')
        if im.get('importado_at') and hasattr(im['importado_at'], 'strftime'):
            im['importado_at'] = im['importado_at'].strftime('%Y-%m-%d %H:%M')

        # Rebotes adicionales (sin envio registrado en camp_envio)
        rebotes_sin_envio = rb.get('emails_rebotados', 0) - rebotes_con_envio

        # Contactos con al menos un rebote dentro del historial importado
        rebotes_en_historial = 0
        try:
            rebotes_en_historial = db.session.execute(db.text("""
                SELECT COUNT(DISTINCT cr.email)
                FROM camp_rebote cr
                INNER JOIN camp_envio ce ON ce.email = cr.email
            """)).scalar() or 0
        except Exception:
            pass

        return {
            'disponible':              True,
            'total_intentos':          r.get('total_intentos', 0),
            'contactos_unicos':        r.get('contactos_unicos', 0),
            'archivos_fuente':         r.get('archivos_fuente', 0),
            'primer_envio':            r.get('primer_envio'),
            'ultimo_envio':            r.get('ultimo_envio'),
            'total_rebotes':           rb.get('total_rebotes', 0),
            'emails_rebotados':        rb.get('emails_rebotados', 0),
            'rebotes_con_envio':       rebotes_con_envio,    # rebotes + envio en historial
            'rebotes_sin_envio':       rebotes_sin_envio,    # rebotes sin envio registrado
            'rebotes_en_historial':    rebotes_en_historial, # contactos con rebote en camp_envio
            'ultima_importacion':      im.get('importado_at'),
            'ultimo_archivo_imp':      im.get('filename'),
        }
    except Exception as exc:
        log.warning("[prospeccion_repo] get_camp_stats: %s", exc)
        return {'disponible': False}


def get_camp_contactos_page(
    page=1,
    per_page=50,
    fecha_desde=None,
    fecha_hasta=None,
    bandeja=None,
    campana=None,
    resultado=None,
    busqueda=None,
    rubro=None,
):
    """
    Tabla de CONTACTOS UNICOS desde camp_envio.
    Una fila por email; enriquecida con datos comerciales de camp_prospecto o prospectos.
    """
    # Filtros pre-GROUP BY (WHERE sobre columnas individuales)
    pre_where  = ["1=1"]
    # Filtros post-GROUP BY (HAVING sobre agregados)
    having_parts = []
    params = {}

    if campana:
        pre_where.append("ce.proceso = :campana")
        params['campana'] = campana
    if bandeja:
        pre_where.append("ce.bandeja LIKE :bandeja")
        params['bandeja'] = '%' + bandeja + '%'
    if busqueda:
        pre_where.append("(ce.email LIKE :q OR ce.empresa LIKE :q OR cp.nombre_contacto LIKE :q OR cp.telefono LIKE :q)")
        params['q'] = '%' + busqueda + '%'
    if rubro:
        pre_where.append("cp.rubro LIKE :rubro")
        params['rubro'] = '%' + rubro + '%'
    if fecha_desde:
        having_parts.append("MAX(ce.enviado_at) >= :fdesde")
        params['fdesde'] = fecha_desde
    if fecha_hasta:
        having_parts.append("MAX(ce.enviado_at) <= :fhasta")
        params['fhasta'] = fecha_hasta + ' 23:59:59'
    if resultado == 'rebotado':
        having_parts.append("MAX(cr.tipo) IS NOT NULL")
    elif resultado == 'OK':
        having_parts.append("MAX(CASE WHEN ce.resultado_log = 'OK' THEN 1 END) IS NOT NULL")
    elif resultado == 'FAIL':
        having_parts.append("MAX(CASE WHEN ce.resultado_log = 'FAIL' THEN 1 END) IS NOT NULL")

    where_clause  = 'WHERE ' + ' AND '.join(pre_where)
    having_clause = ('HAVING ' + ' AND '.join(having_parts)) if having_parts else ''

    try:
        count_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT ce.email
                FROM camp_envio ce
                LEFT JOIN camp_rebote cr ON cr.email = ce.email
                LEFT JOIN camp_prospecto cp ON cp.email = ce.email
                {where_clause}
                GROUP BY ce.email
                {having_clause}
            ) sub
        """
        total = db.session.execute(db.text(count_sql), params).scalar() or 0

        rows_sql = f"""
            SELECT
                ce.email,
                MAX(CASE WHEN ce.empresa IS NOT NULL THEN ce.empresa END) AS empresa,
                COUNT(*)                                        AS total_intentos,
                MAX(ce.enviado_at)                              AS ultimo_contacto,
                MIN(ce.enviado_at)                              AS primer_contacto,
                MAX(ce.bandeja)                                 AS bandeja,
                MAX(ce.proceso)                                 AS proceso,
                MAX(cr.tipo)                                    AS rebote_tipo,
                MAX(cr.motivo)                                  AS rebote_motivo,
                MAX(cr.detectado_at)                            AS rebote_fecha,
                MAX(cp.nombre_contacto)                         AS nombre_contacto,
                MAX(cp.cargo)                                   AS cargo,
                MAX(cp.telefono)                                AS telefono,
                MAX(cp.rubro)                                   AS rubro,
                MAX(cp.ruc)                                     AS ruc,
                MAX(cp.provincia)                               AS provincia
            FROM camp_envio ce
            LEFT JOIN camp_rebote cr ON cr.email = ce.email
            LEFT JOIN camp_prospecto cp ON cp.email = ce.email
            {where_clause}
            GROUP BY ce.email
            {having_clause}
            ORDER BY MAX(ce.enviado_at) DESC
            LIMIT :limit OFFSET :offset
        """
        params['limit']  = per_page
        params['offset'] = (page - 1) * per_page

        rows = []
        for r in db.session.execute(db.text(rows_sql), params).fetchall():
            d = dict(r._mapping)
            for k in ('ultimo_contacto', 'primer_contacto', 'rebote_fecha'):
                if d.get(k) and hasattr(d[k], 'strftime'):
                    d[k] = d[k].strftime('%Y-%m-%d %H:%M')
            rows.append(d)

        import math
        return {
            'disponible':  True,
            'fuente':      'camp_envio',
            'fuente_desc': 'Envios importados (camp_envio)',
            'rows':        rows,
            'total':       int(total),
            'page':        page,
            'per_page':    per_page,
            'pages':       max(1, math.ceil(int(total) / per_page)),
        }
    except Exception as exc:
        log.warning("[prospeccion_repo] get_camp_contactos_page: %s", exc)
        return {
            'disponible': False, 'rows': [], 'total': 0,
            'page': page, 'per_page': per_page, 'pages': 1,
            'error': str(exc),
        }


def get_camp_contacto_historial(email):
    """
    Historial completo de intentos de contacto y rebotes para un email.
    Los rebotes se presentan separados con nota de que la relacion es por email,
    no por envio especifico (a menos que las fechas lo confirmen).
    """
    el = email.lower()
    try:
        envios_rows = db.session.execute(db.text("""
            SELECT
                enviado_at, bandeja, proceso, resultado_log, fuente_archivo
            FROM camp_envio
            WHERE email = :email
            ORDER BY enviado_at DESC
        """), {'email': el}).fetchall()

        rebotes_rows = db.session.execute(db.text("""
            SELECT tipo, motivo, detectado_at, bandeja_detectora, msg_id, fuente_archivo
            FROM camp_rebote
            WHERE email = :email
            ORDER BY detectado_at DESC
        """), {'email': el}).fetchall()

        empresa_row = db.session.execute(db.text("""
            SELECT MAX(CASE WHEN empresa IS NOT NULL THEN empresa END)
            FROM camp_envio WHERE email = :email
        """), {'email': el}).scalar()

        # Datos comerciales de camp_prospecto
        prospecto_row = None
        try:
            pr = db.session.execute(db.text("""
                SELECT ruc, razon_social, nombre_contacto, cargo, telefono, rubro, provincia
                FROM camp_prospecto WHERE email = :email
            """), {'email': el}).fetchone()
            if pr:
                prospecto_row = dict(pr._mapping)
        except Exception:
            pass

        envios = []
        for r in envios_rows:
            d = dict(r._mapping)
            if d.get('enviado_at') and hasattr(d['enviado_at'], 'strftime'):
                d['enviado_at'] = d['enviado_at'].strftime('%Y-%m-%d %H:%M')
            envios.append(d)

        rebotes = []
        for r in rebotes_rows:
            d = dict(r._mapping)
            if d.get('detectado_at') and hasattr(d['detectado_at'], 'strftime'):
                d['detectado_at'] = d['detectado_at'].strftime('%Y-%m-%d %H:%M')
            rebotes.append(d)

        # Nota solo cuando hay rebotes
        nota = None
        if rebotes:
            has_evidence = any(
                r.get('detectado_at') and e.get('enviado_at') and
                abs((len(r.get('detectado_at','')) + len(e.get('enviado_at',''))))  > 0
                for r in rebotes for e in envios
            ) if envios else False
            nota = (
                'Rebote vinculado por email. No es posible confirmarlo con un envio especifico '
                'del historial importado sin evidencia adicional (ej: mismo msg-id).'
            )

        return {
            'disponible':   True,
            'fuente':       'camp_envio',
            'email':        el,
            'empresa':      empresa_row,
            'prospecto':    prospecto_row,
            'envios':       envios,
            'rebotes':      rebotes,
            'nota_rebote':  nota,
        }
    except Exception as exc:
        log.warning("[prospeccion_repo] get_camp_contacto_historial: %s", exc)
        return {'disponible': False, 'email': el, 'error': str(exc)}


def get_camp_importaciones(limit=20):
    """Historial de importaciones realizadas."""
    try:
        rows = db.session.execute(db.text("""
            SELECT filename, tipo, importado_at,
                   total_parseados, total_importados, total_duplicados, total_descartados
            FROM camp_importacion
            ORDER BY importado_at DESC
            LIMIT :limit
        """), {'limit': limit}).fetchall()

        result = []
        for r in rows:
            d = dict(r._mapping)
            if d.get('importado_at') and hasattr(d['importado_at'], 'strftime'):
                d['importado_at'] = d['importado_at'].strftime('%Y-%m-%d %H:%M')
            result.append(d)

        return {'disponible': True, 'importaciones': result}
    except Exception as exc:
        log.warning("[prospeccion_repo] get_camp_importaciones: %s", exc)
        return {'disponible': False, 'importaciones': [], 'error': str(exc)}


def sync_camp_prospecto_from_prospectos():
    """
    Sincroniza camp_prospecto desde la tabla prospectos local (si existe y tiene datos).
    Usa INSERT OR REPLACE para actualizar registros existentes.
    Vincula por email exacto. Retorna {sincronizados, fuente}.
    """
    try:
        # Verificar si prospectos tiene datos
        ct = db.session.execute(db.text("SELECT COUNT(*) FROM prospectos")).scalar() or 0
        if ct == 0:
            return {'sincronizados': 0, 'fuente': 'prospectos_vacia'}

        dialect = db.engine.dialect.name
        if dialect == 'sqlite':
            upsert = """
                INSERT OR REPLACE INTO camp_prospecto
                    (email, ruc, razon_social, nombre_contacto, cargo, telefono,
                     rubro, provincia, fuente, actualizado_at)
                SELECT
                    LOWER(email), ruc, razon_social, nombre_contacto, cargo, telefono,
                    rubro, provincia, 'prospectos', datetime('now')
                FROM prospectos
                WHERE email IS NOT NULL AND email != ''
            """
        else:
            upsert = """
                INSERT INTO camp_prospecto
                    (email, ruc, razon_social, nombre_contacto, cargo, telefono,
                     rubro, provincia, fuente, actualizado_at)
                SELECT
                    LOWER(email), ruc, razon_social, nombre_contacto, cargo, telefono,
                    rubro, provincia, 'prospectos', NOW()
                FROM prospectos
                WHERE email IS NOT NULL AND email != ''
                ON CONFLICT (email) DO UPDATE SET
                    ruc=EXCLUDED.ruc, razon_social=EXCLUDED.razon_social,
                    nombre_contacto=EXCLUDED.nombre_contacto, cargo=EXCLUDED.cargo,
                    telefono=EXCLUDED.telefono, rubro=EXCLUDED.rubro,
                    provincia=EXCLUDED.provincia, fuente=EXCLUDED.fuente,
                    actualizado_at=EXCLUDED.actualizado_at
            """
        db.session.execute(db.text(upsert))
        db.session.commit()

        ct_new = db.session.execute(db.text("SELECT COUNT(*) FROM camp_prospecto")).scalar() or 0
        log.info("[prospeccion_repo] sync_camp_prospecto: %d registros sincronizados", ct_new)
        return {'sincronizados': ct_new, 'fuente': 'prospectos'}
    except Exception as exc:
        db.session.rollback()
        log.warning("[prospeccion_repo] sync_camp_prospecto_from_prospectos: %s", exc)
        return {'sincronizados': 0, 'fuente': 'error', 'error': str(exc)}


def get_camp_prospeccion_cobertura():
    """
    Devuelve el porcentaje de emails en camp_envio que tienen datos en camp_prospecto.
    Utile para el indicador 'historial parcialmente importado'.
    """
    try:
        total    = db.session.execute(db.text("SELECT COUNT(DISTINCT email) FROM camp_envio")).scalar() or 0
        con_data = db.session.execute(db.text("""
            SELECT COUNT(DISTINCT ce.email)
            FROM camp_envio ce
            INNER JOIN camp_prospecto cp ON cp.email = ce.email
            WHERE cp.nombre_contacto IS NOT NULL OR cp.rubro IS NOT NULL
        """)).scalar() or 0
        archivos_imp = db.session.execute(db.text("SELECT COUNT(*) FROM camp_importacion WHERE tipo='log_envio'")).scalar() or 0
        return {
            'contactos_unicos':    total,
            'con_datos_comerciales': con_data,
            'archivos_importados': archivos_imp,
        }
    except Exception as exc:
        log.warning("[prospeccion_repo] get_camp_prospeccion_cobertura: %s", exc)
        return {'contactos_unicos': 0, 'con_datos_comerciales': 0, 'archivos_importados': 0}

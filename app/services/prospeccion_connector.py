"""
prospeccion_connector.py — Conector de Mission Control → ecosistema.db

Lee métricas del ecosistema de prospección (SQLite local) y las expone
al backend Flask para que Mission Control las muestre sin leer Google Sheets.

Arquitectura:
  DEV (mismo servidor):  Lee ecosistema.db directamente vía SQLite.
  PROD (Render separado): El worker postea heartbeats/métricas a Flask API.
    → En ese caso, este conector lee de las tablas Flask (PostgreSQL).
    → Ver: /api/leads/heartbeat endpoint para la transición.

GAP CONOCIDO (documentado):
  Si en producción el worker y la app Flask viven en Render Backgrounds
  separados (servicios distintos), ecosistema.db NO está accesible aquí.
  Resolver ANTES del deploy 24/7 eligiendo una de estas opciones:
    A) Mismo servicio Render → worker escribe ecosistema.db, Flask lo lee.
    B) Worker postea heartbeats a /api/leads/heartbeat → Flask guarda en PG.
  Por ahora la app funciona: si la ruta al DB no existe, retorna datos vacíos.
"""
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

# Ruta al DB del ecosistema de prospección.
# Puede configurarse vía env var ECOSISTEMA_DB_PATH en producción.
_DEFAULT_DB = Path(__file__).parents[3] / ".." / ".." / ".." / "Prospeccion" / "ecosistema.db"
_DEFAULT_DB = _DEFAULT_DB.resolve()

ECOSISTEMA_DB_PATH = Path(os.environ.get("ECOSISTEMA_DB_PATH", str(_DEFAULT_DB)))


def _get_conn():
    """Conexión SQLite read-only al ecosistema.db."""
    if not ECOSISTEMA_DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{ECOSISTEMA_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        log.warning(f"[prospeccion_connector] No se pudo conectar a ecosistema.db: {e}")
        return None


def get_master_stats() -> dict:
    """
    Estadísticas del PROSPECTOS_MASTER desde ecosistema.db.
    Retorna dict vacío si el DB no está disponible (modo offline).
    """
    conn = _get_conn()
    if conn is None:
        return {"disponible": False}

    try:
        cur = conn.cursor()

        total = cur.execute("SELECT COUNT(*) FROM prospectos").fetchone()[0]
        validos = cur.execute(
            "SELECT COUNT(*) FROM prospectos WHERE estado_email='valido'"
        ).fetchone()[0]
        sin_validar = cur.execute(
            "SELECT COUNT(*) FROM prospectos WHERE estado_email='sin_validar'"
        ).fetchone()[0]
        rebotados = cur.execute(
            "SELECT COUNT(*) FROM prospectos WHERE estado_email='correo_rebotado'"
        ).fetchone()[0]
        alta = cur.execute(
            "SELECT COUNT(*) FROM prospectos WHERE prioridad='ALTA'"
        ).fetchone()[0]
        clientes = cur.execute(
            "SELECT COUNT(*) FROM prospectos WHERE estado_com='cliente'"
        ).fetchone()[0]

        # ready_for_outreach: valido + no bloqueado comercialmente
        _stop = ("no_contactar", "correo_rebotado", "cliente", "interesado",
                 "solicita_cotizacion", "solicita_informacion", "solicita_llamada",
                 "solicita_whatsapp", "no_interesado", "persona_incorrecta",
                 "referido", "rebotado")
        placeholders = ",".join("?" * len(_stop))
        ready = cur.execute(
            f"SELECT COUNT(*) FROM prospectos WHERE estado_email='valido' "
            f"AND estado_com NOT IN ({placeholders})",
            _stop
        ).fetchone()[0]

        # Última sincronización
        last_sync = None
        try:
            row = cur.execute(
                "SELECT value FROM sync_state WHERE key='last_full_sync'"
            ).fetchone()
            last_sync = row["value"] if row else None
        except Exception:
            pass

        return {
            "disponible":     True,
            "total":          total,
            "validos":        validos,
            "sin_validar":    sin_validar,
            "rebotados":      rebotados,
            "clientes":       clientes,
            "prioridad_alta": alta,
            "ready_for_outreach": ready,
            "requires_validation": sin_validar,
            "last_full_sync": last_sync,
        }
    except Exception as e:
        log.warning(f"[prospeccion_connector] Error leyendo master_stats: {e}")
        return {"disponible": False, "error": str(e)}
    finally:
        conn.close()


def get_agent_runs(limit: int = 20) -> list:
    """
    Últimas ejecuciones de agentes desde agent_runs de ecosistema.db.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT agent, status, started_at, ended_at, records_in,
                   records_out, error_msg
            FROM agent_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.debug(f"[prospeccion_connector] agent_runs no disponible: {e}")
        return []
    finally:
        conn.close()


def get_outreach_stats_today() -> dict:
    """Emails enviados hoy desde el sistema de prospección."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        row = conn.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as enviados,
                   SUM(CASE WHEN status='bounced' THEN 1 ELSE 0 END) as rebotados
            FROM outreach_attempt
            WHERE DATE(created_at) = ?
            """,
            (today,)
        ).fetchone()
        if row:
            return {"total": row[0] or 0, "enviados": row[1] or 0, "rebotados": row[2] or 0}
        return {"total": 0, "enviados": 0, "rebotados": 0}
    except Exception as e:
        log.debug(f"[prospeccion_connector] outreach_stats no disponible: {e}")
        return {"total": 0, "enviados": 0, "rebotados": 0}
    finally:
        conn.close()


def get_runtime_config() -> dict:
    """Lee runtime_config de ecosistema.db (TC, DRY_RUN, etc.)."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute("SELECT key, value FROM runtime_config").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        log.debug(f"[prospeccion_connector] runtime_config no disponible: {e}")
        return {}
    finally:
        conn.close()


def get_prospeccion_kpis() -> dict:
    """
    KPIs consolidados del ecosistema de prospección.
    Combina master_stats + outreach_today + runtime_config.
    """
    master = get_master_stats()
    outreach = get_outreach_stats_today()
    config = get_runtime_config()

    dry_run = config.get("dry_run", "true").lower() in ("true", "1", "yes")
    tc_compra = config.get("tc_compra", "")
    tc_venta = config.get("tc_venta", "")
    tc_ts = config.get("tc_updated_at", "")

    # Frescura del TC
    tc_fresco = False
    tc_age_min = None
    if tc_ts:
        try:
            ts = datetime.fromisoformat(tc_ts)
            age = datetime.now() - ts
            tc_age_min = int(age.total_seconds() / 60)
            tc_fresco = age < timedelta(hours=3)
        except Exception:
            pass

    return {
        "master": master,
        "outreach_hoy": outreach,
        "dry_run": dry_run,
        "tc": {
            "compra": tc_compra,
            "venta": tc_venta,
            "updated_at": tc_ts,
            "fresco": tc_fresco,
            "age_min": tc_age_min,
        },
        "db_disponible": master.get("disponible", False),
    }

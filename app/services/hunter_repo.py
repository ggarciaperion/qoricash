"""
hunter_repo.py — Repositorio Flask para datos del worker Hunter (personas naturales).

Lee desde la tabla hunter_snapshots (snapshot empujado por scheduler_hunter.py
vía POST /api/sync/hunter cada 5 minutos).

La única función pública es get_hunter_pipeline_cards() que devuelve
el dict listo para jsonify() en /agentes/api/hunter/pipeline-cards.

Fail-safe: si no hay snapshot, retorna un dict vacío con valores cero
(igual que prospeccion_repo.py cuando las tablas no existen).
"""
import json
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

_OFFLINE_MIN = 10   # Scheduler Hunter offline si heartbeat > 10 min


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_hunter_pipeline_cards() -> dict:
    """
    Retorna el estado actual del pipeline Hunter para las 7 tarjetas del panel.

    Estructura de retorno:
      {
        "scheduler": {"online": bool, "status": str, "dry_run": bool, "ts": str},
        "lote":      {"lote_id", "fecha", "es_hoy", "total_candidatos", "elegibles",
                      "excluidos", "pendientes", "enviados_hoy", "fuente_tab"},
        "bandejas":  [{"bandeja", "asignados", "enviados_hoy"}, ...],
        "outreach":  {"enviados_hoy", "pendientes_lote", "cap_bandeja", "cap_global"},
        "rebotes":   {"rebotes_hoy", "suprimidos_total"},
        "respuestas":{"interesados", "no_contactar", "procesados_hoy"},
        "feedback":  {"pendientes_queue", "aplicados_hoy"},
      }
    """
    try:
        from app.models.hunter_snapshot import HunterSnapshot
        snap = HunterSnapshot.query.filter_by(snapshot_key='latest').first()
    except Exception as e:
        log.debug("[hunter_repo] tabla hunter_snapshots no disponible: %s", e)
        snap = None

    if not snap:
        return _empty_response(online=False)

    try:
        data = json.loads(snap.payload)
    except Exception as e:
        log.warning("[hunter_repo] payload JSON inválido: %s", e)
        return _empty_response(online=False)

    # Determinar si el scheduler sigue online (heartbeat reciente)
    received_at = snap.received_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    edad_min = int((_now_utc() - received_at).total_seconds() / 60)
    online = edad_min < _OFFLINE_MIN

    # Scheduler
    sched = data.get('scheduler', {})
    scheduler = {
        'online':   online,
        'status':   sched.get('status', 'desconocido'),
        'dry_run':  data.get('dry_run', True),
        'edad_min': edad_min,
        'ts':       snap.received_at.isoformat() if snap.received_at else None,
        'hostname': snap.worker_hostname or sched.get('hostname', ''),
    }

    # Lote activo
    lote_raw  = data.get('lote') or {}
    lote_id   = lote_raw.get('lote_id')
    fecha_str = lote_raw.get('fecha', '')
    hoy_lima  = _today_lima()
    lote = {
        'lote_id':          lote_id,
        'fecha':            fecha_str,
        'es_hoy':           fecha_str == hoy_lima,
        'total_candidatos': lote_raw.get('total_candidatos', 0),
        'elegibles':        lote_raw.get('elegibles', 0),
        'excluidos':        lote_raw.get('excluidos', 0),
        'pendientes':       lote_raw.get('pendientes', 0),
        'enviados_hoy':     lote_raw.get('enviados_hoy', 0),
        'fuente_tab':       lote_raw.get('fuente_tab', 'Hoja 2'),
        'fuente_sheet_id':  lote_raw.get('fuente_sheet_id', ''),
    }

    # Bandejas
    bandejas = data.get('bandejas', [])

    # Outreach
    out_raw  = data.get('outreach', {})
    outreach = {
        'enviados_hoy':    out_raw.get('enviados_hoy', 0),
        'pendientes_lote': out_raw.get('pendientes_lote', 0),
        'cap_bandeja':     out_raw.get('cap_bandeja', 25),
        'cap_global':      out_raw.get('cap_global', 75),
        'omitidos_hoy':    out_raw.get('omitidos_hoy', 0),
    }

    # Rebotes
    reb_raw  = data.get('rebotes', {})
    rebotes  = {
        'rebotes_hoy':      reb_raw.get('rebotes_hoy', 0),
        'suprimidos_total': reb_raw.get('suprimidos_total', 0),
    }

    # Respuestas
    resp_raw   = data.get('respuestas', {})
    respuestas = {
        'interesados':    resp_raw.get('interesados', 0),
        'no_contactar':   resp_raw.get('no_contactar', 0),
        'procesados_hoy': resp_raw.get('procesados_hoy', 0),
    }

    # Feedback
    fb_raw   = data.get('feedback', {})
    feedback = {
        'pendientes_queue': fb_raw.get('pendientes_queue', 0),
        'aplicados_hoy':    fb_raw.get('aplicados_hoy', 0),
    }

    return {
        'scheduler':  scheduler,
        'lote':       lote,
        'bandejas':   bandejas,
        'outreach':   outreach,
        'rebotes':    rebotes,
        'respuestas': respuestas,
        'feedback':   feedback,
    }


def _today_lima() -> str:
    try:
        import zoneinfo
        lima = zoneinfo.ZoneInfo('America/Lima')
        return datetime.now(lima).strftime('%Y-%m-%d')
    except Exception:
        return datetime.utcnow().strftime('%Y-%m-%d')


def _empty_response(online: bool = False) -> dict:
    return {
        'scheduler':  {'online': online, 'status': 'sin datos', 'dry_run': True,
                       'edad_min': None, 'ts': None, 'hostname': ''},
        'lote':       {'lote_id': None, 'fecha': None, 'es_hoy': False,
                       'total_candidatos': 0, 'elegibles': 0, 'excluidos': 0,
                       'pendientes': 0, 'enviados_hoy': 0,
                       'fuente_tab': 'Hoja 2', 'fuente_sheet_id': ''},
        'bandejas':   [],
        'outreach':   {'enviados_hoy': 0, 'pendientes_lote': 0,
                       'cap_bandeja': 25, 'cap_global': 75, 'omitidos_hoy': 0},
        'rebotes':    {'rebotes_hoy': 0, 'suprimidos_total': 0},
        'respuestas': {'interesados': 0, 'no_contactar': 0, 'procesados_hoy': 0},
        'feedback':   {'pendientes_queue': 0, 'aplicados_hoy': 0},
    }

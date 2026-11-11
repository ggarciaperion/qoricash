"""
sync_api.py — Receptor de sincronización motor_sync (T1) → Panel T3

Implementa los endpoints definidos en CONTRATO_SYNC_T3.md.

Autenticación: Bearer <SYNC_SECRET> (variable de entorno).
Ambas rutas son @csrf.exempt — machine-to-machine, sin sesión de usuario.
No usar @login_required.

Endpoints:
  POST /api/sync/lote       — recibe estado completo de un lote
  POST /api/sync/heartbeat  — verifica conectividad del motor local
  POST /api/sync/agent      — recibe heartbeat de un agente (scheduler_lotes, etc.)
  GET  /api/sync/agents     — lista agentes con estado conectado / dry_run

Nunca registra SYNC_SECRET ni datos sensibles en logs.
"""
import hmac
import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app

from app.extensions import db, csrf

log = logging.getLogger(__name__)

sync_api_bp = Blueprint('sync_api', __name__, url_prefix='/api/sync')


# ─────────────────────────────────────────────────────────────────────────────
# Auth helper
# ─────────────────────────────────────────────────────────────────────────────

def _check_bearer() -> bool:
    """
    Valida Authorization: Bearer <SYNC_SECRET> usando comparación de tiempo
    constante (hmac.compare_digest) para evitar timing attacks.

    Retorna True si el token es correcto y SYNC_SECRET está configurado.
    """
    secret = os.environ.get('SYNC_SECRET', '').strip()
    if not secret:
        log.warning('[sync_api] SYNC_SECRET no configurado — rechazando request')
        return False

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False

    token = auth_header[len('Bearer '):]
    # hmac.compare_digest previene timing attacks
    return hmac.compare_digest(token.encode(), secret.encode())


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/sync/lote
# ─────────────────────────────────────────────────────────────────────────────

@sync_api_bp.route('/lote', methods=['POST'])
@csrf.exempt
def sync_lote():
    """
    Recibe el estado completo de un lote (resumen + items) desde motor_sync.

    Payload esperado (CONTRATO_SYNC_T3.md):
      {
        "schema_version": "1.0",
        "emitido_en": "2026-11-09T18:30:00+00:00",
        "lote": { ... },
        "items": [ ... ]
      }

    Retorna:
      200: {"status":"ok","lote_id":"...","items_procesados":N}
      400: {"error":"..."}
      401: {"error":"Unauthorized"}
    """
    if not _check_bearer():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Payload JSON requerido'}), 400

    schema_version = data.get('schema_version')
    if schema_version != '1.0':
        return jsonify({'error': f'schema_version desconocida: {schema_version!r}'}), 400

    emitido_en = data.get('emitido_en')
    if not emitido_en:
        return jsonify({'error': 'Campo emitido_en requerido'}), 400

    lote_data = data.get('lote')
    if not lote_data or not isinstance(lote_data, dict):
        return jsonify({'error': 'Campo lote requerido (objeto)'}), 400

    items = data.get('items', [])
    if not isinstance(items, list):
        return jsonify({'error': 'Campo items debe ser lista'}), 400

    lote_id = lote_data.get('lote_id')
    if not lote_id:
        return jsonify({'error': 'lote.lote_id requerido'}), 400

    try:
        from app.services.sync_repo import upsert_lote, upsert_items

        lote_pk, actualizado, msg_lote, skip_code = upsert_lote(lote_data, emitido_en)

        # Payload más antiguo que el almacenado → 409 (motor_sync no reintentará)
        if skip_code == '409':
            log.info(f'[sync_api] lote {lote_id} rechazado (snapshot antiguo): {msg_lote}')
            db.session.rollback()
            return jsonify({
                'status': 'rejected',
                'lote_id': lote_id,
                'detalle': msg_lote,
            }), 409

        if lote_pk is None:
            log.warning(f'[sync_api] upsert_lote falló para {lote_id}: {msg_lote}')
            db.session.rollback()
            return jsonify({'error': f'Error procesando lote: {msg_lote}'}), 400

        # Mismo emitido_en → idempotente (ya fue aplicado en un envío previo)
        if skip_code == '200':
            log.debug(f'[sync_api] lote {lote_id} idempotente: {msg_lote}')
            db.session.commit()
            return jsonify({
                'status':           'ok',
                'lote_id':          lote_id,
                'items_procesados': 0,
            }), 200

        # Payload nuevo → procesar items atómicamente junto con la cabecera
        items_procesados = upsert_items(lote_pk, items, emitido_en) if items else 0
        db.session.commit()

        log.info(
            f'[sync_api] lote {lote_id} guardado — '
            f'actualizado={actualizado} items={items_procesados} '
            f'emitido_en={emitido_en}'
        )

        return jsonify({
            'status':           'ok',
            'lote_id':          lote_id,
            'items_procesados': items_procesados,
        }), 200

    except Exception as e:
        db.session.rollback()
        log.error(f'[sync_api] error procesando lote {lote_id}: {e}')
        return jsonify({'error': 'Error interno procesando lote'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/sync/heartbeat
# ─────────────────────────────────────────────────────────────────────────────

@sync_api_bp.route('/heartbeat', methods=['POST'])
@csrf.exempt
def sync_heartbeat():
    """
    Verificación de conectividad del motor local Mac.

    Payload esperado:
      {"ts": "2026-11-09T18:30:00+00:00", "origen": "motor_sync/1.0"}

    Retorna:
      200: {"status":"ok","ts":"..."}
      401: {"error":"Unauthorized"}
    """
    if not _check_bearer():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    ts     = data.get('ts', _now_utc())
    origen = data.get('origen', 'unknown')

    try:
        from app.services.sync_repo import upsert_motor_heartbeat
        upsert_motor_heartbeat(ts, origen)
        db.session.commit()
        log.debug(f'[sync_api] heartbeat registrado ts={ts} origen={origen}')
    except Exception as e:
        db.session.rollback()
        log.error(f'[sync_api] error registrando heartbeat: {e}')
        # Responder OK de todas formas — el motor no debe bloquearse por esto
        # (el panel mostrará "sin conexión" cuando no haya heartbeat reciente)

    return jsonify({'status': 'ok', 'ts': _now_utc()}), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/sync/agent  —  heartbeat de agente (scheduler_lotes, etc.)
# GET  /api/sync/agents —  lista agentes
# ─────────────────────────────────────────────────────────────────────────────

_HB_THRESHOLD_S = 300  # 5 min — desconectado si last_seen > umbral


@sync_api_bp.route('/agent', methods=['POST'])
@csrf.exempt
def sync_agent():
    """
    POST /api/sync/agent
    Recibe heartbeat de un agente local (scheduler_lotes, orchestrator, etc.).
    Payload: {"agent":"scheduler_lotes","status":"idle","dry_run":true}
    dry_run: booleano explícito. Si falta → NULL (desconocido).
    """
    if not _check_bearer():
        return jsonify({'error': 'Unauthorized'}), 401

    data  = request.get_json(silent=True) or {}
    agent = (data.get('agent') or '').strip()
    if not agent:
        return jsonify({'error': 'agent requerido'}), 400

    status = (data.get('status') or 'idle').strip()
    raw_dr = data.get('dry_run')
    dry_run_val = None if not isinstance(raw_dr, bool) else (1 if raw_dr else 0)
    ts = _now_utc()

    try:
        db.session.execute(db.text("""
            INSERT INTO agent_heartbeat (agent, status, last_seen, hostname, dry_run, updated_at)
            VALUES (:agent, :status, :ts, :hostname, :dry_run, :ts)
            ON CONFLICT (agent) DO UPDATE SET
                status     = EXCLUDED.status,
                last_seen  = EXCLUDED.last_seen,
                hostname   = EXCLUDED.hostname,
                dry_run    = EXCLUDED.dry_run,
                updated_at = EXCLUDED.updated_at
        """), {
            'agent':    agent,
            'status':   status,
            'ts':       ts,
            'hostname': data.get('hostname') or data.get('origen') or agent,
            'dry_run':  dry_run_val,
        })
        db.session.commit()
        log.debug(f'[sync_api] agent heartbeat: {agent} status={status} dry_run={dry_run_val}')
    except Exception as e:
        db.session.rollback()
        log.error(f'[sync_api] error guardando heartbeat de {agent}: {e}')
        return jsonify({'error': 'Error interno'}), 500

    return jsonify({'status': 'ok', 'agent': agent}), 200


@sync_api_bp.route('/agents', methods=['GET'])
@csrf.exempt
def sync_agents():
    """
    GET /api/sync/agents
    Lista todos los agentes con estado de conectividad y configuración dry_run.
    Responde sin autenticación para facilitar el polling del panel frontend.
    """
    threshold = int(request.args.get('threshold', _HB_THRESHOLD_S))
    ahora = datetime.now(timezone.utc)

    try:
        rows = db.session.execute(db.text("""
            SELECT agent, status, last_seen, pid, hostname, dry_run
            FROM agent_heartbeat
            ORDER BY last_seen DESC
        """)).fetchall()
    except Exception as e:
        log.error(f'[sync_api] error leyendo agents: {e}')
        return jsonify({'agents': [], 'threshold_segundos': threshold}), 200

    from app.services.sync_repo import _to_utc_dt
    agents = []
    for row in rows:
        d = dict(row._mapping)
        ls_dt   = _to_utc_dt(d.get('last_seen'))
        delta_s = (ahora.replace(tzinfo=None) - ls_dt).total_seconds() if ls_dt else None
        conectado = (delta_s is not None and delta_s < threshold)

        raw_dr = d.get('dry_run')
        if raw_dr is None:
            envios_habilitados, envios_estado = None, 'desconocido'
        elif raw_dr == 1:
            envios_habilitados, envios_estado = False, 'deshabilitado'
        else:
            envios_habilitados, envios_estado = True, 'habilitado'

        agents.append({
            'agent':              d.get('agent'),
            'status':             d.get('status') or '',
            'last_seen':          str(d.get('last_seen')) if d.get('last_seen') else None,
            'pid':                d.get('pid'),
            'hostname':           d.get('hostname'),
            'conectado':          conectado,
            'envios_habilitados': envios_habilitados,
            'envios_estado':      envios_estado,
            'segundos_desde_hb':  round(delta_s) if delta_s is not None else None,
        })

    return jsonify({'agents': agents, 'threshold_segundos': threshold}), 200

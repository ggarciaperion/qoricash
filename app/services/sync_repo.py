"""
sync_repo.py — Almacenamiento del receptor de sincronización motor_sync → Panel T3

Recibe payloads de motor_sync.py (T1) y los persiste en PostgreSQL compartido.

Contrato: CONTRATO_SYNC_T3.md / CONTRATO_LOTES.md

Reglas de idempotencia:
  - lote_id TEXT es la clave de upsert en ec_lotes.
  - emitido_en controla last-write-wins: si el payload recibido es más antiguo
    que el último almacenado, se ignora (no retrocede estados).
  - Items: ON CONFLICT (lote_id BIGINT, email) DO UPDATE con misma guarda.
  - Repetir el mismo sync produce el mismo resultado (idempotente).

Reglas de es_prueba:
  - es_prueba=1 → lote de simulación; excluido de métricas reales.
  - Nunca presentar un lote es_prueba=1 como correo realmente enviado.

Nunca registra SYNC_SECRET ni datos sensibles en logs.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from app.extensions import db

log = logging.getLogger(__name__)

# Nombre de agente para heartbeat del motor local (separado del worker Render)
MOTOR_LOCAL_AGENT = 'motor_local'


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _exec(sql: str, params: dict = None):
    """Ejecuta SQL sin retorno. Lanza excepción si falla."""
    db.session.execute(db.text(sql), params or {})


def _row(sql: str, params: dict = None) -> dict:
    try:
        result = db.session.execute(db.text(sql), params or {})
        row = result.fetchone()
        return dict(row._mapping) if row else {}
    except Exception as e:
        log.debug(f'[sync_repo] _row falló: {e}')
        return {}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value) -> str | None:
    """Normaliza timestamp a string ISO, o None."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _to_utc_dt(value) -> datetime | None:
    """
    Convierte un timestamp (string ISO o datetime) a datetime UTC naive
    para comparaciones seguras independientes del formato de zona horaria.
    Retorna None si no es parseable.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        # datetime con zona → convertir a UTC
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value  # ya naive (asumimos UTC)
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return None
        # Intentar parsear ISO 8601 con zona horaria
        for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f%z',
                    '%Y-%m-%d %H:%M:%S%z', '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%d %H:%M:%S'):
            try:
                dt = datetime.strptime(v, fmt)
                if dt.tzinfo is not None:
                    return dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            except ValueError:
                continue
        # Intentar con fromisoformat (Python 3.7+)
        try:
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except (ValueError, AttributeError):
            pass
    return None


def _bool_to_int(value) -> int:
    """Convierte bool/int/None a 0 o 1."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return 1 if value else 0
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Upsert de lote
# ─────────────────────────────────────────────────────────────────────────────

def upsert_lote(lote_data: dict, emitido_en: str) -> tuple:
    """
    Inserta o actualiza ec_lotes desde el payload del motor_sync.

    Retorna (lote_pk, fue_actualizado, mensaje, skip_code) donde:
      skip_code = None     → procesar normalmente
      skip_code = '200'    → mismo emitido_en, idempotente (ya aplicado)
      skip_code = '409'    → payload más antiguo, rechazar

    Contrato de versiones:
      - mismo emitido_en  → (lote_pk, False, 'idempotente', '200')
      - más antiguo       → (lote_pk, False, msg, '409')
      - más nuevo         → actualizar y retornar (lote_pk, True, msg, None)
    """
    lote_id = lote_data.get('lote_id')
    if not lote_id:
        return None, False, 'lote_id ausente en payload', None

    # Buscar lote existente por lote_id TEXT
    existente = _row(
        "SELECT id, sync_emitido_en FROM ec_lotes WHERE lote_id = :lote_id",
        {'lote_id': lote_id}
    )

    # Comparar emitido_en para last-write-wins (comparación en UTC, timezone-safe)
    if existente:
        stored_ts    = existente.get('sync_emitido_en')
        stored_utc   = _to_utc_dt(stored_ts)
        incoming_utc = _to_utc_dt(emitido_en)
        if stored_utc and incoming_utc:
            if incoming_utc < stored_utc:
                # Payload genuinamente más antiguo → rechazar con 409
                log.debug(
                    f'[sync_repo] {lote_id}: payload antiguo '
                    f'({emitido_en} < {stored_ts}), 409'
                )
                return existente['id'], False, (
                    f'snapshot antiguo: recibido={emitido_en} < almacenado={stored_ts}'
                ), '409'
            elif incoming_utc == stored_utc:
                # Mismo snapshot — idempotente, ya aplicado → 200
                log.debug(f'[sync_repo] {lote_id}: mismo emitido_en, idempotente')
                return existente['id'], False, 'idempotente (mismo emitido_en)', '200'
            # incoming_utc > stored_utc → actualizar (continuar)

    es_prueba   = _bool_to_int(lote_data.get('es_prueba', 0))
    supresion   = lote_data.get('suppression') or lote_data.get('supresion')
    supresion_j = json.dumps(supresion) if supresion else None
    ahora       = _now_utc()

    campos = {
        'lote_id':                   lote_id,
        'fuente_sheet_id':           lote_data.get('fuente_sheet_id') or '—',
        'fuente_tab':                lote_data.get('fuente_tab') or '',
        'fecha_creacion':            _parse_ts(lote_data.get('fecha_creacion')) or ahora,
        'creado_por':                lote_data.get('creado_por'),
        'cupo_elegibles':            int(lote_data.get('cupo_elegibles') or 300),
        'total_candidatos':          int(lote_data.get('total_candidatos') or 0),
        'total_elegibles':           int(lote_data.get('total_elegibles') or 0),
        'total_excluidos':           int(lote_data.get('total_excluidos') or 0),
        'total_enviados':            int(lote_data.get('total_enviados') or 0),
        'aceptados_pendientes':      int(lote_data.get('aceptados_pendientes') or 0),
        'estado':                    lote_data.get('estado') or 'pendiente',
        'es_prueba':                 es_prueba,
        'seleccion_completada_en':   _parse_ts(lote_data.get('seleccion_completada_en')),
        'validacion_completada_en':  _parse_ts(lote_data.get('validacion_completada_en')),
        'asignacion_completada_en':  _parse_ts(lote_data.get('asignacion_completada_en')),
        'supresion_json':            supresion_j,
        'sync_emitido_en':           emitido_en,
        'ultima_sync_en':            ahora,
    }

    # Validar estado
    _ESTADOS_VALIDOS = {'pendiente', 'en_progreso', 'completado', 'cancelado'}
    if campos['estado'] not in _ESTADOS_VALIDOS:
        campos['estado'] = 'pendiente'

    if existente:
        # UPDATE
        _exec("""
            UPDATE ec_lotes SET
                fuente_sheet_id          = :fuente_sheet_id,
                fuente_tab               = :fuente_tab,
                creado_por               = :creado_por,
                cupo_elegibles           = :cupo_elegibles,
                total_candidatos         = :total_candidatos,
                total_elegibles          = :total_elegibles,
                total_excluidos          = :total_excluidos,
                total_enviados           = :total_enviados,
                aceptados_pendientes     = :aceptados_pendientes,
                estado                   = :estado,
                es_prueba                = :es_prueba,
                seleccion_completada_en  = :seleccion_completada_en,
                validacion_completada_en = :validacion_completada_en,
                asignacion_completada_en = :asignacion_completada_en,
                supresion_json           = :supresion_json,
                sync_emitido_en          = :sync_emitido_en,
                ultima_sync_en           = :ultima_sync_en
            WHERE lote_id = :lote_id
        """, campos)
        lote_pk = existente['id']
        log.info(f'[sync_repo] lote {lote_id} actualizado (pk={lote_pk})')
        return lote_pk, True, 'actualizado', None

    else:
        # INSERT
        result = db.session.execute(db.text("""
            INSERT INTO ec_lotes (
                lote_id, fuente_sheet_id, fuente_tab, fecha_creacion, creado_por,
                cupo_elegibles, total_candidatos, total_elegibles, total_excluidos,
                total_enviados, aceptados_pendientes, estado, es_prueba,
                seleccion_completada_en, validacion_completada_en, asignacion_completada_en,
                supresion_json, sync_emitido_en, ultima_sync_en
            ) VALUES (
                :lote_id, :fuente_sheet_id, :fuente_tab, :fecha_creacion, :creado_por,
                :cupo_elegibles, :total_candidatos, :total_elegibles, :total_excluidos,
                :total_enviados, :aceptados_pendientes, :estado, :es_prueba,
                :seleccion_completada_en, :validacion_completada_en, :asignacion_completada_en,
                :supresion_json, :sync_emitido_en, :ultima_sync_en
            )
            RETURNING id
        """), campos)
        row = result.fetchone()
        lote_pk = row[0] if row else None
        log.info(f'[sync_repo] lote {lote_id} insertado (pk={lote_pk})')
        return lote_pk, True, 'insertado', None


# ─────────────────────────────────────────────────────────────────────────────
# Upsert de items
# ─────────────────────────────────────────────────────────────────────────────

def upsert_items(lote_pk: int, items: list[dict], emitido_en: str) -> int:
    """
    Inserta o actualiza ec_lote_items desde el payload.

    Idempotente: ON CONFLICT (lote_id, email) DO UPDATE WHERE sync_emitido_en < emitido_en.
    Retorna el número de items procesados (insertados + actualizados).

    last-write-wins: si el item en DB tiene sync_emitido_en >= emitido_en, se conserva.
    """
    if not items:
        return 0

    _ESTADOS_ENVIO_VALIDOS = {
        'pendiente', 'en_proceso', 'en_envio', 'enviado',
        'conciliacion', 'omitido', 'rebotado', 'error',
        # También aceptar valores del estado máquina T1 (antes de confirmar)
        'aceptado',
    }
    _ESTADOS_SEL_VALIDOS = {'candidato', 'elegible', 'excluido'}

    procesados = 0
    for item in items:
        email = item.get('email')
        if not email:
            continue

        estado_envio = item.get('estado_envio') or 'pendiente'
        if estado_envio not in _ESTADOS_ENVIO_VALIDOS:
            estado_envio = 'pendiente'

        estado_sel = item.get('estado_seleccion') or 'candidato'
        if estado_sel not in _ESTADOS_SEL_VALIDOS:
            estado_sel = 'candidato'

        # Si el motor no envía el campo, se conserva el default de columna ('sin_validar').
        _ESTADOS_VAL_VALIDOS = {'valido', 'invalido', 'sin_validar', 'no_verificado', 'riesgo'}
        estado_val_raw = item.get('estado_validacion')
        estado_val = estado_val_raw if estado_val_raw in _ESTADOS_VAL_VALIDOS else None

        # Campos de rebote — None si el item no ha rebotado (columnas nullable)
        _REBOTE_TIPOS_VALIDOS = {'hard', 'soft', 'reputacion'}
        rebote_tipo_raw = item.get('rebote_tipo')
        rebote_tipo = rebote_tipo_raw if rebote_tipo_raw in _REBOTE_TIPOS_VALIDOS else None

        params = {
            'lote_pk':               lote_pk,
            'email':                 email,
            'ruc':                   item.get('ruc'),
            'razon_social':          item.get('razon_social'),
            'sector':                item.get('sector'),
            'estado_seleccion':      estado_sel,
            'motivo_exclusion':      item.get('motivo_exclusion'),
            'bandeja_asignada':      item.get('bandeja_asignada'),
            'estado_envio':          estado_envio,
            'fecha_envio':           _parse_ts(item.get('fecha_envio')),
            'sync_item_id':          item.get('id'),
            'sync_emitido_en':       emitido_en,
            'estado_validacion':     estado_val,
            'rebote_tipo':           rebote_tipo,
            'rebote_motivo':         item.get('rebote_motivo'),
            # _parse_ts acepta Z y +00:00; PostgreSQL TIMESTAMPTZ los normaliza
            'rebote_detectado_en':   _parse_ts(item.get('rebote_detectado_en')),
            # Campos requeridos para NOT NULL
            'fuente_sheet_id':       '',
            'fuente_tab':            '',
            'fuente_clave':          '',
        }

        # Sin savepoints: fallo en cualquier item propaga excepción al llamador,
        # quien hace db.session.rollback() sobre toda la transacción (cabecera + items).
        db.session.execute(db.text("""
            INSERT INTO ec_lote_items (
                lote_id, email, ruc, razon_social, sector,
                estado_seleccion, motivo_exclusion,
                bandeja_asignada, estado_envio, fecha_envio,
                sync_item_id, sync_emitido_en,
                estado_validacion,
                rebote_tipo, rebote_motivo, rebote_detectado_en,
                fuente_sheet_id, fuente_tab, fuente_clave
            ) VALUES (
                :lote_pk, :email, :ruc, :razon_social, :sector,
                :estado_seleccion, :motivo_exclusion,
                :bandeja_asignada, :estado_envio, :fecha_envio,
                :sync_item_id, :sync_emitido_en,
                COALESCE(:estado_validacion, 'sin_validar'),
                :rebote_tipo, :rebote_motivo, :rebote_detectado_en,
                :fuente_sheet_id, :fuente_tab, :fuente_clave
            )
            ON CONFLICT (lote_id, email) DO UPDATE SET
                ruc                  = EXCLUDED.ruc,
                razon_social         = EXCLUDED.razon_social,
                sector               = EXCLUDED.sector,
                estado_seleccion     = EXCLUDED.estado_seleccion,
                motivo_exclusion     = EXCLUDED.motivo_exclusion,
                bandeja_asignada     = EXCLUDED.bandeja_asignada,
                estado_envio         = EXCLUDED.estado_envio,
                fecha_envio          = EXCLUDED.fecha_envio,
                sync_item_id         = EXCLUDED.sync_item_id,
                sync_emitido_en      = EXCLUDED.sync_emitido_en,
                estado_validacion    = EXCLUDED.estado_validacion,
                rebote_tipo          = EXCLUDED.rebote_tipo,
                rebote_motivo        = EXCLUDED.rebote_motivo,
                rebote_detectado_en  = EXCLUDED.rebote_detectado_en
            WHERE ec_lote_items.sync_emitido_en IS NULL
               OR ec_lote_items.sync_emitido_en < EXCLUDED.sync_emitido_en
        """), params)
        procesados += 1

    return procesados


# ─────────────────────────────────────────────────────────────────────────────
# Heartbeat del motor local
# ─────────────────────────────────────────────────────────────────────────────

def upsert_motor_heartbeat(ts: str, origen: str) -> None:
    """
    Registra el heartbeat del motor local en agent_heartbeat[agent='motor_local'].

    Separado del worker Render ('orchestrator'). El panel los muestra
    en indicadores distintos — nunca combinar para aparentar que Mac está activa.
    """
    db.session.execute(db.text("""
        INSERT INTO agent_heartbeat (agent, status, last_seen, hostname, updated_at)
        VALUES (:agent, 'activo', :ts, :hostname, :ts)
        ON CONFLICT (agent) DO UPDATE SET
            status     = 'activo',
            last_seen  = EXCLUDED.last_seen,
            hostname   = EXCLUDED.hostname,
            updated_at = EXCLUDED.updated_at
    """), {
        'agent':    MOTOR_LOCAL_AGENT,
        'ts':       ts,
        'hostname': origen,
    })
    log.debug(f'[sync_repo] heartbeat motor_local registrado ts={ts}')


# ─────────────────────────────────────────────────────────────────────────────
# Estado del motor local para el panel
# ─────────────────────────────────────────────────────────────────────────────

def get_motor_local_status() -> dict:
    """
    Estado de conectividad del motor local Mac.

    Retorna información del último heartbeat y última sincronización de lote.
    Nunca usa el heartbeat de Render (agent='orchestrator') para representar
    el estado de la Mac.
    """
    from datetime import timedelta
    _OFFLINE_MIN = 10

    try:
        beat = _row("""
            SELECT last_seen, status, hostname, updated_at
            FROM agent_heartbeat
            WHERE agent = :agent
        """, {'agent': MOTOR_LOCAL_AGENT})

        if not beat:
            return {
                'conectado': False,
                'ultimo_heartbeat': None,
                'edad_min': None,
                'hostname': None,
                'ultimo_sync_lote': None,
                'ultimo_lote_id': None,
                'disponible': True,
            }

        ls = beat.get('last_seen')
        now = datetime.now(timezone.utc)
        if ls:
            if hasattr(ls, 'replace'):
                # Normalizar a UTC antes de comparar (ls puede traer offset Lima -05:00)
                ls_dt = _to_utc_dt(ls) or ls.replace(tzinfo=None)
                age = now.replace(tzinfo=None) - ls_dt
            else:
                age = timedelta(seconds=99999)
            conectado = age < timedelta(minutes=_OFFLINE_MIN)
            edad_min  = int(age.total_seconds() / 60)
        else:
            conectado = False
            edad_min  = None

        # Última sincronización de lote recibida
        ultimo = _row("""
            SELECT lote_id, ultima_sync_en::text AS ultima_sync_en
            FROM ec_lotes
            WHERE ultima_sync_en IS NOT NULL
            ORDER BY ultima_sync_en DESC
            LIMIT 1
        """)

        return {
            'conectado':        conectado,
            'ultimo_heartbeat': str(ls) if ls else None,
            'edad_min':         edad_min,
            'hostname':         beat.get('hostname'),
            'ultimo_sync_lote': ultimo.get('ultima_sync_en'),
            'ultimo_lote_id':   ultimo.get('lote_id'),
            'disponible':       True,
        }

    except Exception as e:
        log.debug(f'[sync_repo] get_motor_local_status falló: {e}')
        return {'conectado': False, 'disponible': False}

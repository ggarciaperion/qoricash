"""
Scheduler diario del Estudio Creativo.

INICIO:
  - Con gunicorn (comando Render): gunicorn -c gunicorn_config.py run:app
    preload_app=False → cada worker importa run.py → eventlet.spawn_after(2, start_all_schedulers)
    → start_all_schedulers() llama daily_scheduler.spawn(app) ~2 s después del fork.
  - Con python run.py (desarrollo): __main__ llama start_all_schedulers() directamente.

VENTANA DE GENERACIÓN: 6:30 AM – 7:25 AM Lima.
COMPROBACIÓN DE COMPLETITUD: 7:30 AM Lima — reintenta únicamente etapas fallidas (máx 1 vez/día).
RECUPERACIÓN ATRASADA: si el servidor arranca después de las 7:25 y no hay entrega del día,
  genera una sola vez y marca la entrega con notas='atrasada'.
LIMITE DE REPARACIÓN: REPAIR_LIMIT reintentos de etapas fallidas por día.

CONTROL DE DUPLICADOS:
  - EntregaDiaria.fecha (UNIQUE en DB): bloquea dobles entregas entre reinicios.
  - _fired_today / _repaired_today: flags en memoria que evitan disparar dos veces en el mismo proceso.
  - Seguro con workers=1 (Render). Con workers>1 la DB es la única garantía.
"""
import logging
from datetime import timezone, timedelta, date as _date, datetime as _dt

log = logging.getLogger(__name__)

LIMA_TZ      = timezone(timedelta(hours=-5))
WINDOW_START = (6, 30)   # 6:30 AM Lima — inicio de generación automática
WINDOW_END   = (7, 25)   # 7:25 AM Lima — fin de ventana (no iniciar nuevas entregas después)
REPAIR_TIME  = (7, 30)   # 7:30 AM Lima — comprobación de completitud y reintento
REPAIR_LIMIT = 1         # máximo de intentos de reparación por día

# Clave para advisory lock de PostgreSQL — exclusión compartida entre scheduler,
# generación manual y recuperación. Fija por módulo; no colisiona con otras features.
_LOCK_KEY = 7341523691


def _try_advisory_lock(db):
    """
    Intenta adquirir un advisory lock de nivel-transacción en PostgreSQL.
    Retorna True si se adquirió, False si otra sesión activa ya lo tiene.
    El lock se libera automáticamente al hacer commit o rollback.
    En SQLite (desarrollo) no hay advisory locks: siempre retorna True.
    """
    from sqlalchemy import text
    try:
        result = db.session.execute(
            text('SELECT pg_try_advisory_xact_lock(:key)'),
            {'key': _LOCK_KEY}
        ).scalar()
        return bool(result)
    except Exception:
        return True   # SQLite u otro motor: sin advisory locks, permitir paso


def _now_lima():
    return _dt.now(LIMA_TZ)


def _in_window(now_lima=None):
    """True si la hora Lima está dentro de la ventana de generación inicial."""
    t = now_lima or _now_lima()
    return WINDOW_START <= (t.hour, t.minute) <= WINDOW_END


def _in_repair_window(now_lima=None):
    """True si estamos en la ventana de comprobación de completitud (7:30–7:44 AM)."""
    t = now_lima or _now_lima()
    return REPAIR_TIME <= (t.hour, t.minute) < (7, 45)


def try_generate_today(force=False):
    """
    Intenta generar la entrega de hoy si no existe o está en error.
    Debe llamarse dentro de un app_context activo.
    Retorna (ok, mensaje).
    """
    import eventlet.tpool as _tpool
    from app.models.content_pipeline import EntregaDiaria
    from app.models.content_proposal import ContentProposal
    from app.extensions import db
    from app.utils.formatters import now_peru
    from app.services.content.pipeline_coordinator import create_pipeline, run_pipeline_auto

    if not _try_advisory_lock(db):
        return False, 'Operación de generación activa en otra sesión DB — abortando'

    today   = _date.today()
    entrega = EntregaDiaria.query.filter_by(fecha=today).first()

    if entrega and entrega.status in ('listo', 'parcial') and not force:
        return False, f'Entrega del {today} ya existe ({entrega.status})'
    if entrega and entrega.status == 'generando' and not force:
        return False, f'Entrega del {today} ya está generándose'

    hoy_str  = today.strftime('%Y-%m-%d')
    pipeline = create_pipeline('diario',
                               title=f'Entrega diaria {hoy_str}',
                               user_id=None,
                               notes='Auto-generado por scheduler')
    if entrega:
        entrega.pipeline_id = pipeline.id
        entrega.status      = 'generando'
        entrega.notas       = None
    else:
        entrega = EntregaDiaria(fecha=today, pipeline_id=pipeline.id, status='generando')
        db.session.add(entrega)
    db.session.commit()

    log.info(f'[ESTUDIO-SCHED] Iniciando entrega {today} (pipeline #{pipeline.id})')

    # Ejecutar en OS thread para no bloquear el hub de eventlet.
    # IMPORTANTE: _tpool corre en un OS thread que NO hereda el app context de Flask.
    # Capturamos el objeto app ANTES de entrar al tpool y lo pasamos explícitamente.
    from flask import current_app as _flask_app
    _app    = _flask_app._get_current_object()
    _pip_id = pipeline.id

    def _run_in_thread():
        with _app.app_context():
            from app.services.content.pipeline_coordinator import run_pipeline_auto as _rpa
            return _rpa(_pip_id)

    try:
        result = _tpool.execute(_run_in_thread)
    except Exception as e:
        entrega.status = 'error'
        entrega.notas  = str(e)
        db.session.commit()
        return False, str(e)

    nok = ContentProposal.query.filter_by(pipeline_id=pipeline.id, delivery_type='noticia').count()
    cok = ContentProposal.query.filter_by(pipeline_id=pipeline.id, delivery_type='comercial').count()
    entrega.status       = 'listo' if (result.get('ok') and nok >= 3 and cok >= 3) else (
                           'parcial' if result.get('ok') else 'error')
    entrega.noticias_ok  = nok
    entrega.comercial_ok = cok
    entrega.generado_at  = now_peru()
    if not result.get('ok'):
        entrega.notas = result.get('reason', '')
    db.session.commit()

    msg = f'Entrega {today}: {entrega.status} ({nok}n + {cok}c)'
    log.info(f'[ESTUDIO-SCHED] {msg}')
    return True, msg


def repair_delivery_today():
    """
    Reintenta únicamente las etapas fallidas de la entrega de hoy.
    Solo actúa si EntregaDiaria.status es 'parcial' o 'error'.
    No crea pipelines nuevos ni duplica contenido existente.
    Retorna (ok, mensaje).
    """
    import eventlet.tpool as _tpool
    from app.models.content_pipeline import EntregaDiaria, ContentPipeline, PipelineStage
    from app.models.content_proposal import ContentProposal
    from app.extensions import db
    from app.utils.formatters import now_peru
    from app.services.content.pipeline_coordinator import PIPELINE_SEQUENCES

    if not _try_advisory_lock(db):
        return False, 'Operación de generación activa en otra sesión DB — abortando'

    today   = _date.today()
    entrega = EntregaDiaria.query.filter_by(fecha=today).first()

    if not entrega:
        return False, 'No hay entrega del día para reparar'
    if entrega.status == 'listo':
        return False, 'Entrega ya está completa'
    if entrega.status == 'generando':
        return False, 'Entrega en progreso — esperando finalización'
    if entrega.status not in ('parcial', 'error'):
        return False, f'Estado inesperado para reparación: {entrega.status}'

    pipeline = ContentPipeline.query.get(entrega.pipeline_id)
    if not pipeline:
        return False, 'Pipeline de la entrega no encontrado'

    # Identificar la primera etapa fallida o la primera pendiente después de una fallida
    error_stages = PipelineStage.query.filter_by(
        pipeline_id=pipeline.id,
        status='error'
    ).order_by(PipelineStage.seq).all()

    if not error_stages:
        # No hay etapas en error explícito; puede ser que el pipeline se marcó error
        # antes de ejecutar alguna etapa. Buscamos la primera no completada.
        pending = PipelineStage.query.filter(
            PipelineStage.pipeline_id == pipeline.id,
            PipelineStage.status.in_(['pending', 'error']),
        ).order_by(PipelineStage.seq).first()
        if not pending:
            log.info('[ESTUDIO-SCHED] Repair: no hay etapas pendientes/error, estado inconsistente')
            return False, 'Sin etapas a reparar'
        first_error_seq = pending.seq
    else:
        first_error_seq = error_stages[0].seq

    total = len(PIPELINE_SEQUENCES[pipeline.type])
    log.info(f'[ESTUDIO-SCHED] Reparando entrega {today}: pipeline #{pipeline.id}, desde etapa {first_error_seq}')

    entrega.status = 'generando'
    pipeline.status = 'running'
    pipeline.error_msg = None
    db.session.commit()

    from flask import current_app as _flask_app
    _app    = _flask_app._get_current_object()
    _pip_id = pipeline.id

    def _repair_in_thread():
        with _app.app_context():
            from app.services.content.pipeline_coordinator import run_stage as _rs, PIPELINE_SEQUENCES as _SEQ
            _total = len(_SEQ['diario'])
            results = []
            for seq in range(first_error_seq, _total + 1):
                r = _rs(_pip_id, seq=seq)
                results.append({'seq': seq, 'ok': r.get('ok'), 'agent': r.get('agent')})
                if not r.get('ok'):
                    return {'ok': False, 'results': results, 'failed_seq': seq,
                            'reason': r.get('output', {}).get('reason', 'Error en etapa')}
            return {'ok': True, 'results': results}

    try:
        result = _tpool.execute(_repair_in_thread)
    except Exception as e:
        entrega.status = 'error'
        entrega.notas  = (entrega.notas or '') + f' [repair-error: {e}]'
        db.session.commit()
        return False, f'Excepción en reparación: {e}'

    nok = ContentProposal.query.filter_by(pipeline_id=pipeline.id, delivery_type='noticia').count()
    cok = ContentProposal.query.filter_by(pipeline_id=pipeline.id, delivery_type='comercial').count()
    entrega.status       = 'listo' if (result.get('ok') and nok >= 3 and cok >= 3) else (
                           'parcial' if result.get('ok') else 'error')
    entrega.noticias_ok  = nok
    entrega.comercial_ok = cok
    entrega.generado_at  = now_peru()
    if not result.get('ok'):
        entrega.notas = (entrega.notas or '') + f" [reparación: {result.get('reason', 'sin detalle')}]"
    db.session.commit()

    msg = f'Reparación {today}: {entrega.status} ({nok}n + {cok}c)'
    log.info(f'[ESTUDIO-SCHED] {msg}')
    return True, msg


def run_scheduler_loop(app):
    """
    Bucle principal del scheduler. Se ejecuta en un greenlet de eventlet.
    Comprueba cada 60 s si hay que generar o reparar la entrega del día.

    Ciclo diario:
      6:30 AM  → genera la entrega completa (una sola vez)
      7:30 AM  → comprobación de completitud; reintenta etapas fallidas (máx REPAIR_LIMIT veces)
      8:00 AM+ → /contenido/hoy muestra el estado final (listo / parcial / error)

    Recuperación tras reinicio:
      - Arranque dentro de ventana sin entrega → genera de inmediato.
      - Arranque tardío (≥ 7:25) sin entrega   → genera una vez, marca 'atrasada'.
      - Entrega ya existe y no está en error    → no hace nada.
    """
    import eventlet
    _fired_today   = None
    _repaired_today = None
    _repair_count   = {}  # fecha → número de intentos de reparación

    # ── Startup recovery ──────────────────────────────────────────────────────
    with app.app_context():
        now_lima = _now_lima()
        today    = now_lima.date()
        from app.models.content_pipeline import EntregaDiaria
        from app.extensions import db
        e = EntregaDiaria.query.filter_by(fecha=today).first()

        if e and e.status not in ('error',):
            _fired_today = today
            if e.status == 'listo':
                _repaired_today = today   # no reparar lo que ya está listo
        elif _in_window(now_lima):
            log.info('[ESTUDIO-SCHED] Startup recovery (en ventana): generando entrega del día')
            try:
                ok, msg = try_generate_today()
                if ok:
                    _fired_today = today
                    log.info(f'[ESTUDIO-SCHED] Startup recovery: {msg}')
            except Exception as ex:
                log.error(f'[ESTUDIO-SCHED] Startup recovery error: {ex}')
        else:
            t = (now_lima.hour, now_lima.minute)
            if t > WINDOW_END and (not e or e.status == 'error'):
                log.info('[ESTUDIO-SCHED] Startup recovery tardío: generando entrega atrasada')
                try:
                    ok, msg = try_generate_today()
                    if ok:
                        _fired_today = today
                        e2 = EntregaDiaria.query.filter_by(fecha=today).first()
                        if e2:
                            e2.notas = (e2.notas or '') + ' [entrega atrasada — generada fuera de ventana]'
                            db.session.commit()
                        log.info(f'[ESTUDIO-SCHED] Tardío: {msg}')
                except Exception as ex:
                    log.error(f'[ESTUDIO-SCHED] Startup recovery tardío error: {ex}')
            else:
                _fired_today = today

    # ── Bucle principal ────────────────────────────────────────────────────────
    while True:
        try:
            now_lima = _now_lima()
            today    = now_lima.date()

            # Generación inicial: ventana 6:30–7:25 AM
            if _in_window(now_lima) and _fired_today != today:
                with app.app_context():
                    ok, msg = try_generate_today()
                    if ok:
                        log.info(f'[ESTUDIO-SCHED] {msg}')
                    _fired_today = today  # no reintentar en la misma ventana aunque fallara

            # Comprobación de completitud: 7:30–7:44 AM
            if _in_repair_window(now_lima) and _repaired_today != today:
                count = _repair_count.get(today, 0)
                if count < REPAIR_LIMIT:
                    with app.app_context():
                        ok, msg = repair_delivery_today()
                        log.info(f'[ESTUDIO-SCHED] Repair check: {msg}')
                    _repair_count[today] = count + 1
                _repaired_today = today  # marcar aunque no se haya reparado nada

        except Exception as e:
            log.error(f'[ESTUDIO-SCHED] Error en loop: {e}')

        eventlet.sleep(60)


def recover_pipeline(pipeline_id, target_date):
    """
    Recupera un pipeline diario específico reanudando etapas incompletas.

    - Exclusión compartida con scheduler y generación manual (pg_try_advisory_xact_lock).
    - Verifica entrega.pipeline_id == pipeline_id.
    - Preserva etapas 'done' y sus resultados; no las re-ejecuta.
    - Evita duplicar propuestas si el productor ya generó contenido.
    - Re-consulta entrega y pipeline con sesión fresca tras las etapas.
    - Marca 'listo' solo si: 3 noticias (nacional+internacional+mercados),
      3 comerciales, 6 text_body no vacíos, 6 flow_prompt no vacíos, revisor done.
    - Retorna (ok, mensaje, detalle).
    """
    from app.models.content_pipeline import EntregaDiaria, ContentPipeline, PipelineStage
    from app.models.content_proposal import ContentProposal
    from app.extensions import db
    from app.utils.formatters import now_peru
    from app.services.content.pipeline_coordinator import run_stage, PIPELINE_SEQUENCES

    # ── 1. Exclusión compartida ────────────────────────────────────────────────
    if not _try_advisory_lock(db):
        return False, 'Otra operación de generación activa en DB — abortando', {}

    # ── 2. Verificar entrega y pipeline ───────────────────────────────────────
    entrega = EntregaDiaria.query.filter_by(fecha=target_date).first()
    if not entrega:
        return False, f'No hay EntregaDiaria para fecha={target_date}', {}
    if entrega.pipeline_id != pipeline_id:
        return False, (
            f'EntregaDiaria.pipeline_id={entrega.pipeline_id} '
            f'no coincide con pipeline_id solicitado={pipeline_id}'
        ), {}
    if entrega.status == 'generando':
        return False, 'Entrega en progreso (status=generando) — espera finalización', {}
    if entrega.status == 'listo':
        return False, 'Entrega ya completa (status=listo)', {}

    pipeline = ContentPipeline.query.get(pipeline_id)
    if not pipeline:
        return False, f'Pipeline #{pipeline_id} no encontrado', {}

    # ── 3. Cargar etapas y determinar primera incompleta ──────────────────────
    stages = PipelineStage.query.filter_by(
        pipeline_id=pipeline_id
    ).order_by(PipelineStage.seq).all()

    if not stages:
        return False, f'Pipeline #{pipeline_id} no tiene etapas registradas', {}

    # Capturar (seq, agent_role, status) ANTES de cualquier commit o modificación.
    stage_info = [(s.seq, s.agent_role, s.status) for s in stages]
    done_seqs  = {seq for seq, role, st in stage_info if st == 'done'}

    first_incomplete_seq = None
    for seq, role, st in stage_info:
        if st != 'done':
            first_incomplete_seq = seq
            break

    if first_incomplete_seq is None:
        # Todas las etapas completadas — recalcular estado final.
        nok = ContentProposal.query.filter_by(pipeline_id=pipeline_id, delivery_type='noticia').count()
        cok = ContentProposal.query.filter_by(pipeline_id=pipeline_id, delivery_type='comercial').count()
        entrega.status       = 'listo' if (nok >= 3 and cok >= 3) else 'parcial'
        entrega.noticias_ok  = nok
        entrega.comercial_ok = cok
        entrega.generado_at  = now_peru()
        db.session.commit()
        return False, f'Todas las etapas completas — estado recalculado: {entrega.status} ({nok}n+{cok}c)', {}

    log.info(
        f'[ESTUDIO-RECOVER] Pipeline #{pipeline_id} ({target_date}): '
        f'primera incompleta seq={first_incomplete_seq}, '
        f'done_seqs={sorted(done_seqs)}'
    )

    # ── 4. Limpiar etapas no-done (error/running → pending) ───────────────────
    for s in stages:
        if s.seq >= first_incomplete_seq and s.status not in ('done',):
            s.status    = 'pending'
            s.error_msg = None

    # ── 5. Marcar generando + commit (libera advisory lock) ───────────────────
    # A partir de aquí cualquier otro llamador verá status='generando' y abortará.
    entrega.status     = 'generando'
    pipeline.status    = 'running'
    pipeline.error_msg = None
    db.session.commit()
    # Advisory lock liberado en el commit anterior.

    # ── 6. Ejecutar etapas desde primera incompleta (usando stage_info cacheado) ─
    run_results = []
    for seq, agent_role, _orig_status in stage_info:
        # Preservar etapas done
        if seq in done_seqs:
            run_results.append({'seq': seq, 'agent': agent_role, 'skipped': True, 'reason': 'done'})
            continue

        # No ejecutar etapas antes de la primera incompleta (todas deberían ser done)
        if seq < first_incomplete_seq:
            run_results.append({'seq': seq, 'agent': agent_role, 'skipped': True, 'reason': 'before_start'})
            continue

        # Anti-duplicado: omitir productor solo si ya existe el set completo (3n+3c).
        # Si hay propuestas parciales, el productor corre con su guardia interna
        # de idempotencia (salta noticias por categoría y comerciales en exceso).
        if agent_role == 'productor':
            nok_ex = ContentProposal.query.filter_by(
                pipeline_id=pipeline_id, delivery_type='noticia').count()
            cok_ex = ContentProposal.query.filter_by(
                pipeline_id=pipeline_id, delivery_type='comercial').count()
            if nok_ex >= 3 and cok_ex >= 3:
                log.info(f'[ESTUDIO-RECOVER] Productor omitido: set completo ({nok_ex}n+{cok_ex}c)')
                run_results.append({
                    'seq': seq, 'agent': 'productor', 'skipped': True,
                    'reason': f'set completo {nok_ex}n+{cok_ex}c',
                })
                continue

        r = run_stage(pipeline_id, seq=seq)
        run_results.append({'seq': seq, 'ok': r.get('ok'), 'agent': r.get('agent')})

        if not r.get('ok'):
            # Re-consultar entrega con sesión fresca (no usar expire sobre objeto posiblemente desvinculado)
            entrega2 = EntregaDiaria.query.filter_by(fecha=target_date).first()
            if entrega2:
                entrega2.status = 'error'
                entrega2.notas  = (entrega2.notas or '') + (
                    f' [recover: fallo seq={seq} ({agent_role})]'
                )
                db.session.commit()
            return (
                False,
                f'Falló etapa seq={seq} ({agent_role})',
                {'run_results': run_results},
            )

    # ── 7. Re-consultar entrega y pipeline con sesión fresca ──────────────────
    entrega  = EntregaDiaria.query.filter_by(fecha=target_date).first()
    pipeline = ContentPipeline.query.get(pipeline_id)

    nok = ContentProposal.query.filter_by(pipeline_id=pipeline_id, delivery_type='noticia').count()
    cok = ContentProposal.query.filter_by(pipeline_id=pipeline_id, delivery_type='comercial').count()

    # ── 8. Criterios estrictos para marcar 'listo' ────────────────────────────
    textos_y_prompts_listos = False
    if entrega and pipeline:
        revisor_st  = PipelineStage.query.filter_by(
            pipeline_id=pipeline_id, agent_role='revisor'
        ).first()
        revisor_ok  = revisor_st and revisor_st.status == 'done'

        proposals   = ContentProposal.query.filter_by(pipeline_id=pipeline_id).all()
        all_texts   = all(bool((p.text_body   or '').strip()) for p in proposals) if proposals else False
        all_prompts = all(bool((p.flow_prompt or '').strip()) for p in proposals) if proposals else False

        noticia_cats = {p.noticia_category for p in proposals if p.delivery_type == 'noticia'}
        has_cats     = {'nacional', 'internacional', 'mercados'}.issubset(noticia_cats)

        textos_y_prompts_listos = (
            nok >= 3 and cok >= 3
            and len(proposals) >= 6
            and all_texts and all_prompts
            and has_cats
            and revisor_ok
        )

        entrega.status       = 'listo' if textos_y_prompts_listos else 'parcial'
        entrega.noticias_ok  = nok
        entrega.comercial_ok = cok
        entrega.generado_at  = now_peru()
        db.session.commit()

    msg = (
        f'Recuperación #{pipeline_id} ({target_date}): '
        f'{entrega.status if entrega else "?"} ({nok}n+{cok}c)'
    )
    log.info(f'[ESTUDIO-RECOVER] {msg}')
    return True, msg, {
        'run_results':             run_results,
        'noticias':                nok,
        'comerciales':             cok,
        'textos_y_prompts_listos': textos_y_prompts_listos,
    }


def spawn(app):
    """
    Inicia el scheduler en un greenlet de eventlet.
    Llamar desde gunicorn post_fork hook o desde run.py __main__.
    """
    import eventlet
    import os

    if os.environ.get('ESTUDIO_DIARIO_AUTO', 'true').lower() == 'false':
        log.info('[ESTUDIO-SCHED] DESACTIVADO (ESTUDIO_DIARIO_AUTO=false)')
        return

    eventlet.spawn(run_scheduler_loop, app)
    log.info('[ESTUDIO-SCHED] Scheduler diario iniciado '
             '(generación 6:30 AM Lima, comprobación 7:30 AM Lima)')

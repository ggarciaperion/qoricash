"""
Scheduler diario del Estudio Creativo.

INICIO:
  - Con gunicorn (comando Render): `python3 -m gunicorn --worker-class eventlet -w 1 run:app`
    preload_app=False → cada worker importa run.py → eventlet.spawn_after(2, start_all_schedulers)
    → start_all_schedulers() llama daily_scheduler.spawn(app) ~2 s después del fork.
  - Con python run.py (desarrollo): __main__ llama start_all_schedulers() directamente.

VENTANA NORMAL: 5:00 AM – 7:55 AM Lima.
RECUPERACIÓN ATRASADA: si el servidor arranca después de las 7:55 y no hay entrega del día,
  genera una sola vez y marca la entrega con notas='atrasada'.

CONTROL DE DUPLICADOS: EntregaDiaria.fecha (UNIQUE en DB) + flags en memoria (_fired_today).
  Seguro entre reinicios (DB) y en workers únicos (memoria). Con workers > 1 la DB sería
  la única garantía (race condition estrecha en el commit — aceptable dado workers=1 en Render).
"""
import logging
from datetime import timezone, timedelta, date as _date, datetime as _dt

log = logging.getLogger(__name__)

LIMA_TZ    = timezone(timedelta(hours=-5))
WINDOW_START = (5, 0)   # 5:00 AM Lima
WINDOW_END   = (7, 55)  # 7:55 AM Lima


def _now_lima():
    return _dt.now(LIMA_TZ)


def _in_window(now_lima=None):
    """True si la hora Lima está dentro de la ventana de generación."""
    t = now_lima or _now_lima()
    return WINDOW_START <= (t.hour, t.minute) <= WINDOW_END


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
    _app     = _flask_app._get_current_object()
    _pip_id  = pipeline.id

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


def run_scheduler_loop(app):
    """
    Bucle principal del scheduler. Se ejecuta en un greenlet separado.
    Comprueba cada 60 s si hay que generar la entrega.
    También hace una comprobación al arrancar (startup recovery).
    """
    import eventlet
    _fired_today = None

    # ── Startup recovery ──────────────────────────────────────────────────────
    with app.app_context():
        now_lima = _now_lima()
        today    = now_lima.date()
        from app.models.content_pipeline import EntregaDiaria
        from app.extensions import db
        e = EntregaDiaria.query.filter_by(fecha=today).first()

        if e and e.status not in ('error',):
            # Ya existe y no está en error: no hacer nada
            _fired_today = today
        elif _in_window(now_lima):
            # Dentro de la ventana y sin entrega válida → generar
            log.info('[ESTUDIO-SCHED] Startup recovery (en ventana): generando entrega del día')
            try:
                ok, msg = try_generate_today()
                if ok:
                    _fired_today = today
                    log.info(f'[ESTUDIO-SCHED] Startup recovery: {msg}')
            except Exception as ex:
                log.error(f'[ESTUDIO-SCHED] Startup recovery error: {ex}')
        else:
            # Fuera de la ventana (arranque tardío o reinicio) → recuperar UNA vez si falta
            t = (now_lima.hour, now_lima.minute)
            if t > WINDOW_END and (not e or e.status == 'error'):
                log.info('[ESTUDIO-SCHED] Startup recovery tardío: generando entrega atrasada')
                try:
                    ok, msg = try_generate_today()
                    if ok:
                        _fired_today = today
                        # Marcar como atrasada
                        e2 = EntregaDiaria.query.filter_by(fecha=today).first()
                        if e2:
                            e2.notas = (e2.notas or '') + ' [entrega atrasada — generada fuera de ventana]'
                            db.session.commit()
                        log.info(f'[ESTUDIO-SCHED] Tardío: {msg}')
                except Exception as ex:
                    log.error(f'[ESTUDIO-SCHED] Startup recovery tardío error: {ex}')
            else:
                _fired_today = today   # ya dentro del día pero sin necesidad de generar

    while True:
        try:
            now_lima = _now_lima()
            today    = now_lima.date()

            if _in_window(now_lima) and _fired_today != today:
                with app.app_context():
                    ok, msg = try_generate_today()
                    if ok:
                        log.info(f'[ESTUDIO-SCHED] {msg}')
                    _fired_today = today   # no reintentar hoy aunque fallara
        except Exception as e:
            log.error(f'[ESTUDIO-SCHED] Error en loop: {e}')

        eventlet.sleep(60)


def spawn(app):
    """
    Inicia el scheduler en un greenlet de eventlet.
    Llamar desde gunicorn post_fork o desde run.py __main__.
    """
    import eventlet

    import os
    if os.environ.get('ESTUDIO_DIARIO_AUTO', 'true').lower() == 'false':
        log.info('[ESTUDIO-SCHED] DESACTIVADO (ESTUDIO_DIARIO_AUTO=false)')
        return

    eventlet.spawn(run_scheduler_loop, app)
    log.info('[ESTUDIO-SCHED] Scheduler diario iniciado (ventana 5:00–7:55 AM Lima)')

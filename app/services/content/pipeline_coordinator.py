"""
Coordinador de pipelines del Estudio Creativo.

Gestiona el avance entre etapas, persiste resultados y maneja errores
a nivel de etapa individual (no aborta el pipeline completo).
"""
import json
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# Definición de pipelines: orden de agentes por tipo
PIPELINE_SEQUENCES = {
    'actualidad': [
        'investigador',   # 1 — recopila fuentes
        'analista',       # 2 — analiza el contexto
        'editor',         # 3 — adapta por red social
        'productor',      # 4 — genera imágenes y paquetes
        'revisor',        # 5 — verifica y presenta al usuario
    ],
    'comercial': [
        'creativo',       # 1 — propone desde ficha de marca
        'editor',         # 2 — adapta por red social
        'productor',      # 3 — genera imágenes y paquetes
        'revisor',        # 4 — verifica y presenta al usuario
    ],
    'diario': [
        'investigador',   # 1 — 3 noticias categorizadas (nacional/internacional/mercados)
        'editor',         # 2 — 3 posts LinkedIn 80-140 palabras
        'creativo',       # 3 — 3 propuestas comerciales con audiencia rotativa
        'productor',      # 4 — director visual: prompts Gemini/Flow (sin Pillow)
        'revisor',        # 5 — revisión con correcciones y límite de reintentos
    ],
}

AGENT_LABELS = {
    'investigador': 'Investigador de actualidad',
    'analista':     'Analista económico',
    'creativo':     'Creativo comercial',
    'editor':       'Editor de redes',
    'productor':    'Productor visual',
    'revisor':      'Revisor y coordinador',
}


def create_pipeline(pipeline_type: str, title: str = '', user_id: int = None,
                    notes: str = '') -> 'ContentPipeline':
    """
    Crea un nuevo pipeline con todas sus etapas en estado 'pending'.
    No ejecuta ninguna etapa todavía.
    """
    from app.models.content_pipeline import ContentPipeline, PipelineStage
    from app.extensions import db

    if pipeline_type not in PIPELINE_SEQUENCES:
        raise ValueError(f'Tipo de pipeline desconocido: {pipeline_type}')

    pipeline = ContentPipeline(
        type       = pipeline_type,
        title      = title or PIPELINE_SEQUENCES[pipeline_type][0].title(),
        status     = 'pending',
        created_by = user_id,
        notes      = notes,
        current_stage_seq = 1,
    )
    db.session.add(pipeline)
    db.session.flush()

    for seq, role in enumerate(PIPELINE_SEQUENCES[pipeline_type], 1):
        stage = PipelineStage(
            pipeline_id = pipeline.id,
            seq         = seq,
            agent_role  = role,
            status      = 'pending',
        )
        db.session.add(stage)

    db.session.commit()
    return pipeline


def run_pipeline_auto(pipeline_id: int, user_instruction: str = '',
                      user_urls: list = None) -> dict:
    """
    Ejecuta TODAS las etapas del pipeline en secuencia automática.
    Se detiene solo ante error o al llegar a la última etapa (waiting_user).
    Retorna el estado final del pipeline y un log de etapas.
    """
    from app.models.content_pipeline import ContentPipeline
    from app.extensions import db

    pipeline = ContentPipeline.query.get(pipeline_id)
    if not pipeline:
        return {'ok': False, 'reason': f'Pipeline {pipeline_id} no encontrado'}

    # Anti-duplicate: si ya está corriendo, no relanzar
    if pipeline.status == 'running':
        return {'ok': False, 'reason': 'El pipeline ya está en ejecución', 'duplicate': True}

    total   = len(PIPELINE_SEQUENCES[pipeline.type])
    results = []

    for seq in range(1, total + 1):
        # Solo pasar user_urls al primer agente (investigador)
        urls = user_urls if seq == 1 else None
        instr = user_instruction if seq == 1 else ''

        r = run_stage(pipeline_id, seq=seq,
                      user_instruction=instr, user_urls=urls)
        results.append({'seq': seq, 'agent': r.get('agent'), 'ok': r.get('ok'),
                        'status': r.get('status')})

        if not r.get('ok'):
            return {
                'ok':         False,
                'failed_seq': seq,
                'reason':     r.get('output', {}).get('reason', 'Error desconocido'),
                'stages':     results,
                'pipeline_status': r.get('pipeline_status', 'error'),
            }

    return {
        'ok':              True,
        'stages':          results,
        'pipeline_status': 'waiting_user',
        'pipeline_id':     pipeline_id,
    }


def run_stage(pipeline_id: int, seq: int = None,
              user_instruction: str = '',
              user_urls: list = None) -> dict:
    """
    Ejecuta la etapa indicada (o la actual del pipeline).
    Persiste entrada, salida, estado y fechas.
    Si la etapa tiene error, marca solo esa etapa — no cancela el pipeline.
    Si es la última etapa, marca el pipeline como 'waiting_user'.
    """
    from app.models.content_pipeline import ContentPipeline, PipelineStage
    from app.extensions import db
    from app.utils.formatters import now_peru

    pipeline = ContentPipeline.query.get(pipeline_id)
    if not pipeline:
        return {'ok': False, 'reason': f'Pipeline {pipeline_id} no encontrado'}

    target_seq = seq if seq is not None else pipeline.current_stage_seq
    stage = PipelineStage.query.filter_by(
        pipeline_id=pipeline_id, seq=target_seq
    ).first()
    if not stage:
        return {'ok': False, 'reason': f'Etapa {target_seq} no encontrada'}

    # Marcar inicio
    stage.status     = 'running'
    stage.started_at = now_peru()
    if user_instruction:
        stage.user_instruction = user_instruction
    pipeline.status  = 'running'
    pipeline.current_stage_seq = target_seq
    db.session.commit()
    # Liberar la conexión antes del agente: puede tardar minutos.
    # pool_pre_ping garantizará una conexión válida al volver a persistir.
    db.session.close()

    # Recargar con sesión fresca antes de ejecutar el agente.
    stage    = PipelineStage.query.filter_by(pipeline_id=pipeline_id, seq=target_seq).first()
    pipeline = ContentPipeline.query.get(pipeline_id)
    agent_role = stage.agent_role if stage else None

    # Ejecutar el agente correspondiente
    try:
        output = _dispatch_agent(stage, pipeline, user_instruction, user_urls)
    except Exception as e:
        log.error(f'[Pipeline] etapa {agent_role} error: {e}', exc_info=True)
        output = {'ok': False, 'reason': str(e)}

    # Liberar conexión potencialmente obsoleta tras el agente y recargar para persistir.
    db.session.close()
    stage    = PipelineStage.query.filter_by(pipeline_id=pipeline_id, seq=target_seq).first()
    pipeline = ContentPipeline.query.get(pipeline_id)
    if not stage or not pipeline:
        log.error(f'[Pipeline] pipeline {pipeline_id} etapa {target_seq} no encontrada al persistir')
        return {'ok': False, 'reason': 'Pipeline/etapa no encontrada al persistir resultado'}

    # Persistir resultado
    stage.output_data   = json.dumps(output, ensure_ascii=False, default=str)
    stage.completed_at  = now_peru()
    stage.version       = (stage.version or 0) + 1

    if output.get('ok'):
        stage.status = 'done'
        # Avanzar al siguiente paso
        total = len(PIPELINE_SEQUENCES[pipeline.type])
        if target_seq >= total:
            # Última etapa → esperar aprobación del usuario
            pipeline.status = 'waiting_user'
        else:
            pipeline.current_stage_seq = target_seq + 1
            pipeline.status = 'running'
            # Activar siguiente stage
            next_stage = PipelineStage.query.filter_by(
                pipeline_id=pipeline_id, seq=target_seq + 1
            ).first()
            if next_stage:
                next_stage.status = 'pending'
    else:
        stage.status    = 'error'
        stage.error_msg = output.get('reason', 'Error desconocido')
        pipeline.status = 'error'
        pipeline.error_msg = f'Error en etapa {target_seq} ({agent_role}): {stage.error_msg}'

    try:
        db.session.commit()
    except Exception as persist_exc:
        log.error(f'[Pipeline] OperationalError al persistir etapa {target_seq}: {persist_exc}',
                  exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        db.session.close()
        # Reintento de emergencia con sesión nueva: marcar error sin output_data
        try:
            s2 = PipelineStage.query.filter_by(pipeline_id=pipeline_id, seq=target_seq).first()
            p2 = ContentPipeline.query.get(pipeline_id)
            if s2 and p2:
                s2.status       = 'error'
                s2.error_msg    = f'OperationalError al persistir: {persist_exc}'
                s2.completed_at = now_peru()
                p2.status       = 'error'
                p2.error_msg    = f'OperationalError etapa {target_seq} ({agent_role})'
                db.session.commit()
        except Exception as retry_exc:
            log.error(f'[Pipeline] Reintento emergencia también falló: {retry_exc}')
        return {
            'ok':              False,
            'stage_id':        None,
            'seq':             target_seq,
            'agent':           agent_role,
            'status':          'error',
            'output':          output,
            'pipeline_status': 'error',
            'next_seq':        target_seq,
        }

    return {
        'ok':       output.get('ok', False),
        'stage_id': stage.id,
        'seq':      target_seq,
        'agent':    agent_role,
        'status':   stage.status,
        'output':   output,
        'pipeline_status': pipeline.status,
        'next_seq': pipeline.current_stage_seq,
    }


def approve_and_advance(pipeline_id: int, stage_id: int, user_id: int,
                        notes: str = '') -> dict:
    """
    El usuario aprueba el resultado de una etapa y autoriza continuar.
    Si hay etapas siguientes, las marca como pendientes de ejecución.
    """
    from app.models.content_pipeline import ContentPipeline, PipelineStage
    from app.extensions import db
    from app.utils.formatters import now_peru

    pipeline = ContentPipeline.query.get(pipeline_id)
    stage    = PipelineStage.query.get(stage_id)
    if not pipeline or not stage:
        return {'ok': False, 'reason': 'Pipeline o etapa no encontrada'}

    stage.approved_by  = user_id
    stage.approved_at  = now_peru()
    stage.review_notes = notes
    stage.status       = 'done'

    # Marcar pipeline como done si era la última
    total = len(PIPELINE_SEQUENCES[pipeline.type])
    if stage.seq >= total:
        pipeline.status = 'done'
    else:
        pipeline.status = 'running'
        pipeline.current_stage_seq = stage.seq + 1

    db.session.commit()
    return {'ok': True, 'pipeline_status': pipeline.status,
            'next_seq': pipeline.current_stage_seq}


def retry_stage(pipeline_id: int, stage_id: int,
                user_instruction: str = '',
                user_urls: list = None) -> dict:
    """
    Reintenta únicamente la etapa afectada por error.
    Las etapas siguientes se marcan 'needs_review' si ya estaban done.
    """
    from app.models.content_pipeline import ContentPipeline, PipelineStage
    from app.extensions import db
    from app.utils.formatters import now_peru

    pipeline = ContentPipeline.query.get(pipeline_id)
    stage    = PipelineStage.query.get(stage_id)
    if not pipeline or not stage:
        return {'ok': False, 'reason': 'Pipeline o etapa no encontrada'}

    # Marcar downstream como needs_review
    later = PipelineStage.query.filter(
        PipelineStage.pipeline_id == pipeline_id,
        PipelineStage.seq > stage.seq,
        PipelineStage.status == 'done',
    ).all()
    for s in later:
        s.status = 'needs_review'

    stage.error_msg = None
    pipeline.error_msg = None
    db.session.commit()

    return run_stage(pipeline_id, seq=stage.seq,
                     user_instruction=user_instruction, user_urls=user_urls)


def invalidate_downstream(pipeline_id: int, changed_stage_seq: int):
    """
    Cuando se modifica una entrega anterior, marca las siguientes como needs_review.
    """
    from app.models.content_pipeline import PipelineStage
    from app.extensions import db

    stages = PipelineStage.query.filter(
        PipelineStage.pipeline_id == pipeline_id,
        PipelineStage.seq > changed_stage_seq,
    ).all()
    for s in stages:
        if s.status == 'done':
            s.status = 'needs_review'
    db.session.commit()


# ── Despachador de agentes ────────────────────────────────────────────────────

def _dispatch_agent(stage, pipeline, user_instruction='', user_urls=None):
    role = stage.agent_role

    if role == 'investigador':
        from app.services.content.agents.investigador import run
        return run(stage, pipeline, user_urls=user_urls)

    elif role == 'analista':
        from app.services.content.agents.analista import run
        return run(stage, pipeline)

    elif role == 'creativo':
        from app.services.content.agents.creativo import run
        return run(stage, pipeline)

    elif role == 'editor':
        if pipeline.type == 'diario':
            input_type = 'investigador'
        elif pipeline.type == 'actualidad':
            input_type = 'analista'
        else:
            input_type = 'creativo'
        from app.services.content.agents.editor import run
        return run(stage, pipeline, input_type=input_type)

    elif role == 'productor':
        from app.services.content.agents.productor import run
        return run(stage, pipeline)

    elif role == 'revisor':
        from app.services.content.agents.revisor import run
        return run(stage, pipeline)

    else:
        raise ValueError(f'Rol desconocido: {role}')


def get_agent_summary() -> list:
    """
    Retorna resumen de estado de los 6 agentes: última actividad, pipelines activos.
    """
    from app.models.content_pipeline import ContentPipeline, PipelineStage
    from app.utils.formatters import now_peru

    agents = [
        {'role': 'investigador', 'label': 'Investigador de actualidad',
         'description': 'Recopila fuentes reales: noticias, TC y cotizaciones de Perú e internacional.',
         'icon': 'bi-search', 'color': '#0ea5e9'},
        {'role': 'analista', 'label': 'Analista económico',
         'description': 'Analiza fuentes, separa hechos de interpretación, evalúa impacto en TC.',
         'icon': 'bi-graph-up-arrow', 'color': '#8b5cf6'},
        {'role': 'creativo', 'label': 'Creativo comercial',
         'description': 'Propone campañas usando solo beneficios verificados de la ficha de marca.',
         'icon': 'bi-lightbulb', 'color': '#f59e0b'},
        {'role': 'editor', 'label': 'Editor de redes',
         'description': 'Adapta análisis o propuestas a LinkedIn, Instagram, Facebook y Reels.',
         'icon': 'bi-pen', 'color': '#10b981'},
        {'role': 'productor', 'label': 'Productor visual y audiovisual',
         'description': 'Genera imágenes de marca, carruseles y paquetes para Flow/Gemini.',
         'icon': 'bi-camera-video', 'color': '#ef4444'},
        {'role': 'revisor', 'label': 'Revisor y coordinador editorial',
         'description': 'Verifica fuentes, cifras, afirmaciones comerciales y coherencia visual.',
         'icon': 'bi-shield-check', 'color': '#00DEA8'},
    ]

    for ag in agents:
        role = ag['role']
        # Última etapa ejecutada con este rol
        last_stage = (
            PipelineStage.query
            .filter_by(agent_role=role)
            .filter(PipelineStage.completed_at.isnot(None))
            .order_by(PipelineStage.completed_at.desc())
            .first()
        )
        ag['last_activity'] = (
            last_stage.completed_at.strftime('%d/%m %H:%M')
            if last_stage and last_stage.completed_at else 'Sin actividad'
        )
        ag['last_status'] = last_stage.status if last_stage else 'idle'

        # Etapas pendientes
        pending = PipelineStage.query.filter_by(
            agent_role=role
        ).filter(
            PipelineStage.status.in_(['pending', 'running', 'error', 'needs_review'])
        ).count()
        ag['pending_tasks'] = pending

        # Pipeline activo
        active = (
            PipelineStage.query
            .filter_by(agent_role=role)
            .filter(PipelineStage.status.in_(['running', 'pending']))
            .join(ContentPipeline)
            .filter(ContentPipeline.status.in_(['running', 'waiting_user']))
            .first()
        )
        ag['active_pipeline_id'] = active.pipeline_id if active else None

    return agents

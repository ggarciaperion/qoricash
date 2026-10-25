"""
Módulo de Contenido — /contenido
==================================
Agente creativo que propone, genera imágenes y gestiona el flujo de aprobación
para publicaciones en redes sociales de Qoricash.

Roles con acceso: Master, Presidente de Negocios, Middle Office
"""

import json
import logging
from datetime import datetime

from flask import (Blueprint, render_template, request, jsonify,
                   redirect, url_for, abort, send_file)
from app.extensions import db, csrf
from app.utils.formatters import now_peru

log = logging.getLogger(__name__)

contenido_bp = Blueprint('contenido', __name__, url_prefix='/contenido')

# Acceso abierto (sin login) — modo desarrollo
def _require_access(f):
    return f


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_proposals(network=None, status=None, date_from=None, date_to=None):
    from app.models.content_proposal import ContentProposal
    q = ContentProposal.query.order_by(ContentProposal.created_at.desc())
    if network:
        q = q.filter_by(network=network)
    if status:
        q = q.filter_by(status=status)
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            q = q.filter(ContentProposal.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt_ = datetime.strptime(date_to, '%Y-%m-%d')
            q = q.filter(ContentProposal.created_at <= dt_)
        except ValueError:
            pass
    return q.all()


def _last_batch_age_days():
    """Retorna días desde el último lote, o None si no hay ninguno."""
    from app.models.content_proposal import ContentBatch
    last = ContentBatch.query.order_by(ContentBatch.created_at.desc()).first()
    if not last:
        return None
    delta = now_peru() - last.created_at
    return delta.days


def _proposal_to_dict(p):
    """Serialización mínima de una propuesta para JSON."""
    badge_class, badge_label = p.status_badge
    return {
        'id':          p.id,
        'network':     p.network,
        'network_icon': p.network_icon,
        'topic':       p.topic,
        'objective':   p.objective,
        'audience':    p.audience,
        'text_body':   p.text_body,
        'visual_idea': p.visual_idea,
        'cta':         p.cta,
        'hashtags':    p.hashtags,
        'sources':     p.sources_list,
        'status':      p.status,
        'status_label': badge_label,
        'status_class': badge_class,
        'is_demo':     p.is_demo,
        'image_url':   f'/static/{p.image_path}' if p.image_path else None,
        'scheduled_at': p.scheduled_at.strftime('%Y-%m-%dT%H:%M') if p.scheduled_at else None,
        'published_url': p.published_url,
        'error_msg':   p.error_msg,
        'script_scenes': p.scenes_list,
        'flow_prompt': p.flow_prompt,
        'adjustment_result': p.adjustment_result,
        'created_at':  p.created_at.strftime('%d/%m/%Y %H:%M'),
        'batch_id':    p.batch_id,
    }


# ── Vistas HTML ───────────────────────────────────────────────────────────────

@contenido_bp.route('/')
@_require_access
def index():
    network    = request.args.get('network', '')
    status     = request.args.get('status', '')
    date_from  = request.args.get('date_from', '')
    date_to    = request.args.get('date_to', '')

    proposals  = _get_proposals(network or None, status or None,
                                 date_from or None, date_to or None)
    batch_age  = _last_batch_age_days()

    counts = {'total': len(proposals)}
    for p in proposals:
        counts[p.status] = counts.get(p.status, 0) + 1

    return render_template(
        'contenido/index.html',
        proposals=proposals,
        counts=counts,
        batch_age=batch_age,
        filters={'network': network, 'status': status,
                 'date_from': date_from, 'date_to': date_to},
    )


@contenido_bp.route('/propuesta/<int:pid>')
@_require_access
def detail(pid):
    from app.models.content_proposal import ContentProposal
    p = ContentProposal.query.get_or_404(pid)
    return render_template('contenido/detail.html', p=p,
                           image_url=f'/static/{p.image_path}' if p.image_path else None)


# ── API JSON ──────────────────────────────────────────────────────────────────

@contenido_bp.route('/api/generar', methods=['POST'])
@_require_access
@csrf.exempt
def api_generar():
    """
    Genera un lote de propuestas con el agente creativo.
    Evita duplicar si ya hay un lote generado hoy.
    """
    from app.models.content_proposal import ContentProposal, ContentBatch
    from app.services.content.creative_agent import generate_batch
    from app.services.content.image_service import render_and_save

    force = request.json.get('force', False) if request.json else False
    n     = int((request.json or {}).get('n', 3))
    n     = max(1, min(n, 10))

    # Anti-duplicado: no generar si ya hay un lote de hoy
    if not force:
        age = _last_batch_age_days()
        if age is not None and age == 0:
            return jsonify({'ok': False,
                            'msg': 'Ya se generó un lote hoy. Usa force=true para regenerar.',
                            'age_days': age}), 409

    try:
        raw_proposals = generate_batch(n=n, user_id=None)
    except Exception as e:
        log.error(f'[Contenido] generate_batch: {e}', exc_info=True)
        return jsonify({'ok': False, 'msg': f'Error del agente: {str(e)}'}), 500

    batch = ContentBatch(created_by=None, count=len(raw_proposals),
                         model_used='claude-sonnet-4-6')
    db.session.add(batch)
    db.session.flush()

    created = []
    for raw in raw_proposals:
        try:
            p = ContentProposal(
                batch_id    = batch.id,
                network     = raw.get('network', 'linkedin'),
                topic       = raw.get('topic', ''),
                objective   = raw.get('objective', ''),
                audience    = raw.get('audience', ''),
                tag         = raw.get('tag', ''),
                text_body   = raw.get('text_body', ''),
                visual_idea = raw.get('visual_idea', ''),
                cta         = raw.get('cta', ''),
                hashtags    = raw.get('hashtags', ''),
                sources     = json.dumps(raw.get('sources', []), ensure_ascii=False),
                is_demo     = bool(raw.get('is_demo', False)),
                status      = 'borrador',
            )
            # Reels
            if raw.get('script_scenes'):
                p.script_scenes = json.dumps(raw['script_scenes'], ensure_ascii=False)
            if raw.get('flow_prompt'):
                p.flow_prompt = raw['flow_prompt']

            db.session.add(p)
            db.session.flush()

            # Generar imagen
            img_path = render_and_save(p)
            if img_path:
                p.image_path   = img_path
                p.image_format = 'png'

            created.append(_proposal_to_dict(p))
        except Exception as e:
            log.warning(f'[Contenido] propuesta fallida: {e}')
            err_p = ContentProposal(
                batch_id=batch.id, network=raw.get('network', 'linkedin'),
                topic=raw.get('topic', 'Error'), status='error',
                error_msg=str(e)
            )
            db.session.add(err_p)

    db.session.commit()
    return jsonify({'ok': True, 'proposals': created, 'batch_id': batch.id})


@contenido_bp.route('/api/propuesta/<int:pid>/aprobar', methods=['POST'])
@_require_access
@csrf.exempt
def api_aprobar(pid):
    from app.models.content_proposal import ContentProposal
    p = ContentProposal.query.get_or_404(pid)
    if p.status not in ('borrador', 'rechazado'):
        return jsonify({'ok': False, 'msg': 'Solo se pueden aprobar borradores o rechazados'}), 400
    p.status = 'aprobado'
    p.updated_at = now_peru()
    db.session.commit()
    return jsonify({'ok': True, 'status': 'aprobado'})


@contenido_bp.route('/api/propuesta/<int:pid>/rechazar', methods=['POST'])
@_require_access
@csrf.exempt
def api_rechazar(pid):
    from app.models.content_proposal import ContentProposal
    p = ContentProposal.query.get_or_404(pid)
    data = request.json or {}
    p.status = 'rechazado'
    p.rejection_reason = data.get('reason', '')
    p.updated_at = now_peru()
    db.session.commit()
    return jsonify({'ok': True, 'status': 'rechazado'})


@contenido_bp.route('/api/propuesta/<int:pid>/programar', methods=['POST'])
@_require_access
@csrf.exempt
def api_programar(pid):
    from app.models.content_proposal import ContentProposal
    p = ContentProposal.query.get_or_404(pid)
    data = request.json or {}
    date_str = data.get('scheduled_at', '')
    if not date_str:
        return jsonify({'ok': False, 'msg': 'Falta scheduled_at'}), 400
    try:
        p.scheduled_at = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        p.status = 'programado'
        p.updated_at = now_peru()
        db.session.commit()
        return jsonify({'ok': True, 'status': 'programado',
                        'scheduled_at': date_str})
    except ValueError:
        return jsonify({'ok': False, 'msg': 'Formato de fecha inválido (YYYY-MM-DDTHH:MM)'}), 400


@contenido_bp.route('/api/propuesta/<int:pid>/ajustar', methods=['POST'])
@_require_access
@csrf.exempt
def api_ajustar(pid):
    """Pide al agente que ajuste la pieza según las instrucciones del usuario."""
    from app.models.content_proposal import ContentProposal
    from app.services.content.creative_agent import adjust_proposal
    from app.services.content.image_service import render_and_save

    p = ContentProposal.query.get_or_404(pid)
    data = request.json or {}
    adjustment = data.get('adjustment', '').strip()
    if not adjustment:
        return jsonify({'ok': False, 'msg': 'Falta el texto de ajuste'}), 400

    try:
        result = adjust_proposal(pid, adjustment)
    except Exception as e:
        log.error(f'[Contenido] ajuste pid={pid}: {e}')
        return jsonify({'ok': False, 'msg': str(e)}), 500

    # Aplicar cambios devueltos por el agente
    for field in ('topic', 'text_body', 'visual_idea', 'cta', 'hashtags',
                  'objective', 'audience'):
        if field in result:
            setattr(p, field, result[field])
    if 'script_scenes' in result:
        p.script_scenes = json.dumps(result['script_scenes'], ensure_ascii=False)
    if 'flow_prompt' in result:
        p.flow_prompt = result['flow_prompt']

    p.adjustment_request = adjustment
    p.adjustment_result  = result.get('_notes', '')
    p.status             = 'borrador'  # volver a borrador tras ajuste
    p.updated_at         = now_peru()

    # Redibujar imagen con contenido actualizado
    p.tag = result.get('tag', '')
    new_img = render_and_save(p)
    if new_img:
        p.image_path   = new_img
        p.image_format = 'png'

    db.session.commit()
    return jsonify({'ok': True, 'proposal': _proposal_to_dict(p)})


@contenido_bp.route('/api/propuesta/<int:pid>/editar', methods=['POST'])
@_require_access
@csrf.exempt
def api_editar(pid):
    """Edición manual de campos de una propuesta."""
    from app.models.content_proposal import ContentProposal
    from app.services.content.image_service import render_and_save

    p = ContentProposal.query.get_or_404(pid)
    data = request.json or {}

    edits = p.edits_list
    for field in ('topic', 'text_body', 'visual_idea', 'cta', 'hashtags',
                  'objective', 'audience', 'scheduled_at', 'published_url'):
        if field in data:
            old_val = getattr(p, field, None)
            new_val = data[field]
            if str(old_val) != str(new_val):
                edits.append({'timestamp': now_peru().isoformat(),
                              'field': field, 'old': str(old_val), 'new': str(new_val)})
                setattr(p, field, new_val)

    p.user_edits = json.dumps(edits, ensure_ascii=False)
    p.updated_at = now_peru()

    # Si había una aprobación, la edición la invalida (vuelve a borrador)
    if p.status == 'aprobado' and edits:
        p.status = 'borrador'

    # Re-renderizar si cambió el texto principal
    if any(k in data for k in ('topic', 'text_body', 'cta')):
        p.tag = data.get('tag', '')
        new_img = render_and_save(p)
        if new_img:
            p.image_path   = new_img
            p.image_format = 'png'

    db.session.commit()
    return jsonify({'ok': True, 'proposal': _proposal_to_dict(p)})


@contenido_bp.route('/api/propuesta/<int:pid>/regenerar', methods=['POST'])
@_require_access
@csrf.exempt
def api_regenerar(pid):
    """Regenera únicamente la pieza afectada (útil para errores)."""
    from app.models.content_proposal import ContentProposal
    from app.services.content.creative_agent import generate_batch
    from app.services.content.image_service import render_and_save

    p = ContentProposal.query.get_or_404(pid)

    try:
        raws = generate_batch(n=1)
        raw  = raws[0] if raws else {}
        if raw:
            p.network     = raw.get('network', p.network)
            p.topic       = raw.get('topic', p.topic)
            p.objective   = raw.get('objective', p.objective)
            p.audience    = raw.get('audience', p.audience)
            p.text_body   = raw.get('text_body', p.text_body)
            p.visual_idea = raw.get('visual_idea', p.visual_idea)
            p.cta         = raw.get('cta', p.cta)
            p.hashtags    = raw.get('hashtags', p.hashtags)
            p.sources     = json.dumps(raw.get('sources', []), ensure_ascii=False)
            if raw.get('script_scenes'):
                p.script_scenes = json.dumps(raw['script_scenes'], ensure_ascii=False)
            if raw.get('flow_prompt'):
                p.flow_prompt = raw['flow_prompt']
            p.status      = 'borrador'
            p.error_msg   = None
            p.is_demo     = bool(raw.get('is_demo', False))
            p.tag = raw.get('tag', '')
            img_path = render_and_save(p)
            if img_path:
                p.image_path   = img_path
                p.image_format = 'png'
        p.updated_at = now_peru()
        db.session.commit()
        return jsonify({'ok': True, 'proposal': _proposal_to_dict(p)})
    except Exception as e:
        p.status    = 'error'
        p.error_msg = str(e)
        db.session.commit()
        return jsonify({'ok': False, 'msg': str(e)}), 500


@contenido_bp.route('/api/propuesta/<int:pid>/imagen')
@_require_access
def api_imagen(pid):
    """Descarga directa de la imagen de una propuesta."""
    from app.models.content_proposal import ContentProposal
    import os
    from flask import current_app, send_file

    p = ContentProposal.query.get_or_404(pid)
    if not p.image_path:
        abort(404)

    path = os.path.join(current_app.root_path, 'static', p.image_path)
    if not os.path.exists(path):
        abort(404)

    fname = f'qoricash_{p.network}_{p.id}.png'
    return send_file(path, mimetype='image/png',
                     as_attachment=True, download_name=fname)


@contenido_bp.route('/api/propuesta/<int:pid>/flow-prompt')
@_require_access
def api_flow_prompt(pid):
    """Devuelve el prompt de Google Flow/Gemini para copiar."""
    from app.models.content_proposal import ContentProposal
    p = ContentProposal.query.get_or_404(pid)
    if not p.flow_prompt:
        return jsonify({'ok': False, 'msg': 'Esta propuesta no tiene prompt de video'}), 404
    return jsonify({'ok': True, 'flow_prompt': p.flow_prompt,
                    'topic': p.topic, 'network': p.network})


# ── Estudio Creativo — Vistas de pipeline ────────────────────────────────────

@contenido_bp.route('/agentes')
@_require_access
def agentes():
    from app.services.content.pipeline_coordinator import get_agent_summary
    from app.models.content_pipeline import ContentPipeline
    agents  = get_agent_summary()
    recents = ContentPipeline.query.order_by(
        ContentPipeline.created_at.desc()
    ).limit(10).all()
    return render_template('contenido/agentes.html',
                           agents=agents, recents=recents, active_tab='agentes')


@contenido_bp.route('/pipeline/<int:pid>')
@_require_access
def pipeline_detail(pid):
    from app.models.content_pipeline import ContentPipeline, PipelineStage, ContentSource
    pipeline = ContentPipeline.query.get_or_404(pid)
    stages   = PipelineStage.query.filter_by(pipeline_id=pid).order_by(PipelineStage.seq).all()
    sources  = ContentSource.query.filter_by(pipeline_id=pid).all()
    return render_template('contenido/pipeline_detail.html',
                           pipeline=pipeline, stages=stages, sources=sources)


@contenido_bp.route('/calendario')
@_require_access
def calendario():
    from app.models.content_proposal import ContentProposal
    programados = ContentProposal.query.filter(
        ContentProposal.status.in_(['programado', 'publicado'])
    ).order_by(ContentProposal.scheduled_at).all()
    return render_template('contenido/calendario.html',
                           programados=programados, active_tab='calendario')


@contenido_bp.route('/configuracion')
@_require_access
def configuracion():
    from app.models.content_pipeline import BrandConfig
    brand = BrandConfig.get_current()
    return render_template('contenido/configuracion.html',
                           brand=brand, active_tab='configuracion')


# ── API Pipeline ──────────────────────────────────────────────────────────────

@contenido_bp.route('/api/pipeline/crear', methods=['POST'])
@_require_access
@csrf.exempt
def api_pipeline_crear():
    from app.services.content.pipeline_coordinator import create_pipeline
    data  = request.json or {}
    ptype = data.get('type', 'actualidad')
    title = data.get('title', '')
    notes = data.get('notes', '')
    try:
        pipeline = create_pipeline(ptype, title=title, user_id=None, notes=notes)
        return jsonify({'ok': True, 'pipeline_id': pipeline.id, 'status': pipeline.status})
    except ValueError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400
    except Exception as e:
        log.error(f'[Pipeline] crear: {e}', exc_info=True)
        return jsonify({'ok': False, 'msg': str(e)}), 500


@contenido_bp.route('/api/pipeline/<int:pid>/ejecutar', methods=['POST'])
@_require_access
@csrf.exempt
def api_pipeline_ejecutar(pid):
    from app.services.content.pipeline_coordinator import run_stage
    data             = request.json or {}
    seq              = data.get('seq')
    user_instruction = data.get('user_instruction', '')
    user_urls        = data.get('user_urls', [])
    result = run_stage(pid, seq=seq,
                       user_instruction=user_instruction,
                       user_urls=user_urls or None)
    status_code = 200 if result.get('ok') else 500
    return jsonify(result), status_code


@contenido_bp.route('/api/pipeline/<int:pid>/ejecutar-todo', methods=['POST'])
@_require_access
@csrf.exempt
def api_pipeline_ejecutar_todo(pid):
    """
    Ejecuta TODAS las etapas en secuencia automática.
    Se detiene solo al llegar a la última (waiting_user) o ante error.
    """
    from app.models.content_pipeline import ContentPipeline
    from app.services.content.pipeline_coordinator import run_pipeline_auto

    pipeline = ContentPipeline.query.get_or_404(pid)

    # Anti-duplicate: rechazar si ya está corriendo
    if pipeline.status == 'running':
        return jsonify({'ok': False, 'reason': 'El pipeline ya está en ejecución',
                        'duplicate': True}), 409

    data             = request.json or {}
    user_instruction = data.get('user_instruction', '')
    user_urls        = data.get('user_urls', [])

    result = run_pipeline_auto(pid,
                               user_instruction=user_instruction,
                               user_urls=user_urls or None)
    status_code = 200 if result.get('ok') else 500
    return jsonify(result), status_code


@contenido_bp.route('/api/pipeline/<int:pid>/stage/<int:sid>/aprobar', methods=['POST'])
@_require_access
@csrf.exempt
def api_stage_aprobar(pid, sid):
    from app.services.content.pipeline_coordinator import approve_and_advance
    data  = request.json or {}
    notes = data.get('notes', '')
    result = approve_and_advance(pid, sid, None, notes=notes)
    return jsonify(result), (200 if result.get('ok') else 400)


@contenido_bp.route('/api/pipeline/<int:pid>/stage/<int:sid>/reintentar', methods=['POST'])
@_require_access
@csrf.exempt
def api_stage_reintentar(pid, sid):
    from app.services.content.pipeline_coordinator import retry_stage
    data             = request.json or {}
    user_instruction = data.get('user_instruction', '')
    user_urls        = data.get('user_urls', [])
    result = retry_stage(pid, sid,
                         user_instruction=user_instruction,
                         user_urls=user_urls or None)
    return jsonify(result), (200 if result.get('ok') else 500)


@contenido_bp.route('/api/pipeline/<int:pid>/stage/<int:sid>/ajustar', methods=['POST'])
@_require_access
@csrf.exempt
def api_stage_ajustar(pid, sid):
    """Edición manual del output de una etapa; invalida las posteriores."""
    from app.models.content_pipeline import PipelineStage
    from app.services.content.pipeline_coordinator import invalidate_downstream
    import json as _json

    stage = PipelineStage.query.get_or_404(sid)
    data  = request.json or {}
    patch = data.get('output_patch', {})
    if not patch:
        return jsonify({'ok': False, 'msg': 'Falta output_patch'}), 400

    current_out = stage.output_dict
    current_out.update(patch)
    stage.output_data = _json.dumps(current_out, ensure_ascii=False, default=str)
    stage.version     = (stage.version or 0) + 1
    db.session.commit()

    invalidate_downstream(pid, stage.seq)
    return jsonify({'ok': True, 'seq': stage.seq, 'version': stage.version})


@contenido_bp.route('/api/propuesta/<int:pid>/cargar-recurso', methods=['POST'])
@_require_access
@csrf.exempt
def api_cargar_recurso(pid):
    """Sube el resultado de video generado externamente (Flow/Gemini)."""
    from app.models.content_proposal import ContentProposal
    import os
    from flask import current_app
    from werkzeug.utils import secure_filename

    p = ContentProposal.query.get_or_404(pid)
    f = request.files.get('file')
    if not f:
        return jsonify({'ok': False, 'msg': 'Falta archivo'}), 400

    ext       = os.path.splitext(f.filename)[1].lower()
    allowed   = {'.mp4', '.mov', '.png', '.jpg', '.jpeg'}
    if ext not in allowed:
        return jsonify({'ok': False, 'msg': f'Extensión no permitida: {ext}'}), 400

    save_dir  = os.path.join(current_app.root_path, 'static', 'content', 'uploads')
    os.makedirs(save_dir, exist_ok=True)
    fname     = secure_filename(f'recurso_{pid}_{now_peru().strftime("%Y%m%d%H%M%S")}{ext}')
    fpath     = os.path.join(save_dir, fname)
    f.save(fpath)

    rel_path  = f'content/uploads/{fname}'
    p.image_path   = rel_path
    p.image_format = ext.lstrip('.')
    p.status     = 'borrador'
    p.updated_at = now_peru()
    db.session.commit()
    return jsonify({'ok': True, 'path': f'/static/{rel_path}'})


# ── API Configuración de marca ────────────────────────────────────────────────

@contenido_bp.route('/api/configuracion/guardar', methods=['POST'])
@_require_access
@csrf.exempt
def api_configuracion_guardar():
    from app.models.content_pipeline import BrandConfig
    import json as _json

    data  = request.json or {}
    brand = BrandConfig.get_current()

    raw_benefits = data.get('verified_benefits', '')
    raw_claims   = data.get('prohibited_claims', '')

    if isinstance(raw_benefits, str):
        benefits = [b.strip() for b in raw_benefits.splitlines() if b.strip()]
    else:
        benefits = raw_benefits

    if isinstance(raw_claims, str):
        claims = [c.strip() for c in raw_claims.splitlines() if c.strip()]
    else:
        claims = raw_claims

    brand.verified_benefits  = _json.dumps(benefits, ensure_ascii=False)
    brand.prohibited_claims  = _json.dumps(claims, ensure_ascii=False)
    brand.tone_guide         = data.get('tone_guide', brand.tone_guide or '')
    brand.hashtag_sets       = _json.dumps(
        data.get('hashtag_sets', brand.hashtag_sets_list), ensure_ascii=False)
    brand.updated_at         = now_peru()
    db.session.commit()
    return jsonify({'ok': True, 'benefits_count': len(benefits),
                    'claims_count': len(claims)})


# ── Entrega Diaria ────────────────────────────────────────────────────────────

@contenido_bp.route('/hoy')
@_require_access
def hoy():
    """Vista principal de la Entrega de Hoy."""
    from app.models.content_pipeline import EntregaDiaria
    from app.models.content_proposal import ContentProposal
    from datetime import date

    entrega  = EntregaDiaria.get_today()
    pipeline = entrega.pipeline if entrega else None

    noticias       = []
    comercial      = []
    fuentes_by_cat = {}   # {cat: {fuente_nombre, fuente_url, fecha}}
    cats_faltantes = []   # categorías que el Investigador no pudo cubrir

    if pipeline:
        noticias  = ContentProposal.query.filter_by(
            pipeline_id=pipeline.id, delivery_type='noticia'
        ).order_by(ContentProposal.id).all()
        comercial = ContentProposal.query.filter_by(
            pipeline_id=pipeline.id, delivery_type='comercial'
        ).order_by(ContentProposal.id).all()

        # Fuentes desde el output del Investigador (sin columnas extra en DB)
        from app.models.content_pipeline import PipelineStage
        inv_stage = PipelineStage.query.filter_by(
            pipeline_id=pipeline.id, agent_role='investigador'
        ).first()
        if inv_stage and inv_stage.output_data:
            inv_out = inv_stage.output_dict
            cats_faltantes = inv_out.get('categorias_faltantes', [])
            for cat, noticia in inv_out.get('categorized', {}).items():
                fuentes_by_cat[cat] = {
                    'fuente_nombre':  noticia.get('source_name',
                                      noticia.get('source', noticia.get('fuente_nombre', ''))),
                    'fuente_url':     noticia.get('url', noticia.get('fuente_url', '')),
                    'fecha':          (noticia.get('published_at') or
                                       noticia.get('fecha') or
                                       noticia.get('published') or ''),
                    'is_market_feed': bool(noticia.get('is_market_feed', False)),
                }

    return render_template(
        'contenido/hoy.html',
        entrega        = entrega,
        pipeline       = pipeline,
        noticias       = noticias,
        comercial      = comercial,
        fuentes_by_cat = fuentes_by_cat,
        cats_faltantes = cats_faltantes,
        hoy_str        = date.today().strftime('%d de %B de %Y'),
        active_tab     = 'hoy',
    )


@contenido_bp.route('/api/generar-diario', methods=['POST'])
@_require_access
@csrf.exempt
def api_generar_diario():
    """
    Inicia la generación de la Entrega de Hoy.
    - Dedup: si ya existe EntregaDiaria para hoy y el pipeline NO está en error, rechaza.
    - Crea pipeline 'diario', registra EntregaDiaria, ejecuta todo en background.
    """
    from app.models.content_pipeline import EntregaDiaria, ContentPipeline
    from app.services.content.pipeline_coordinator import create_pipeline, run_pipeline_auto
    import threading

    force = (request.json or {}).get('force', False)

    # Dedup check
    entrega_existente = EntregaDiaria.get_today()
    if entrega_existente and not force:
        pip = entrega_existente.pipeline
        if pip and pip.status not in ('error', 'cancelled'):
            return jsonify({
                'ok':         False,
                'msg':        f'Ya existe entrega para hoy (pipeline #{pip.id}, estado: {pip.status}).',
                'pipeline_id': pip.id,
                'status':     pip.status,
                'duplicate':  True,
            }), 409

    try:
        from datetime import date as _d
        from app.utils.formatters import now_peru
        hoy_str = _d.today().strftime('%Y-%m-%d')
        pipeline = create_pipeline(
            'diario',
            title    = f'Entrega diaria {hoy_str}',
            user_id  = None,
            notes    = 'Generado automáticamente',
        )

        # Registrar EntregaDiaria
        if entrega_existente:
            entrega_existente.pipeline_id = pipeline.id
            entrega_existente.status = 'generando'
            entrega = entrega_existente
        else:
            entrega = EntregaDiaria(
                fecha      = _d.today(),
                pipeline_id = pipeline.id,
                status     = 'generando',
            )
            db.session.add(entrega)
        db.session.commit()

        # Ejecutar en background para no bloquear la respuesta HTTP
        def _bg():
            with pipeline._sa_instance_state.session_id.__class__:
                pass  # no-op para evitar import cíclico
            from app import create_app
            app_ctx = create_app()
            with app_ctx.app_context():
                from app.models.content_pipeline import EntregaDiaria as ED
                from app.models.content_proposal import ContentProposal
                from app.services.content.pipeline_coordinator import run_pipeline_auto
                from app.extensions import db as _db
                result = run_pipeline_auto(pipeline.id)
                # Actualizar EntregaDiaria
                e = ED.query.filter_by(pipeline_id=pipeline.id).first()
                if e:
                    if result.get('ok'):
                        nok = ContentProposal.query.filter_by(
                            pipeline_id=pipeline.id, delivery_type='noticia').count()
                        cok = ContentProposal.query.filter_by(
                            pipeline_id=pipeline.id, delivery_type='comercial').count()
                        e.status       = 'listo' if (nok >= 3 and cok >= 3) else 'parcial'
                        e.noticias_ok  = nok
                        e.comercial_ok = cok
                    else:
                        e.status = 'error'
                        e.notas  = result.get('reason', '')
                    from app.utils.formatters import now_peru as _np
                    e.generado_at = _np()
                    _db.session.commit()

        t = threading.Thread(target=_bg, daemon=True)
        t.start()

        return jsonify({
            'ok':          True,
            'pipeline_id': pipeline.id,
            'msg':         'Entrega diaria iniciada. Recarga en ~2-3 min.',
        })

    except Exception as e:
        log.error(f'[Contenido] generar-diario: {e}', exc_info=True)
        return jsonify({'ok': False, 'msg': str(e)}), 500


@contenido_bp.route('/api/generar-diario-sync', methods=['POST'])
@csrf.exempt
def api_generar_diario_sync():
    """
    Versión síncrona de generar-diario (para el scheduler / cron externo).
    Protegida por X-Cron-Token (si ESTUDIO_CRON_TOKEN está configurado).
    Bloquea hasta completar. No usar desde el navegador.
    """
    import os
    token_esperado = os.environ.get('ESTUDIO_CRON_TOKEN', '').strip()
    if not token_esperado:
        return jsonify({'ok': False, 'msg': 'ESTUDIO_CRON_TOKEN no configurado en el servidor'}), 503
    token_recibido = request.headers.get('X-Cron-Token', '').strip()
    if not token_recibido or token_recibido != token_esperado:
        return jsonify({'ok': False, 'msg': 'No autorizado'}), 401
    from app.models.content_pipeline import EntregaDiaria
    from app.services.content.pipeline_coordinator import create_pipeline, run_pipeline_auto
    from datetime import date as _d

    force = (request.json or {}).get('force', False)
    entrega_existente = EntregaDiaria.get_today()
    if entrega_existente and not force:
        pip = entrega_existente.pipeline
        if pip and pip.status not in ('error', 'cancelled'):
            return jsonify({'ok': False, 'duplicate': True,
                            'pipeline_id': pip.id, 'status': pip.status}), 409

    try:
        from app.utils.formatters import now_peru
        hoy_str  = _d.today().strftime('%Y-%m-%d')
        pipeline = create_pipeline('diario', title=f'Entrega diaria {hoy_str}', user_id=None)

        if entrega_existente:
            entrega_existente.pipeline_id = pipeline.id
            entrega_existente.status = 'generando'
            entrega = entrega_existente
        else:
            entrega = EntregaDiaria(
                fecha=_d.today(), pipeline_id=pipeline.id, status='generando')
            db.session.add(entrega)
        db.session.commit()

        # Run pipeline in OS thread via tpool to avoid blocking eventlet hub
        def _run_sync():
            return run_pipeline_auto(pipeline.id)

        try:
            import eventlet.tpool as _tpool
            result = _tpool.execute(_run_sync)
        except ImportError:
            result = _run_sync()

        from app.models.content_proposal import ContentProposal
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

        return jsonify({**result, 'pipeline_id': pipeline.id,
                        'noticias_ok': nok, 'comercial_ok': cok})

    except Exception as e:
        log.error(f'[Contenido] generar-diario-sync: {e}', exc_info=True)
        return jsonify({'ok': False, 'msg': str(e)}), 500


@contenido_bp.route('/api/propuesta/<int:pid>/aprobar-diario', methods=['POST'])
@_require_access
@csrf.exempt
def api_aprobar_diario(pid):
    """Aprueba una pieza de la entrega diaria, actualizando resource_status."""
    from app.models.content_proposal import ContentProposal
    p = ContentProposal.query.get_or_404(pid)
    p.status          = 'aprobado'
    p.resource_status = 'aprobado'
    p.updated_at      = now_peru()
    db.session.commit()
    return jsonify({'ok': True, 'resource_status': 'aprobado'})


@contenido_bp.route('/api/propuesta/<int:pid>/planificar-diario', methods=['POST'])
@_require_access
@csrf.exempt
def api_planificar_diario(pid):
    """Marca una pieza como planificada para publicación manual."""
    from app.models.content_proposal import ContentProposal
    p = ContentProposal.query.get_or_404(pid)
    data = request.json or {}
    date_str = data.get('scheduled_at', '')
    if date_str:
        try:
            p.scheduled_at = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
    p.status          = 'programado'
    p.resource_status = 'planificado'
    p.updated_at      = now_peru()
    db.session.commit()
    return jsonify({'ok': True, 'resource_status': 'planificado'})


@contenido_bp.route('/api/propuesta/<int:pid>/cargar-recurso-diario', methods=['POST'])
@_require_access
@csrf.exempt
def api_cargar_recurso_diario(pid):
    """Carga imagen/video generado externamente para una pieza diaria."""
    from app.models.content_proposal import ContentProposal
    import os
    from flask import current_app
    from werkzeug.utils import secure_filename

    p = ContentProposal.query.get_or_404(pid)
    f = request.files.get('file')
    if not f:
        return jsonify({'ok': False, 'msg': 'Falta archivo'}), 400

    ext     = os.path.splitext(f.filename)[1].lower()
    allowed = {'.mp4', '.mov', '.png', '.jpg', '.jpeg', '.webp'}
    if ext not in allowed:
        return jsonify({'ok': False, 'msg': f'Extensión no permitida: {ext}'}), 400

    save_dir = os.path.join(current_app.root_path, 'static', 'content', 'uploads')
    os.makedirs(save_dir, exist_ok=True)
    fname    = secure_filename(f'diario_{pid}_{now_peru().strftime("%Y%m%d%H%M%S")}{ext}')
    fpath    = os.path.join(save_dir, fname)
    f.save(fpath)

    p.image_path      = f'content/uploads/{fname}'
    p.image_format    = ext.lstrip('.')
    p.resource_status = 'recurso_cargado'
    p.updated_at      = now_peru()
    db.session.commit()
    return jsonify({'ok': True, 'path': f'/static/{p.image_path}',
                    'resource_status': 'recurso_cargado'})

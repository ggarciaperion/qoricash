"""
Agente 6: Revisor y coordinador editorial.

Comprueba:
- Fuentes: ¿los hechos citados están respaldados?
- Cifras: ¿son verificables o se inventaron?
- Afirmaciones comerciales: ¿están en BrandConfig.verified_benefits?
- Repetición de temas: ¿ya se publicó algo similar recientemente?
- Coherencia visual: ¿hay imagen generada y concuerda con el texto?

Devuelve observaciones o presenta la pieza para aprobación final.
"""
import json
import logging

log = logging.getLogger(__name__)

SYSTEM = """Eres el Revisor editorial de Qoricash, una casa de cambio digital peruana.

Tu función es verificar que las piezas de contenido sean:
1. Verídicas: hechos respaldados en fuentes, sin cifras inventadas.
2. Regulatorias: no afirman nada sobre la SBS u organismos reguladores
   más allá de lo verificado (p.ej. estar registrado en el padrón SBS).
3. Comercialmente responsables: solo beneficios verificados, sin promesas vacías.
4. Sin repetición: temas frescos, no duplicados de contenido reciente.
5. Coherentes: texto e imagen alineados.

REVISIÓN VISUAL DEL PROMPT (para piezas con flow_prompt):
Verifica que el prompt visual:
a) Describe una escena concreta con sujeto, acción y entorno — NO una ilustración abstracta.
b) Representa el beneficio comercial de forma comprensible, sin íconos ni diagramas.
c) Respeta los servicios reales de Qoricash (casa de cambio): no inventa interfaces,
   importes, tasas, garantías, sellos regulatorios ni testimonios.
d) Usa el color de marca (#196BFE) como acento en un detalle, no como tinte de toda la imagen.
e) Se diferencia de las otras propuestas del día (escenario y composición distintos).
f) No incluye elementos prohibidos: dashboards flotantes, monedas/billetes decorativos,
   neón, hologramas, fondos tecnológicos, piel plástica, texto en inglés.

IMPORTANTE: Revisar el texto del prompt no equivale a verificar la calidad de la imagen
generada. Si no hay imagen cargada, la revisión visual queda como MANUAL — no marques
la pieza como aprobada solo porque el prompt existe.

Responde de forma directa: qué apruebas, qué necesita corrección y por qué.
"""


RETRY_LIMIT = 2   # máximo de correcciones automáticas antes de escalar al usuario


def run(stage, pipeline):
    """
    Ejecuta el Revisor.
    En modo 'diario': revisa 6 piezas (3 noticias + 3 comercial), aplica correcciones
    con límite de reintentos. Marca resource_status según resultado.
    En modo estándar: revisa propuestas del batch y presenta al usuario.
    """
    if pipeline.type == 'diario':
        return _run_diario(stage, pipeline)
    from app.models.content_pipeline import PipelineStage, ContentSource, BrandConfig
    from app.models.content_proposal import ContentProposal
    from app.services.ai.client import ask_json, SONNET

    # Recopilar contexto: fuentes, análisis/creativo, editor, propuestas
    sources = ContentSource.query.filter_by(pipeline_id=pipeline.id).all()
    brand   = BrandConfig.get_current()

    # Obtener propuestas generadas en este pipeline (por batch vinculado al pipeline)
    productor_stage = PipelineStage.query.filter_by(
        pipeline_id=pipeline.id,
        agent_role='productor',
    ).first()

    proposals = []
    if productor_stage and productor_stage.output_dict.get('batch_id'):
        batch_id = productor_stage.output_dict['batch_id']
        proposals = ContentProposal.query.filter_by(batch_id=batch_id).all()

    if not proposals:
        return {
            'ok':       False,
            'approved': False,
            'reason':   'No hay propuestas del Productor para revisar.',
            'observations': [],
        }

    # Construir contexto para Claude
    sources_summary = '\n'.join(
        f'- [{s.source_type}] {s.title} ({s.published_at or "s/f"}) '
        f'— {"URL: " + s.url if s.url else "sin URL"}'
        for s in sources[:8]
    ) or 'Sin fuentes registradas.'

    proposals_summary = []
    for p in proposals[:4]:
        proposals_summary.append(
            f'Red: {p.network.upper()}\n'
            f'Tema: {p.topic}\n'
            f'Texto (inicio): {(p.text_body or "")[:300]}...\n'
            f'CTA: {p.cta}\n'
            f'Imagen: {"sí" if p.image_path else "no"}\n'
            f'Fuentes en pieza: {len(p.sources_list)}'
        )

    prompt = f"""Revisa las siguientes piezas de contenido de Qoricash.

FUENTES DE INFORMACIÓN UTILIZADAS:
{sources_summary}

BENEFICIOS VERIFICADOS DE MARCA:
{json.dumps(brand.benefits_list[:6], ensure_ascii=False)}

AFIRMACIONES PROHIBIDAS:
{json.dumps(brand.claims_list[:5], ensure_ascii=False)}

PIEZAS A REVISAR:
{'---'.join(proposals_summary)}

Para cada pieza devuelve un objeto JSON:
{{
  "revisiones": [
    {{
      "red": "linkedin|instagram|facebook|reel",
      "aprobada": true|false,
      "observaciones": ["obs 1", "obs 2"],
      "correcciones_requeridas": ["corrección específica si no está aprobada"],
      "alerta_regulatoria": "si hay alguna afirmación indebida sobre regulación o null"
    }}
  ],
  "aprobacion_global": true|false,
  "siguiente_paso": "qué debe hacer el usuario o el pipeline",
  "nota_revision": "resumen de la revisión"
}}
Solo JSON."""

    try:
        result = ask_json(prompt, system=SYSTEM, model=SONNET, max_tokens=2500)
        if not isinstance(result, dict):
            raise ValueError(f'Respuesta inesperada: {type(result)}')

        aprobacion = result.get('aprobacion_global', False)
        result['ok'] = True
        result['proposal_ids'] = [p.id for p in proposals]

        # Si aprobado globalmente, marcar propuestas como aprobadas
        if aprobacion:
            from app.extensions import db
            from app.utils.formatters import now_peru
            for p in proposals:
                p.status = 'aprobado'
                p.updated_at = now_peru()
            db.session.commit()
            result['proposals_approved'] = len(proposals)

        return result

    except Exception as e:
        log.error(f'[Revisor] Claude error: {e}', exc_info=True)
        return {
            'ok':       False,
            'approved': False,
            'reason':   f'Error del agente revisor: {str(e)}',
            'observations': [],
        }


# ── Modo diario ───────────────────────────────────────────────────────────────

def _run_diario(stage, pipeline):
    """
    Revisor en modo diario.
    Revisa las 6 piezas (3 noticias + 3 comercial) del pipeline diario.
    - Piezas sin correcciones → resource_status = 'pendiente_aprobacion'
    - Piezas con correcciones leves (retry_count < RETRY_LIMIT) → guarda correcciones, marca 'pendiente_aprobacion'
    - Piezas con correcciones críticas → resource_status = 'recurso_pendiente' (requiere atención)
    """
    from app.models.content_pipeline import ContentSource, BrandConfig
    from app.models.content_proposal import ContentProposal
    from app.services.ai.client import ask_json, SONNET
    from app.extensions import db
    from app.utils.formatters import now_peru

    brand   = BrandConfig.get_current()
    sources = ContentSource.query.filter_by(pipeline_id=pipeline.id).all()

    # Obtener propuestas del pipeline diario (por pipeline_id)
    proposals = ContentProposal.query.filter_by(pipeline_id=pipeline.id).all()

    if not proposals:
        return {
            'ok':    False,
            'reason': 'No hay propuestas del Director Visual para revisar.',
            'revisiones': [],
        }

    sources_summary = '\n'.join(
        f'- [{s.source_type}] {s.title} ({s.published_at or "s/f"})'
        + (f' — {s.url}' if s.url else '')
        for s in sources[:8]
    ) or 'Sin fuentes registradas.'

    proposals_ctx = []
    for p in proposals:
        tipo = '📰 Noticia' if p.delivery_type == 'noticia' else '💼 Comercial'
        proposals_ctx.append(
            f'[ID:{p.id}] {tipo} | {p.noticia_category or p.audience or ""}\n'
            f'Tema: {p.topic}\n'
            f'Texto (inicio): {(p.text_body or "")[:250]}...\n'
            f'CTA: {p.cta}\n'
            f'Prompt visual: {"sí (" + (p.flow_prompt or "")[:80] + "...)" if p.flow_prompt else "no"}'
        )

    prompt = f"""Revisa estas piezas de contenido de Qoricash para su entrega diaria.

FUENTES UTILIZADAS:
{sources_summary}

BENEFICIOS VERIFICADOS:
{json.dumps(brand.benefits_list[:6], ensure_ascii=False)}

AFIRMACIONES PROHIBIDAS:
{json.dumps(brand.claims_list[:5], ensure_ascii=False)}

PIEZAS:
{'---'.join(proposals_ctx)}

Para cada pieza evalúa:
TEXTO:
1. ¿Es preciso, sin cifras inventadas ni afirmaciones regulatorias indebidas?
2. ¿Cumple aproximadamente 80-140 palabras?
3. ¿Las piezas comerciales usan solo beneficios verificados?
4. ¿El CTA es claro y apropiado?

PROMPT VISUAL (si existe):
5. ¿Describe una escena concreta con sujeto, acción y entorno? (No ilustración abstracta)
6. ¿El beneficio comercial es comprensible sin íconos ni diagramas?
7. ¿Evita elementos prohibidos: dashboards, monedas flotantes, neón, texto en inglés?
8. ¿Esta pieza se diferencia de las otras piezas comerciales del día?
9. Si no hay imagen cargada, la revisión visual es MANUAL — no aprobar automáticamente.

Devuelve un JSON:
{{
  "revisiones": [
    {{
      "proposal_id": <id>,
      "aprobada": true|false,
      "correcciones": ["corrección específica si no aprobada"],
      "alerta_critica": "afirmación indebida o null",
      "nota": "observación general"
    }}
  ],
  "resumen": "estado general de la entrega en 1-2 oraciones"
}}
Solo JSON."""

    # Guardar IDs antes de cerrar la sesión: proposals se re-consultarán tras la llamada IA.
    _proposal_ids = [p.id for p in proposals]
    db.session.close()

    try:
        result = ask_json(prompt, system=SYSTEM, model=SONNET, max_tokens=3000)
        if not isinstance(result, dict):
            raise ValueError(f'Respuesta inesperada: {type(result)}')

        # Re-consultar proposals con sesión fresca (la anterior fue liberada antes del AI call).
        proposals = ContentProposal.query.filter(
            ContentProposal.id.in_(_proposal_ids)
        ).all()

        revisiones = result.get('revisiones', [])
        rev_map = {r['proposal_id']: r for r in revisiones if 'proposal_id' in r}

        aprobadas = 0
        con_correcciones = 0

        for p in proposals:
            rev = rev_map.get(p.id, {})
            aprobada        = rev.get('aprobada', True)
            correcciones    = rev.get('correcciones', [])
            alerta_critica  = rev.get('alerta_critica')
            nota            = rev.get('nota', '')

            p.revisor_notas = nota
            if correcciones:
                p.correcciones = json.dumps(correcciones, ensure_ascii=False)
                con_correcciones += 1

            if alerta_critica:
                # Alerta crítica: requiere atención manual
                p.resource_status = 'recurso_pendiente'
            else:
                # Listo para aprobación del usuario
                p.resource_status = 'pendiente_aprobacion'
                if aprobada:
                    aprobadas += 1

        db.session.commit()

        return {
            'ok':             True,
            'revisiones':     revisiones,
            'resumen':        result.get('resumen', ''),
            'total':          len(proposals),
            'aprobadas':      aprobadas,
            'con_correcciones': con_correcciones,
            'proposal_ids':   [p.id for p in proposals],
            'mode':           'diario',
        }

    except Exception as e:
        log.error(f'[Revisor-diario] Claude error: {e}', exc_info=True)
        return {
            'ok':    False,
            'reason': f'Error del Revisor diario: {str(e)}',
            'revisiones': [],
        }

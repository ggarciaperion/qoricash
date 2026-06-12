"""
Agente de Prospección Inteligente — Lead Scoring
-------------------------------------------------
Analiza el portafolio de prospectos y asigna un score de conversión (0-100)
basado en: rubro, tamaño, historial de contacto, nivel de interés, estado comercial,
volumen estimado, y señales de engagement.

También genera el mensaje de email personalizado por empresa.
"""
import logging
from app.services.ai.client import ask_json, ask, HAIKU, SONNET

_log = logging.getLogger(__name__)

# Rubros con alta demanda de cambio de divisas
_HIGH_VALUE_RUBROS = {
    'importacion', 'exportacion', 'comercio exterior', 'logistica', 'agro',
    'mineria', 'construccion', 'tecnologia', 'farmaceutica', 'textil',
    'manufactura', 'industria', 'retail', 'supermercado', 'hoteleria',
}

def _score_heuristico(p) -> int:
    """Score base 0-100 por reglas antes de pasar a Claude."""
    score = 0
    rubro = (p.rubro or '').lower()
    for kw in _HIGH_VALUE_RUBROS:
        if kw in rubro:
            score += 20
            break
    tam = (p.tamano_empresa or '').lower()
    score += {'grande': 20, 'mediana': 15, 'pequeña': 8, 'mype': 3}.get(tam, 5)
    score += min((p.num_contactos or 0) * 5, 15)
    interes = (p.nivel_interes or '').lower()
    score += {'alto': 25, 'medio': 12, 'bajo': 0}.get(interes, 5)
    estado = (p.estado_comercial or '').lower()
    score += {'negociacion': 20, 'interesado': 15, 'contactado': 8, 'nuevo': 5}.get(estado, 0)
    if p.volumen_estimado_usd and float(p.volumen_estimado_usd) > 10000:
        score += 10
    return min(score, 100)


def score_batch(limit: int = 100) -> dict:
    """
    Puntúa los top prospectos sin cliente_lfc (los que aún no son clientes).
    Retorna lista ordenada por score descendente.
    """
    try:
        from app.models.prospecto import Prospecto
        prospectos = (
            Prospecto.query
            .filter(
                Prospecto.estado_email != 'REBOTE',
                Prospecto.estado_comercial != 'NO CONTACTAR',
            )
            .order_by(Prospecto.num_contactos.desc())
            .limit(limit * 3)
            .all()
        )

        scored = []
        for p in prospectos:
            base_score = _score_heuristico(p)
            scored.append({
                'id':             p.id,
                'razon_social':   p.razon_social or p.nombre_contacto or '—',
                'rubro':          p.rubro or '—',
                'tamano':         p.tamano_empresa or '—',
                'estado':         p.estado_comercial or '—',
                'nivel_interes':  p.nivel_interes or '—',
                'contactos':      p.num_contactos or 0,
                'volumen_usd':    float(p.volumen_estimado_usd or 0),
                'ultimo_contacto':p.fecha_ultimo_contacto or '—',
                'score':          base_score,
                'email':          p.email or '—',
                'departamento':   p.departamento or '—',
            })

        scored.sort(key=lambda x: x['score'], reverse=True)
        top = scored[:limit]

        # Enriquecer el top 10 con análisis Claude
        if top:
            top_10_txt = '\n'.join(
                f"{i+1}. {p['razon_social']} | rubro:{p['rubro']} | tamaño:{p['tamano']} "
                f"| interés:{p['nivel_interes']} | estado:{p['estado']} | contactos:{p['contactos']} "
                f"| vol_est:${p['volumen_usd']:,.0f} | score_base:{p['score']}"
                for i, p in enumerate(top[:10])
            )
            prompt = f"""Eres el director comercial de QoriCash, casa de cambio B2B en Lima Perú.
Analiza estos 10 prospectos y para cada uno asigna un score final (0-100) y una acción recomendada.

PROSPECTOS (score_base ya calculado por reglas, ajusta según tu criterio):
{top_10_txt}

Responde SOLO JSON:
{{
  "enriched": [
    {{
      "rank": 1,
      "razon_social": "...",
      "score_final": <0-100>,
      "potencial": "alto|medio|bajo",
      "accion": "<acción específica en una oración>",
      "mensaje_apertura": "<primera frase personalizada para el email>"
    }}
  ],
  "insight_general": "<observación clave del portafolio en 1-2 oraciones>"
}}"""
            enriched_data = ask_json(prompt, model=HAIKU, max_tokens=2000)
            # Merge enriched data con top 10
            if 'enriched' in enriched_data:
                enriched_map = {e['razon_social']: e for e in enriched_data['enriched']}
                for p in top[:10]:
                    key = p['razon_social']
                    if key in enriched_map:
                        e = enriched_map[key]
                        p['score_final']       = e.get('score_final', p['score'])
                        p['potencial']         = e.get('potencial', '—')
                        p['accion']            = e.get('accion', '—')
                        p['mensaje_apertura']  = e.get('mensaje_apertura', '')
            insight = enriched_data.get('insight_general', '')
        else:
            insight = 'Sin prospectos disponibles para analizar.'

        return {
            'ok':      True,
            'total':   len(prospectos),
            'scored':  top,
            'insight': insight,
        }
    except Exception as e:
        _log.error(f'[ProspectingAgent] Error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}


def generate_email(prospecto_id: int) -> dict:
    """
    Genera un email personalizado para un prospecto específico.
    """
    try:
        from app.models.prospecto import Prospecto
        from app.models.exchange_rate import ExchangeRate

        p = Prospecto.query.get(prospecto_id)
        if not p:
            return {'ok': False, 'error': 'Prospecto no encontrado'}

        er = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
        compra = float(er.buy_rate)  if er else 3.70
        venta  = float(er.sell_rate) if er else 3.75

        prompt = f"""Eres el director comercial de QoriCash, casa de cambio digital B2B en Lima.
Escribe un email de prospección CORTO y PERSONALIZADO para:

Empresa: {p.razon_social or 'la empresa'}
Rubro: {p.rubro or 'comercio'}
Tamaño: {p.tamano_empresa or 'mediana'}
Contacto: {p.nombre_contacto or 'Estimado/a'}
Cargo: {p.cargo or 'Gerente'}
Estado previo: {p.estado_comercial or 'nuevo'}
Notas: {p.notas or 'sin notas previas'}

TC HOY: Compramos USD a {compra:.4f} | Vendemos USD a {venta:.4f}

Responde SOLO JSON:
{{
  "asunto": "<asunto del email>",
  "saludo": "<saludo personalizado>",
  "cuerpo": "<2-3 párrafos max, menciona el TC de hoy, beneficios concretos para su rubro>",
  "llamada_accion": "<CTA específico>"
}}"""

        result = ask_json(prompt, model=HAIKU, max_tokens=1000)
        result['prospecto_id'] = prospecto_id
        return {'ok': True, 'email': result}

    except Exception as e:
        _log.error(f'[ProspectingAgent] Error email: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}

"""
Agente de Análisis de Mercado
------------------------------
Reemplaza el clasificador de keywords con Claude para:
  1. Clasificar noticias (impacto + dirección USD) con comprensión real
  2. Generar el análisis diario del mercado en lenguaje natural
  3. Predecir tendencia TC PEN/USD con justificación

Integración: se llama desde daily_analysis_service.py como upgrade drop-in.
"""
import logging
from app.services.ai.client import ask_json, ask, HAIKU, SONNET

_log = logging.getLogger(__name__)


def classify_news(title: str, summary: str = '') -> tuple[str, str, float]:
    """
    Clasifica una noticia financiera.
    Retorna: (impact_level, direction, sentiment_score)
    - impact_level: 'high' | 'medium' | 'low'
    - direction:    'bullish_usd' | 'bearish_usd' | 'neutral'
    - sentiment_score: -1.0 a +1.0

    Fallback al clasificador de keywords si falla.
    """
    try:
        prompt = f"""Clasifica esta noticia financiera para su impacto en el tipo de cambio USD/PEN de Perú.

TÍTULO: {title}
RESUMEN: {summary[:300] if summary else '(sin resumen)'}

Responde SOLO JSON:
{{"impact": "high|medium|low", "direction": "bullish_usd|bearish_usd|neutral", "score": <float -1.0 a 1.0>}}

Donde:
- impact: high=mueve mercados (Fed, BCRP, NFP, crisis), medium=relevante, low=ruido
- direction: bullish_usd=dólar sube vs sol, bearish_usd=dólar baja, neutral=sin impacto claro
- score: -1.0=muy bearish USD, 0=neutral, +1.0=muy bullish USD"""

        r = ask_json(prompt, model=HAIKU, max_tokens=100)
        return r.get('impact', 'low'), r.get('direction', 'neutral'), float(r.get('score', 0.0))

    except Exception as e:
        _log.warning(f'[MarketAgent] classify_news fallback: {e}')
        from app.services.market.news_classifier import classify as _legacy
        return _legacy(title, summary)


def generate_daily_analysis(news_items: list, market_data: dict) -> dict:
    """
    Genera el análisis diario del mercado PEN/USD.

    Args:
        news_items: lista de dicts {title, summary, impact_level, direction, sentiment_score}
        market_data: {
            tc_actual: {compra, venta},
            tc_ayer: {compra, venta},
            competitors_avg: {compra, venta},
            usd_bcrp: float (optional),
        }

    Retorna: {trend, confidence, title, summary, main_drivers, prediction_text}
    """
    try:
        high_news   = [n for n in news_items if n.get('impact_level') == 'high']
        medium_news = [n for n in news_items if n.get('impact_level') == 'medium']

        news_txt = ''
        for n in (high_news + medium_news)[:8]:
            dir_label = {'bullish_usd': '↑USD', 'bearish_usd': '↓USD', 'neutral': '—'}.get(n.get('direction', ''), '—')
            news_txt += f"  [{dir_label}] {n.get('title', '')}\n"

        tc = market_data.get('tc_actual', {})
        tc_ayer = market_data.get('tc_ayer', {})
        var_venta = round(float(tc.get('venta', 0)) - float(tc_ayer.get('venta', 0)), 4) if tc and tc_ayer else 0

        prompt = f"""Eres el analista de mercado de QoriCash, casa de cambio en Lima Perú.
Genera el análisis diario del tipo de cambio USD/PEN.

TC QORICASH HOY: Compra {tc.get('compra', '—')} | Venta {tc.get('venta', '—')}
VARIACIÓN vs AYER: {var_venta:+.4f}

NOTICIAS RELEVANTES:
{news_txt if news_txt else '  (sin noticias de alto impacto)'}

Responde SOLO JSON:
{{
  "trend": "alcista|bajista|lateral",
  "confidence": <entero 0-100>,
  "title": "<título del análisis, max 80 caracteres>",
  "summary": "<análisis en 3-4 oraciones: qué pasó, por qué, qué esperar>",
  "main_drivers": ["<driver1>", "<driver2>", "<driver3>"],
  "prediction_text": "<predicción para las próximas 4 horas en 1 oración>",
  "recomendacion_trader": "<consejo operativo concreto en 1 oración>"
}}"""

        result = ask_json(prompt, model=SONNET, max_tokens=800)
        return {'ok': True, **result}

    except Exception as e:
        _log.error(f'[MarketAgent] generate_daily_analysis error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}


def generate_intraday_update(base_analysis: dict, new_news: list) -> dict:
    """
    Actualización intradía: dado el análisis base y nuevas noticias, genera actualización.
    """
    try:
        news_txt = '\n'.join(f"  - {n.get('title', '')}" for n in new_news[:5])
        prompt = f"""Actualización intradía del mercado USD/PEN para QoriCash.

ANÁLISIS BASE PREVIO: {base_analysis.get('summary', '')}
TENDENCIA BASE: {base_analysis.get('trend', 'lateral')}

NUEVAS NOTICIAS:
{news_txt if news_txt else '(sin nuevas noticias)'}

Responde SOLO JSON:
{{
  "trend": "alcista|bajista|lateral",
  "confidence": <0-100>,
  "title": "<título actualización>",
  "summary": "<actualización en 2-3 oraciones>",
  "cambio_relevante": true|false,
  "prediction_text": "<predicción próximas 2 horas>"
}}"""

        result = ask_json(prompt, model=HAIKU, max_tokens=500)
        return {'ok': True, **result}

    except Exception as e:
        _log.error(f'[MarketAgent] intraday update error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}

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


def generate_trader_analysis(snap, news_items: list, events: list,
                             fed_rate, bcrp_rate,
                             net_score: int, trend: str, confidence: int,
                             mode: str = 'base') -> dict:
    """
    Genera análisis profesional en lenguaje de trader FX para QoriCash.
    Reemplaza _build_base_text y _build_intraday_text del DailyAnalysisService.

    Args:
        snap: objeto MarketSnapshot (o None)
        news_items: lista de dicts {title, direction, impact_level, source}
        events: lista de EconomicEvent del día
        fed_rate, bcrp_rate: floats
        net_score, trend, confidence: del scoring engine
        mode: 'base' (8:30 AM) | 'intraday' (actualización manual)

    Returns: {ok, title, summary, alertas, niveles_clave, recomendacion_trader}
    """
    try:
        def _f(val, decimals=2):
            return f'{float(val):.{decimals}f}' if val is not None else 'N/D'

        def _chg(val, decimals=2):
            if val is None: return 'N/D'
            v = float(val)
            return f'{v:+.{decimals}f}%'

        # ── Snapshot de precios ──────────────────────────────────────────────
        mkt = ''
        if snap:
            usdpen_line = f'USD/PEN: S/{_f(snap.usdpen,4)} ({_chg(snap.usdpen_chg_pct)})'
            mkt = f"""
PRECIOS ACTUALES:
  {usdpen_line}
  DXY: {_f(snap.dxy,3)} ({_chg(snap.dxy_chg_pct)})  | EUR/USD: {_f(snap.eurusd,4)} ({_chg(snap.eurusd_chg_pct)})
  VIX: {_f(snap.vix)}  ({_chg(snap.vix_chg_pct)})   | S&P500: {_f(snap.sp500)} ({_chg(snap.sp500_chg_pct)}) | Nasdaq: {_f(snap.nasdaq)} ({_chg(snap.nasdaq_chg_pct)})
  Gold: ${_f(snap.gold)} ({_chg(snap.gold_chg_pct)}) | Oil WTI: ${_f(snap.oil)} ({_chg(snap.oil_chg_pct)})
  Cobre: ${_f(snap.copper,4)} ({_chg(snap.copper_chg_pct)})  (crítico para PEN — Perú 2do exportador mundial)
  Treasury 10Y: {_f(snap.treasury_10y,3)}% ({_chg(snap.treasury_10y_chg,3)})
  USD/JPY: {_f(snap.usdjpy,3)} ({_chg(snap.usdjpy_chg_pct)})  | BTC: ${_f(snap.btc)} ({_chg(snap.btc_chg_pct)})
  EEM (Emergentes ETF): {_f(snap.eem)} ({_chg(snap.eem_chg_pct)}) | EPU (Perú ETF): {_f(snap.epu)} ({_chg(snap.epu_chg_pct)})"""

        # ── Tasas de referencia ──────────────────────────────────────────────
        rates = f'Tasa FED: {fed_rate:.2f}%' if fed_rate else 'Tasa FED: N/D'
        rates += f' | Tasa BCRP: {bcrp_rate:.2f}%' if bcrp_rate else ' | Tasa BCRP: N/D'

        # ── Noticias relevantes ──────────────────────────────────────────────
        high_news = [n for n in news_items if n.get('impact_level') == 'high']
        med_news  = [n for n in news_items if n.get('impact_level') == 'medium']
        bull_count = sum(1 for n in news_items if n.get('direction') == 'bullish_usd')
        bear_count = sum(1 for n in news_items if n.get('direction') == 'bearish_usd')

        news_txt = ''
        for n in (high_news + med_news)[:10]:
            arrow = {'bullish_usd': '▲USD', 'bearish_usd': '▼USD', 'neutral': '━'}.get(n.get('direction',''), '━')
            news_txt += f"  [{arrow}] [{n.get('impact_level','').upper()}] [{n.get('source','')}] {n.get('title','')}\n"

        # ── Eventos económicos del día ───────────────────────────────────────
        ev_txt = ''
        for ev in events[:6]:
            ev_txt += f"  ⚑ {getattr(ev,'flag','')} {getattr(ev,'event_name','')} ({getattr(ev,'country','')}) — {getattr(ev,'impact','').upper()}\n"

        mode_label = 'ANÁLISIS BASE 8:30 AM' if mode == 'base' else 'ACTUALIZACIÓN INTRADÍA'
        from datetime import datetime, timezone, timedelta
        hora_lima = datetime.now(timezone(timedelta(hours=-5))).strftime('%H:%M')

        prompt = f"""Eres el analista senior de FX de QoriCash, casa de cambio digital en Lima Perú.
Hora Lima actual: {hora_lima} | Modo: {mode_label}

SCORING ENGINE (reglas cuantitativas):
  Tendencia: {trend.upper()} | Confianza: {confidence}% | Net Score: {net_score:+d}
  Señales alcistas USD: {bull_count} | Señales bajistas USD: {bear_count}
{mkt}

TASAS DE REFERENCIA:
  {rates}

NOTICIAS PROCESADAS (últimas horas):
{news_txt if news_txt else '  (sin noticias relevantes en la ventana)'}

EVENTOS ECONÓMICOS HOY:
{ev_txt if ev_txt else '  (sin eventos de alto impacto programados)'}

TAREA: Genera un análisis FX profesional para el equipo trader de QoriCash.
Habla como trader experimentado en FX de mercados emergentes latinoamericanos.
Sé específico con niveles, catalizadores, y riesgos. No uses frases genéricas.
Menciona correlaciones relevantes (cobre↔sol, DXY↔USD/PEN, VIX↔risk-off, EPU↔sentimiento Perú).
Si hay evento de alto impacto hoy, explica exactamente cómo puede mover el USD/PEN.

Responde SOLO JSON:
{{
  "title": "<titular ejecutivo con sesgo y nivel spot, máx 100 chars>",
  "summary": "<análisis completo en 4-5 párrafos. Párrafo 1: diagnóstico y sesgo. Párrafo 2: drivers principales con números específicos. Párrafo 3: correlaciones cross-asset relevantes. Párrafo 4: niveles y zonas de interés en USD/PEN. Párrafo 5: implicaciones operativas para QoriCash (en qué momento ajustar TC, qué esperar de los clientes)>",
  "alertas": [
    "<alerta accionable específica — ej: 'DXY rompió 104.5 — vigilar presión alcista en sol', 'VIX >30 activa modo risk-off — clientes buscarán cobertura en USD'>",
    "<alerta 2>",
    "<alerta 3 si aplica>"
  ],
  "niveles_clave": {{
    "soporte_usdpen": "<nivel en S/ — ej: 3.7250>",
    "resistencia_usdpen": "<nivel en S/ — ej: 3.7800>",
    "zona_neutral": "<rango lateral — ej: 3.74–3.76>",
    "nivel_critico": "<nivel que si rompe cambia el sesgo completamente>"
  }},
  "recomendacion_trader": "<instrucción operativa concreta para las próximas 4h: cuándo ajustar TC, hacia dónde, qué señal esperar>",
  "sesion": "<contexto de sesión: London close / NY session / Lima apertura / cierre local — y qué implica para la liquidez>",
  "riesgo_principal": "<el principal riesgo o catalizador que podría invalidar el análisis>"
}}"""

        result = ask_json(prompt, model=SONNET, max_tokens=2000)
        return {'ok': True, **result}

    except Exception as e:
        _log.error(f'[MarketAgent] generate_trader_analysis error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}


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

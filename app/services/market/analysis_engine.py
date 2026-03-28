"""
Motor de análisis: convierte precios + noticias en señales interpretables.
Fase 1: correlaciones básicas (DXY, Oro, Petróleo, índices)
Fase 3: + VIX, Cobre, Bono 10Y, EUR/USD, ETF Perú/Emergentes
"""
import json
import logging
from .price_fetcher import MarketPrices

logger = logging.getLogger(__name__)

# ── Reglas de correlación ─────────────────────────────────────────────────────
# threshold positivo → disparar si chg_pct >= threshold
# threshold negativo → disparar si chg_pct <= threshold
# weight: importancia 1-5

RULES = [
    # ── DXY (correlación directa más fuerte con USD/PEN) ─────────────────────
    dict(asset='dxy', threshold=+0.20, direction='bullish', weight=5,
         reason="DXY ↑ {chg:+.2f}% — dólar se fortalece globalmente → USD/PEN al alza"),
    dict(asset='dxy', threshold=-0.20, direction='bearish', weight=5,
         reason="DXY ↓ {chg:+.2f}% — dólar se debilita globalmente → presión bajista USD/PEN"),

    # ── VIX (índice de miedo — risk-off = USD sube) ───────────────────────────
    dict(asset='vix', threshold=+5.0,  direction='bullish', weight=4,
         reason="VIX ↑ {chg:+.2f}% — pánico en mercados → flight-to-safety → dólar como refugio"),
    dict(asset='vix', threshold=+2.0,  direction='bullish', weight=2,
         reason="VIX sube {chg:+.2f}% — aumento de aversión al riesgo → soporte para el dólar"),
    dict(asset='vix', threshold=-5.0,  direction='bearish', weight=3,
         reason="VIX ↓ {chg:+.2f}% — mercados en modo risk-on → capitales fluyen a emergentes"),

    # ── Bono 10Y (rendimiento sube = USD atractivo) ───────────────────────────
    dict(asset='treasury_10y', threshold=+0.03, direction='bullish', weight=4,
         reason="Bono 10Y EE.UU. sube {chg:+.2f}% — mayor rendimiento atrae capitales hacia USD"),
    dict(asset='treasury_10y', threshold=-0.03, direction='bearish', weight=3,
         reason="Bono 10Y EE.UU. cae {chg:+.2f}% — menor atractivo del USD → presión bajista"),

    # ── Cobre (Perú es 2do exportador mundial — cobre ↑ = PEN ↑ = USD/PEN ↓) ─
    dict(asset='copper', threshold=+1.5, direction='bearish', weight=3,
         reason="Cobre ↑ {chg:+.2f}% — beneficia exportaciones peruanas → sol se aprecia"),
    dict(asset='copper', threshold=-1.5, direction='bullish', weight=2,
         reason="Cobre ↓ {chg:+.2f}% — presión sobre economías exportadoras de metales como Perú"),

    # ── EUR/USD (EUR sube = DXY baja = USD más débil) ────────────────────────
    dict(asset='eurusd', threshold=+0.30, direction='bearish', weight=2,
         reason="EUR/USD ↑ {chg:+.2f}% — euro gana vs dólar → DXY debilitado → USD/PEN a la baja"),
    dict(asset='eurusd', threshold=-0.30, direction='bullish', weight=2,
         reason="EUR/USD ↓ {chg:+.2f}% — euro cae vs dólar → DXY fortalecido → USD/PEN al alza"),

    # ── ETF Perú EPU (cae = riesgo país Perú sube = USD/PEN sube) ────────────
    dict(asset='epu', threshold=-1.5, direction='bullish', weight=3,
         reason="ETF Perú (EPU) ↓ {chg:+.2f}% — sentimiento negativo sobre Perú → presión sobre el sol"),
    dict(asset='epu', threshold=+1.5, direction='bearish', weight=2,
         reason="ETF Perú (EPU) ↑ {chg:+.2f}% — flujo positivo a activos peruanos → sol se fortalece"),

    # ── ETF Emergentes EEM ────────────────────────────────────────────────────
    dict(asset='eem', threshold=-1.5, direction='bullish', weight=2,
         reason="ETF Emergentes (EEM) ↓ {chg:+.2f}% — salida de capitales de EM → USD como refugio"),
    dict(asset='eem', threshold=+1.5, direction='bearish', weight=1,
         reason="ETF Emergentes (EEM) ↑ {chg:+.2f}% — apetito por riesgo en EM → capitales fluyen a región"),

    # ── Oro ───────────────────────────────────────────────────────────────────
    dict(asset='gold', threshold=+1.0, direction='bearish', weight=2,
         reason="Oro ↑ {chg:+.2f}% — demanda de refugio refleja desconfianza en dólar"),
    dict(asset='gold', threshold=-0.8, direction='bullish', weight=2,
         reason="Oro ↓ {chg:+.2f}% — menor demanda de refugio → fortaleza relativa del dólar"),

    # ── Petróleo ─────────────────────────────────────────────────────────────
    dict(asset='oil', threshold=+2.0, direction='bearish', weight=1,
         reason="Petróleo ↑ {chg:+.2f}% — beneficia economías exportadoras como Perú → sol se aprecia"),
    dict(asset='oil', threshold=-2.5, direction='bullish', weight=1,
         reason="Petróleo ↓ {chg:+.2f}% — presión sobre monedas ligadas a commodities"),

    # ── S&P 500 ───────────────────────────────────────────────────────────────
    dict(asset='sp500', threshold=-1.5, direction='bullish', weight=2,
         reason="S&P 500 ↓ {chg:+.2f}% — risk-off en Wall Street → flujo hacia dólar como activo seguro"),
    dict(asset='sp500', threshold=+1.5, direction='bearish', weight=1,
         reason="S&P 500 ↑ {chg:+.2f}% — risk-on → capitales hacia mercados emergentes"),

    # ── USD/JPY (JPY es activo refugio — JPY sube = USD/JPY baja = risk-off) ──
    dict(asset='usdjpy', threshold=+0.50, direction='bullish', weight=3,
         reason="USD/JPY ↑ {chg:+.2f}% — yen se deprecia, mercados en modo risk-on → no hay flight-to-safety"),
    dict(asset='usdjpy', threshold=-0.50, direction='bearish', weight=3,
         reason="USD/JPY ↓ {chg:+.2f}% — yen se aprecia como refugio → mercados en modo risk-off, presión bajista en EM"),

    # ── Bitcoin (sentimiento de riesgo global) ────────────────────────────────
    dict(asset='btc', threshold=+3.0, direction='bearish', weight=1,
         reason="Bitcoin ↑ {chg:+.2f}% — apetito de riesgo elevado → capitales en modo risk-on"),
    dict(asset='btc', threshold=-5.0, direction='bullish', weight=2,
         reason="Bitcoin ↓ {chg:+.2f}% — caída cripto refleja aversión al riesgo → favorece USD"),
]


def _evaluate_rules(prices: MarketPrices) -> tuple[int, int, list[str]]:
    bullish = bearish = 0
    triggers = []

    for rule in RULES:
        ap = getattr(prices, rule['asset'], None)
        if not ap or not ap.ok or ap.chg_pct is None:
            continue
        chg = ap.chg_pct
        thr = rule['threshold']
        fired = (thr > 0 and chg >= thr) or (thr < 0 and chg <= thr)
        if not fired:
            continue

        reason = rule['reason'].format(chg=chg)
        if rule['direction'] == 'bullish':
            bullish += rule['weight']
        else:
            bearish += rule['weight']
        triggers.append(reason)

    return bullish, bearish, triggers


def _score_news(news: list) -> tuple[int, int, list[str]]:
    bullish = bearish = 0
    news_triggers = []
    for article in news:
        direction = article.get('direction', 'neutral')
        impact    = article.get('impact_level', 'low')
        weight    = 3 if impact == 'high' else (2 if impact == 'medium' else 0)
        if weight == 0:
            continue
        title_short = article.get('title', '')[:65]
        source      = article.get('source', '')
        if direction == 'bullish_usd':
            bullish += weight
            news_triggers.append(f'[{source}] "{title_short}…"')
        elif direction == 'bearish_usd':
            bearish += weight
            news_triggers.append(f'[{source}] "{title_short}…"')
    return bullish, bearish, news_triggers[:3]


def _build_reasoning(triggers: list[str], net: int, prices: MarketPrices) -> str:
    if not triggers:
        return ("No hay señales técnicas dominantes en este momento. "
                "El mercado se mantiene en rango sin catalizadores claros.")

    direction = "alcista" if net > 0 else "bajista"

    # Cada factor en su propia línea
    parts = [f"  ({i+1}) {t}" for i, t in enumerate(triggers[:5])]
    body = f"El análisis detecta presión {direction} sobre el USD/PEN:\n" + "\n".join(parts)

    # Spot price context
    ap = prices.usdpen
    if ap.ok and ap.chg_pct and abs(ap.chg_pct) > 0.05:
        move = "compradora" if ap.chg_pct > 0 else "vendedora"
        body += (
            f"\n\nEl spot USD/PEN refleja {ap.chg_pct:+.2f}% en la sesión, "
            f"confirmando presión {move} en el mercado cambiario local."
        )

    # Contexto VIX + DXY
    vix = prices.vix
    dxy = prices.dxy
    ctx = []
    if vix.ok and vix.price:
        v = vix.price
        if v > 30:
            ctx.append(f"VIX {v:.1f} — alta volatilidad sistémica, se esperan movimientos amplios en USD/PEN")
        elif v > 20:
            ctx.append(f"VIX {v:.1f} — incertidumbre global elevada, el dólar tiende a fortalecerse como activo refugio")
        else:
            ctx.append(f"VIX {v:.1f} — mercado en calma relativa, menor prima de refugio en el dólar")
    if dxy.ok and dxy.price:
        ctx.append(f"DXY {dxy.price:.2f} — referencia del poder global del dólar frente a divisas principales")
    if ctx:
        body += "\n\nContexto de mercado: " + " · ".join(ctx) + "."

    # Convicción
    total = abs(net)
    if total >= 10:
        body += (
            "\n\nSeñal de alta convicción — múltiples factores técnicos alinean "
            "consistentemente en la misma dirección."
        )
    elif total >= 5:
        body += (
            "\n\nConvicción moderada — mayoría de factores apuntan en la misma dirección, "
            "con señales contrarias menores. Gestionar riesgo con prudencia."
        )
    else:
        body += (
            "\n\nSeñal débil — los factores no son concluyentes. "
            "Se recomienda monitorear la evolución antes de tomar posición."
        )

    return body


def generate_signal(prices: MarketPrices, news: list = None) -> dict:
    bullish, bearish, triggers = _evaluate_rules(prices)

    if news:
        n_bull, n_bear, n_triggers = _score_news(news)
        bullish += n_bull
        bearish += n_bear
        triggers.extend(n_triggers)

    net   = bullish - bearish
    total = bullish + bearish
    confidence = min(int(abs(net) / max(total, 1) * 100), 95) if total > 0 else 0

    if net >= 4:
        signal_type, title = 'bullish',  'Posible subida del dólar'
    elif net <= -4:
        signal_type, title = 'bearish',  'Presión bajista sobre el dólar'
    elif total >= 6:
        signal_type, title = 'volatile', 'Alta volatilidad — señales mixtas'
    else:
        signal_type, title = 'lateral',  'Mercado sin tendencia definida'

    reasoning = _build_reasoning(triggers, net, prices)

    logger.info(f"[Mercado] Señal: {signal_type} conf={confidence}% bull={bullish} bear={bearish}")

    return {
        'signal_type':  signal_type,
        'confidence':   confidence,
        'title':        title,
        'reasoning':    reasoning,
        'triggered_by': json.dumps(triggers),
    }

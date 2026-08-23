"""
Clasificador de noticias financieras.
Determina: impacto (high/medium/low) y dirección (bullish_usd / bearish_usd / neutral).
Sin ML — basado en keywords ponderadas para máxima velocidad y transparencia.
"""

# ── Filtro de relevancia financiera ──────────────────────────────────────────
# Términos que delatan contenido NO financiero → rechazar el artículo
_BLOCKLIST = [
    # Deportes
    'futbol', 'fútbol', 'football', 'partido de fut', 'gol ', ' goles',
    'liga de fútbol', 'liga española', 'premier league', 'champions league',
    'europa league', 'copa del mundo', 'copa america', 'copa américa',
    'mundial de fut', 'selección peruana', 'seleccion peruana',
    'sporting cristal', 'universitario', 'alianza lima',
    'nba ', ' nfl ', ' mlb ', ' nhl ', ' fifa ',
    'baloncesto', 'basquetbol', 'basquet', 'vóley', 'voley', 'voleibol',
    'atletismo', 'ciclismo', 'natación', 'tenis ',
    'directv sport', 'direc tv sport', 'espn ', 'fanatiz', 'win sport',
    # Entretenimiento / espectáculos
    'farándula', 'farandula', 'espectáculos', 'espectaculos',
    'telenovela', 'reality show', 'reality tv',
    'concierto de ', 'gira de ', 'álbum de ', 'album de ',
    'película del', 'pelicula del', 'serie de netflix', 'serie de hbo',
    'disney+', 'amazon prime video',
    'cantante ', 'reggaeton', 'salsa ', 'cumbia ',
    # Tecnología de consumo (no fintech)
    'playstation', 'xbox game', 'nintendo switch', 'videojuego', 'gaming ',
    # Salud / lifestyle
    'receta de ', 'receta cocin', 'dieta ', 'adelgazar', 'horóscopo', 'horoscopo',
    'turismo ', 'destino turístico', 'destino turistico',
    # Política sin impacto económico
    'elecciones municipales', 'candidato a la alcaldía',
]

# Al menos uno de estos términos debe estar presente → noticia financiera
_FINANCIAL_REQUIRED = [
    # Divisas / tipo de cambio
    'dólar', 'dollar', 'usd', 'tipo de cambio', 'exchange rate', 'divisa',
    'sol peruano', 'pen ', 'moneda ',
    # Mercados de valores
    'bolsa', 'mercado ', 'market', 'acciones', 'stock ', 'índice', 'indice',
    'wall street', 's&p', 'nasdaq', 'dow jones', 'nyse', 'bvl',
    # Commodities
    'oro ', 'gold ', 'petróleo', 'petroleo', 'oil ', 'cobre ', 'copper',
    'plata ', 'silver ', 'commodity', 'commodities', 'mineral', 'minería', 'mineria',
    # Macro
    'economía', 'economia', 'economy', 'pbi', 'gdp', 'pib',
    'inflación', 'inflation', 'deflación', 'deflation',
    'tasa de interés', 'tasa de interes', 'interest rate',
    'fed ', 'federal reserve', 'banco central', 'bcrp', 'bce', 'bcra',
    'crecimiento económico', 'recesión', 'recesion', 'recession',
    'exportaciones', 'importaciones', 'balanza comercial', 'balanza de pagos',
    'déficit fiscal', 'deficit fiscal', 'superávit', 'superavit',
    'reservas internacionales', 'deuda pública', 'deuda publica',
    # Finanzas corporativas / banca
    'finanzas', 'finance', 'inversión', 'inversion', 'investment',
    'deuda ', 'debt ', 'bono ', 'bond ', 'yield ', 'rendimiento financiero',
    'banco ', 'bank ', 'crédito', 'credito', 'préstamo', 'prestamo',
    'fusión', 'fusion', 'adquisición', 'acquisition', 'opa ', 'ipo ',
    'utilidades ', 'earnings', 'ganancias empresa',
    # Comercio / política económica
    'arancel', 'tariff', 'guerra comercial', 'trade war', 'sanción', 'sanction',
    'fmi', 'imf', 'banco mundial', 'world bank', 'ocde', 'oecd',
    'mef ', 'sunat ', 'indecopi', 'sbs ', 'smv ',
    # Criptomonedas
    'bitcoin', 'btc', 'ethereum', 'eth ', 'crypto', 'criptomoneda', 'blockchain',
]


def is_financial(title: str, summary: str = '') -> bool:
    """
    Retorna True solo si el artículo es de temática financiera/económica.
    Doble filtro:
      1. Blocklist: rechaza si hay términos de deportes / entretenimiento / lifestyle
      2. Whitelist: requiere al menos un término financiero
    """
    text = (title + ' ' + (summary or '')).lower()

    # Capa 1: rechazar contenido claramente no financiero
    if any(term in text for term in _BLOCKLIST):
        return False

    # Capa 2: requiere al menos un término de temática financiera
    return any(term in text for term in _FINANCIAL_REQUIRED)


# ── Palabras clave por nivel de impacto ──────────────────────────────────────

HIGH_IMPACT = [
    # FED / política monetaria EE.UU.
    "federal reserve", "fed ", "jerome powell", "fomc", "interest rate decision",
    "rate hike", "rate cut", "basis points", "bps",
    # Inflación EE.UU.
    "consumer price index", "cpi", "pce inflation", "core inflation",
    # Empleo EE.UU.
    "nonfarm payroll", "nfp", "unemployment rate", "jobs report",
    # Trump / política comercial
    "trump", "tariffs", "aranceles", "trade war", "sanctions",
    # BCRP / Perú macro
    "banco central de reserva", "bcrp", "tipo de cambio oficial",
    # Crisis sistémica
    "recession", "recesión", "financial crisis", "default", "debt ceiling",
    "bank collapse", "banking crisis",
]

MEDIUM_IMPACT = [
    # Tipo de cambio directo
    "dólar", "dollar", "usd/pen", "sol peruano", "tipo de cambio", "exchange rate",
    # Activos clave
    "gold", "oro", "crude oil", "petróleo", "wti", "brent",
    "s&p 500", "nasdaq", "dow jones", "wall street", "bolsa",
    "dxy", "dollar index", "índice del dólar",
    # Macro Perú
    "pbi perú", "gdp peru", "economía peruana", "exportaciones perú",
    "reservas internacionales", "balanza comercial",
    # Macro global
    "gdp", "pib", "economic growth", "crecimiento económico",
    "emerging markets", "mercados emergentes",
    # Fed secundario
    "federal open market", "treasury yield", "bond yield", "rendimiento bono",
    "10-year treasury", "us 10y",
]

# ── Palabras clave por dirección USD ─────────────────────────────────────────

BULLISH_USD = {
    # Peso alto (3 pts)
    "high": [
        "hawkish", "rate hike", "sube tasas", "alza de tasas",
        "higher for longer", "quantitative tightening", "qt",
        "strong jobs", "better than expected", "beats estimates",
        "trump tariffs", "new tariffs", "escalation", "sanctions",
        "flight to safety", "risk off", "safe haven demand",
        "dollar strengthens", "dollar gains", "dólar sube",
        "sol se deprecia", "presión sobre el sol",
        "salida de capitales perú", "political uncertainty peru",
    ],
    # Peso medio (1 pt)
    "low": [
        "dollar", "usd rises", "greenback up", "dxy up",
        "inflation concern", "fed minutes", "fed official",
        "economic uncertainty", "market volatility",
    ],
}

BEARISH_USD = {
    # Peso alto (3 pts)
    "high": [
        "dovish", "rate cut", "baja tasas", "recorte de tasas",
        "fed pivot", "pausa fed", "fed pause", "quantitative easing", "qe",
        "dollar weakens", "dollar falls", "dólar baja",
        "sol se aprecia", "soles gana",
        "weak jobs", "misses estimates", "disappoints",
        "us recession", "recesión eeuu", "economic slowdown us",
        "risk on", "emerging markets rally", "capital inflows peru",
        "crecimiento perú", "superávit comercial",
    ],
    # Peso medio (1 pt)
    "low": [
        "dollar retreats", "greenback down", "dxy falls",
        "fed rate expectations lower", "inflation easing",
        "economic recovery emerging",
    ],
}


def classify(title: str, summary: str = "") -> tuple[str, str, float]:
    """
    Retorna: (impact_level, direction, sentiment_score)
    - impact_level: 'high' | 'medium' | 'low'
    - direction:    'bullish_usd' | 'bearish_usd' | 'neutral'
    - sentiment_score: -1.0 (muy bearish) a +1.0 (muy bullish)
    """
    text = (title + " " + (summary or "")).lower()

    # ── Impacto ───────────────────────────────────────────────────────────────
    if any(kw in text for kw in HIGH_IMPACT):
        impact = "high"
    elif any(kw in text for kw in MEDIUM_IMPACT):
        impact = "medium"
    else:
        impact = "low"

    # ── Dirección ─────────────────────────────────────────────────────────────
    bullish_score = (
        sum(3 for kw in BULLISH_USD["high"] if kw in text) +
        sum(1 for kw in BULLISH_USD["low"]  if kw in text)
    )
    bearish_score = (
        sum(3 for kw in BEARISH_USD["high"] if kw in text) +
        sum(1 for kw in BEARISH_USD["low"]  if kw in text)
    )

    net = bullish_score - bearish_score
    total = bullish_score + bearish_score

    if net > 0:
        direction = "bullish_usd"
    elif net < 0:
        direction = "bearish_usd"
    else:
        direction = "neutral"

    # Sentiment normalizado [-1, +1]
    sentiment = round(max(-1.0, min(1.0, net / max(total, 1))), 2) if total > 0 else 0.0

    return impact, direction, sentiment

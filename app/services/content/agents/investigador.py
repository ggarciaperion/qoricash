"""
Agente 1: Investigador de actualidad.

Recopila información real de fuentes identificadas sobre Perú y el contexto
internacional. Guarda URLs, fechas y evidencia utilizada.

REGLAS:
- No inventa noticias ni cotizaciones.
- Si no hay acceso a una URL, registra el bloqueo.
- Distingue fuente oficial (BCRP, SBS, MEF) de medios de comunicación.
- Permite que el usuario aporte URLs adicionales para investigación.
"""
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# Fuentes que SÍ tienen datos disponibles a través del news_fetcher existente
KNOWN_SOURCES = {
    'market_feed':    'Feed de mercado local (MarketService)',
    'news_fetcher':   'Fetcher de noticias financieras',
}


def run(stage, pipeline, user_urls=None):
    """
    Ejecuta el Investigador sobre el pipeline/stage.
    Recupera fuentes reales y las guarda en ContentSource.

    En modo 'diario': devuelve exactamente 3 noticias categorizadas
    (nacional, internacional, mercados), priorizando noticias del día o el día anterior.

    Args:
        stage: PipelineStage (seq=1)
        pipeline: ContentPipeline
        user_urls: lista de {'url': str, 'title': str} aportadas por el usuario
    Returns:
        dict con sources encontradas y bloqueos
    """
    if pipeline.type == 'diario':
        return _run_diario(stage, pipeline)

    from app.models.content_pipeline import ContentSource
    from app.extensions import db

    sources_created = []
    blocks = []

    # ── 1. Fuentes del market feed ────────────────────────────────────────────
    try:
        from app.services.market.market_service import MarketService
        data = MarketService.get_dashboard_data()
        snap = data.get('snapshot') or {}
        analysis = data.get('daily_analysis') or {}

        if snap.get('usdpen'):
            src = ContentSource(
                pipeline_id  = pipeline.id,
                stage_id     = stage.id,
                url          = None,
                title        = f'USD/PEN {snap["usdpen"]} — tipo de cambio de mercado',
                excerpt      = (
                    f'Tipo de cambio USD/PEN: {snap["usdpen"]}\n'
                    f'Variación hoy: {snap.get("usdpen_chg_pct", "n/d")}\n'
                    f'Fuente: MarketService (datos de mercado local)\n'
                    f'Nota: Esta es la tasa de mercado de referencia, no la tasa operativa de Qoricash.'
                ),
                published_at = datetime.now().strftime('%Y-%m-%d'),
                source_name  = 'MarketService (feed interno)',
                source_type  = 'market_feed',
                is_verified  = True,
                used_in_analysis = True,
            )
            db.session.add(src)
            sources_created.append({'title': src.title, 'type': 'market_feed'})

        if analysis.get('summary'):
            src2 = ContentSource(
                pipeline_id  = pipeline.id,
                stage_id     = stage.id,
                url          = None,
                title        = 'Análisis de mercado diario',
                excerpt      = analysis['summary'][:800],
                published_at = str(analysis.get('generated_at', ''))[:10],
                source_name  = 'Análisis interno (MarketService)',
                source_type  = 'market_feed',
                is_verified  = True,
                used_in_analysis = True,
            )
            db.session.add(src2)
            sources_created.append({'title': src2.title, 'type': 'market_feed'})

    except Exception as e:
        log.warning(f'[Investigador] MarketService no disponible: {e}')
        blocks.append({'source': 'MarketService', 'reason': str(e)})

    # ── 2. Noticias: DB primero (rápido y confiable) → live RSS si DB vacía ──
    news_items = []

    # Fuente primaria: noticias almacenadas en DB (últimas 72 h, high/medium)
    try:
        from app.models.market import MarketNews
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=7)
        db_news = (
            MarketNews.query
            .filter(MarketNews.impact_level.in_(['high', 'medium']))
            .filter(MarketNews.published_at >= cutoff)
            .order_by(MarketNews.published_at.desc())
            .limit(8)
            .all()
        )
        for n in db_news:
            news_items.append({
                'title':        n.title,
                'url':          n.url,
                'summary':      n.summary or '',
                'published_at': n.published_at.strftime('%Y-%m-%d') if n.published_at else '',
                'source_name':  n.source or 'Medio de comunicación',
                'impact_level': n.impact_level,
            })
        if db_news:
            log.info(f'[Investigador] DB: {len(db_news)} noticias de las últimas 72 h')
    except Exception as e:
        log.warning(f'[Investigador] DB noticias falló: {e}')
        blocks.append({'source': 'news_db', 'reason': str(e)})

    # Fuente secundaria: RSS live solo si la DB no tiene noticias recientes
    if not news_items:
        try:
            from app.services.market.news_fetcher import fetch_all_news
            live = fetch_all_news()
            news_items = [n for n in live if n.get('impact_level') in ('high', 'medium')][:8]
            if news_items:
                log.info(f'[Investigador] RSS live: {len(news_items)} noticias')
            else:
                blocks.append({'source': 'news_fetcher_live', 'reason': 'Sin noticias relevantes en RSS'})
        except Exception as e:
            log.warning(f'[Investigador] news_fetcher live falló: {e}')
            blocks.append({'source': 'news_fetcher_live', 'reason': str(e)})

    for n in news_items:
        excerpt = n.get('summary') or n.get('title', '')
        src = ContentSource(
            pipeline_id  = pipeline.id,
            stage_id     = stage.id,
            url          = n.get('url') or n.get('link'),
            title        = n.get('title', 'Sin título'),
            excerpt      = excerpt[:600],
            published_at = str(n.get('published_at', ''))[:10],
            source_name  = n.get('source_name', 'Medio de comunicación'),
            source_type  = 'media',
            is_verified  = False,
            used_in_analysis = True,
        )
        db.session.add(src)
        sources_created.append({
            'title':  src.title,
            'url':    src.url,
            'source': src.source_name,
            'type':   'media',
        })

    # ── 3. URLs aportadas por el usuario ─────────────────────────────────────
    if user_urls:
        for item in user_urls:
            # Accept both plain strings and {url, title} dicts
            if isinstance(item, str):
                url, title = item.strip(), item.strip()[:80]
            else:
                url   = item.get('url', '').strip()
                title = item.get('title', url[:80])
            if not url:
                continue
            content = _fetch_url_content(url)
            src = ContentSource(
                pipeline_id  = pipeline.id,
                stage_id     = stage.id,
                url          = url,
                title        = title,
                excerpt      = content or '[No se pudo recuperar el contenido de la URL]',
                published_at = datetime.now().strftime('%Y-%m-%d'),
                source_name  = 'URL aportada por el usuario',
                source_type  = 'user_provided',
                is_verified  = False,
                used_in_analysis = bool(content),
            )
            db.session.add(src)
            entry = {'title': title, 'url': url, 'type': 'user_provided'}
            if not content:
                entry['warning'] = 'URL no accesible; se registró sin contenido.'
            sources_created.append(entry)

    db.session.flush()

    if not sources_created:
        return {
            'ok':         False,
            'sources':    [],
            'blocks':     blocks or [{'source': 'todas', 'reason': 'Sin fuentes disponibles en este entorno'}],
            'count':      0,
            'message':    (
                'No se encontraron fuentes. Aporte URLs en el formulario de entrada '
                'o configure el acceso al feed de noticias.'
            ),
        }

    return {
        'ok':      True,
        'sources': sources_created,
        'blocks':  blocks,
        'count':   len(sources_created),
        'message': f'{len(sources_created)} fuentes recuperadas. '
                   + (f'{len(blocks)} fuentes no accesibles.' if blocks else ''),
    }


def _fetch_url_content(url: str, timeout: int = 8) -> str:
    """
    Intenta recuperar el texto de una URL.
    Corre en OS thread si eventlet está activo (evita conflicto httpx).
    Retorna texto o cadena vacía si falla.
    """
    def _do_fetch():
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(20000)
                # Extraer texto plano básico (sin HTML parser para evitar dependencias)
                text = raw.decode('utf-8', errors='replace')
                # Eliminar tags HTML simples
                import re
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:1000]
        except Exception as e:
            log.debug(f'[Investigador] fetch {url}: {e}')
            return ''

    try:
        import eventlet.tpool
        return eventlet.tpool.execute(_do_fetch)
    except ImportError:
        return _do_fetch()


# ── Modo diario ───────────────────────────────────────────────────────────────

# Keywords para clasificar noticias. Solo nacional y mercados; resto = internacional.
_KW_NACIONAL = [
    'peru', 'perú', 'lima', 'mef', 'bcrp', 'sbs', 'sunat', 'sol peruano',
    'economía peruana', 'pbi peruano', 'bcr peru', 'exportación peruana',
    'banco central de reserva', 'ministerio de economía', 'congreso peru',
]
_KW_MERCADOS = [
    'tipo de cambio', 'usd/pen', 'usd pen', 'dólar hoy', 'dólar peruano',
    'sol peruano', 'bolsa de valores lima', 'bvl',
]


def _categorizar_diario(title: str, summary: str) -> str:
    """
    Clasifica una noticia para el modo diario.
    Regla estricta: nacional si menciona a Perú/BCRP/MEF en contexto económico local;
    mercados solo para TC USD/PEN y BVL; todo lo demás es internacional.
    """
    texto = (title + ' ' + (summary or '')).lower()
    for kw in _KW_NACIONAL:
        if kw in texto:
            return 'nacional'
    for kw in _KW_MERCADOS:
        if kw in texto:
            return 'mercados'
    return 'internacional'


def _run_diario(stage, pipeline):
    """
    Investigador en modo diario.
    Produce EXACTAMENTE una fuente por categoría (nacional, internacional, mercados).
    La categoría mercados proviene siempre del feed de mercado (USD/PEN).
    nacional e internacional provienen de MarketNews DB (últimas 48 h, luego 7 días).

    Si una categoría no tiene noticia disponible, la marca en 'categorias_faltantes'.
    NO reclasifica artificialmente para cubrir el contador.
    """
    from app.models.content_pipeline import ContentSource
    from app.models.market import MarketNews
    from app.extensions import db
    from datetime import timedelta

    blocks          = []
    categorized     = {}   # {cat: news_item_dict}

    # ── 1. Categoría MERCADOS siempre desde el market feed ────────────────────
    try:
        from app.services.market.market_service import MarketService
        data = MarketService.get_dashboard_data()
        snap = data.get('snapshot') or {}
        if snap.get('usdpen'):
            tc = snap['usdpen']
            chg = snap.get('usdpen_chg_pct', 'n/d')
            categorized['mercados'] = {
                'title':        f'Cierre USD/PEN: S/ {tc} ({chg} en el día)',
                'url':          None,
                'summary':      (
                    f'Tipo de cambio USD/PEN al cierre: S/ {tc}. '
                    f'Variación del día: {chg}. '
                    f'Dato: feed interno de mercado (MarketService). '
                    f'Esta es la tasa de mercado de referencia local, no la tasa BCRP oficial '
                    f'ni la tasa operativa de Qoricash.'
                ),
                'published_at': datetime.now().strftime('%Y-%m-%d'),
                'source_name':  'MarketService (feed interno — último cierre)',
                'is_market_feed': True,
            }
    except Exception as e:
        log.warning(f'[Investigador-diario] MarketService: {e}')
        blocks.append({'source': 'MarketService', 'reason': str(e)})

    # ── 2. Categorías NACIONAL e INTERNACIONAL desde DB ───────────────────────
    news_pool = []
    try:
        cutoff = datetime.now() - timedelta(hours=48)
        recent = (
            MarketNews.query
            .filter(MarketNews.impact_level.in_(['high', 'medium']))
            .filter(MarketNews.published_at >= cutoff)
            .order_by(MarketNews.published_at.desc())
            .limit(30)
            .all()
        )
        if not recent:
            cutoff = datetime.now() - timedelta(days=7)
            recent = (
                MarketNews.query
                .filter(MarketNews.impact_level.in_(['high', 'medium']))
                .filter(MarketNews.published_at >= cutoff)
                .order_by(MarketNews.published_at.desc())
                .limit(30)
                .all()
            )
        for n in recent:
            cat = _categorizar_diario(n.title, n.summary)
            news_pool.append({
                'title':        n.title,
                'url':          n.url,
                'summary':      n.summary or '',
                'published_at': n.published_at.strftime('%Y-%m-%d') if n.published_at else '',
                'source_name':  n.source or 'Medio de comunicación',
                'category':     cat,
            })
    except Exception as e:
        log.warning(f'[Investigador-diario] DB noticias: {e}')
        blocks.append({'source': 'news_db', 'reason': str(e)})

    # Seleccionar exactamente 1 nacional y 1 internacional (sin reclasificar)
    for item in news_pool:
        cat = item['category']
        if cat in ('nacional', 'internacional') and cat not in categorized:
            categorized[cat] = item
        if 'nacional' in categorized and 'internacional' in categorized:
            break

    # ── 3. Registrar qué categorías están presentes / faltan ──────────────────
    REQUIRED = ('nacional', 'internacional', 'mercados')
    categorias_faltantes = [c for c in REQUIRED if c not in categorized]

    # ── 4. Guardar ContentSource solo para las categorías presentes ────────────
    sources_created = []
    for cat in REQUIRED:
        n = categorized.get(cat)
        if not n:
            continue
        src = ContentSource(
            pipeline_id      = pipeline.id,
            stage_id         = stage.id,
            url              = n.get('url'),
            title            = n.get('title', 'Sin título'),
            excerpt          = (n.get('summary') or n.get('title', ''))[:600],
            published_at     = str(n.get('published_at', ''))[:10],
            source_name      = n.get('source_name', 'Fuente desconocida'),
            source_type      = 'market_feed' if n.get('is_market_feed') else 'media',
            is_verified      = bool(n.get('is_market_feed')),
            used_in_analysis = True,
        )
        db.session.add(src)
        sources_created.append({
            'title':       src.title,
            'url':         src.url,
            'source':      src.source_name,
            'category':    cat,
            'published_at': str(n.get('published_at', '')),
        })

    db.session.flush()

    if not sources_created:
        return {
            'ok':                  False,
            'sources':             [],
            'categorized':         {},
            'categorias_faltantes': list(REQUIRED),
            'categorias_completas': False,
            'blocks':              blocks or [{'source': 'todas', 'reason': 'Sin fuentes'}],
            'count':               0,
            'message':             'No se encontraron noticias.',
        }

    return {
        'ok':                  True,
        'sources':             sources_created,
        'categorized':         categorized,   # {cat: news_item_dict}
        'categorias_faltantes': categorias_faltantes,
        'categorias_completas': len(categorias_faltantes) == 0,
        'blocks':              blocks,
        'count':               len(sources_created),
        'message':             (
            f'{len(sources_created)} noticias recuperadas. '
            + (f'Sin {", ".join(categorias_faltantes)}.' if categorias_faltantes else 'Todas las categorías cubiertas.')
        ),
    }

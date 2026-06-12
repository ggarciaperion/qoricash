"""
Agente de Caza de Prospectos — Lead Hunter
-------------------------------------------
Busca activamente potenciales clientes en múltiples fuentes web y los
registra automáticamente en el CRM de QoriCash con score y justificación.

Fuentes:
  1. SUNAT (api.apis.net.pe) — empresas activas por código CIIU
  2. Páginas Amarillas Perú — directorio web por rubro
  3. Google Custom Search API — búsquedas semánticas (requiere key)
  4. RSS de noticias — empresas con actividad de comercio exterior
  5. Reviews de competidores — clientes insatisfechos (fuente futura)

Flujo por ciclo:
  1. Fetch de leads crudos de todas las fuentes activas
  2. Deduplicación contra prospectos + clientes existentes
  3. Claude Haiku califica y puntúa cada lead (0-100)
  4. Inserción automática en tabla prospectos
  5. Retorna reporte: encontrados / nuevos / descartados / top 5
"""
import logging
import os
import time
import re
import json
import requests
from datetime import datetime, timezone, timedelta

from app.services.ai.client import ask_json, HAIKU, SONNET

_log = logging.getLogger(__name__)

_LIMA_TZ = timezone(timedelta(hours=-5))
_UA = 'Mozilla/5.0 (compatible; QoriCashBot/1.0; +https://qoricash.pe)'
_TIMEOUT = 10  # segundos por request HTTP

# ── Códigos CIIU de alto valor para casa de cambio ──────────────────────────
_CIIU_TARGETS = [
    ('4610', 'Comercio al por mayor no especializado',           'importacion'),
    ('4620', 'Venta mayorista de materias primas agropecuarias', 'agro'),
    ('4630', 'Venta mayorista de alimentos, bebidas y tabaco',   'alimentos'),
    ('4641', 'Venta mayorista de textiles y calzado',            'textil'),
    ('4649', 'Venta mayorista de otros enseres domésticos',      'manufactura'),
    ('4659', 'Venta mayorista de maquinaria y equipo',           'tecnologia'),
    ('4661', 'Venta mayorista de combustibles y minerales',      'mineria'),
    ('4690', 'Venta mayorista diversa',                          'comercio exterior'),
    ('4520', 'Mantenimiento y reparación de vehículos',          'automotriz'),
    ('5510', 'Actividades de alojamiento para estancias cortas', 'hoteleria'),
    ('4711', 'Venta al por menor en supermercados',              'retail'),
    ('0111', 'Cultivo de cereales y leguminosas',                'agro exportador'),
    ('2610', 'Fabricación de componentes electrónicos',          'tecnologia'),
    ('3011', 'Construcción de barcos y otras embarcaciones',     'logistica'),
    ('4922', 'Transporte de carga por carretera',                'logistica'),
]

# ── Búsquedas Google (si API key configurada) ────────────────────────────────
_GOOGLE_QUERIES = [
    'empresa importadora Lima Peru "tipo de cambio" OR "dólares"',
    'exportadora Peru Lima "cambio de divisas" OR "compra dolares"',
    'constructora Lima Peru importa materiales "dólares"',
    'agro exportadora Peru Lima "venta de dólares"',
    'tecnología importadora Lima Peru empresa',
    'farmacéutica importadora Lima Peru empresa',
    'hotelería Lima Peru empresa directorio',
    '"comercio exterior" Peru Lima empresa contacto email',
    'minería Peru Lima empresa "dólares" OR "divisas"',
    'logística importación exportación Lima Peru empresa',
]


# ─────────────────────────────────────────────────────────────────────────────
# 1. SUNAT — via api.apis.net.pe (gratis, sin key)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_sunat_by_ciiu(ciiu: str, rubro: str, max_pages: int = 2) -> list:
    """Obtiene empresas activas de SUNAT filtradas por código CIIU."""
    leads = []
    for page in range(1, max_pages + 1):
        try:
            url = f'https://api.apis.net.pe/v2/sunat/contribuyentes'
            params = {'ciiu': ciiu, 'page': page}
            r = requests.get(url, params=params, headers={'User-Agent': _UA},
                             timeout=_TIMEOUT)
            if r.status_code != 200:
                break
            data = r.json()
            items = data if isinstance(data, list) else data.get('data', [])
            if not items:
                break
            for item in items:
                estado = (item.get('estado') or '').upper()
                if estado not in ('ACTIVO', 'HABIDO'):
                    continue
                razon = item.get('razonSocial') or item.get('nombre') or ''
                ruc   = item.get('ruc') or ''
                dist  = item.get('distrito') or ''
                prov  = item.get('provincia') or ''
                dept  = item.get('departamento') or ''
                if not razon or not ruc:
                    continue
                leads.append({
                    'razon_social': razon.title(),
                    'ruc':          ruc,
                    'rubro':        rubro,
                    'distrito':     dist.title() if dist else '',
                    'provincia':    prov.title() if prov else '',
                    'departamento': dept.title() if dept else 'Lima',
                    'fuente':       f'SUNAT-CIIU-{ciiu}',
                    'email':        '',
                    'telefono':     '',
                    'web':          '',
                    'notas':        f'Extraído automáticamente de SUNAT. CIIU {ciiu}.',
                })
            time.sleep(0.3)
        except Exception as e:
            _log.warning(f'[LeadHunter] SUNAT CIIU {ciiu} page {page}: {e}')
            break
    return leads


def fetch_sunat_leads(max_per_ciiu: int = 20) -> list:
    """Obtiene leads de SUNAT para todos los rubros objetivo."""
    all_leads = []
    for ciiu, _, rubro in _CIIU_TARGETS[:8]:  # top 8 para no saturar
        leads = _fetch_sunat_by_ciiu(ciiu, rubro, max_pages=2)
        all_leads.extend(leads[:max_per_ciiu])
        time.sleep(0.5)
    _log.info(f'[LeadHunter] SUNAT: {len(all_leads)} empresas encontradas')
    return all_leads


# ─────────────────────────────────────────────────────────────────────────────
# 2. Páginas Amarillas Perú — scraping directo
# ─────────────────────────────────────────────────────────────────────────────

_PA_CATEGORIES = [
    ('importadores',         'importacion'),
    ('exportadores',         'exportacion'),
    ('comercio-exterior',    'comercio exterior'),
    ('constructoras',        'construccion'),
    ('agencias-de-carga',    'logistica'),
    ('mineria',              'mineria'),
    ('hoteleria',            'hoteleria'),
    ('farmaceuticas',        'farmaceutica'),
]

def _scrape_paginas_amarillas(category: str, rubro: str, max_pages: int = 2) -> list:
    """Scraping de Páginas Amarillas Perú por categoría."""
    from bs4 import BeautifulSoup
    leads = []
    for page in range(1, max_pages + 1):
        try:
            url = f'https://www.paginasamarillas.com.pe/s/{category}/todo-peru/en/{page}'
            r = requests.get(url, headers={'User-Agent': _UA}, timeout=_TIMEOUT)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, 'lxml')

            # Cada empresa está en un elemento .item-list-data o similar
            for card in soup.select('.item-list, .listing-item, .result-item, [class*="item"]'):
                name_el  = card.select_one('[class*="name"], [class*="title"], h2, h3')
                phone_el = card.select_one('[class*="phone"], [class*="tel"]')
                web_el   = card.select_one('a[href*="http"]')
                addr_el  = card.select_one('[class*="address"], [class*="addr"]')

                name = name_el.get_text(strip=True) if name_el else ''
                if not name or len(name) < 3:
                    continue

                phone = phone_el.get_text(strip=True) if phone_el else ''
                web   = web_el['href'] if web_el and web_el.get('href','').startswith('http') else ''
                addr  = addr_el.get_text(strip=True) if addr_el else ''

                leads.append({
                    'razon_social': name,
                    'ruc':          '',
                    'rubro':        rubro,
                    'distrito':     '',
                    'provincia':    '',
                    'departamento': 'Lima',
                    'fuente':       'PaginasAmarillas',
                    'email':        '',
                    'telefono':     phone[:50] if phone else '',
                    'web':          web[:200] if web else '',
                    'notas':        f'Directorio Páginas Amarillas. Categoría: {category}. {addr[:100]}',
                })
            time.sleep(1.0)
        except Exception as e:
            _log.warning(f'[LeadHunter] PaginasAmarillas {category} page {page}: {e}')
            break
    return leads


def fetch_paginas_amarillas_leads() -> list:
    all_leads = []
    for cat, rubro in _PA_CATEGORIES[:5]:  # primeras 5 categorías
        leads = _scrape_paginas_amarillas(cat, rubro, max_pages=2)
        all_leads.extend(leads)
        time.sleep(1.0)
    _log.info(f'[LeadHunter] PaginasAmarillas: {len(all_leads)} empresas encontradas')
    return all_leads


# ─────────────────────────────────────────────────────────────────────────────
# 3. Google Custom Search (requiere GOOGLE_SEARCH_API_KEY + GOOGLE_SEARCH_CX)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_google_leads(max_queries: int = 5) -> list:
    """Busca empresas usando Google Custom Search API."""
    api_key = os.environ.get('GOOGLE_SEARCH_API_KEY', '')
    cx      = os.environ.get('GOOGLE_SEARCH_CX', '')
    if not api_key or not cx:
        _log.info('[LeadHunter] Google Search no configurado (sin GOOGLE_SEARCH_API_KEY/CX)')
        return []

    leads = []
    for query in _GOOGLE_QUERIES[:max_queries]:
        try:
            r = requests.get(
                'https://www.googleapis.com/customsearch/v1',
                params={'key': api_key, 'cx': cx, 'q': query, 'num': 10,
                        'gl': 'pe', 'hl': 'es'},
                timeout=_TIMEOUT,
            )
            if r.status_code != 200:
                continue
            items = r.json().get('items', [])
            for item in items:
                title   = item.get('title', '')
                snippet = item.get('snippet', '')
                link    = item.get('link', '')
                # Extraer nombre empresa del título
                name = re.split(r'[|\-–]', title)[0].strip()[:200]
                if not name:
                    continue
                # Extraer email del snippet si aparece
                emails_found = re.findall(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', snippet, re.I)
                leads.append({
                    'razon_social': name,
                    'ruc':          '',
                    'rubro':        'comercio exterior',
                    'distrito':     '',
                    'provincia':    '',
                    'departamento': 'Lima',
                    'fuente':       'GoogleSearch',
                    'email':        emails_found[0] if emails_found else '',
                    'telefono':     '',
                    'web':          link[:300] if link else '',
                    'notas':        f'Google: "{query}". {snippet[:150]}',
                })
            time.sleep(1.5)
        except Exception as e:
            _log.warning(f'[LeadHunter] Google query "{query}": {e}')
    _log.info(f'[LeadHunter] Google: {len(leads)} resultados encontrados')
    return leads


# ─────────────────────────────────────────────────────────────────────────────
# 4. RSS de noticias de negocios peruanos
# ─────────────────────────────────────────────────────────────────────────────

_BUSINESS_RSS = [
    'https://gestion.pe/feed/',
    'https://elcomercio.pe/rss/economia/',
    'https://andina.pe/agencia/rss.aspx?cat=economia',
]

_COMPANY_SIGNALS = [
    'importa', 'exporta', 'importación', 'exportación', 'millones de dólares',
    'comercio exterior', 'inversión', 'proyecto', 'expansión', 'contrato',
    'millones USD', 'adquirió', 'inauguró', 'abrió', 'lanzó',
]

def fetch_news_leads() -> list:
    """Extrae empresas mencionadas en noticias de negocios con señales de comercio exterior."""
    try:
        import feedparser
    except ImportError:
        return []

    leads = []
    seen = set()
    for rss_url in _BUSINESS_RSS:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:20]:
                title   = entry.get('title', '')
                summary = entry.get('summary', '') or entry.get('description', '')
                text    = f'{title} {summary}'.lower()

                # Filtrar por señales de comercio exterior
                if not any(sig in text for sig in _COMPANY_SIGNALS):
                    continue

                # Extraer nombre de empresa (heurística: palabras en mayúscula o S.A./S.R.L.)
                companies = re.findall(
                    r'\b([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ]+){1,4})'
                    r'(?:\s+S\.?A\.?|S\.R\.L\.?|E\.I\.R\.L\.?|S\.A\.C\.)?',
                    title
                )
                for company in companies[:2]:
                    if len(company) < 5 or company.lower() in seen:
                        continue
                    seen.add(company.lower())
                    leads.append({
                        'razon_social': company.strip(),
                        'ruc':          '',
                        'rubro':        'comercio exterior',
                        'distrito':     '',
                        'provincia':    '',
                        'departamento': 'Lima',
                        'fuente':       'NoticiasNegocios',
                        'email':        '',
                        'telefono':     '',
                        'web':          entry.get('link', '')[:300],
                        'notas':        f'Mencionada en noticias: {title[:150]}',
                    })
        except Exception as e:
            _log.warning(f'[LeadHunter] RSS {rss_url}: {e}')

    _log.info(f'[LeadHunter] Noticias: {len(leads)} empresas mencionadas')
    return leads


# ─────────────────────────────────────────────────────────────────────────────
# Deduplicación contra CRM existente
# ─────────────────────────────────────────────────────────────────────────────

def _load_existing_identifiers() -> set:
    """Carga RUCs y razones sociales normalizadas ya existentes en el CRM."""
    from app.models.prospecto import Prospecto
    from app.models.client import Client

    existing = set()
    for p in Prospecto.query.with_entities(Prospecto.ruc, Prospecto.razon_social).all():
        if p.ruc:
            existing.add(p.ruc.strip())
        if p.razon_social:
            existing.add(_normalize(p.razon_social))

    for c in Client.query.with_entities(Client.dni, Client.razon_social).all():
        if c.dni:
            existing.add(c.dni.strip())
        if c.razon_social:
            existing.add(_normalize(c.razon_social))

    return existing


def _normalize(text: str) -> str:
    """Normaliza nombre para deduplicación fuzzy básica."""
    return re.sub(r'\s+', ' ', text.upper()
                  .replace('S.A.C.', '').replace('S.A.', '').replace('S.R.L.', '')
                  .replace('E.I.R.L.', '').replace('CIA.', '').strip())


def _deduplicate(leads: list, existing: set) -> list:
    """Elimina leads ya presentes en el CRM."""
    new_leads = []
    seen_this_run = set()
    for lead in leads:
        key_ruc  = (lead.get('ruc') or '').strip()
        key_name = _normalize(lead.get('razon_social', ''))
        if not key_name or len(key_name) < 4:
            continue
        # Deduplicar por RUC o nombre normalizado
        dedup_key = key_ruc if key_ruc else key_name
        if dedup_key in existing or dedup_key in seen_this_run:
            continue
        seen_this_run.add(dedup_key)
        new_leads.append(lead)
    return new_leads


# ─────────────────────────────────────────────────────────────────────────────
# Calificación con Claude
# ─────────────────────────────────────────────────────────────────────────────

def _qualify_batch(leads: list) -> list:
    """
    Claude Haiku evalúa un lote de leads y asigna score + acción.
    Procesa en lotes de 20 para eficiencia.
    """
    if not leads:
        return leads

    qualified = []
    batch_size = 20

    for i in range(0, len(leads), batch_size):
        batch = leads[i:i + batch_size]
        leads_txt = '\n'.join(
            f'{j+1}. {l["razon_social"]} | rubro:{l["rubro"]} | '
            f'dept:{l["departamento"]} | fuente:{l["fuente"]} | '
            f'notas:{l["notas"][:80]}'
            for j, l in enumerate(batch)
        )
        try:
            prompt = f"""Eres el director comercial de QoriCash, casa de cambio B2B en Lima Perú.
Evalúa estos {len(batch)} prospectos y para cada uno asigna un score de potencial (0-100).

Criterios de score alto (80-100): importadores, exportadores, minería, construcción, tecnología, logística, hotelería de cadena, farmacéuticas — empresas con flujo regular de divisas.
Criterios de score medio (40-79): retail, manufactura, servicios profesionales — posible necesidad de divisas.
Criterios de score bajo (0-39): sin relación clara con divisas, muy pequeños, o información insuficiente.

PROSPECTOS:
{leads_txt}

Responde SOLO JSON:
{{
  "calificaciones": [
    {{
      "numero": <1-{len(batch)}>,
      "score": <0-100>,
      "potencial": "alto|medio|bajo",
      "tamano_estimado": "MYPE|Pequeña|Mediana|Grande",
      "vol_estimado_usd": <monto mensual estimado en USD o null>,
      "accion": "<acción de primer contacto recomendada en una oración>",
      "descartado": <true si es completamente irrelevante>
    }}
  ]
}}"""
            result = ask_json(prompt, model=HAIKU, max_tokens=2000)
            for cal in result.get('calificaciones', []):
                idx = cal.get('numero', 0) - 1
                if 0 <= idx < len(batch):
                    if cal.get('descartado'):
                        continue
                    batch[idx]['score']              = cal.get('score', 0)
                    batch[idx]['potencial']          = cal.get('potencial', 'bajo')
                    batch[idx]['tamano_empresa']     = cal.get('tamano_estimado', 'MYPE')
                    batch[idx]['volumen_estimado_usd'] = cal.get('vol_estimado_usd')
                    batch[idx]['accion_sugerida']    = cal.get('accion', '')
                    qualified.append(batch[idx])
        except Exception as e:
            _log.warning(f'[LeadHunter] qualify_batch error: {e}')
            # En caso de error de Claude, conservar leads con score 30
            for lead in batch:
                lead.setdefault('score', 30)
                lead.setdefault('potencial', 'bajo')
                qualified.append(lead)

    return qualified


# ─────────────────────────────────────────────────────────────────────────────
# Inserción en CRM
# ─────────────────────────────────────────────────────────────────────────────

def _insert_prospects(leads: list) -> int:
    """Inserta leads calificados en la tabla prospectos. Retorna cantidad insertada."""
    from app.extensions import db
    from app.models.prospecto import Prospecto
    from app.utils.formatters import now_peru

    inserted = 0
    today_str = now_peru().strftime('%Y-%m-%d')

    for lead in leads:
        try:
            vol = lead.get('volumen_estimado_usd')
            p = Prospecto(
                razon_social        = (lead.get('razon_social') or '')[:300],
                ruc                 = (lead.get('ruc') or '')[:20] or None,
                tipo                = 'Empresa',
                rubro               = (lead.get('rubro') or '')[:150],
                departamento        = (lead.get('departamento') or 'Lima')[:100],
                provincia           = (lead.get('provincia') or '')[:100],
                distrito            = (lead.get('distrito') or '')[:100],
                email               = (lead.get('email') or '')[:200] or None,
                telefono            = (lead.get('telefono') or '')[:200] or None,
                web                 = (lead.get('web') or '')[:300] or None,
                fuente              = (lead.get('fuente') or 'LeadHunterIA')[:80],
                canal               = 'IA-LeadHunter',
                score               = int(lead.get('score', 30)),
                prioridad           = lead.get('potencial', 'baja'),
                tamano_empresa      = lead.get('tamano_empresa', 'MYPE'),
                volumen_estimado_usd= float(vol) if vol else None,
                estado_comercial    = 'nuevo',
                nivel_interes       = 'bajo',
                notas               = (
                    f"[IA {today_str}] {lead.get('accion_sugerida', '')}. "
                    f"{lead.get('notas', '')}"
                )[:500],
                fecha_primer_contacto = today_str,
            )
            db.session.add(p)
            inserted += 1
        except Exception as e:
            _log.warning(f'[LeadHunter] insert error for {lead.get("razon_social")}: {e}')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        _log.error(f'[LeadHunter] commit error: {e}')
        return 0

    return inserted


# ─────────────────────────────────────────────────────────────────────────────
# Ciclo principal del agente
# ─────────────────────────────────────────────────────────────────────────────

def run_hunt(
    sources: list = None,
    min_score: int = 35,
    max_new_leads: int = 100,
) -> dict:
    """
    Ejecuta un ciclo completo de caza de prospectos.

    Args:
        sources: lista de fuentes a usar ['sunat','paginas_amarillas','google','news']
                 Si None, usa todas las disponibles.
        min_score: score mínimo para insertar en CRM (0-100)
        max_new_leads: máximo de nuevos registros por ciclo

    Returns:
        {ok, encontrados, nuevos, insertados, descartados, top_leads, resumen}
    """
    if sources is None:
        sources = ['sunat', 'paginas_amarillas', 'google', 'news']

    try:
        _log.info(f'[LeadHunter] Iniciando ciclo — fuentes: {sources}')
        raw_leads = []

        if 'sunat' in sources:
            raw_leads.extend(fetch_sunat_leads(max_per_ciiu=15))
        if 'paginas_amarillas' in sources:
            raw_leads.extend(fetch_paginas_amarillas_leads())
        if 'google' in sources:
            raw_leads.extend(fetch_google_leads(max_queries=5))
        if 'news' in sources:
            raw_leads.extend(fetch_news_leads())

        _log.info(f'[LeadHunter] Raw leads: {len(raw_leads)}')

        # Deduplicar contra CRM existente
        existing = _load_existing_identifiers()
        unique_leads = _deduplicate(raw_leads, existing)
        _log.info(f'[LeadHunter] Después de deduplicar: {len(unique_leads)} nuevos')

        if not unique_leads:
            return {
                'ok': True, 'encontrados': len(raw_leads), 'nuevos': 0,
                'insertados': 0, 'descartados': len(raw_leads),
                'top_leads': [], 'resumen': 'Todos los leads ya existen en el CRM.',
            }

        # Calificar con Claude (en lotes)
        qualified = _qualify_batch(unique_leads[:200])  # max 200 para calificar

        # Filtrar por score mínimo
        above_threshold = [l for l in qualified if l.get('score', 0) >= min_score]
        above_threshold.sort(key=lambda x: x.get('score', 0), reverse=True)

        # Insertar en CRM
        to_insert = above_threshold[:max_new_leads]
        inserted  = _insert_prospects(to_insert)

        # Top 10 para el reporte
        top_leads = [
            {
                'razon_social': l['razon_social'],
                'rubro':        l['rubro'],
                'score':        l.get('score', 0),
                'potencial':    l.get('potencial', '—'),
                'fuente':       l['fuente'],
                'accion':       l.get('accion_sugerida', '—'),
                'volumen_usd':  l.get('volumen_estimado_usd'),
            }
            for l in to_insert[:10]
        ]

        # Resumen ejecutivo con Claude
        resumen = _generate_hunt_summary(
            found=len(raw_leads),
            unique=len(unique_leads),
            qualified=len(above_threshold),
            inserted=inserted,
            top_leads=top_leads,
        )

        _log.info(f'[LeadHunter] Ciclo completado — {inserted} nuevos prospectos insertados')

        return {
            'ok':          True,
            'encontrados': len(raw_leads),
            'nuevos':      len(unique_leads),
            'calificados': len(above_threshold),
            'insertados':  inserted,
            'descartados': len(raw_leads) - len(above_threshold),
            'top_leads':   top_leads,
            'resumen':     resumen,
        }

    except Exception as e:
        _log.error(f'[LeadHunter] run_hunt error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}


def _generate_hunt_summary(found, unique, qualified, inserted, top_leads) -> str:
    """Claude genera un resumen ejecutivo del ciclo de prospección."""
    try:
        top_txt = '\n'.join(
            f"  {i+1}. {l['razon_social']} | {l['rubro']} | score:{l['score']} | {l['fuente']}"
            for i, l in enumerate(top_leads[:5])
        )
        prompt = f"""Eres el director comercial de QoriCash. Resume los resultados del ciclo automático de prospección.

RESULTADOS:
  Leads encontrados en webs: {found}
  Nuevos (no estaban en CRM): {unique}
  Calificados (score≥35): {qualified}
  Insertados en CRM: {inserted}

TOP PROSPECTOS ENCONTRADOS:
{top_txt if top_txt else '  (ninguno)'}

En 2-3 oraciones, resume qué se encontró, qué rubros dominan, y qué acción inmediata recomiendas."""

        from app.services.ai.client import ask
        return ask(prompt, model=HAIKU, max_tokens=200)
    except Exception:
        return f'Ciclo completado: {inserted} nuevos prospectos insertados en CRM de {found} encontrados.'


# ─────────────────────────────────────────────────────────────────────────────
# Búsqueda puntual por nombre / rubro / RUC (para uso desde UI)
# ─────────────────────────────────────────────────────────────────────────────

def search_prospect(query: str) -> dict:
    """
    Búsqueda puntual: dado un nombre, rubro o RUC, busca en SUNAT y web,
    enriquece con Claude y retorna el perfil del prospecto.
    """
    try:
        leads = []

        # Buscar en SUNAT por nombre si parece una razón social
        if re.match(r'^\d{11}$', query.strip()):
            # Es un RUC — lookup directo
            r = requests.get(
                f'https://api.apis.net.pe/v2/sunat/ruc',
                params={'numero': query.strip()},
                headers={'User-Agent': _UA},
                timeout=_TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                leads.append({
                    'razon_social': data.get('razonSocial', query).title(),
                    'ruc':          query.strip(),
                    'rubro':        data.get('ciiu', 'comercio')[:150],
                    'departamento': (data.get('departamento') or 'Lima').title(),
                    'provincia':    (data.get('provincia') or '').title(),
                    'distrito':     (data.get('distrito') or '').title(),
                    'fuente':       'SUNAT-RUC',
                    'email': '', 'telefono': '', 'web': '',
                    'notas': f"Estado SUNAT: {data.get('estado','')}. Dirección: {data.get('direccion','')}",
                })
        else:
            # Búsqueda por nombre — Google si está configurado
            leads.extend(fetch_google_leads(max_queries=2))
            leads = [l for l in leads
                     if query.lower() in l.get('razon_social','').lower()
                     or query.lower() in l.get('notas','').lower()]

        if not leads:
            return {'ok': True, 'leads': [], 'message': f'Sin resultados para "{query}"'}

        qualified = _qualify_batch(leads[:10])
        return {'ok': True, 'leads': qualified[:5]}

    except Exception as e:
        _log.error(f'[LeadHunter] search_prospect error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}

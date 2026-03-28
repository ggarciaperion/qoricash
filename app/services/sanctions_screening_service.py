"""
Servicio de screening automático contra listas de sanciones internacionales.

Fuentes:
  - OFAC SDN (US Treasury) — sdn.xml
  - ONU Consolidated Sanctions — consolidated.xml

Estrategia de caché:
  - Los datos se descargan y guardan en la tabla `sanctions_entries`.
  - Se recargan automáticamente si tienen más de 7 días.
"""
import json
import logging
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Umbrales de coincidencia ──────────────────────────────────────────────────
SCORE_MATCH          = 88   # ≥88 → Match (🔴)
SCORE_POTENTIAL      = 78   # ≥78 y <88 → Potential_Match (🟡)
CACHE_DAYS           = 7    # Días antes de refrescar los datos

# ── URLs de listas oficiales ──────────────────────────────────────────────────
OFAC_URL = 'https://www.treasury.gov/ofac/downloads/sdn.xml'
UN_URL   = 'https://scsanctions.un.org/resources/xml/en/consolidated.xml'


def _normalize(text: str) -> str:
    """Convierte a mayúsculas y elimina acentos/diacríticos."""
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', text.upper())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _fuzzy_score(query: str, candidate: str) -> int:
    """Calcula similitud entre dos cadenas normalizadas (0-100).

    token_sort_ratio solo se aplica a consultas cortas (≤3 palabras) para
    evitar falsos positivos con nombres largos — ej. 'GARCIA VILCA GIAN PIERRE'
    vs. 'ARMED ISLAMIC GROUP' generaba 74% por reordenamiento de tokens.
    """
    try:
        from rapidfuzz import fuzz
        score = fuzz.WRatio(query, candidate)
        # token_sort_ratio solo para nombres cortos (≤3 tokens)
        if len(query.split()) <= 3:
            score = max(score, fuzz.token_sort_ratio(query, candidate))
        return score
    except ImportError:
        # Fallback simple si rapidfuzz no está disponible
        if query == candidate:
            return 100
        if query in candidate or candidate in query:
            return 85
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

def _needs_refresh(source: str) -> bool:
    """Verifica si los datos de una fuente deben recargarse."""
    from app.models.sanctions import SanctionsEntry
    latest = SanctionsEntry.query.filter_by(source=source).order_by(
        SanctionsEntry.loaded_at.desc()
    ).first()
    if not latest:
        return True
    cutoff = datetime.utcnow() - timedelta(days=CACHE_DAYS)
    return latest.loaded_at < cutoff


def load_ofac(force: bool = False) -> dict:
    """Descarga y carga la lista SDN de OFAC en la BD. Retorna {'loaded': N, 'skipped': bool}."""
    from app.extensions import db
    from app.models.sanctions import SanctionsEntry

    if not force and not _needs_refresh('OFAC'):
        count = SanctionsEntry.query.filter_by(source='OFAC').count()
        return {'loaded': count, 'skipped': True}

    logger.info('[OFAC] Descargando lista SDN...')
    try:
        req = urllib.request.Request(OFAC_URL, headers={'User-Agent': 'QoriCash/2.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
    except Exception as e:
        logger.error(f'[OFAC] Error descargando: {e}')
        return {'loaded': 0, 'skipped': False, 'error': str(e)}

    try:
        root = ET.fromstring(xml_data)
        ns   = {'': 'https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML'}

        # Detectar namespace dinámicamente
        tag = root.tag
        if tag.startswith('{'):
            ns_uri = tag[1:tag.index('}')]
            ns = {'': ns_uri}

        # Eliminar registros viejos de OFAC
        SanctionsEntry.query.filter_by(source='OFAC').delete()
        db.session.flush()

        loaded    = 0
        now       = datetime.utcnow()
        batch     = []

        for entry in root.findall('.//sdnEntry', ns) or root.findall('.//sdnEntry'):
            uid       = _get_text(entry, 'uid', ns)
            last_name = _get_text(entry, 'lastName', ns)
            first_name = _get_text(entry, 'firstName', ns)
            sdn_type  = _get_text(entry, 'sdnType', ns)

            name = f'{first_name} {last_name}'.strip() if first_name else last_name
            if not name:
                continue

            # Aliases
            aliases = []
            for aka in entry.findall('.//aka', ns) or entry.findall('.//aka'):
                aka_fn = _get_text(aka, 'firstName', ns)
                aka_ln = _get_text(aka, 'lastName', ns)
                alias  = f'{aka_fn} {aka_ln}'.strip() if aka_fn else aka_ln
                if alias:
                    aliases.append(_normalize(alias))

            # Programa
            programs = [p.text for p in (entry.findall('.//program', ns) or entry.findall('.//program')) if p.text]

            batch.append(SanctionsEntry(
                source          = 'OFAC',
                entity_type     = 'Individual' if sdn_type == 'Individual' else 'Entity',
                uid             = uid,
                name            = name,
                name_normalized = _normalize(name),
                aliases_json    = json.dumps(aliases) if aliases else None,
                program         = '; '.join(programs[:3]) if programs else None,
                loaded_at       = now,
            ))
            loaded += 1

            if len(batch) >= 500:
                db.session.bulk_save_objects(batch)
                db.session.flush()
                batch = []

        if batch:
            db.session.bulk_save_objects(batch)

        db.session.commit()
        logger.info(f'[OFAC] {loaded} entradas cargadas.')
        return {'loaded': loaded, 'skipped': False}

    except Exception as e:
        db.session.rollback()
        logger.error(f'[OFAC] Error parseando XML: {e}')
        return {'loaded': 0, 'skipped': False, 'error': str(e)}


def load_un(force: bool = False) -> dict:
    """Descarga y carga la lista consolidada de la ONU en la BD."""
    from app.extensions import db
    from app.models.sanctions import SanctionsEntry

    if not force and not _needs_refresh('UN'):
        count = SanctionsEntry.query.filter_by(source='UN').count()
        return {'loaded': count, 'skipped': True}

    logger.info('[UN] Descargando lista consolidada...')
    try:
        req = urllib.request.Request(UN_URL, headers={'User-Agent': 'QoriCash/2.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
    except Exception as e:
        logger.error(f'[UN] Error descargando: {e}')
        return {'loaded': 0, 'skipped': False, 'error': str(e)}

    try:
        root   = ET.fromstring(xml_data)
        SanctionsEntry.query.filter_by(source='UN').delete()
        db.session.flush()

        loaded = 0
        now    = datetime.utcnow()
        batch  = []

        # Individuos
        for ind in root.findall('.//INDIVIDUAL'):
            name = _build_un_name(ind)
            if not name:
                continue
            aliases = _un_aliases(ind)
            batch.append(SanctionsEntry(
                source          = 'UN',
                entity_type     = 'Individual',
                uid             = _get_text(ind, 'DATAID'),
                name            = name,
                name_normalized = _normalize(name),
                aliases_json    = json.dumps(aliases) if aliases else None,
                nationality     = _get_text(ind, 'NATIONALITY'),
                program         = _get_text(ind, 'UN_LIST_TYPE'),
                loaded_at       = now,
            ))
            loaded += 1

        # Entidades
        for ent in root.findall('.//ENTITY'):
            name = _get_text(ent, 'FIRST_NAME') or _get_text(ent, 'ENTITY_NAME')
            if not name:
                continue
            aliases = [_normalize(a.text) for a in ent.findall('.//ALIAS_NAME') if a.text]
            batch.append(SanctionsEntry(
                source          = 'UN',
                entity_type     = 'Entity',
                uid             = _get_text(ent, 'DATAID'),
                name            = name,
                name_normalized = _normalize(name),
                aliases_json    = json.dumps(aliases) if aliases else None,
                program         = _get_text(ent, 'UN_LIST_TYPE'),
                loaded_at       = now,
            ))
            loaded += 1

            if len(batch) >= 500:
                db.session.bulk_save_objects(batch)
                db.session.flush()
                batch = []

        if batch:
            db.session.bulk_save_objects(batch)

        db.session.commit()
        logger.info(f'[UN] {loaded} entradas cargadas.')
        return {'loaded': loaded, 'skipped': False}

    except Exception as e:
        db.session.rollback()
        logger.error(f'[UN] Error parseando XML: {e}')
        return {'loaded': 0, 'skipped': False, 'error': str(e)}


def _get_text(element, tag, ns=None):
    """Helper para obtener texto de un subelemento XML."""
    el = element.find(tag, ns) if ns else element.find(tag)
    return (el.text or '').strip() if el is not None and el.text else ''


def _build_un_name(ind) -> str:
    parts = [
        _get_text(ind, 'FIRST_NAME'),
        _get_text(ind, 'SECOND_NAME'),
        _get_text(ind, 'THIRD_NAME'),
        _get_text(ind, 'FOURTH_NAME'),
    ]
    return ' '.join(p for p in parts if p).strip()


def _un_aliases(ind) -> list:
    aliases = []
    for alias in ind.findall('.//ALIAS'):
        quality = _get_text(alias, 'QUALITY')
        if quality.lower() in ('good', 'a.k.a.', 'low'):
            aname = ' '.join(filter(None, [
                _get_text(alias, 'ALIAS_NAME'),
            ]))
            if aname:
                aliases.append(_normalize(aname))
    return aliases


# ─────────────────────────────────────────────────────────────────────────────
# SCREENING
# ─────────────────────────────────────────────────────────────────────────────

def screen_name(query_name: str, sources=('OFAC', 'UN'), top_n: int = 5) -> list:
    """
    Busca coincidencias del nombre en las listas de sanciones cargadas.

    Returns:
        Lista de dicts con los mejores matches:
        [{'source', 'name', 'score', 'result', 'uid', 'program', 'entity_type'}]
    """
    from app.models.sanctions import SanctionsEntry

    query_norm = _normalize(query_name)
    if not query_norm:
        return []

    results = []
    for source in sources:
        entries = SanctionsEntry.query.filter_by(source=source).all()
        for entry in entries:
            best_score = _fuzzy_score(query_norm, entry.name_normalized or '')

            # Revisar aliases también
            if entry.aliases_json:
                try:
                    for alias in json.loads(entry.aliases_json):
                        s = _fuzzy_score(query_norm, alias)
                        if s > best_score:
                            best_score = s
                except Exception:
                    pass

            if best_score >= SCORE_POTENTIAL:
                result_label = 'Match' if best_score >= SCORE_MATCH else 'Potential_Match'
                results.append({
                    'source':       source,
                    'name':         entry.name,
                    'score':        best_score,
                    'result':       result_label,
                    'uid':          entry.uid,
                    'program':      entry.program or '',
                    'entity_type':  entry.entity_type or '',
                })

    # Ordenar por score descendente y limitar
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n * len(sources)]


def screen_client(client_id: int) -> dict:
    """
    Ejecuta screening completo para un cliente.

    Returns dict con resultados por fuente y resumen general.
    """
    from app.models.client import Client

    client = Client.query.get(client_id)
    if not client:
        return {'error': 'Cliente no encontrado'}

    # Construir los nombres a buscar
    names_to_search = []

    if client.document_type == 'RUC':
        if client.razon_social:
            names_to_search.append(('Razón Social', client.razon_social))
    else:
        full = ' '.join(filter(None, [
            client.apellido_paterno,
            client.apellido_materno,
            client.nombres,
        ]))
        if full:
            names_to_search.append(('Nombre completo', full))
        # También nombre + apellido paterno
        if client.nombres and client.apellido_paterno:
            names_to_search.append((
                'Nombres + Ap. Paterno',
                f'{client.nombres} {client.apellido_paterno}'
            ))

    if not names_to_search:
        return {'error': 'El cliente no tiene nombre registrado'}

    # Asegurar datos cargados (descarga si es necesario)
    ofac_info = load_ofac()
    un_info   = load_un()

    all_matches  = []
    ofac_matches = []
    un_matches   = []

    for label, name in names_to_search:
        matches = screen_name(name)
        for m in matches:
            m['searched_as'] = label
            m['searched_name'] = name
            all_matches.append(m)
            if m['source'] == 'OFAC':
                ofac_matches.append(m)
            elif m['source'] == 'UN':
                un_matches.append(m)

    # Resultado por fuente
    def _source_result(matches):
        if not matches:
            return 'Clean'
        if any(m['result'] == 'Match' for m in matches):
            return 'Match'
        return 'Potential_Match'

    ofac_result = _source_result(ofac_matches)
    un_result   = _source_result(un_matches)

    overall_results = [ofac_result, un_result]
    if 'Match' in overall_results:
        overall = 'Match'
    elif 'Potential_Match' in overall_results:
        overall = 'Potential_Match'
    else:
        overall = 'Clean'

    max_score = max((m['score'] for m in all_matches), default=0)

    return {
        'overall':       overall,
        'max_score':     max_score,
        'ofac_result':   ofac_result,
        'ofac_matches':  ofac_matches[:5],
        'un_result':     un_result,
        'un_matches':    un_matches[:5],
        'all_matches':   all_matches[:10],
        'names_searched': [n for _, n in names_to_search],
        'data_sources': {
            'OFAC': {'entries': ofac_info.get('loaded', 0), 'refreshed': not ofac_info.get('skipped')},
            'UN':   {'entries': un_info.get('loaded', 0),   'refreshed': not un_info.get('skipped')},
        },
    }

"""
Recolector de Calendario Económico Semanal.
Fuente: ForexFactory (JSON público, sin key) — alta/media confianza.
Filtra: solo eventos HIGH impact + MEDIUM para USD/EUR/GBP.
"""
import hashlib
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_FF_URL     = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
_HEADERS    = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
_LIMA_TZ    = timezone(timedelta(hours=-5))

_FLAG = {
    'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧', 'JPY': '🇯🇵',
    'CNY': '🇨🇳', 'AUD': '🇦🇺', 'CAD': '🇨🇦', 'NZD': '🇳🇿',
    'CHF': '🇨🇭', 'PEN': '🇵🇪', 'BRL': '🇧🇷', 'MXN': '🇲🇽',
}
_DAYS_ES = {0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'}

# Traducción de eventos comunes al español
_TRANSLATE = {
    'Flash Manufacturing PMI':          'PMI Manufacturero Flash',
    'Flash Services PMI':               'PMI Servicios Flash',
    'Manufacturing PMI':                'PMI Manufacturero',
    'Services PMI':                     'PMI Servicios',
    'Composite PMI':                    'PMI Compuesto',
    'CPI m/m':                          'IPC mensual',
    'CPI y/y':                          'IPC anual',
    'Core CPI m/m':                     'IPC Subyacente mensual',
    'Core CPI y/y':                     'IPC Subyacente anual',
    'Trimmed Mean CPI m/m':             'IPC Media Recortada mensual',
    'PPI m/m':                          'IPP mensual',
    'PCE Price Index m/m':              'Índice PCE mensual',
    'Core PCE Price Index m/m':         'PCE Subyacente mensual',
    'Non-Farm Employment Change':       'Variación Empleo No Agrícola (NFP)',
    'Non-Farm Payrolls':                'Nóminas No Agrícolas (NFP)',
    'Unemployment Rate':                'Tasa de Desempleo',
    'Initial Jobless Claims':           'Solicitudes Iniciales de Desempleo',
    'Continuing Jobless Claims':        'Solicitudes Continuas de Desempleo',
    'JOLTS Job Openings':               'Vacantes Laborales (JOLTS)',
    'ADP Non-Farm Employment Change':   'Empleo ADP (sector privado)',
    'GDP q/q':                          'PIB trimestral',
    'Prelim GDP q/q':                   'PIB Preliminar trimestral',
    'Final GDP q/q':                    'PIB Final trimestral',
    'Retail Sales m/m':                 'Ventas Minoristas mensual',
    'Core Retail Sales m/m':            'Ventas Minoristas Subyacente',
    'Consumer Confidence':              'Confianza del Consumidor',
    'Michigan Consumer Sentiment':      'Sentimiento Michigan',
    'Durable Goods Orders m/m':         'Pedidos Bienes Duraderos',
    'Trade Balance':                    'Balanza Comercial',
    'Current Account':                  'Cuenta Corriente',
    'Housing Starts':                   'Inicio de Construcción',
    'Building Permits':                 'Permisos de Construcción',
    'Existing Home Sales':              'Venta de Viviendas Existentes',
    'New Home Sales':                   'Venta de Viviendas Nuevas',
    'Industrial Production m/m':        'Producción Industrial mensual',
    'ISM Manufacturing PMI':            'ISM Manufacturero',
    'ISM Non-Manufacturing PMI':        'ISM Servicios',
    'ISM Services PMI':                 'ISM Servicios',
    'Richmond Manufacturing Index':     'Índice Manufacturero Richmond',
    'Empire State Manufacturing Index': 'Índice Manufacturero Empire State',
    'Philadelphia Fed Manufacturing':   'Fed Filadelfia Manufactura',
    'Chicago PMI':                      'PMI Chicago',
    'EIA Crude Oil Inventories':        'Inventarios Petróleo EIA',
    'EIA Natural Gas Storage':          'Almacenamiento Gas Natural EIA',
    'Crude Oil Inventories':            'Inventarios Petróleo',
    'FOMC Statement':                   'Comunicado FOMC (Fed)',
    'FOMC Meeting Minutes':             'Minutas FOMC',
    'Federal Funds Rate':               'Tasa de Interés Fed',
    'Interest Rate Decision':           'Decisión de Tasa de Interés',
    'Monetary Policy Statement':        'Comunicado de Política Monetaria',
    'Press Conference':                 'Conferencia de Prensa',
    'Fed Chair Powell Speaks':          '🎤 Fed: Discurso de Powell',
    'FOMC Member':                      'Miembro FOMC habla',
    'ECB President Lagarde Speaks':     '🎤 BCE: Discurso de Lagarde',
    'ECB Monetary Policy Statement':    'BCE: Política Monetaria',
    'ECB Interest Rate Decision':       'BCE: Decisión de Tasa',
    'BOE Interest Rate Decision':       'BOE: Tasa de Interés',
    'BOJ Interest Rate Decision':       'BOJ: Tasa de Interés',
    'President Trump Speaks':           '🎤 Discurso de Trump',
    'German Flash Manufacturing PMI':   'PMI Manufacturero Alemania Flash',
    'German Flash Services PMI':        'PMI Servicios Alemania Flash',
    'German IFO Business Climate':      'IFO Clima Empresarial Alemania',
    'German ZEW Economic Sentiment':    'ZEW Sentimiento Económico Alemania',
    'German GDP m/m':                   'PIB Alemania mensual',
    'German Prelim GDP q/q':            'PIB Preliminar Alemania trimestral',
    'Eurozone CPI y/y':                 'IPC Zona Euro anual',
    'Eurozone Flash CPI y/y':           'IPC Flash Zona Euro',
    'Eurozone GDP q/q':                 'PIB Zona Euro trimestral',
    'Flash GDP q/q':                    'PIB Flash trimestral',
    'Claimant Count Change':            'Cambio en Subsidios por Desempleo (UK)',
    'Average Earnings Index':           'Índice Salarios Promedio (UK)',
    'Prelim Business Investment q/q':   'Inversión Empresarial Preliminar (UK)',
}


def _translate(event_name: str) -> str:
    """Busca traducción exacta o por coincidencia parcial."""
    if event_name in _TRANSLATE:
        return _TRANSLATE[event_name]
    # Buscar coincidencia parcial (el nombre puede tener prefijo de país)
    for eng, esp in _TRANSLATE.items():
        if eng in event_name:
            return event_name.replace(eng, esp)
    return event_name


def _event_key(event_date: str, country: str, title: str) -> str:
    raw = f"{event_date[:10]}|{country}|{title}"
    return hashlib.md5(raw.encode()).hexdigest()


def fetch_calendar() -> list[dict]:
    """
    Retorna lista de eventos económicos de la semana actual.
    Solo HIGH impact + MEDIUM de USD/EUR/GBP.
    Incluye fecha/hora en Lima (UTC-5).
    """
    events = []
    try:
        r = requests.get(_FF_URL, headers=_HEADERS, timeout=12)
        if r.status_code != 200:
            logger.warning(f"[Calendario] ForexFactory HTTP {r.status_code}")
            return events

        data = r.json()
        for item in data:
            impact  = (item.get('impact') or '').lower()
            country = (item.get('country') or '').upper()

            # Filtro: high siempre; medium solo USD/EUR/GBP
            if impact == 'high':
                pass
            elif impact == 'medium' and country in ('USD', 'EUR', 'GBP'):
                pass
            else:
                continue

            date_str = item.get('date', '')
            if not date_str:
                continue
            try:
                # ForexFactory: ISO 8601 con offset (ej: 2026-03-25T14:00:00-04:00)
                dt_utc  = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                dt_lima = dt_utc.astimezone(_LIMA_TZ)
            except Exception:
                continue

            now_lima = datetime.now(_LIMA_TZ)
            is_today = dt_lima.date() == now_lima.date()
            is_past  = dt_lima < now_lima

            actual   = (item.get('actual')   or '').strip()
            forecast = (item.get('forecast') or '').strip()
            previous = (item.get('previous') or '').strip()

            events.append({
                'event_key':   _event_key(date_str, country, item.get('title', '')),
                'event_date':  dt_utc.replace(tzinfo=None),  # UTC para DB
                'date_lima':   dt_lima.strftime('%Y-%m-%d'),
                'time_lima':   dt_lima.strftime('%H:%M'),
                'day_es':      _DAYS_ES[dt_lima.weekday()],
                'country':     country,
                'flag':        _FLAG.get(country, '🌐'),
                'event_name':  _translate((item.get('title') or '').strip())[:200],
                'impact':      impact,
                'actual':      actual[:25],
                'forecast':    forecast[:25],
                'previous':    previous[:25],
                'is_today':    is_today,
                'is_past':     is_past,
                'source':      'ForexFactory',
            })

        logger.info(f"[Calendario] {len(events)} eventos alta relevancia esta semana")

    except Exception as e:
        logger.error(f"[Calendario] Error fetching calendar: {e}", exc_info=True)

    # Ordenar por fecha/hora
    return sorted(events, key=lambda x: x['event_date'])

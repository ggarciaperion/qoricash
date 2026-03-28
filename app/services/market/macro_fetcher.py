"""
Recolector de indicadores macroeconómicos.
Fuentes:
  - BLS API   (sin key)  → CPI EE.UU., NFP
  - yfinance  (sin key)  → Tasa FED proxy (^IRX), 10Y Treasury (^TNX)
  - BCRP API  (sin key)  → TC oficial diario + tasa referencia
  - FRED API  (key opt.) → Fed Funds Rate exacta, si FRED_API_KEY en .env
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

_HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; QoriCash/1.0)', 'Content-Type': 'application/json'}


# ── BLS (Bureau of Labor Statistics) — sin key ───────────────────────────────
_BLS_URL    = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'
_BLS_CPI    = 'CUUR0000SA0'   # CPI all urban consumers
_BLS_NFP    = 'CES0000000001' # Total nonfarm employment (thousands)
_BLS_UNRATE = 'LNS14000000'   # Tasa de desempleo

def _fetch_bls() -> dict:
    """Retorna {cpi_value, cpi_prev, cpi_period, nfp_added, nfp_period, unrate, unrate_period}"""
    result = {}
    try:
        payload = {
            'seriesid':  [_BLS_CPI, _BLS_NFP, _BLS_UNRATE],
            'startyear': '2025',
            'endyear':   str(datetime.utcnow().year),
        }
        r = requests.post(_BLS_URL, json=payload, headers=_HEADERS, timeout=12)
        data = r.json()
        if data.get('status') != 'REQUEST_SUCCEEDED':
            logger.warning(f"[Macro] BLS error: {data.get('message')}")
            return result

        for series in data.get('Results', {}).get('series', []):
            sid   = series['seriesID']
            items = series.get('data', [])
            if not items:
                continue
            last = items[0]
            prev = items[1] if len(items) > 1 else None

            if sid == _BLS_CPI:
                curr_val = float(last['value'])
                # CPI YoY actual: (CPI[M] - CPI[M-12]) / CPI[M-12] * 100
                yoy_item = next((x for x in items if x['year'] == str(int(last['year'])-1)
                                 and x['period'] == last['period']), None)
                if yoy_item:
                    result['cpi_yoy'] = round((curr_val - float(yoy_item['value'])) / float(yoy_item['value']) * 100, 2)
                # CPI YoY anterior: mes M-1 vs M-13
                if prev:
                    prev_val = float(prev['value'])
                    yoy_prev_item = next((x for x in items
                                         if x['year'] == str(int(prev['year'])-1)
                                         and x['period'] == prev['period']), None)
                    if yoy_prev_item:
                        result['cpi_yoy_prev'] = round((prev_val - float(yoy_prev_item['value'])) / float(yoy_prev_item['value']) * 100, 2)
                result['cpi_raw']    = curr_val
                result['cpi_period'] = f"{last['periodName']} {last['year']}"

            elif sid == _BLS_NFP:
                curr_val = float(last['value'])
                prev2    = items[2] if len(items) > 2 else None
                prev_val = float(prev['value'])  if prev  else None
                prev2_val= float(prev2['value']) if prev2 else None
                # NFP actual = empleos netos mes M vs M-1
                added      = round(curr_val  - prev_val,  0) if prev_val  else None
                # NFP anterior = empleos netos mes M-1 vs M-2
                added_prev = round(prev_val  - prev2_val, 0) if (prev_val and prev2_val) else None
                result['nfp_total']      = curr_val
                result['nfp_added']      = added
                result['nfp_added_prev'] = added_prev
                result['nfp_period']     = f"{last['periodName']} {last['year']}"

            elif sid == _BLS_UNRATE:
                result['unrate']        = float(last['value'])
                result['unrate_prev']   = float(prev['value']) if prev else None
                result['unrate_period'] = f"{last['periodName']} {last['year']}"

        logger.info(f"[Macro] BLS OK — CPI YoY: {result.get('cpi_yoy')}% | NFP: +{result.get('nfp_added')}K | Desempleo: {result.get('unrate')}%")
    except Exception as e:
        logger.warning(f"[Macro] BLS error: {e}")
    return result


# ── BCRP API — sin key ───────────────────────────────────────────────────────
_BCRP_BASE    = 'https://estadisticas.bcrp.gob.pe/estadisticas/series/api'
_BCRP_TC_SELL = 'PD04638PD'   # TC venta interbancario DIARIO
_BCRP_TC_BUY  = 'PD04637PD'   # TC compra interbancario DIARIO

_MESES_ES = {
    'Jan':'ene','Feb':'feb','Mar':'mar','Apr':'abr','May':'may','Jun':'jun',
    'Jul':'jul','Aug':'ago','Sep':'sep','Oct':'oct','Nov':'nov','Dec':'dic',
}

def _parse_bcrp_period(name: str) -> str:
    """Convierte '24.Mar.26' → '24 mar 2026'."""
    try:
        parts = name.split('.')        # ['24', 'Mar', '26']
        day   = parts[0]
        mon   = _MESES_ES.get(parts[1], parts[1].lower())
        year  = '20' + parts[2] if len(parts[2]) == 2 else parts[2]
        return f"{day} {mon} {year}"
    except Exception:
        return name

def _fetch_bcrp() -> dict:
    result = {}
    now       = datetime.utcnow()
    date_from = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    date_to   = now.strftime('%Y-%m-%d')

    for key, code in [('tc_sell', _BCRP_TC_SELL), ('tc_buy', _BCRP_TC_BUY)]:
        try:
            url = f"{_BCRP_BASE}/{code}/json/{date_from}/{date_to}"
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; QoriCash/1.0)'}, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            periods = [p for p in data.get('periods', [])
                       if p.get('values') and p['values'][0] not in ('n.d.', '', None)]
            if not periods:
                continue
            last = periods[-1]
            prev = periods[-2] if len(periods) > 1 else None
            result[key]             = round(float(last['values'][0]), 4)
            result[f'{key}_prev']   = round(float(prev['values'][0]), 4) if prev else None
            result[f'{key}_period'] = _parse_bcrp_period(last['name'])
        except Exception as e:
            logger.debug(f"[Macro] BCRP {key}: {e}")

    if result:
        logger.info(f"[Macro] BCRP OK — TC venta: {result.get('tc_sell')} ({result.get('tc_sell_period')})")
    return result


# ── yfinance: T-bill 13W como proxy de tasa FED ──────────────────────────────
def _fetch_rates_yfinance() -> dict:
    result = {}
    try:
        irx = yf.Ticker('^IRX').fast_info
        result['fed_proxy']      = round(float(irx.last_price), 3)
        result['fed_proxy_prev'] = round(float(irx.previous_close), 3) if irx.previous_close else None
        logger.debug(f"[Macro] yfinance ^IRX: {result['fed_proxy']}%")
    except Exception as e:
        logger.debug(f"[Macro] ^IRX error: {e}")
    return result


# ── DatosMacro — Tasa de referencia BCRP ─────────────────────────────────────
_DATOSMACRO_BCRP = 'https://datosmacro.expansion.com/tipo-interes/peru'

def _fetch_bcrp_rate() -> dict:
    """Obtiene la tasa de referencia BCRP desde datosmacro.expansion.com."""
    import re
    result = {}
    try:
        r = requests.get(_DATOSMACRO_BCRP,
                         headers={'User-Agent': 'Mozilla/5.0 (compatible; QoriCash/1.0)'},
                         timeout=12)
        if r.status_code != 200:
            return result
        rows = re.findall(
            r'data-value="(\d{4}-\d{2}-\d{2})"[^>]*>[^<]*</td>\s*'
            r'<td[^>]*data-value="([\d.]+)"',
            r.text
        )
        if not rows:
            return result
        last_date,  last_val  = rows[0]
        prev_date,  prev_val  = rows[1] if len(rows) > 1 else (None, None)
        result['rate']      = float(last_val)
        result['prev']      = float(prev_val) if prev_val else None
        # Mostrar mes actual como período vigente (la tasa puede mantenerse meses sin cambio)
        result['period']    = datetime.utcnow().strftime('%b %Y')
        result['notes']     = f'Sin cambios desde {last_date[:7]}'
        logger.info(f"[Macro] BCRP rate OK — {last_val}% (desde {last_date})")
    except Exception as e:
        logger.warning(f"[Macro] DatosMacro BCRP rate error: {e}")
    return result


# ── FRED API (opcional — solo si FRED_API_KEY en .env) ───────────────────────
_FRED_BASE = 'https://api.stlouisfed.org/fred/series/observations'

def _fetch_fred(series_id: str) -> Optional[tuple]:
    """Retorna (latest_value, prev_value, period) o None."""
    key = os.getenv('FRED_API_KEY', '')
    if not key:
        return None
    try:
        params = {
            'series_id':  series_id,
            'api_key':    key,
            'file_type':  'json',
            'sort_order': 'desc',
            'limit':      13,
        }
        r = requests.get(_FRED_BASE, params=params, timeout=10)
        obs = [o for o in r.json().get('observations', []) if o['value'] != '.']
        if not obs:
            return None
        last = obs[0]
        prev = obs[1] if len(obs) > 1 else None
        return (float(last['value']),
                float(prev['value']) if prev else None,
                last['date'][:7])
    except Exception as e:
        logger.debug(f"[Macro] FRED {series_id}: {e}")
        return None


# ── Orquestador principal ─────────────────────────────────────────────────────
def fetch_macro_data() -> list[dict]:
    """
    Retorna lista de indicadores listos para upsert en MacroIndicator.
    Cada item: {key, label, value, prev_value, unit, period, source, direction, notes}
    """
    indicators = []

    def _dir(curr, prev):
        if curr is None or prev is None: return 'flat'
        return 'up' if curr > prev else ('down' if curr < prev else 'flat')

    def _add(key, label, value, prev, unit, period, source, notes=''):
        if value is None:
            return
        indicators.append({
            'key':        key,
            'label':      label,
            'value':      value,
            'prev_value': prev,
            'unit':       unit,
            'period':     period,
            'source':     source,
            'direction':  _dir(value, prev),
            'notes':      notes,
        })

    # ── 1. BLS — CPI y NFP ───────────────────────────────────────────────────
    bls = _fetch_bls()
    _add('us_cpi_yoy', 'Inflación EE.UU. (CPI YoY)',
         bls.get('cpi_yoy'), bls.get('cpi_yoy_prev'), '%',
         bls.get('cpi_period', ''), 'BLS',
         'CPI: Índice de precios al consumidor anualizado')

    if bls.get('nfp_added') is not None:
        _add('us_nfp', 'Nóminas EE.UU. (NFP)',
             bls.get('nfp_added'), bls.get('nfp_added_prev'), 'K empleos',
             bls.get('nfp_period', ''), 'BLS',
             'Variación mensual de empleo no agrícola')

    _add('us_unrate', 'Desempleo EE.UU.',
         bls.get('unrate'), bls.get('unrate_prev'), '%',
         bls.get('unrate_period', ''), 'BLS')

    # ── 2. Tasa FED ──────────────────────────────────────────────────────────
    # Primero intentar FRED, sino usar yfinance proxy
    fred_ff = _fetch_fred('FEDFUNDS')
    if fred_ff:
        _add('fed_rate', 'Tasa FED (Fed Funds)',
             fred_ff[0], fred_ff[1], '%', fred_ff[2], 'FRED',
             'Federal Funds Rate efectiva')
    else:
        rates_yf = _fetch_rates_yfinance()
        proxy = rates_yf.get('fed_proxy')
        if proxy:
            _add('fed_rate', 'Tasa FED (T-Bill 13W proxy)',
                 proxy, rates_yf.get('fed_proxy_prev'), '%',
                 datetime.utcnow().strftime('%b %Y'), 'yfinance',
                 'Proxy via T-Bill 13 semanas (^IRX)')

    # ── 3. BCRP — TC oficial ─────────────────────────────────────────────────
    bcrp = _fetch_bcrp()
    _add('bcrp_tc_sell', 'TC Oficial BCRP (Venta)',
         bcrp.get('tc_sell'), bcrp.get('tc_sell_prev'), 'S/',
         bcrp.get('tc_sell_period', ''), 'BCRP',
         'TC interbancario venta — dato diario BCRP')

    # ── 4. Tasa de referencia BCRP — DatosMacro (primario) / FRED (fallback) ──
    bcrp_rate_dm = _fetch_bcrp_rate()
    if bcrp_rate_dm.get('rate') is not None:
        _add('bcrp_rate', 'Tasa de Referencia BCRP',
             bcrp_rate_dm['rate'], bcrp_rate_dm.get('prev'), '%',
             bcrp_rate_dm['period'], 'BCRP',
             bcrp_rate_dm.get('notes', 'Tasa de política monetaria del BCRP'))
    else:
        fred_bcrp_rate = _fetch_fred('INTDSRPEM193N')
        if fred_bcrp_rate:
            _add('bcrp_rate', 'Tasa de Referencia BCRP',
                 fred_bcrp_rate[0], fred_bcrp_rate[1], '%',
                 fred_bcrp_rate[2], 'FRED')

    fred_cpi_core = _fetch_fred('CPILFESL')  # CPI Core (ex food & energy)
    if fred_cpi_core:
        # Calcular YoY manualmente desde las últimas 13 observaciones
        pass  # Simplificado — se implementa si la clave está disponible

    logger.info(f"[Macro] Ciclo completo — {len(indicators)} indicadores recolectados")
    return indicators

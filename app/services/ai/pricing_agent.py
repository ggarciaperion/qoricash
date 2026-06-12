"""
Agente de Pricing Dinámico
--------------------------
Analiza en tiempo real:
  - TC actual de QoriCash (ExchangeRate)
  - Tasas de los 19 competidores scrapeados (CompetitorRateCurrent)
  - Saldos USD/PEN por banco (BankBalance via FinanceEngine)
  - Flujo del día (operaciones completadas)
  - Hora del día (horario de mercado Lima)

Retorna: sugerencia de compra/venta óptima + justificación + alertas.
"""
import logging
from datetime import datetime, timezone, timedelta
from app.services.ai.client import ask_json, SONNET

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))


def _get_context() -> dict:
    """Reúne todos los datos de mercado necesarios."""
    from app.extensions import db
    from app.models.exchange_rate import ExchangeRate
    from app.models.competitor_rate import CompetitorRateCurrent, Competitor
    from app.services.finance_engine import FinanceEngine

    # TC actual QoriCash
    er = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
    current_tc = {
        'compra': float(er.buy_rate)  if er else None,
        'venta':  float(er.sell_rate) if er else None,
        'updated': er.updated_at.isoformat() if er and er.updated_at else None,
    }

    # Competidores activos con precio actual
    competitors = []
    for cur in CompetitorRateCurrent.query.all():
        comp = cur.competitor
        if comp:
            competitors.append({
                'nombre':  comp.name,
                'compra':  float(cur.buy_rate),
                'venta':   float(cur.sell_rate),
                'spread':  round(float(cur.sell_rate) - float(cur.buy_rate), 4),
                'prev_compra': float(cur.prev_buy_rate)  if cur.prev_buy_rate  else None,
                'prev_venta':  float(cur.prev_sell_rate) if cur.prev_sell_rate else None,
            })
    competitors.sort(key=lambda x: x['venta'])  # ordenar por venta asc

    # Saldos por banco (teórico)
    balances = FinanceEngine.get_balances()
    saldos = {bk: {'USD': round(v['USD'], 2), 'PEN': round(v['PEN'], 2)}
              for bk, v in balances['by_bank'].items()}

    # Operaciones del día
    from app.services.finance_engine import FinanceEngine as FE
    ops = FE.get_daily_ops(datetime.now(_LIMA).date())

    # Hora Lima
    now_lima = datetime.now(_LIMA)

    return {
        'hora_lima':    now_lima.strftime('%H:%M'),
        'dia_semana':   now_lima.strftime('%A'),
        'tc_qoricash':  current_tc,
        'competidores': competitors[:10],  # top 10 más relevantes
        'saldos':       saldos,
        'total_usd':    round(balances['total_usd'], 2),
        'total_pen':    round(balances['total_pen'], 2),
        'ops_hoy':      ops,
    }


def analyze() -> dict:
    """
    Ejecuta el agente de pricing.
    Retorna dict con: sugerido_compra, sugerido_venta, justificacion, alertas, datos.
    """
    try:
        ctx = _get_context()
        competitors_txt = '\n'.join(
            f"  - {c['nombre']}: compra {c['compra']:.4f} / venta {c['venta']:.4f}"
            + (f" (↓ bajó venta)" if c.get('prev_venta') and c['venta'] < c['prev_venta'] else '')
            + (f" (↑ subió venta)" if c.get('prev_venta') and c['venta'] > c['prev_venta'] else '')
            for c in ctx['competidores']
        )
        saldos_txt = '\n'.join(
            f"  - {bk}: USD {v['USD']:,.2f} / PEN {v['PEN']:,.2f}"
            for bk, v in ctx['saldos'].items()
        )
        ops = ctx['ops_hoy']
        ops_txt = (f"Compras: {ops.get('compras_count',0)} ops por ${ops.get('buy_usd',0):,.0f} USD | "
                   f"Ventas: {ops.get('ventas_count',0)} ops por ${ops.get('sell_usd',0):,.0f} USD")

        prompt = f"""Eres el analista de pricing de QoriCash, casa de cambio digital en Lima Perú.

DATOS ACTUALES ({ctx['hora_lima']} Lima, {ctx['dia_semana']}):

TC ACTUAL QORICASH:
  Compra: {ctx['tc_qoricash']['compra']} | Venta: {ctx['tc_qoricash']['venta']}

TOP COMPETIDORES (ordenados por venta):
{competitors_txt}

SALDOS POR BANCO:
{saldos_txt}
Total USD: ${ctx['total_usd']:,.2f} | Total PEN: S/{ctx['total_pen']:,.2f}

OPERACIONES HOY: {ops_txt}

TAREA: Analiza la situación y recomienda el TC óptimo para los próximos 30 minutos.

Responde SOLO con JSON válido, sin texto extra:
{{
  "sugerido_compra": <número con 4 decimales>,
  "sugerido_venta":  <número con 4 decimales>,
  "spread_sugerido": <número con 4 decimales>,
  "posicion_mercado": "competitivo|agresivo|conservador",
  "justificacion": "<2-3 oraciones explicando la recomendación>",
  "alertas": ["<alerta1>", "<alerta2>"],
  "accion_urgente": true|false,
  "ranking_qoricash": "<posición estimada en el mercado, ej: Top 3 más competitivo>"
}}"""

        result = ask_json(prompt, model=SONNET, max_tokens=1024)
        result['datos'] = ctx
        result['timestamp'] = datetime.now(_LIMA).isoformat()
        return {'ok': True, 'analysis': result}

    except Exception as e:
        _log.error(f'[PricingAgent] Error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}

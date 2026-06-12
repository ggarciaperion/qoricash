"""
Agente de Tesorería — Asistente de Cuadre Diario
-------------------------------------------------
Analiza la posición financiera del día:
  - Saldos teóricos vs reales por banco
  - Flujo de caja (ingresos/egresos)
  - Inconsistencias y diferencias
  - Recomendaciones de cuadre y gestión de liquidez
"""
import logging
from app.services.ai.client import ask_json, SONNET

_log = logging.getLogger(__name__)


def _get_treasury_context() -> dict:
    from app.extensions import db
    from app.services.finance_engine import FinanceEngine
    from app.models.daily_closure import DailyClosure
    from app.utils.formatters import now_peru

    today = now_peru().date()

    # Cashflow teórico del día
    cf = FinanceEngine.get_daily_cashflow(today)

    # Saldos por banco
    balances = FinanceEngine.get_balances()

    # Cierre del día (si existe)
    closure = DailyClosure.query.filter_by(closure_date=today).first()
    cierre_info = None
    if closure and closure.closing_balance_json and closure.closing_balance_json != '{}':
        import json
        try:
            real_balances = json.loads(closure.closing_balance_json)
            cierre_info = {'tiene_cierre': True, 'saldos_reales': real_balances}
        except Exception:
            cierre_info = {'tiene_cierre': True, 'saldos_reales': {}}
    else:
        cierre_info = {'tiene_cierre': False, 'saldos_reales': {}}

    # Operaciones del día
    ops = FinanceEngine.get_daily_ops(today)

    return {
        'fecha': today.isoformat(),
        'cashflow': cf,
        'balances': balances,
        'cierre': cierre_info,
        'ops_hoy': ops,
    }


def analyze_daily_position() -> dict:
    """
    Genera análisis inteligente de la posición tesorera del día.
    """
    try:
        ctx = _get_treasury_context()
        cf = ctx['cashflow']
        ops = ctx['ops_hoy']

        # Construir texto de bancos
        bancos_txt = ''
        by_bank = cf.get('by_bank', {})
        for bk, currencies in by_bank.items():
            for cur, data in currencies.items():
                teo  = data.get('teorico', 0)
                ini  = data.get('inicial', 0)
                ing  = data.get('ingresos', 0)
                egr  = data.get('egresos', 0)
                bancos_txt += (
                    f"  {bk} {cur}: inicial={ini:,.2f} + ing={ing:,.2f} - egr={egr:,.2f} = teórico={teo:,.2f}\n"
                )

        # Diferencias si existe cierre
        diffs_txt = ''
        if ctx['cierre']['tiene_cierre']:
            real = ctx['cierre']['saldos_reales']
            for key, teo_val in (cf.get('totals') or {}).items():
                real_val = float(real.get(key, 0))
                diff = real_val - float(teo_val)
                if abs(diff) > 0.01:
                    diffs_txt += f"  {key}: teórico={teo_val:,.2f} | real={real_val:,.2f} | diff={diff:+,.2f}\n"
            if not diffs_txt:
                diffs_txt = '  Sin diferencias detectadas — cuadre perfecto.'
        else:
            diffs_txt = '  (día aún no cerrado — sin saldos reales ingresados)'

        prompt = f"""Eres el oficial de tesorería de QoriCash, casa de cambio regulada por la SBS en Lima Perú.
Analiza la posición financiera del día {ctx['fecha']} y emite un diagnóstico operativo.

FLUJO DEL DÍA:
  Operaciones completadas: {ops.get('total_ops', 0)}
  Compras USD: {ops.get('compras_count', 0)} ops | ${ops.get('buy_usd', 0):,.2f} USD
  Ventas USD:  {ops.get('ventas_count', 0)} ops | ${ops.get('sell_usd', 0):,.2f} USD
  Ganancia bruta estimada: S/ {ops.get('ganancia_pen', 0):,.2f}

SALDOS TEÓRICOS POR BANCO:
{bancos_txt if bancos_txt else '  (sin movimientos registrados)'}

DIFERENCIAS TEÓRICO vs REAL:
{diffs_txt}

TOTALES:
  USD teórico total: ${cf.get('total_teo_usd', 0):,.2f}
  PEN teórico total: S/ {cf.get('total_teo_pen', 0):,.2f}

Detecta inconsistencias, riesgos de liquidez, y da recomendaciones concretas para el oficial de tesorería.

Responde SOLO JSON:
{{
  "estado_general": "Saludable|Atención|Crítico",
  "resumen": "<diagnóstico en 3-4 oraciones>",
  "inconsistencias": ["<inconsistencia1>", "<inconsistencia2>"],
  "alertas_liquidez": ["<alerta1>"],
  "recomendaciones": ["<acción1>", "<acción2>"],
  "score_cuadre": <0-100>,
  "requiere_atencion_inmediata": true|false,
  "notas_sbs": "<observaciones de cumplimiento SBS si aplica>"
}}"""

        result = ask_json(prompt, model=SONNET, max_tokens=1000)
        result['fecha'] = ctx['fecha']
        result['context'] = {
            'total_ops': ops.get('total_ops', 0),
            'total_teo_usd': cf.get('total_teo_usd', 0),
            'total_teo_pen': cf.get('total_teo_pen', 0),
            'tiene_cierre': ctx['cierre']['tiene_cierre'],
        }
        return {'ok': True, 'analysis': result}

    except Exception as e:
        _log.error(f'[TreasuryAgent] Error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}


def suggest_bank_distribution() -> dict:
    """
    Recomienda distribución óptima de saldos entre bancos según operaciones recientes.
    """
    try:
        from app.services.finance_engine import FinanceEngine
        from app.utils.formatters import now_peru
        from datetime import timedelta

        today = now_peru().date()

        # Últimos 7 días de operaciones por banco
        from app.extensions import db
        from app.models.bank_movement import BankMovement
        from sqlalchemy import func

        cutoff = today - timedelta(days=7)
        stats = db.session.query(
            BankMovement.bank_name,
            BankMovement.currency,
            func.sum(BankMovement.amount).label('flujo'),
            func.count(BankMovement.id).label('movs'),
        ).filter(
            BankMovement.movement_date >= cutoff,
        ).group_by(BankMovement.bank_name, BankMovement.currency).all()

        stats_txt = '\n'.join(
            f"  {r.bank_name} {r.currency}: flujo={float(r.flujo or 0):+,.2f} | {int(r.movs)} movimientos"
            for r in stats
        ) or '  (sin movimientos en 7 días)'

        balances = FinanceEngine.get_balances()
        saldos_txt = '\n'.join(
            f"  {bk}: USD {v['USD']:,.2f} | PEN {v['PEN']:,.2f}"
            for bk, v in balances['by_bank'].items()
        )

        prompt = f"""Eres el tesorero de QoriCash. Analiza la distribución de saldos entre bancos.

SALDOS ACTUALES:
{saldos_txt}
  TOTAL: USD {balances['total_usd']:,.2f} | PEN {balances['total_pen']:,.2f}

FLUJO ÚLTIMOS 7 DÍAS:
{stats_txt}

Recomienda la distribución óptima de liquidez entre bancos para las próximas 24h.

Responde SOLO JSON:
{{
  "distribucion_recomendada": [
    {{"banco": "<nombre>", "currency": "USD|PEN", "monto_sugerido": <float>, "razon": "<motivo>"}}
  ],
  "transferencias_sugeridas": [
    {{"origen": "<banco>", "destino": "<banco>", "moneda": "USD|PEN", "monto": <float>, "prioridad": "alta|media|baja"}}
  ],
  "observacion": "<análisis general en 2 oraciones>"
}}"""

        result = ask_json(prompt, model=SONNET, max_tokens=800)
        return {'ok': True, 'recommendation': result}

    except Exception as e:
        _log.error(f'[TreasuryAgent] suggest_distribution error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}

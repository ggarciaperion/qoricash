"""
Servicio de análisis diario fundamental del USD/PEN.

Ciclo de vida:
  - Análisis base: generado a las 8:30 AM Lima lun–vie.
    Ventana: cierre del mercado anterior (1:30 PM Lima del día anterior)
             hasta las 8:30 AM del día actual.
  - Actualización intradía: manual, a petición del trader.
    Incorpora noticias de ALTO impacto desde las 8:30 AM hasta la hora actual.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from app.utils.formatters import now_peru

from app.extensions import db
from app.models.market import (
    MarketNews, MacroIndicator, EconomicEvent,
    DailyAnalysis, MarketSnapshot
)

logger = logging.getLogger(__name__)

_LIMA_TZ     = timezone(timedelta(hours=-5))
_MARKET_OPEN  = (9,  0)   # 9:00 AM Lima
_MARKET_CLOSE = (13, 30)  # 1:30 PM Lima


class DailyAnalysisService:

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def generate_daily_analysis() -> dict:
        """
        Análisis base de las 8:30 AM Lima.

        Ventana de noticias:
          Desde: ayer 1:30 PM Lima (cierre del mercado anterior)
          Hasta:  hoy  8:30 AM Lima (momento de generación)
        """
        try:
            now_lima   = datetime.now(_LIMA_TZ)
            today_date = now_lima.date()

            # Cierre del mercado del día anterior: ayer 1:30 PM Lima
            yesterday_close_lima = (now_lima - timedelta(days=1)).replace(
                hour=13, minute=30, second=0, microsecond=0
            )
            window_start_utc = yesterday_close_lima.astimezone(timezone.utc).replace(tzinfo=None)

            news_rows = (
                MarketNews.query
                .filter(MarketNews.fetched_at >= window_start_utc)
                .filter(MarketNews.direction != 'neutral')
                .order_by(MarketNews.impact_level.desc(), MarketNews.fetched_at.desc())
                .all()
            )

            bullish_count = bearish_count = 0
            net_score     = 0
            key_factors   = []
            _w = {'high': 3, 'medium': 2, 'low': 1}

            for art in news_rows:
                w = _w.get(art.impact_level, 0)
                if art.direction == 'bullish_usd':
                    bullish_count += 1
                    net_score     += w
                    if art.impact_level in ('high', 'medium'):
                        key_factors.append({
                            'direction': 'bullish',
                            'text': f"[{art.source}] {art.title[:110]}",
                            'impact': art.impact_level,
                        })
                elif art.direction == 'bearish_usd':
                    bearish_count += 1
                    net_score     -= w
                    if art.impact_level in ('high', 'medium'):
                        key_factors.append({
                            'direction': 'bearish',
                            'text': f"[{art.source}] {art.title[:110]}",
                            'impact': art.impact_level,
                        })

            # ── Ajustes macro ─────────────────────────────────────────────
            snap = MarketSnapshot.query.order_by(MarketSnapshot.captured_at.desc()).first()
            fed  = MacroIndicator.query.filter_by(key='fed_rate').first()
            bcrp = MacroIndicator.query.filter_by(key='bcrp_rate').first()
            macro_notes = []

            if fed and fed.value:
                v = float(fed.value)
                if v >= 5.25:
                    net_score += 1
                    macro_notes.append(f"Tasa FED elevada ({v:.2f}%) — soporte estructural al USD")
                elif v <= 3.5:
                    net_score -= 1
                    macro_notes.append(f"Tasa FED baja ({v:.2f}%) — presión bajista en USD")

            if snap:
                if snap.dxy_chg_pct is not None:
                    d = float(snap.dxy_chg_pct)
                    if d >= 0.30:
                        net_score += 2
                        macro_notes.append(f"DXY subió {d:+.2f}% — dólar fuerte globalmente")
                    elif d <= -0.30:
                        net_score -= 2
                        macro_notes.append(f"DXY cayó {d:+.2f}% — dólar débil globalmente")
                if snap.copper_chg_pct is not None:
                    c = float(snap.copper_chg_pct)
                    if c >= 1.5:
                        net_score -= 1
                        macro_notes.append(f"Cobre subió {c:+.2f}% — beneficia al sol peruano")
                    elif c <= -1.5:
                        net_score += 1
                        macro_notes.append(f"Cobre cayó {c:+.2f}% — presión sobre el sol peruano")
                if snap.vix is not None and float(snap.vix) > 30:
                    net_score += 1
                    macro_notes.append(f"VIX en zona de pánico ({float(snap.vix):.1f}) → flight-to-safety USD")

            for note in macro_notes:
                key_factors.append({'direction': 'macro', 'text': note, 'impact': 'medium'})

            # ── Eventos de alto impacto del día ───────────────────────────
            today_start_utc = (
                now_lima.replace(hour=0, minute=0, second=0, microsecond=0)
                .astimezone(timezone.utc).replace(tzinfo=None)
            )
            today_end_utc = (
                now_lima.replace(hour=23, minute=59, second=59)
                .astimezone(timezone.utc).replace(tzinfo=None)
            )
            today_events = (
                EconomicEvent.query
                .filter(EconomicEvent.event_date >= today_start_utc)
                .filter(EconomicEvent.event_date <= today_end_utc)
                .filter(EconomicEvent.impact == 'high')
                .order_by(EconomicEvent.event_date.asc())
                .all()
            )
            for ev in today_events:
                key_factors.append({
                    'direction': 'event',
                    'text': f"⚠️ HOY {ev.flag} {ev.event_name} ({ev.country})",
                    'impact': 'high',
                })

            # ── Tendencia y confianza ──────────────────────────────────────
            trend, confidence = DailyAnalysisService._score_to_trend(net_score)

            # ── Texto ─────────────────────────────────────────────────────
            title, summary = DailyAnalysisService._build_base_text(
                trend, confidence, net_score, bullish_count, bearish_count,
                macro_notes, today_events, snap, bcrp,
            )

            # ── Desactivar análisis anteriores del día ────────────────────
            DailyAnalysis.query.filter_by(
                analysis_date=today_date, is_active=True
            ).update({'is_active': False})

            analysis = DailyAnalysis(
                analysis_date        = today_date,
                generated_at         = now_peru(),
                trend                = trend,
                confidence           = confidence,
                title                = title,
                summary              = summary,
                key_factors          = json.dumps(key_factors[:12], ensure_ascii=False),
                news_analyzed        = len(news_rows),
                bullish_signals      = bullish_count,
                bearish_signals      = bearish_count,
                net_score            = net_score,
                is_extraordinary     = False,
                extraordinary_reason = None,
                is_active            = True,
            )
            db.session.add(analysis)
            db.session.commit()

            logger.info(
                f"[DailyAnalysis] ✅ Análisis base generado — {trend} conf={confidence}% "
                f"net={net_score} noticias={len(news_rows)}"
            )
            return {'ok': True, 'trend': trend, 'confidence': confidence, 'net_score': net_score}

        except Exception as e:
            db.session.rollback()
            logger.error(f"[DailyAnalysis] ❌ Error en análisis base: {e}", exc_info=True)
            return {'ok': False, 'error': str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def update_intraday_analysis() -> dict:
        """
        Actualización intradía manual (a petición del trader).

        Incorpora noticias de ALTO impacto desde las 8:30 AM Lima hasta ahora.
        Combina con el análisis base del día para ajustar la tendencia.
        """
        try:
            now_lima   = datetime.now(_LIMA_TZ)
            today_date = now_lima.date()

            # Ventana: 8:30 AM Lima hoy → ahora
            base_time_lima = now_lima.replace(hour=8, minute=30, second=0, microsecond=0)
            base_time_utc  = base_time_lima.astimezone(timezone.utc).replace(tzinfo=None)

            # Solo noticias de ALTO impacto desde las 8:30 AM
            new_news = (
                MarketNews.query
                .filter(MarketNews.fetched_at >= base_time_utc)
                .filter(MarketNews.direction != 'neutral')
                .filter(MarketNews.impact_level == 'high')
                .order_by(MarketNews.fetched_at.desc())
                .all()
            )

            # Análisis base del día (el primero generado hoy, no el más reciente)
            base = (
                DailyAnalysis.query
                .filter_by(analysis_date=today_date)
                .filter(DailyAnalysis.extraordinary_reason == None)
                .order_by(DailyAnalysis.generated_at.asc())
                .first()
            )
            # Si no hay base, usar el primero del día
            if not base:
                base = (
                    DailyAnalysis.query
                    .filter_by(analysis_date=today_date)
                    .order_by(DailyAnalysis.generated_at.asc())
                    .first()
                )

            base_score = base.net_score            if base else 0
            base_bull  = base.bullish_signals       if base else 0
            base_bear  = base.bearish_signals       if base else 0
            base_facts = json.loads(base.key_factors) if (base and base.key_factors) else []

            # Calcular delta de noticias nuevas
            delta_score = 0
            new_bull = new_bear = 0
            new_factors = []

            for art in new_news:
                if art.direction == 'bullish_usd':
                    delta_score += 3
                    new_bull    += 1
                    new_factors.append({
                        'direction': 'bullish',
                        'text': f"[NUEVO {art.source}] {art.title[:110]}",
                        'impact': 'high',
                    })
                elif art.direction == 'bearish_usd':
                    delta_score -= 3
                    new_bear    += 1
                    new_factors.append({
                        'direction': 'bearish',
                        'text': f"[NUEVO {art.source}] {art.title[:110]}",
                        'impact': 'high',
                    })

            combined_score = base_score + delta_score
            trend, confidence = DailyAnalysisService._score_to_trend(combined_score)

            # Snapshot para precios actuales
            snap = MarketSnapshot.query.order_by(MarketSnapshot.captured_at.desc()).first()

            # Construir texto
            title, summary = DailyAnalysisService._build_intraday_text(
                trend, confidence, combined_score, delta_score,
                new_bull, new_bear, new_news, base, snap, now_lima,
            )

            # Desactivar análisis activos
            DailyAnalysis.query.filter_by(
                analysis_date=today_date, is_active=True
            ).update({'is_active': False})

            # Combinar factores: nuevos primero, luego los del base
            combined_factors = new_factors + [
                f for f in base_facts if f.get('direction') != 'event'
            ]

            analysis = DailyAnalysis(
                analysis_date        = today_date,
                generated_at         = now_peru(),
                trend                = trend,
                confidence           = confidence,
                title                = title,
                summary              = summary,
                key_factors          = json.dumps(combined_factors[:12], ensure_ascii=False),
                news_analyzed        = (base.news_analyzed if base else 0) + len(new_news),
                bullish_signals      = base_bull + new_bull,
                bearish_signals      = base_bear + new_bear,
                net_score            = combined_score,
                is_extraordinary     = False,
                extraordinary_reason = f"Actualización intradía {now_lima.strftime('%H:%M')} Lima",
                is_active            = True,
            )
            db.session.add(analysis)
            db.session.commit()

            logger.info(
                f"[DailyAnalysis] ↺ Actualización intradía — {trend} ({confidence}%) "
                f"delta={delta_score:+d} nuevas_noticias={len(new_news)}"
            )
            return {
                'ok': True, 'trend': trend, 'confidence': confidence,
                'new_news': len(new_news), 'delta_score': delta_score,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"[DailyAnalysis] ❌ Error en actualización intradía: {e}", exc_info=True)
            return {'ok': False, 'error': str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_today_analysis():
        """Devuelve el análisis activo del día actual (hora Lima)."""
        today_date = datetime.now(_LIMA_TZ).date()
        analysis = (
            DailyAnalysis.query
            .filter_by(analysis_date=today_date, is_active=True)
            .order_by(DailyAnalysis.generated_at.desc())
            .first()
        )
        return analysis.to_dict() if analysis else None

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _score_to_trend(net_score: int):
        """Convierte net_score → (trend, confidence)."""
        abs_score = abs(net_score)
        if abs_score >= 8:
            confidence = min(90 + (abs_score - 8), 95)
        elif abs_score >= 5:
            confidence = 70 + (abs_score - 5) * 5
        elif abs_score >= 2:
            confidence = 45 + (abs_score - 2) * 8
        else:
            confidence = 30 + abs_score * 5

        if net_score >= 3:
            trend = 'alza'
        elif net_score <= -3:
            trend = 'baja'
        else:
            trend = 'estable'

        return trend, confidence

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_base_text(trend, confidence, net_score, bullish, bearish,
                         macro_notes, today_events, snap, bcrp):
        """Resumen técnico para el análisis base de 8:30 AM."""
        if trend == 'alza':
            prefix = "📈 Probable subida del dólar" if confidence >= 65 else "📈 Ligera presión alcista"
        elif trend == 'baja':
            prefix = "📉 Probable caída del dólar" if confidence >= 65 else "📉 Ligera presión bajista"
        else:
            prefix = "↔ Dólar sin dirección clara"

        usd_str = f" · S/{float(snap.usdpen):.4f}" if (snap and snap.usdpen) else ""
        title = f"{prefix}{usd_str}"

        trend_word = {'alza': 'alcista', 'baja': 'bajista', 'estable': 'neutral'}[trend]
        total = bullish + bearish

        # ── Párrafo 1: Veredicto ─────────────────────────────────────────────
        main_drivers = []
        if snap:
            if snap.dxy_chg_pct and abs(float(snap.dxy_chg_pct)) >= 0.15:
                d = float(snap.dxy_chg_pct)
                main_drivers.append(
                    f"{'fortalecimiento' if d > 0 else 'debilitamiento'} del DXY ({d:+.2f}%)"
                )
            if snap.vix is not None and float(snap.vix) > 18:
                v = float(snap.vix)
                main_drivers.append(
                    f"{'pánico en mercados' if v > 30 else 'aversión al riesgo elevada'} (VIX {v:.1f})"
                )
            if snap.copper_chg_pct and abs(float(snap.copper_chg_pct)) >= 1.0:
                c = float(snap.copper_chg_pct)
                main_drivers.append(
                    f"{'alza' if c > 0 else 'caída'} del cobre ({c:+.2f}%)"
                )
            if snap.treasury_10y_chg and abs(float(snap.treasury_10y_chg)) >= 0.03:
                t = float(snap.treasury_10y_chg)
                main_drivers.append(
                    f"bono 10Y EE.UU. {'al alza' if t > 0 else 'a la baja'} ({t:+.3f}%)"
                )

        if main_drivers:
            if len(main_drivers) > 1:
                drivers_str = ", ".join(main_drivers[:-1]) + f" y {main_drivers[-1]}"
            else:
                drivers_str = main_drivers[0]
            p1 = (
                f"El dólar muestra sesgo {trend_word} con una confianza del {confidence}%, "
                f"impulsado principalmente por {drivers_str}."
            )
        else:
            p1 = (
                f"El dólar muestra sesgo {trend_word} con una confianza del {confidence}%, "
                f"sin catalizadores técnicos dominantes en el período analizado."
            )

        # ── Párrafo 2: Detalle de cada driver ───────────────────────────────
        driver_lines = []
        if snap:
            if snap.dxy_chg_pct and abs(float(snap.dxy_chg_pct)) >= 0.15:
                d = float(snap.dxy_chg_pct)
                accion = "se fortalece" if d > 0 else "se debilita"
                impacto = "presión alcista" if d > 0 else "presión bajista"
                driver_lines.append(
                    f"  • DXY {d:+.2f}%: el índice del dólar {accion} frente a divisas principales → "
                    f"{impacto} directa sobre el USD/PEN"
                )
            if snap.vix is not None and float(snap.vix) > 18:
                v = float(snap.vix)
                vc = f" ({float(snap.vix_chg_pct):+.2f}%)" if snap.vix_chg_pct else ""
                if v > 30:
                    interp = "zona de pánico — el dólar actúa como refugio global, impulsando el USD/PEN al alza"
                else:
                    interp = "incertidumbre elevada — favorece la demanda de dólar como activo seguro"
                driver_lines.append(f"  • VIX {v:.1f}{vc}: {interp}")
            if snap.copper_chg_pct and abs(float(snap.copper_chg_pct)) >= 1.0:
                c = float(snap.copper_chg_pct)
                if c > 0:
                    interp = "Perú (2do exportador mundial) se beneficia → el sol peruano gana fuerza → presión bajista en USD/PEN"
                else:
                    interp = "menores ingresos de exportación para Perú → el sol se debilita → presión alcista en USD/PEN"
                driver_lines.append(f"  • Cobre {c:+.2f}%: {interp}")
            if snap.treasury_10y_chg and abs(float(snap.treasury_10y_chg)) >= 0.03:
                t = float(snap.treasury_10y_chg)
                tv = float(snap.treasury_10y) if snap.treasury_10y else None
                tv_str = f" (rinde {tv:.3f}%)" if tv else ""
                if t > 0:
                    interp = f"rendimiento sube{tv_str} → mayor atractivo del bono EE.UU. → capitales fluyen hacia USD"
                else:
                    interp = f"rendimiento baja{tv_str} → menor atractivo del bono EE.UU. → reducción del diferencial con emergentes"
                driver_lines.append(f"  • Bono 10Y {t:+.3f}%: {interp}")
            if snap.gold_chg_pct and abs(float(snap.gold_chg_pct)) >= 0.8:
                g = float(snap.gold_chg_pct)
                gv = f"${float(snap.gold):.0f}/oz" if snap.gold else ""
                if g > 0:
                    interp = "alza en oro refleja demanda de refugio y desconfianza en el dólar — señal mixta"
                else:
                    interp = "caída en oro indica menor demanda de refugio — soporte relativo al dólar"
                driver_lines.append(f"  • Oro {g:+.2f}%{' ' + gv if gv else ''}: {interp}")
            if snap.eurusd_chg_pct and abs(float(snap.eurusd_chg_pct)) >= 0.30:
                e = float(snap.eurusd_chg_pct)
                if e > 0:
                    interp = "euro sube vs dólar → DXY presionado → USD/PEN con sesgo bajista"
                else:
                    interp = "euro cae vs dólar → DXY fortalecido → USD/PEN con sesgo alcista"
                driver_lines.append(f"  • EUR/USD {e:+.2f}%: {interp}")

        p2 = ""
        if driver_lines:
            p2 = "Factores determinantes:\n" + "\n".join(driver_lines)

        # ── Párrafo 3: Balance de noticias ───────────────────────────────────
        p3 = ""
        if total > 0:
            window = "ventana 1:30 PM ayer → 8:30 AM hoy"
            if bullish > bearish:
                p3 = (
                    f"Balance noticioso: {bullish} noticias con impacto alcista para el dólar "
                    f"frente a {bearish} bajistas (score neto {net_score:+d}) en la {window}. "
                    f"El flujo informativo respalda la presión {trend_word}."
                )
            elif bearish > bullish:
                p3 = (
                    f"Balance noticioso: {bearish} noticias con impacto bajista para el dólar "
                    f"frente a {bullish} alcistas (score neto {net_score:+d}) en la {window}. "
                    f"El flujo informativo refuerza la presión {trend_word}."
                )
            else:
                p3 = (
                    f"Balance noticioso mixto: {bullish} noticias alcistas y {bearish} bajistas "
                    f"en partes iguales (score neto {net_score:+d}) en la {window}. "
                    f"Sin sesgo informativo claro."
                )

        # ── Párrafo 4: Contexto operativo ────────────────────────────────────
        ctx_lines = []
        if snap:
            if snap.usdpen_chg_pct:
                chg = float(snap.usdpen_chg_pct)
                if abs(chg) > 0.05:
                    ctx_lines.append(
                        f"  • Spot USD/PEN lleva {chg:+.2f}% en lo que va de la sesión"
                    )
            if snap.dxy is not None:
                dxy_val = float(snap.dxy)
                if dxy_val > 104:
                    ctx_lines.append(
                        f"  • DXY en zona alta ({dxy_val:.2f}) — estructuralmente favorable al dólar"
                    )
                elif dxy_val < 100:
                    ctx_lines.append(
                        f"  • DXY en zona baja ({dxy_val:.2f}) — limita el potencial alcista del dólar"
                    )
            if snap.sp500_chg_pct:
                sp = float(snap.sp500_chg_pct)
                if abs(sp) >= 1.0:
                    ctx_lines.append(
                        f"  • S&P 500 {sp:+.2f}%: {'caída en Wall Street → risk-off → dólar como refugio' if sp < 0 else 'alza en Wall Street → apetito de riesgo → capitales a emergentes'}"
                    )
        if bcrp and bcrp.value:
            b = float(bcrp.value)
            ctx_lines.append(f"  • Tasa BCRP {b:.2f}%: referencia local del Banco Central del Perú")

        p4 = ""
        if ctx_lines:
            p4 = "Contexto operativo:\n" + "\n".join(ctx_lines)

        # ── Párrafo 5: Eventos de alto impacto ───────────────────────────────
        p5 = ""
        if today_events:
            ev_list = "; ".join(f"{ev.flag} {ev.event_name}" for ev in today_events[:4])
            p5 = (
                f"⚠ Eventos de alto impacto programados para hoy: {ev_list}. "
                f"Pueden generar volatilidad puntual — monitorear en sus horarios de publicación."
            )

        # ── Párrafo 6: Implicaciones para la operación de QoriCash ───────────
        op_lines = []

        if trend == 'alza':
            op_lines.append(
                "Con sesgo alcista en el dólar, se anticipa mayor demanda de compra de USD "
                "por parte de clientes que buscan cobertura o anticipan mayor tipo de cambio. "
                "Considerar ajustar el precio de venta al alza para capturar el movimiento "
                "sin perder competitividad."
            )
            if confidence >= 70:
                op_lines.append(
                    "La alta convicción del análisis sugiere sostenibilidad del movimiento "
                    "durante la jornada — el margen de venta puede ampliarse con menor riesgo "
                    "de reversión inmediata."
                )
            else:
                op_lines.append(
                    "La convicción moderada aconseja monitorear el comportamiento del USD/PEN "
                    "en la apertura del mercado local (9:00 AM) antes de realizar ajustes "
                    "significativos en los precios publicados."
                )
        elif trend == 'baja':
            op_lines.append(
                "Con presión bajista sobre el dólar, se espera mayor flujo de clientes "
                "vendiendo USD (quienes anticipan caída del tipo de cambio). "
                "Evaluar ajustar el precio de compra a la baja para mantener margen "
                "y evitar acumular posición en dólares a precios elevados."
            )
            if confidence >= 70:
                op_lines.append(
                    "La señal de alta convicción refuerza la cautela en la acumulación de USD — "
                    "priorizar rotación de posición y mantener liquidez en soles."
                )
            else:
                op_lines.append(
                    "Dada la convicción moderada, se recomienda no realizar ajustes bruscos "
                    "en precios hasta confirmar la dirección en la apertura del mercado (9:00 AM)."
                )
        else:
            op_lines.append(
                "Sin tendencia definida, el mercado cambiario local operará probablemente "
                "en rango estrecho. Mantener precios vigentes y aprovechar el spread actual "
                "sin necesidad de ajustes. Estar atentos a catalizadores que rompan el rango."
            )

        # Alerta de volatilidad si VIX está elevado
        if snap and snap.vix is not None:
            v = float(snap.vix)
            if v > 25:
                op_lines.append(
                    f"Con el VIX en {v:.1f}, la volatilidad global es elevada — "
                    f"los movimientos intradiarios pueden ser más amplios de lo habitual. "
                    f"Reducir el tiempo de exposición entre actualización de precios y "
                    f"confirmación de operaciones."
                )

        p6 = "Implicaciones para la operación:\n" + "\n\n".join(f"  {l}" for l in op_lines)

        parts = [x for x in [p1, p2, p3, p4, p5, p6] if x]
        summary = "\n\n".join(parts)
        return title, summary

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_intraday_text(trend, confidence, combined_score, delta_score,
                             new_bull, new_bear, new_news, base, snap, now_lima):
        """Resumen técnico para la actualización intradía."""
        time_str = now_lima.strftime('%H:%M')

        if not new_news:
            prefix = f"↺ {time_str} — Sin nuevos factores"
        elif delta_score > 0:
            prefix = f"📈 {time_str} — Nuevos factores alcistas"
        else:
            prefix = f"📉 {time_str} — Nuevos factores bajistas"

        usd_str = f" · S/{float(snap.usdpen):.4f}" if (snap and snap.usdpen) else ""
        title = f"{prefix}{usd_str}"

        trend_word = {'alza': 'alcista', 'baja': 'bajista', 'estable': 'neutral'}[trend]

        # Párrafo 1: estado actual de las nuevas noticias
        if not new_news:
            p1 = (
                f"Sin noticias de alto impacto desde las 8:30 AM Lima. "
                f"La tendencia base se mantiene: {trend_word} ({confidence}%, score {combined_score:+d})."
            )
        else:
            base_ref = f" La base de 8:30 AM era {base.trend} (score {base.net_score:+d})." if base else ""
            p1 = (
                f"Se incorporaron {len(new_news)} noticia(s) de alto impacto desde las 8:30 AM: "
                f"{new_bull} alcista(s) y {new_bear} bajista(s) — delta {delta_score:+d} sobre la base.{base_ref}"
            )

        # Párrafo 2: tendencia actualizada
        p2 = (
            f"Tendencia actualizada: {trend_word} · confianza {confidence}% · score neto {combined_score:+d}."
        )

        # Párrafo 3: snapshot del mercado en este momento
        mkt_lines = []
        if snap:
            if snap.usdpen and snap.usdpen_chg_pct:
                chg = float(snap.usdpen_chg_pct)
                mkt_lines.append(
                    f"  • USD/PEN S/{float(snap.usdpen):.4f} ({chg:+.2f}% en sesión)"
                )
            if snap.dxy and snap.dxy_chg_pct:
                mkt_lines.append(
                    f"  • DXY {float(snap.dxy):.2f} ({float(snap.dxy_chg_pct):+.2f}%)"
                )
            if snap.vix:
                vix_str = f" ({float(snap.vix_chg_pct):+.2f}%)" if snap.vix_chg_pct else ""
                mkt_lines.append(f"  • VIX {float(snap.vix):.1f}{vix_str}")
            if snap.copper and snap.copper_chg_pct:
                mkt_lines.append(
                    f"  • Cobre ${float(snap.copper):.4f} ({float(snap.copper_chg_pct):+.2f}%)"
                )

        p3 = ""
        if mkt_lines:
            p3 = "Estado del mercado en este momento:\n" + "\n".join(mkt_lines)

        parts = [x for x in [p1, p2, p3] if x]
        return title, "\n\n".join(parts)

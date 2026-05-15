"""
Rutas del módulo FX Monitor — /monitor
"""
import json
import logging
import os
from datetime import datetime, timezone

import requests as http_requests
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.utils.decorators import require_role as role_required
from app.services.fx_monitor.monitor_service import FXMonitorService
from app.models.competitor_rate import Competitor

logger = logging.getLogger(__name__)

fx_monitor_bp = Blueprint("fx_monitor", __name__, url_prefix="/monitor")


_MON = ("Master", "Operador", "Trader")


@fx_monitor_bp.route("/")
@login_required
@role_required(*_MON)
def dashboard():
    """Panel principal de monitoreo de competencia."""
    try:
        data = FXMonitorService.get_dashboard_data()
    except Exception as e:
        logger.error(f'[FXMonitor] Error en get_dashboard_data: {e}', exc_info=True)
        data = FXMonitorService.empty_dashboard_data()
    return render_template("fx_monitor/dashboard.html", **data)


@fx_monitor_bp.route("/api/current")
@login_required
@role_required(*_MON)
def api_current():
    """JSON con precios actuales de todos los competidores."""
    data = FXMonitorService.get_dashboard_data()
    return jsonify({"success": True, "data": data})


@fx_monitor_bp.route("/api/history/<slug>")
@login_required
@role_required(*_MON)
def api_history(slug):
    """Histórico de precios de un competidor."""
    hours = request.args.get("hours", 24, type=int)
    rows  = FXMonitorService.get_history(slug, hours=hours)
    return jsonify({"success": True, "data": rows})


@fx_monitor_bp.route("/api/price-evolution")
@login_required
@role_required(*_MON)
def api_price_evolution():
    """Serie temporal: promedio competencia vs QoriCash."""
    hours = request.args.get("hours", 24, type=int)
    data  = FXMonitorService.get_price_evolution(hours=hours)
    return jsonify({"success": True, "data": data})


@fx_monitor_bp.route("/api/scrape-now", methods=["POST"])
@login_required
@role_required("Master")
def api_scrape_now():
    """Fuerza un ciclo de scraping inmediato (solo Master)."""
    result = FXMonitorService.run_scrape_cycle()
    return jsonify({"success": True, "result": result})


@fx_monitor_bp.route("/api/competitors", methods=["GET"])
@login_required
def api_competitors():
    """Lista de competidores registrados."""
    comps = Competitor.query.order_by(Competitor.name).all()
    return jsonify({"success": True, "data": [c.to_dict() for c in comps]})


@fx_monitor_bp.route("/api/competitors/<int:comp_id>/toggle", methods=["POST"])
@login_required
@role_required("Master")
def api_toggle_competitor(comp_id):
    """Activa/desactiva un competidor."""
    comp = db.get_or_404(Competitor, comp_id)
    comp.is_active = not comp.is_active
    db.session.commit()
    return jsonify({"success": True, "is_active": comp.is_active})


@fx_monitor_bp.route("/api/update-noticias", methods=["POST"])
@login_required
@role_required("Master")
def api_update_noticias():
    """Genera 15 noticias financieras con Gemini y las publica en Redis (solo Master)."""
    gemini_key    = os.environ.get("GEMINI_API_KEY")
    upstash_url   = os.environ.get("UPSTASH_REDIS_REST_URL")
    upstash_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

    if not gemini_key:
        return jsonify({"success": False, "error": "GEMINI_API_KEY no configurada"}), 500
    if not upstash_url or not upstash_token:
        return jsonify({"success": False, "error": "UPSTASH_REDIS no configurado"}), 500

    now      = datetime.now(timezone.utc)
    iso_date = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    weekdays = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    months   = ["enero","febrero","marzo","abril","mayo","junio",
                "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    fecha_texto = (
        f"{weekdays[now.weekday()]} {now.day} de {months[now.month-1]} de {now.year}"
    )

    prompt = f"""Genera exactamente 15 noticias financieras del día {fecha_texto} para QoriCash, casa de cambio online peruana especializada en PEN/USD.

Distribución EXACTA (respeta al pie de la letra):
- Las 2 primeras: destacada true — temas macro que impactan el tipo de cambio PEN/USD
- 4 de fuente "Gestión", categoría "Nacional" — BCRP, exportaciones, MEF, sector productivo
- 3 de fuente "Bloomberg", categoría "Internacional" — Fed, China, commodities, mercados globales
- 3 de fuente "TradingView", categoría "Nacional" o "Internacional" — datos de mercado: PEN/USD, DXY, petróleo, metales, BTC
- 3 de fuente "Infobae", categoría "Internacional" — Argentina, Colombia, Chile o Brasil

Reglas de contenido:
- Cifras realistas para 2026 (tipo de cambio S/ 3.60–3.80, Fed entre 4%–5%)
- "contenido": mínimo 3 párrafos con nombres, cifras concretas y contexto
- "analisis": siempre 2 párrafos — (1) impacto en PEN/USD y (2) qué hacer si tienes exposición cambiaria
- "fecha": exactamente "{iso_date}" para todas

IDs: gen_001 a gen_015
Imágenes: usa una de estas fotos de Unsplash (no repitas más de 3 veces la misma):
photo-1611974789855-9c2a0a7236a3, photo-1554224155-6726b3ff858f, photo-1621981386829-9b458080ee07,
photo-1578575437130-527eed3abbec, photo-1570129477492-45c003edd2be, photo-1547981609-4b6bfe67ca0b,
photo-1611273426858-450d8e3c9fce, photo-1580519542036-c47de6196ba5, photo-1518546305927-5a555bb7020d,
photo-1486325212027-8081e485255e, photo-1526628953301-3cd9ea6a7b0e, photo-1535320903710-d993d3d77d29,
photo-1559526324-593bc073d938, photo-1604594849809-dfedbc827105, photo-1521791136064-7986c2920216
Formato imagen: "https://images.unsplash.com/{{photo_id}}?w=1200&q=80"

Estructura de cada objeto:
{{
  "id": "gen_001",
  "titulo": "Título informativo con datos numéricos",
  "descripcion": "Resumen de 2-3 oraciones",
  "contenido": "3-4 párrafos con detalles",
  "analisis": "2 párrafos: impacto PEN/USD y recomendación",
  "categoria": "Nacional" o "Internacional",
  "fuente": "Gestión" | "Bloomberg" | "TradingView" | "Infobae",
  "fecha": "{iso_date}",
  "destacada": false,
  "imagen": "https://images.unsplash.com/photo-XXXXX?w=1200&q=80"
}}

Devuelve ÚNICAMENTE el array JSON. Sin texto antes ni después. Sin bloques de código markdown. Solo el JSON puro empezando con [ y terminando con ]."""

    try:
        gemini_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash-latest:generateContent?key={gemini_key}"
        )
        resp = http_requests.post(
            gemini_url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.8, "maxOutputTokens": 10000},
            },
            timeout=90,
        )
        resp.raise_for_status()

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0].strip()

        noticias = json.loads(raw)
        if not isinstance(noticias, list) or not noticias:
            raise ValueError("Gemini no devolvió un array válido")

        # Guardar en Upstash Redis
        redis_resp = http_requests.post(
            upstash_url,
            headers={
                "Authorization": f"Bearer {upstash_token}",
                "Content-Type": "application/json",
            },
            json=["SET", "qoricash:noticias", json.dumps(noticias)],
            timeout=15,
        )
        redis_resp.raise_for_status()

        logger.info(f"[update-noticias] {len(noticias)} noticias publicadas por {current_user.email}")
        return jsonify({"success": True, "count": len(noticias), "fecha": iso_date})

    except Exception as exc:
        logger.error(f"[update-noticias] Error: {exc}", exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500

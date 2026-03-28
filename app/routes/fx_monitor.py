"""
Rutas del módulo FX Monitor — /monitor
"""
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.utils.decorators import role_required
from app.services.fx_monitor.monitor_service import FXMonitorService
from app.models.competitor_rate import Competitor

fx_monitor_bp = Blueprint("fx_monitor", __name__, url_prefix="/monitor")


_MON = ("Master", "Operador")


@fx_monitor_bp.route("/")
@login_required
@role_required(*_MON)
def dashboard():
    """Panel principal de monitoreo de competencia."""
    data = FXMonitorService.get_dashboard_data()
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
    from app.extensions import db
    comp = Competitor.query.get_or_404(comp_id)
    comp.is_active = not comp.is_active
    db.session.commit()
    return jsonify({"success": True, "is_active": comp.is_active})

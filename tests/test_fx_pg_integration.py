#!/usr/bin/env python3
"""
tests/test_fx_pg_integration.py
Integración local con PostgreSQL real — TKambio y Okane.

Requisito: base de datos local qoricash_fx_test
  createdb qoricash_fx_test   (una sola vez)

Cobertura:
  PG1: TKambio — captura mock → _persist_one → CompetitorRateCurrent guardado
  PG2: TKambio — segundo ciclo igual → sin segunda fila de history (≤15 min sin cambio)
  PG3: Okane   — captura mock con fecha → source_updated_at guardado como None en DB
                 (columna es datetime; timezone-aware datetimes se almacenan como naive UTC)
  PG4: Okane   — fallo de scrape no sobreescribe último precio válido
  PG5: get_dashboard_data incluye TKambio y Okane con buy/sell correctos
  PG6: _is_valid_rate pasa para las tasas guardadas

Ejecutar:
    python3 -m pytest tests/test_fx_pg_integration.py -v
    # o como script directo:
    python3 tests/test_fx_pg_integration.py

Nota: usa la misma base de datos entre tests del módulo (scope='module').
Las tablas se crean al inicio y se eliminan al final para no dejar residuos.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# ── Configuración de entorno antes de cualquier import de la app ─────────────

_TEST_DB = os.environ.get(
    "FX_TEST_DB",
    "postgresql://gianpierre@localhost/qoricash_fx_test"
)

os.environ["DATABASE_URL"]             = _TEST_DB
os.environ.setdefault("SECRET_KEY",          "test-fx-pg-int")
os.environ.setdefault("WTF_CSRF_SECRET_KEY", "test-fx-pg-csrf")
os.environ.setdefault("ANTHROPIC_API_KEY",   "")
os.environ.setdefault("CLOUDINARY_URL",      "")
os.environ.setdefault("TWILIO_ACCOUNT_SID",  "")
os.environ.setdefault("TWILIO_AUTH_TOKEN",   "")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "")

# Agregar raíz del proyecto al path (necesario si se ejecuta como script)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Pre-mock cloudinary (evita crash eventlet/kqueue en macOS al importar la app)
for _m in ("cloudinary", "cloudinary.uploader", "cloudinary.api",
           "cloudinary.exceptions", "cloudinary.utils"):
    sys.modules.setdefault(_m, MagicMock())


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app_ctx():
    """
    Crea la app Flask con la BD de test, inicializa tablas, siembra
    solo los competidores necesarios (tkambio, okane) y hace teardown
    al finalizar el módulo.
    """
    from app import create_app
    from app.extensions import db as _db

    app = create_app("development")
    app.config["SQLALCHEMY_DATABASE_URI"] = _TEST_DB
    app.config["WTF_CSRF_ENABLED"]        = False
    app.config["TESTING"]                 = True
    app.config["RATELIMIT_ENABLED"]       = False

    # Matar greenlets del scheduler de fondo para que no interfieran
    import app as _app_module
    for _attr in ("_scheduler_greenlet", "_fx_scheduler_greenlet"):
        _gl = getattr(_app_module, _attr, None)
        if _gl is not None:
            try:
                _gl.kill()
            except Exception:
                pass

    with app.app_context():
        _db.create_all()

        # Limpiar estado previo de los competidores de prueba
        from app.models.competitor_rate import (
            Competitor, CompetitorRateCurrent, CompetitorRateHistory,
        )
        for slug in ("tkambio", "okane"):
            comp = Competitor.query.filter_by(slug=slug).first()
            if comp:
                CompetitorRateCurrent.query.filter_by(competitor_id=comp.id).delete()
                CompetitorRateHistory.query.filter_by(competitor_id=comp.id).delete()
                _db.session.delete(comp)
        _db.session.commit()

        # Insertar competidores de prueba
        _db.session.add(Competitor(
            slug="tkambio", name="TKambio", website="https://tkambio.com"
        ))
        _db.session.add(Competitor(
            slug="okane", name="Okane", website="https://okanecambiodigital.com"
        ))
        _db.session.commit()

        yield app, _db

        # Teardown: eliminar datos de prueba
        for slug in ("tkambio", "okane"):
            comp = Competitor.query.filter_by(slug=slug).first()
            if comp:
                CompetitorRateCurrent.query.filter_by(competitor_id=comp.id).delete()
                CompetitorRateHistory.query.filter_by(competitor_id=comp.id).delete()
                _db.session.delete(comp)
        _db.session.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_tk_response(buy=3.401, sell=3.431):
    """Respuesta sanitizada de TKambio (WordPress AJAX)."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "buying_rate": buy, "selling_rate": sell,
        "text_updated_at": "28 minutos", "outdates_in": 49440,
        "discounts": [], "ibk_buying_rate": 0, "ibk_selling_rate": 0,
        "campaigns": [],
    }
    return m


def _mock_ok_response(buy=3.370, sell=3.450, fecha="2026-09-24T18:04:35"):
    """Respuesta sanitizada de Okane (API JSON)."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    entry = {
        "idTipoCambio": "064427",
        "idMoneda": "USD",
        "valorCompra": buy,
        "valorVenta": sell,
        "tipoModalidad": "01",
    }
    if fecha is not None:
        entry["fecha"] = fecha
    m.json.return_value = [entry]
    return m


def _run_persist(app_ctx_tuple, slug, mock_resp, patch_target):
    """
    Ejecuta fetch() + _persist_one() dentro del contexto de la app.
    Retorna (rate_ok, CompetitorRateCurrent).
    """
    app, db = app_ctx_tuple
    from app.models.competitor_rate import Competitor, CompetitorRateCurrent
    from app.services.fx_monitor import monitor_service as ms

    with app.app_context():
        comp = Competitor.query.filter_by(slug=slug).first()
        assert comp is not None, f"Competidor {slug!r} no encontrado en BD de test"

        prev = CompetitorRateCurrent.query.filter_by(competitor_id=comp.id).first()

        with patch(patch_target) as mock_sess:
            if "tkambio" in patch_target:
                mock_sess.return_value.post.return_value = mock_resp
                from app.services.fx_monitor.scrapers.tkambio import TKambioScraper
                result = TKambioScraper().fetch()
            else:
                mock_sess.return_value.get.return_value = mock_resp
                from app.services.fx_monitor.scrapers.okane import OkaneScraper
                result = OkaneScraper().fetch()

        slug_map = {slug: prev} if prev else {}
        rate_ok, _ = ms._persist_one(result, comp, prev, slug_map, 0)
        db.session.commit()

        # Volver a leer de la BD para confirmar persistencia real
        saved = CompetitorRateCurrent.query.filter_by(competitor_id=comp.id).first()
        return rate_ok, saved


# ── PG1: TKambio — captura mock → _persist_one → fila guardada ───────────────

def test_PG1_tkambio_persists_rates_to_db(app_ctx):
    rate_ok, saved = _run_persist(
        app_ctx, "tkambio",
        _mock_tk_response(3.401, 3.431),
        "app.services.fx_monitor.scrapers.tkambio.requests.Session",
    )

    assert rate_ok is True, "_persist_one debe retornar rate_ok=True"
    assert saved is not None, "CompetitorRateCurrent debe existir en DB"
    assert float(saved.buy_rate)  == pytest.approx(3.401, abs=1e-4)
    assert float(saved.sell_rate) == pytest.approx(3.431, abs=1e-4)
    assert saved.scrape_ok is True
    assert saved.data_source == "direct"
    assert saved.last_valid_at  is not None
    assert saved.last_attempt_at is not None
    assert saved.last_error is None
    # TKambio no provee timestamp de proveedor
    assert saved.source_updated_at is None


# ── PG2: TKambio — segundo ciclo igual → sin nueva fila de history ───────────

def test_PG2_tkambio_no_dup_history_within_interval(app_ctx):
    """
    Con las mismas tasas dentro del intervalo de 15 min,
    _persist_one no debe insertar una segunda entrada de history.
    (La primera ya fue insertada por PG1.)
    """
    app, db = app_ctx
    from app.models.competitor_rate import Competitor, CompetitorRateHistory
    from app.services.fx_monitor import monitor_service as ms

    with app.app_context():
        comp = Competitor.query.filter_by(slug="tkambio").first()
        count_before = CompetitorRateHistory.query.filter_by(
            competitor_id=comp.id
        ).count()

    _run_persist(
        app_ctx, "tkambio",
        _mock_tk_response(3.401, 3.431),   # mismas tasas
        "app.services.fx_monitor.scrapers.tkambio.requests.Session",
    )

    with app_ctx[0].app_context():
        comp = Competitor.query.filter_by(slug="tkambio").first()
        count_after = CompetitorRateHistory.query.filter_by(
            competitor_id=comp.id
        ).count()

    assert count_after == count_before, (
        f"No debe insertar historia extra sin cambio de tasa ni intervalo de 15 min: "
        f"antes={count_before} después={count_after}"
    )


# ── PG3: Okane — source_updated_at guardado en DB ────────────────────────────

def test_PG3_okane_persists_source_updated_at(app_ctx):
    """
    Okane provee fecha ('2026-09-24T18:04:35') interpretada como Lima UTC-5.
    El scraper produce source_updated_at = datetime UTC aware.
    SQLAlchemy lo guarda como naive UTC; al leerlo no debe ser None.
    """
    rate_ok, saved = _run_persist(
        app_ctx, "okane",
        _mock_ok_response(3.370, 3.450, fecha="2026-09-24T18:04:35"),
        "app.services.fx_monitor.scrapers.okane.requests.Session",
    )

    assert rate_ok is True
    assert float(saved.buy_rate)  == pytest.approx(3.370, abs=1e-4)
    assert float(saved.sell_rate) == pytest.approx(3.450, abs=1e-4)
    assert saved.data_source == "direct"
    # source_updated_at debe haberse persistido (columna DateTime nullable)
    assert saved.source_updated_at is not None, (
        "source_updated_at debe guardarse en DB cuando la fecha es válida"
    )


# ── PG4: Okane — fallo no sobreescribe precio válido previo ──────────────────

def test_PG4_okane_failure_preserves_previous_rate(app_ctx):
    """
    Después de PG3 hay un precio válido. Un fallo de scrape no debe
    sobreescribir buy_rate/sell_rate/last_valid_at/data_source.
    """
    app, db = app_ctx
    from app.models.competitor_rate import Competitor, CompetitorRateCurrent
    from app.services.fx_monitor.scrapers.base import RateResult
    from app.utils.formatters import now_peru
    from app.services.fx_monitor import monitor_service as ms

    with app.app_context():
        comp = Competitor.query.filter_by(slug="okane").first()
        prev = CompetitorRateCurrent.query.filter_by(competitor_id=comp.id).first()
        assert prev is not None, "PG3 debe haberse ejecutado antes"
        buy_before     = float(prev.buy_rate)
        sell_before    = float(prev.sell_rate)
        valid_at_before = prev.last_valid_at
        source_before  = prev.data_source

        fail_result = RateResult(
            slug="okane", buy_rate=0.0, sell_rate=0.0,
            scraped_at=now_peru(), response_ms=250,
            success=False, error="Timeout simulado",
        )
        slug_map = {"okane": prev}
        rate_ok, _ = ms._persist_one(fail_result, comp, prev, slug_map, 0)
        db.session.commit()

        saved = CompetitorRateCurrent.query.filter_by(competitor_id=comp.id).first()

    assert rate_ok is False
    assert float(saved.buy_rate)   == pytest.approx(buy_before,  abs=1e-4), "buy_rate no debe cambiar"
    assert float(saved.sell_rate)  == pytest.approx(sell_before, abs=1e-4), "sell_rate no debe cambiar"
    assert saved.last_valid_at     == valid_at_before,  "last_valid_at no debe cambiar"
    assert saved.data_source       == source_before,    "data_source no debe cambiar"
    assert saved.scrape_ok         is False,            "scrape_ok debe ser False tras fallo"
    assert saved.last_error        == "Timeout simulado"


# ── PG5: get_dashboard_data incluye TKambio y Okane ──────────────────────────

def test_PG5_dashboard_includes_tkambio_and_okane(app_ctx):
    """
    get_dashboard_data() debe devolver entradas con buy/sell correctos para
    ambos competidores. Valida la capa de lectura sobre los datos persistidos.
    """
    app, db = app_ctx
    from app.services.fx_monitor.monitor_service import FXMonitorService

    with app.app_context():
        data = FXMonitorService.get_dashboard_data()

    competitors = data.get("competitors", [])
    slugs = {c["slug"]: c for c in competitors}

    assert "tkambio" in slugs, "TKambio debe aparecer en el dashboard"
    assert "okane"   in slugs, "Okane debe aparecer en el dashboard"

    tk = slugs["tkambio"]
    ok = slugs["okane"]

    assert float(tk["buy"])  == pytest.approx(3.401, abs=1e-4)
    assert float(tk["sell"]) == pytest.approx(3.431, abs=1e-4)
    assert float(ok["buy"])  == pytest.approx(3.370, abs=1e-4)
    assert float(ok["sell"]) == pytest.approx(3.450, abs=1e-4)


# ── PG6: _is_valid_rate pasa para las tasas guardadas ────────────────────────

def test_PG6_is_valid_rate_passes_for_stored_rates(app_ctx):
    """
    Las tasas guardadas en DB deben pasar la validación de _is_valid_rate().
    Confirma que el rango 2.5–6.0 y el orden buy < sell se mantienen.
    """
    app, db = app_ctx
    from app.models.competitor_rate import Competitor, CompetitorRateCurrent
    from app.services.fx_monitor.scrapers.manager import _is_valid_rate

    with app.app_context():
        for slug in ("tkambio", "okane"):
            comp  = Competitor.query.filter_by(slug=slug).first()
            # No filtrar por scrape_ok: okane tiene scrape_ok=False tras PG4,
            # pero sus tasas se preservan. Lo que importa es que las tasas
            # almacenadas sean numéricamente válidas.
            saved = CompetitorRateCurrent.query.filter_by(
                competitor_id=comp.id
            ).first()
            assert saved is not None, f"{slug}: debe haber un registro en DB"
            assert float(saved.buy_rate) > 0, f"{slug}: buy_rate debe ser > 0"
            assert _is_valid_rate(float(saved.buy_rate), float(saved.sell_rate)), (
                f"{slug}: buy={saved.buy_rate} sell={saved.sell_rate} "
                f"debe pasar _is_valid_rate()"
            )


# ── Ejecución directa ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

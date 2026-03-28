"""
Script standalone para inicializar las tablas del FX Monitor.
No depende del servidor Flask completo (evita conflictos con eventlet/socketio).

Uso:
    cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
    python3 scripts/init_fx_monitor.py
"""
import os
import sys
from datetime import datetime

# Asegurar que encontramos los módulos del proyecto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import sqlalchemy as sa
from sqlalchemy import text

# Leer DATABASE_URL del .env
db_url = os.environ.get("DATABASE_URL", "sqlite:///qoricash_local.db")
# SQLAlchemy 1.x/2.x compatibility: reemplazar postgres:// si aplica
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Para SQLite relativo, resolver respecto al directorio del proyecto
if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
    rel_path = db_url[len("sqlite:///"):]
    abs_path = os.path.join(os.path.dirname(__file__), "..", rel_path)
    db_url = f"sqlite:///{os.path.abspath(abs_path)}"

print(f"📁 Base de datos: {db_url}")

engine = sa.create_engine(db_url)

DDL = """
CREATE TABLE IF NOT EXISTS fx_competitors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    slug         VARCHAR(50)  UNIQUE NOT NULL,
    name         VARCHAR(100) NOT NULL,
    website      VARCHAR(255) NOT NULL,
    scraper_type VARCHAR(20)  DEFAULT 'requests',
    is_active    BOOLEAN      DEFAULT 1,
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fx_rate_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER NOT NULL REFERENCES fx_competitors(id),
    buy_rate      NUMERIC(8,4) NOT NULL,
    sell_rate     NUMERIC(8,4) NOT NULL,
    scraped_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    response_ms   INTEGER,
    error         VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_fx_history_competitor_time
    ON fx_rate_history (competitor_id, scraped_at);

CREATE TABLE IF NOT EXISTS fx_rate_current (
    competitor_id  INTEGER PRIMARY KEY REFERENCES fx_competitors(id),
    buy_rate       NUMERIC(8,4) NOT NULL,
    sell_rate      NUMERIC(8,4) NOT NULL,
    prev_buy_rate  NUMERIC(8,4),
    prev_sell_rate NUMERIC(8,4),
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scrape_ok      BOOLEAN  DEFAULT 1
);

CREATE TABLE IF NOT EXISTS fx_change_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER NOT NULL REFERENCES fx_competitors(id),
    field         VARCHAR(10) NOT NULL,
    old_buy       NUMERIC(8,4),
    new_buy       NUMERIC(8,4),
    old_sell      NUMERIC(8,4),
    new_sell      NUMERIC(8,4),
    buy_delta     NUMERIC(8,4),
    sell_delta    NUMERIC(8,4),
    buy_delta_pct NUMERIC(6,3),
    sell_delta_pct NUMERIC(6,3),
    detected_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    alert_sent    BOOLEAN  DEFAULT 0
);
"""

COMPETITORS = [
    ("kambista",     "Kambista",      "https://kambista.com"),
    ("instakash",    "Instakash",     "https://instakash.net"),
    ("cambioseguro", "Cambio Seguro", "https://www.cambioseguro.com"),
    ("tucambio",     "TuCambio",      "https://tucambio.com.pe"),
    ("tucambista",   "TuCambista",    "https://tucambista.pe"),
    ("rextie",       "Rextie",        "https://www.rextie.com"),
    ("dollarhouse",  "Dollar House",  "https://dollarhouse.pe"),
    ("moneyhouse",   "Moneyhouse",    "https://moneyhouse.pe"),
    ("jetperu",      "JetPerú",       "https://jetperu.com.pe"),
]

with engine.connect() as conn:
    # Crear tablas
    for stmt in DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(text(stmt))
    conn.commit()
    print("✅ Tablas creadas (o ya existían)")

    # Sembrar competidores (INSERT OR IGNORE)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    for slug, name, website in COMPETITORS:
        result = conn.execute(
            text("SELECT id FROM fx_competitors WHERE slug = :slug"),
            {"slug": slug}
        ).fetchone()
        if not result:
            conn.execute(
                text("""
                    INSERT INTO fx_competitors (slug, name, website, scraper_type, is_active, created_at)
                    VALUES (:slug, :name, :website, 'requests', 1, :now)
                """),
                {"slug": slug, "name": name, "website": website, "now": now}
            )
            inserted += 1
    conn.commit()
    print(f"✅ {inserted} nuevos competidores insertados (de {len(COMPETITORS)} total)")

    # Mostrar listado
    rows = conn.execute(
        text("SELECT slug, name, website, is_active FROM fx_competitors ORDER BY name")
    ).fetchall()
    print(f"\n{len(rows)} competidores registrados:")
    for r in rows:
        status = "activo  " if r[3] else "inactivo"
        print(f"  [{status}]  {r[1]:20s}  {r[2]}")

print("\n✅ Inicialización completada. Ya puedes correr: python3 run.py")

#!/usr/bin/env python3
"""
Validación rápida:
- Crear la app (verifica que el factory no lanza excepciones)
- Probar conexión a la BD (SELECT 1)
- Listar tablas y comprobar que existen las tablas esperadas y alembic_version
"""
import os
import sys
import traceback

# Asegura que la raíz del proyecto esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def masked(url):
    if not url:
        return None
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return f"{p.scheme}://{p.username or ''}:***@{p.hostname or ''}:{p.port or ''}{p.path or ''}"
    except Exception:
        return "<masked>"

def main():
    try:
        from app import create_app, db
    except Exception:
        print("ERROR importando app (puede que el paquete 'app' no esté en PYTHONPATH).")
        traceback.print_exc()
        return 10

    # 1) Crear la app (verifica que el factory no lanza excepciones)
    try:
        app = create_app()
        print("✅ create_app() OK — la app se creó sin lanzar excepciones")
    except Exception:
        print("❌ create_app() falló:")
        traceback.print_exc()
        return 20

    # 2) Comprobar la BD y listar tablas (no renderiza plantillas)
    with app.app_context():
        # Mostrar URL enmascarada
        url = app.config.get("SQLALCHEMY_DATABASE_URI") or os.getenv("SQLALCHEMY_DATABASE_URI") or app.config.get("DATABASE_URL")
        print("DB URL (enmascarada):", masked(url))

        # Intentar SELECT 1
        try:
            from sqlalchemy import text, inspect
            r = db.session.execute(text("SELECT 1")).scalar()
            print("✅ Conexión a la BD OK (SELECT 1 -> {})".format(r))
        except Exception:
            print("❌ Error al conectar/ejecutar SELECT 1:")
            traceback.print_exc()
            return 30

        # Listar tablas con el inspector
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print("Tablas encontradas en la BD ({}):".format(len(tables)))
            for t in sorted(tables):
                print(" -", t)
        except Exception:
            print("❌ Error al listar tablas (inspector):")
            traceback.print_exc()
            return 40

        # Comprobar tablas esperadas
        expected = ["users", "clients", "operations", "audit_logs"]
        missing = [t for t in expected if t not in tables]
        if missing:
            print("⚠️  Faltan tablas esperadas:", missing)
        else:
            print("✅ Todas las tablas esperadas existen:", expected)

        # Comprobar alembic_version (si existe, mostrar valor)
        if "alembic_version" in tables:
            try:
                ver = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchone()
                print("✅ alembic_version presente, versión:", ver[0] if ver else "<vacío>")
            except Exception:
                print("⚠️  alembic_version existe pero no se pudo leer:")
                traceback.print_exc()
        else:
            print("⚠️  No se encontró la tabla alembic_version (puede que no se haya hecho 'flask db upgrade')")

    print("\nResumen: revisa las líneas anteriores. Código de salida 0 = OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
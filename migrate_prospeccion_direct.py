"""
Migración directa — usa SQLAlchemy sin cargar el app Flask completo.
Uso: DATABASE_URL="postgresql://..." python3 migrate_prospeccion_direct.py
"""
import os, sys, openpyxl
from datetime import datetime
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: define DATABASE_URL como variable de entorno.")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

EXCEL_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "QoriCash_BASE_MAESTRA_2026.xlsx")

HOJAS_SKIP = {"📊 RESUMEN"}

HOJA_GRUPO = {
    "🎯 PIPELINE ACTIVO":      "PIPELINE ACTIVO",
    "✅ CLIENTES LFC":          "CLIENTES LFC",
    "🔥 PRIORITARIOS":          "PRIORITARIOS",
    "⭐ CALIFICADOS":           "CALIFICADOS",
    "📬 POR CONTACTAR":        "POR CONTACTAR",
    "📋 UNIVERSO CONTACTADOS":  "UNIVERSO CONTACTADOS",
    "🔄 SOFT BOUNCE":           "SOFT BOUNCE",
    "🚫 NO CONTACTAR":          "NO CONTACTAR",
}

COL_MAP = {
    1:"razon_social", 2:"ruc", 3:"tipo", 4:"rubro", 5:"departamento",
    6:"provincia", 7:"nombre_contacto", 8:"cargo", 9:"email", 10:"email_alt",
    11:"telefono", 12:"cliente_lfc", 13:"score", 14:"clasificacion",
    15:"canal", 16:"remitente", 17:"tipo_ultimo_envio",
    18:"fecha_primer_contacto", 19:"fecha_ultimo_contacto",
    20:"fecha_proximo_contacto", 21:"num_contactos", 22:"estado_email",
    23:"estado_comercial", 24:"nivel_interes", 25:"fuente", 26:"notas",
}

INT_FIELDS = {"score", "num_contactos"}


def run():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    with engine.connect() as conn:
        # Crear tablas si no existen
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prospectos (
                id SERIAL PRIMARY KEY,
                razon_social VARCHAR(300),
                ruc VARCHAR(20),
                tipo VARCHAR(50),
                rubro VARCHAR(150),
                departamento VARCHAR(100),
                provincia VARCHAR(100),
                nombre_contacto VARCHAR(200),
                cargo VARCHAR(150),
                email VARCHAR(200),
                email_alt VARCHAR(200),
                telefono VARCHAR(50),
                cliente_lfc VARCHAR(50),
                score INTEGER DEFAULT 0,
                clasificacion VARCHAR(80),
                canal VARCHAR(80),
                fuente VARCHAR(80),
                remitente VARCHAR(100),
                tipo_ultimo_envio VARCHAR(80),
                fecha_primer_contacto VARCHAR(30),
                fecha_ultimo_contacto VARCHAR(30),
                fecha_proximo_contacto VARCHAR(30),
                num_contactos INTEGER DEFAULT 0,
                estado_email VARCHAR(80),
                estado_comercial VARCHAR(80),
                nivel_interes VARCHAR(80),
                grupo VARCHAR(80),
                notas TEXT,
                creado_en TIMESTAMP DEFAULT NOW(),
                actualizado_en TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS asignaciones_prospecto (
                id SERIAL PRIMARY KEY,
                prospecto_id INTEGER REFERENCES prospectos(id),
                trader_id INTEGER REFERENCES users(id),
                activo BOOLEAN DEFAULT TRUE,
                asignado_por INTEGER REFERENCES users(id),
                asignado_en TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_asignacion UNIQUE (prospecto_id, trader_id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS actividades_prospecto (
                id SERIAL PRIMARY KEY,
                prospecto_id INTEGER REFERENCES prospectos(id),
                user_id INTEGER REFERENCES users(id),
                tipo VARCHAR(50),
                descripcion TEXT,
                resultado VARCHAR(200),
                nuevo_estado VARCHAR(80),
                creado_en TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()
        print("Tablas verificadas/creadas.")

        existing = conn.execute(text("SELECT COUNT(*) FROM prospectos")).scalar()
        if existing > 0:
            resp = input(f"Ya existen {existing} registros. Sobreescribir? (s/N): ")
            if resp.lower() != "s":
                print("Cancelado.")
                return
            conn.execute(text("TRUNCATE prospectos CASCADE"))
            conn.commit()
            print("Tabla limpiada.")

        print(f"Cargando {EXCEL_PATH} ...")
        wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)

        emails_vistos = set()
        total = duplicados = 0

        for hoja_name in wb.sheetnames:
            if hoja_name in HOJAS_SKIP:
                continue
            ws    = wb[hoja_name]
            grupo = HOJA_GRUPO.get(hoja_name, hoja_name)
            rows  = list(ws.iter_rows(min_row=2))
            print(f"  [{hoja_name}] — {len(rows)} filas...")

            lote = []
            for row in rows:
                if len(row) <= 9:
                    continue
                email_val = row[9].value
                if not email_val:
                    continue
                email = str(email_val).strip().lower()
                if not email or "@" not in email:
                    continue
                if email in emails_vistos:
                    duplicados += 1
                    continue
                emails_vistos.add(email)

                record = {"grupo": grupo}
                for col_idx, field in COL_MAP.items():
                    if col_idx < len(row):
                        v = row[col_idx].value
                        v = str(v).strip() if v is not None else None
                        if field in INT_FIELDS:
                            try:
                                record[field] = int(float(v)) if v else 0
                            except (ValueError, TypeError):
                                record[field] = 0
                        else:
                            record[field] = v or None
                lote.append(record)

                if len(lote) >= 500:
                    conn.execute(text("""
                        INSERT INTO prospectos
                        (razon_social,ruc,tipo,rubro,departamento,provincia,
                         nombre_contacto,cargo,email,email_alt,telefono,
                         cliente_lfc,score,clasificacion,canal,remitente,
                         tipo_ultimo_envio,fecha_primer_contacto,fecha_ultimo_contacto,
                         fecha_proximo_contacto,num_contactos,estado_email,
                         estado_comercial,nivel_interes,fuente,notas,grupo)
                        VALUES
                        (:razon_social,:ruc,:tipo,:rubro,:departamento,:provincia,
                         :nombre_contacto,:cargo,:email,:email_alt,:telefono,
                         :cliente_lfc,:score,:clasificacion,:canal,:remitente,
                         :tipo_ultimo_envio,:fecha_primer_contacto,:fecha_ultimo_contacto,
                         :fecha_proximo_contacto,:num_contactos,:estado_email,
                         :estado_comercial,:nivel_interes,:fuente,:notas,:grupo)
                    """), lote)
                    conn.commit()
                    total += len(lote)
                    lote = []

            if lote:
                conn.execute(text("""
                    INSERT INTO prospectos
                    (razon_social,ruc,tipo,rubro,departamento,provincia,
                     nombre_contacto,cargo,email,email_alt,telefono,
                     cliente_lfc,score,clasificacion,canal,remitente,
                     tipo_ultimo_envio,fecha_primer_contacto,fecha_ultimo_contacto,
                     fecha_proximo_contacto,num_contactos,estado_email,
                     estado_comercial,nivel_interes,fuente,notas,grupo)
                    VALUES
                    (:razon_social,:ruc,:tipo,:rubro,:departamento,:provincia,
                     :nombre_contacto,:cargo,:email,:email_alt,:telefono,
                     :cliente_lfc,:score,:clasificacion,:canal,:remitente,
                     :tipo_ultimo_envio,:fecha_primer_contacto,:fecha_ultimo_contacto,
                     :fecha_proximo_contacto,:num_contactos,:estado_email,
                     :estado_comercial,:nivel_interes,:fuente,:notas,:grupo)
                """), lote)
                conn.commit()
                total += len(lote)

        wb.close()
        final = conn.execute(text("SELECT COUNT(*) FROM prospectos")).scalar()
        print(f"\nMigracion completada:")
        print(f"  Importados : {total}")
        print(f"  Duplicados : {duplicados}")
        print(f"  Total en BD: {final}")


if __name__ == "__main__":
    run()

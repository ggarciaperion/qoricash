"""
Script de PRUEBA: eleva artificialmente el perfil de riesgo de un cliente.
Uso en la shell de Render:
    python set_test_risk.py

Para revertir después de la prueba:
    python set_test_risk.py --revert
"""

import os, sys
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: variable DATABASE_URL no encontrada")
    sys.exit(1)

# Render usa 'postgres://' pero SQLAlchemy necesita 'postgresql://'
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

engine = sa.create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

REVERT = '--revert' in sys.argv

try:
    # Buscar cliente de prueba (Gian Pierre - DNI 73085751)
    client_row = session.execute(
        sa.text("SELECT id, full_name, dni FROM clients WHERE dni = '73085751' LIMIT 1")
    ).fetchone()

    if not client_row:
        # Fallback: cualquier cliente activo
        client_row = session.execute(
            sa.text("SELECT id, full_name, dni FROM clients WHERE status = 'Activo' LIMIT 1")
        ).fetchone()

    if not client_row:
        print("ERROR: No se encontró ningún cliente activo.")
        sys.exit(1)

    client_id, full_name, dni = client_row
    print(f"Cliente seleccionado: {full_name} (DNI: {dni}, ID: {client_id})")

    # Verificar si tiene perfil de riesgo
    profile_row = session.execute(
        sa.text("SELECT id, risk_score, kyc_status FROM client_risk_profiles WHERE client_id = :cid"),
        {'cid': client_id}
    ).fetchone()

    if REVERT:
        # Revertir a valores normales
        if profile_row:
            session.execute(
                sa.text("""
                    UPDATE client_risk_profiles
                    SET risk_score = 10,
                        is_pep = FALSE,
                        has_legal_issues = FALSE,
                        in_restrictive_lists = FALSE,
                        high_volume_operations = FALSE,
                        dd_level = 'Básica',
                        kyc_status = 'Aprobado',
                        updated_at = :now
                    WHERE client_id = :cid
                """),
                {'cid': client_id, 'now': datetime.utcnow()}
            )
            session.commit()
            print(f"✅ Perfil REVERTIDO: {full_name} → risk_score=10 (Bajo), KYC=Aprobado")
        # Eliminar alertas de prueba
        deleted = session.execute(
            sa.text("DELETE FROM compliance_alerts WHERE client_id = :cid AND status = 'Pendiente'"),
            {'cid': client_id}
        ).rowcount
        session.commit()
        if deleted:
            print(f"✅ {deleted} alertas de prueba eliminadas")
        if not profile_row:
            print("No había perfil que revertir.")
    else:
        # Elevar riesgo a nivel ALTO (score 75, flags activados)
        if profile_row:
            session.execute(
                sa.text("""
                    UPDATE client_risk_profiles
                    SET risk_score = 75,
                        is_pep = TRUE,
                        has_legal_issues = TRUE,
                        in_restrictive_lists = FALSE,
                        high_volume_operations = TRUE,
                        dd_level = 'Reforzada',
                        kyc_status = 'En Proceso',
                        updated_at = :now
                    WHERE client_id = :cid
                """),
                {'cid': client_id, 'now': datetime.utcnow()}
            )
            print(f"✅ Perfil ELEVADO: {full_name} → risk_score=75 (Alto), PEP=Sí, KYC=En Proceso")
        else:
            # Crear perfil desde cero
            session.execute(
                sa.text("""
                    INSERT INTO client_risk_profiles
                        (client_id, risk_score, is_pep, has_legal_issues, in_restrictive_lists,
                         high_volume_operations, dd_level, kyc_status, created_at, updated_at)
                    VALUES
                        (:cid, 75, TRUE, TRUE, FALSE, TRUE, 'Reforzada', 'En Proceso', :now, :now)
                """),
                {'cid': client_id, 'now': datetime.utcnow()}
            )
            print(f"✅ Perfil CREADO: {full_name} → risk_score=75 (Alto), PEP=Sí, KYC=En Proceso")

        session.commit()

        # Insertar alertas de prueba si no existen ya
        existing_alerts = session.execute(
            sa.text("SELECT COUNT(*) FROM compliance_alerts WHERE client_id = :cid"),
            {'cid': client_id}
        ).scalar()

        if existing_alerts == 0:
            test_alerts = [
                ('AML',        'Crítica', 'Operación de alto monto detectada',
                 f'Cliente {full_name} realizó operación superior a $10,000 USD en una sola transacción.'),
                ('PEP',        'Alta',    'Cliente identificado como PEP',
                 f'{full_name} figura como Persona Expuesta Políticamente. Requiere debida diligencia reforzada.'),
                ('Behavioral', 'Media',   'Patrón de operaciones inusual',
                 f'Se detectaron múltiples operaciones en horario fuera de lo habitual para {full_name}.'),
            ]
            for atype, severity, title, desc in test_alerts:
                session.execute(
                    sa.text("""
                        INSERT INTO compliance_alerts
                            (alert_type, severity, title, description, client_id,
                             status, created_at, updated_at)
                        VALUES
                            (:atype, :severity, :title, :desc, :cid,
                             'Pendiente', :now, :now)
                    """),
                    {'atype': atype, 'severity': severity, 'title': title,
                     'desc': desc, 'cid': client_id, 'now': datetime.utcnow()}
                )
            session.commit()
            print(f"✅ 3 alertas de prueba creadas para {full_name}")
        else:
            print(f"ℹ️  Ya existen {existing_alerts} alertas para este cliente, no se duplicaron")

    print("\nPara revertir después de la prueba:")
    print("  python set_test_risk.py --revert")

except Exception as e:
    session.rollback()
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)
finally:
    session.close()

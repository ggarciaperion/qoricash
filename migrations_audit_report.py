"""
Migración: crear tabla audit_reports
Ejecutar en Render Shell: python3 migrations_audit_report.py

NOTA: usa SQLAlchemy directamente para evitar conflictos con eventlet en Python 3.14
"""
import os
import sys

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print('❌ DATABASE_URL no está configurada. Asegúrate de estar en Render Shell.')
    sys.exit(1)

from sqlalchemy import (
    create_engine, inspect, text,
    Column, Integer, String, Text, Date, DateTime, Numeric, Index, ForeignKey
)
from sqlalchemy.orm import declarative_base

engine = create_engine(DATABASE_URL)
Base = declarative_base()


class AuditReport(Base):
    __tablename__ = 'audit_reports'

    id                      = Column(Integer, primary_key=True)
    audit_date              = Column(Date, nullable=False, index=True)
    period_label            = Column(String(10), nullable=True)
    estado                  = Column(String(20), nullable=False, default='APROBADO')
    hallazgos_json          = Column(Text, default='[]')
    metricas_json           = Column(Text, default='{}')
    conciliacion_json       = Column(Text, default='{}')
    ops_sin_asiento         = Column(Integer, default=0)
    asientos_descuadrados   = Column(Integer, default=0)
    diferencias_banco       = Column(Integer, default=0)
    gastos_sin_comprobante  = Column(Integer, default=0)
    activos_sin_depreciar   = Column(Integer, default=0)
    total_hallazgos         = Column(Integer, default=0)
    hallazgos_criticos      = Column(Integer, default=0)
    ingresos_pen            = Column(Numeric(18, 2), default=0)
    gastos_pen              = Column(Numeric(18, 2), default=0)
    utilidad_neta_pen       = Column(Numeric(18, 2), default=0)
    ir_pago_cuenta_pen      = Column(Numeric(18, 2), default=0)
    trigger                 = Column(String(20), default='cron')
    execution_seconds       = Column(Numeric(8, 2), nullable=True)
    error_message           = Column(Text, nullable=True)
    executed_by             = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at              = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_audit_date_estado', 'audit_date', 'estado'),
    )


inspector = inspect(engine)
tables = inspector.get_table_names()

if 'audit_reports' in tables:
    print('✅ La tabla audit_reports ya existe — nada que hacer.')
else:
    print('🔧 Creando tabla audit_reports...')
    Base.metadata.create_all(engine, tables=[AuditReport.__table__])
    print('✅ Tabla audit_reports creada correctamente.')

# Verificar columnas
cols = [c['name'] for c in inspector.get_columns('audit_reports')] if 'audit_reports' in inspector.get_table_names() else []
# Re-inspect after potential creation
inspector2 = inspect(engine)
if 'audit_reports' in inspector2.get_table_names():
    cols = [c['name'] for c in inspector2.get_columns('audit_reports')]
    print(f'Columnas ({len(cols)}): {", ".join(cols)}')

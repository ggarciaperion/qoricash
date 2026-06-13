CREATE TABLE IF NOT EXISTS audit_reports (
    id SERIAL PRIMARY KEY,
    audit_date DATE NOT NULL,
    period_label VARCHAR(10),
    estado VARCHAR(20) NOT NULL DEFAULT 'APROBADO',
    hallazgos_json TEXT DEFAULT '[]',
    metricas_json TEXT DEFAULT '{}',
    conciliacion_json TEXT DEFAULT '{}',
    ops_sin_asiento INTEGER DEFAULT 0,
    asientos_descuadrados INTEGER DEFAULT 0,
    diferencias_banco INTEGER DEFAULT 0,
    gastos_sin_comprobante INTEGER DEFAULT 0,
    activos_sin_depreciar INTEGER DEFAULT 0,
    total_hallazgos INTEGER DEFAULT 0,
    hallazgos_criticos INTEGER DEFAULT 0,
    ingresos_pen NUMERIC(18,2) DEFAULT 0,
    gastos_pen NUMERIC(18,2) DEFAULT 0,
    utilidad_neta_pen NUMERIC(18,2) DEFAULT 0,
    ir_pago_cuenta_pen NUMERIC(18,2) DEFAULT 0,
    trigger VARCHAR(20) DEFAULT 'cron',
    execution_seconds NUMERIC(8,2),
    error_message TEXT,
    executed_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_date_estado ON audit_reports (audit_date, estado);
CREATE INDEX IF NOT EXISTS ix_audit_reports_audit_date ON audit_reports (audit_date);

SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'audit_reports' ORDER BY ordinal_position;

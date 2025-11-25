-- Script para crear la tabla trader_goals
-- Ejecutar este script en PostgreSQL para agregar la funcionalidad de metas mensuales

CREATE TABLE IF NOT EXISTS trader_goals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    year INTEGER NOT NULL,
    goal_amount_pen NUMERIC(15, 2) NOT NULL DEFAULT 0 CHECK (goal_amount_pen >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    CONSTRAINT uq_trader_month_year UNIQUE (user_id, month, year)
);

-- Crear índices para mejorar el rendimiento
CREATE INDEX IF NOT EXISTS idx_trader_goals_user_id ON trader_goals(user_id);
CREATE INDEX IF NOT EXISTS idx_trader_goals_month_year ON trader_goals(month, year);

-- Comentarios de la tabla
COMMENT ON TABLE trader_goals IS 'Metas mensuales comerciales asignadas a cada trader';
COMMENT ON COLUMN trader_goals.goal_amount_pen IS 'Meta comercial mensual en soles (S/)';
COMMENT ON COLUMN trader_goals.month IS 'Mes del año (1-12)';
COMMENT ON COLUMN trader_goals.year IS 'Año de la meta';

-- Mensaje de confirmación
SELECT 'Tabla trader_goals creada exitosamente!' AS resultado;

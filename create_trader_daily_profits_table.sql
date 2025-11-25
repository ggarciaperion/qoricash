-- Script para crear la tabla trader_daily_profits
-- Ejecutar este script en PostgreSQL para agregar la funcionalidad de utilidades diarias manuales

CREATE TABLE IF NOT EXISTS trader_daily_profits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profit_date DATE NOT NULL,
    profit_amount_pen NUMERIC(15, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    CONSTRAINT uq_trader_profit_date UNIQUE (user_id, profit_date)
);

-- Crear índices para mejorar el rendimiento
CREATE INDEX IF NOT EXISTS idx_trader_daily_profits_user_id ON trader_daily_profits(user_id);
CREATE INDEX IF NOT EXISTS idx_trader_daily_profits_date ON trader_daily_profits(profit_date);

-- Comentarios de la tabla
COMMENT ON TABLE trader_daily_profits IS 'Utilidades diarias de cada trader (ingreso manual)';
COMMENT ON COLUMN trader_daily_profits.profit_amount_pen IS 'Utilidad diaria en soles (S/) - ingreso manual';
COMMENT ON COLUMN trader_daily_profits.profit_date IS 'Fecha de la utilidad';

-- Mensaje de confirmación
SELECT 'Tabla trader_daily_profits creada exitosamente!' AS resultado;

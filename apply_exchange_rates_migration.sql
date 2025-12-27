-- Migración: Crear tabla exchange_rates
-- Fecha: 2025-12-27
-- Descripción: Tabla para almacenar tipos de cambio con historial de actualizaciones

-- Crear tabla exchange_rates
CREATE TABLE IF NOT EXISTS exchange_rates (
    id SERIAL PRIMARY KEY,
    buy_rate NUMERIC(10, 4) NOT NULL,
    sell_rate NUMERIC(10, 4) NOT NULL,
    updated_by INTEGER NOT NULL REFERENCES users(id),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Crear índice para mejorar performance en consultas de tipos actuales
CREATE INDEX IF NOT EXISTS idx_exchange_rates_updated_at ON exchange_rates(updated_at DESC);

-- Insertar valores iniciales (los que estaban hardcodeados)
INSERT INTO exchange_rates (buy_rate, sell_rate, updated_by, updated_at)
SELECT 3.7500, 3.7700, u.id, CURRENT_TIMESTAMP
FROM users u
WHERE u.role = 'Master'
LIMIT 1;

-- Verificar que se creó correctamente
SELECT * FROM exchange_rates ORDER BY updated_at DESC LIMIT 1;

-- Crear tabla exchange_rates en producción
CREATE TABLE exchange_rates (
    id SERIAL PRIMARY KEY,
    buy_rate NUMERIC(10, 4) NOT NULL,
    sell_rate NUMERIC(10, 4) NOT NULL,
    updated_by INTEGER NOT NULL REFERENCES users(id),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Crear índice
CREATE INDEX idx_exchange_rates_updated_at ON exchange_rates(updated_at DESC);

-- Insertar valores iniciales
INSERT INTO exchange_rates (buy_rate, sell_rate, updated_by, updated_at)
SELECT 3.7500, 3.7700, u.id, CURRENT_TIMESTAMP
FROM users u
WHERE u.role = 'Master'
LIMIT 1;

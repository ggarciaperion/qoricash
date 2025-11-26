-- Agregar índices para mejorar performance del dashboard
-- Reducción estimada de 70-80% en tiempo de query

-- Índices para tabla operations
CREATE INDEX IF NOT EXISTS idx_operations_created_at ON operations(created_at);
CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_user_id ON operations(user_id);
CREATE INDEX IF NOT EXISTS idx_operations_client_id ON operations(client_id);
CREATE INDEX IF NOT EXISTS idx_operations_operation_type ON operations(operation_type);

-- Índice compuesto para queries comunes del dashboard
CREATE INDEX IF NOT EXISTS idx_operations_created_status ON operations(created_at, status);
CREATE INDEX IF NOT EXISTS idx_operations_user_created ON operations(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_operations_user_status ON operations(user_id, status);

-- Índices para trader_daily_profits
CREATE INDEX IF NOT EXISTS idx_trader_daily_profits_user_date ON trader_daily_profits(user_id, profit_date);
CREATE INDEX IF NOT EXISTS idx_trader_daily_profits_date ON trader_daily_profits(profit_date);

-- Índices para trader_goals
CREATE INDEX IF NOT EXISTS idx_trader_goals_user_period ON trader_goals(user_id, year, month);
CREATE INDEX IF NOT EXISTS idx_trader_goals_period ON trader_goals(year, month);

-- Índices para clients
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);

-- Índices para users
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_role_status ON users(role, status);

-- Verificar índices creados
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE schemaname = 'public' 
  AND tablename IN ('operations', 'trader_daily_profits', 'trader_goals', 'clients', 'users')
ORDER BY tablename, indexname;

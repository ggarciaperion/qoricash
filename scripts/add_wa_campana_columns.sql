-- Migración: agrega columnas de campaña WA a wa_bot_sessions
-- Ejecutar en producción (PostgreSQL):
--   psql $DATABASE_URL -f scripts/add_wa_campana_columns.sql

ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS opt_out_wa          BOOLEAN DEFAULT FALSE;
ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS campana_secuencia    INTEGER DEFAULT 0;
ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS campana_ultimo_envio TIMESTAMP;
ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS campana_pausada      BOOLEAN DEFAULT FALSE;

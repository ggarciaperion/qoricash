-- ============================================================
-- RESET CONTABILIDAD + APERTURA 01/06/2026
-- Ejecutar: psql $DATABASE_URL -f reset_contabilidad_junio.sql
-- ============================================================
-- Saldos confirmados al 01/06/2026 (cierre del 31/05/2026):
--   BCP PEN  (1041): S/  4,021.38
--   BCP USD  (1044): USD 5,802.30  → TC 3.71 → S/ 21,526.53
--   IBK USD  (1047): USD 4,089.06  → TC 3.71 → S/ 15,170.41
--   IBK PEN  (1048): S/      7.51
--   BanBif: 0 en ambas monedas (omitido)
--
-- TOTAL APERTURA: S/ 40,725.83
-- ============================================================

BEGIN;

-- ── PASO 1: Limpiar referencias FK antes de borrar journal_entries ────
UPDATE expense_records SET journal_entry_id = NULL WHERE journal_entry_id IS NOT NULL;

-- ── PASO 2: Limpiar todo el Libro Diario ─────────────────────────────
DELETE FROM journal_entry_lines;
DELETE FROM journal_entries;

-- ── PASO 3: Resetear secuencia de numeración 2026 ────────────
UPDATE journal_sequences SET last_number = 0 WHERE year = 2026;
INSERT INTO journal_sequences (year, last_number)
  SELECT 2026, 0
  WHERE NOT EXISTS (SELECT 1 FROM journal_sequences WHERE year = 2026);

-- ── PASO 4: Asegurar período junio 2026 abierto ───────────────
INSERT INTO accounting_periods (year, month, status)
  SELECT 2026, 6, 'abierto'
  WHERE NOT EXISTS (
    SELECT 1 FROM accounting_periods WHERE year = 2026 AND month = 6
  );

-- Marcar períodos anteriores como cerrados (limpieza)
UPDATE accounting_periods SET status = 'cerrado'
WHERE year < 2026 OR (year = 2026 AND month < 6);

-- ── PASO 5: Crear asiento de apertura ─────────────────────────
WITH upd_seq AS (
  UPDATE journal_sequences
  SET last_number = last_number + 1
  WHERE year = 2026
  RETURNING last_number
),
new_entry AS (
  INSERT INTO journal_entries (
    entry_number, period_id, entry_date, description,
    entry_type, source_type, source_id,
    total_debe, total_haber, status, created_at
  )
  SELECT
    'AS-2026-' || LPAD(s.last_number::text, 4, '0'),
    p.id,
    '2026-06-01',
    'Asiento de Apertura — Saldos bancarios al 01/06/2026 (TC=3.71)',
    'apertura', 'manual', NULL,
    40725.83, 40725.83,
    'activo', NOW()
  FROM upd_seq s, accounting_periods p
  WHERE p.year = 2026 AND p.month = 6
  RETURNING id
)
INSERT INTO journal_entry_lines (
  journal_entry_id, account_code, description,
  debe, haber, currency, amount_usd, exchange_rate, line_order
)
SELECT
  e.id,
  v.account_code, v.description,
  v.debe, v.haber, v.currency,
  v.amount_usd, v.exchange_rate, v.line_order
FROM new_entry e,
(VALUES
  ('1041', 'BCP PEN — Saldo inicial 01/06/2026',    4021.38::numeric,       0::numeric, 'PEN', NULL::numeric,    NULL::numeric, 1),
  ('1044', 'BCP USD — Saldo inicial 01/06/2026',   21526.53::numeric,       0::numeric, 'USD', 5802.30::numeric,  3.71::numeric, 2),
  ('1047', 'IBK USD — Saldo inicial 01/06/2026',   15170.41::numeric,       0::numeric, 'USD', 4089.06::numeric,  3.71::numeric, 3),
  ('1048', 'IBK PEN — Saldo inicial 01/06/2026',       7.51::numeric,       0::numeric, 'PEN', NULL::numeric,    NULL::numeric, 4),
  ('3111', 'Capital — Patrimonio inicial 01/06/2026',  0::numeric,    40725.83::numeric, 'PEN', NULL::numeric,    NULL::numeric, 5)
) AS v(account_code, description, debe, haber, currency, amount_usd, exchange_rate, line_order);

-- ── VERIFICACIÓN FINAL ────────────────────────────────────────
SELECT
  'Apertura creada' AS estado,
  SUM(debe)              AS total_debe,
  SUM(haber)             AS total_haber,
  SUM(debe) - SUM(haber) AS diferencia
FROM journal_entry_lines
WHERE journal_entry_id = (SELECT MAX(id) FROM journal_entries);

SELECT entry_number, entry_date, entry_type, total_debe, total_haber
FROM journal_entries ORDER BY id DESC LIMIT 1;

COMMIT;

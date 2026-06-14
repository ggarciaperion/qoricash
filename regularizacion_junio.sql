-- ============================================================
-- ASIENTO DE REGULARIZACIÓN — 13/06/2026
-- Ajusta el Libro Diario para que coincida con Tesorería real.
--
-- Diferencias detectadas por el Agente Contable:
--   1041 BCP PEN  : Diario -10,998.67 ≠ Tesorería 68,724.20  Δ +79,722.87
--   1044 BCP USD  : Diario    3,133.93 ≠ Tesorería  7,025.84  Δ +3,891.91 USD → S/ 14,438.99 (TC 3.71)
--   1047 IBK USD  : Diario    1,889.06 ≠ Tesorería  7,941.92  Δ +6,052.86 USD → S/ 22,456.11 (TC 3.71)
--   1048 IBK PEN  : Diario   34,761.57 ≠ Tesorería 21,141.52  Δ -13,620.05
--
-- DEBE total : S/ 116,617.97
-- HABER total: S/ 116,617.97  (13,620.05 + 102,997.92 a cuenta 5011)
-- ============================================================

BEGIN;

WITH upd_seq AS (
  UPDATE journal_sequences SET last_number = last_number + 1
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
    '2026-06-13',
    'Regularización: ajuste Tesorería vs Libro Diario al 13/06/2026',
    'manual', 'manual', NULL,
    116617.97, 116617.97,
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
  ('1041', 'BCP PEN — Regularización banco vs diario',   79722.87::numeric,       0::numeric, 'PEN', NULL::numeric,    NULL::numeric, 1),
  ('1044', 'BCP USD — Regularización banco vs diario',   14438.99::numeric,       0::numeric, 'USD', 3891.91::numeric,  3.71::numeric, 2),
  ('1047', 'IBK USD — Regularización banco vs diario',   22456.11::numeric,       0::numeric, 'USD', 6052.86::numeric,  3.71::numeric, 3),
  ('1048', 'IBK PEN — Regularización banco vs diario',       0::numeric,   13620.05::numeric, 'PEN', NULL::numeric,    NULL::numeric, 4),
  ('5011', 'Resultado acumulado — diferencia contable',      0::numeric,  102997.92::numeric, 'PEN', NULL::numeric,    NULL::numeric, 5)
) AS v(account_code, description, debe, haber, currency, amount_usd, exchange_rate, line_order);

-- Verificar cuadre del asiento
SELECT 'Regularización' AS estado, SUM(debe) AS debe, SUM(haber) AS haber, SUM(debe)-SUM(haber) AS diferencia
FROM journal_entry_lines
WHERE journal_entry_id = (SELECT MAX(id) FROM journal_entries);

-- Verificar saldos resultantes por cuenta (post-regularización)
SELECT jel.account_code,
       SUM(jel.debe) - SUM(jel.haber) AS saldo_pen
FROM journal_entry_lines jel
JOIN journal_entries je ON je.id = jel.journal_entry_id
WHERE je.status = 'activo'
  AND jel.account_code IN ('1041','1044','1047','1048')
GROUP BY jel.account_code
ORDER BY jel.account_code;

COMMIT;

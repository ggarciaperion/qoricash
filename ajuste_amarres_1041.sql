-- ============================================================
-- AJUSTE: Reclasificar cuenta 1041 de asientos calce_match
-- Los amarres usaban 1041 como contrapartida, pero el cash
-- ya está capturado en los asientos de operaciones.
-- Solución: mover esa contrapartida a 3599 (Otras reservas).
--
-- Efecto neto en 1041: -3,235.70 (queda igual a Tesorería)
-- ============================================================

BEGIN;

-- 1. Reclasificar líneas DEBE 1041 en asientos calce_match → 3599
UPDATE journal_entry_lines jel
SET account_code = '3599',
    description  = REPLACE(description, 'BCP PEN', 'Reserva diferencial FX')
WHERE jel.debe > 0
  AND jel.account_code = '1041'
  AND jel.journal_entry_id IN (
      SELECT id FROM journal_entries
      WHERE entry_type IN ('calce_match', 'calce_netting')
        AND status = 'activo'
  );

-- 2. Reclasificar líneas HABER 1041 en asientos calce_match → 3599
UPDATE journal_entry_lines jel
SET account_code = '3599',
    description  = REPLACE(description, 'BCP PEN', 'Reserva diferencial FX')
WHERE jel.haber > 0
  AND jel.account_code = '1041'
  AND jel.journal_entry_id IN (
      SELECT id FROM journal_entries
      WHERE entry_type IN ('calce_match', 'calce_netting')
        AND status = 'activo'
  );

-- Verificar saldo 1041 post-ajuste (debe coincidir con Tesorería 68,724.20)
SELECT jel.account_code,
       SUM(jel.debe) - SUM(jel.haber) AS saldo_pen
FROM journal_entry_lines jel
JOIN journal_entries je ON je.id = jel.journal_entry_id
WHERE je.status = 'activo'
  AND jel.account_code IN ('1041', '3599', '7711', '6762')
GROUP BY jel.account_code
ORDER BY jel.account_code;

COMMIT;

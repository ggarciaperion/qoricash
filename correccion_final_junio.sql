-- ============================================================
-- CORRECCIÓN FINAL: Ajustar Libro Diario a saldos reales
-- Control de Apertura y Cierre — 13/06/2026
--
-- Saldos reales (Tesorería):
--   BCP PEN  (1041): S/  10,606.94
--   BCP USD  (1044): $    3,841.70
--   IBK USD  (1047): $      378.91
--   IBK PEN  (1048): S/   9,020.59
--   BanBif         : S/ 0  /  $ 0
--
-- Pasos:
--   1. Eliminar regularización incorrecta del 13/06/2026
--   2. Mostrar saldos actuales post-eliminación
--   3. Crear asiento de corrección con valores dinámicos
--   4. Actualizar tabla BankBalance
--   5. Verificación final
-- ============================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- PASO 1: Eliminar regularización incorrecta
-- ─────────────────────────────────────────────────────────────────────────────

DELETE FROM journal_entry_lines
WHERE journal_entry_id IN (
    SELECT id FROM journal_entries
    WHERE entry_type   = 'manual'
      AND source_type  = 'manual'
      AND entry_date   = '2026-06-13'
      AND description ILIKE '%regularización%'
      AND status       = 'activo'
);

WITH deleted AS (
    DELETE FROM journal_entries
    WHERE entry_type   = 'manual'
      AND source_type  = 'manual'
      AND entry_date   = '2026-06-13'
      AND description ILIKE '%regularización%'
      AND status       = 'activo'
    RETURNING entry_number, description
)
SELECT 'ELIMINADO: ' || entry_number || ' — ' || description AS paso1_log
FROM deleted;

-- ─────────────────────────────────────────────────────────────────────────────
-- PASO 2: Saldos actuales post-eliminación
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    jel.account_code,
    SUM(jel.debe) - SUM(jel.haber) AS saldo_pen,
    SUM(CASE WHEN jel.debe  > 0 THEN COALESCE(jel.amount_usd, 0) ELSE 0 END)
    - SUM(CASE WHEN jel.haber > 0 THEN COALESCE(jel.amount_usd, 0) ELSE 0 END) AS saldo_usd
FROM journal_entry_lines jel
JOIN journal_entries je ON je.id = jel.journal_entry_id
WHERE je.status = 'activo'
  AND jel.account_code IN ('1041','1044','1047','1048')
GROUP BY jel.account_code
ORDER BY jel.account_code;

-- ─────────────────────────────────────────────────────────────────────────────
-- PASO 3: Asiento de corrección dinámico
-- TC referencial: 3.71 (mismo que apertura)
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
    v_entry_id    INTEGER;
    v_seq         INTEGER;
    v_period_id   INTEGER;
    v_entry_num   TEXT;
    v_lo          INTEGER := 1;

    -- Saldos actuales del journal
    v_s1041_pen   NUMERIC;
    v_s1044_usd   NUMERIC;
    v_s1047_usd   NUMERIC;
    v_s1048_pen   NUMERIC;

    -- Targets reales (Tesorería 13/06/2026)
    v_t1041       NUMERIC := 10606.94;
    v_t1044_usd   NUMERIC := 3841.70;
    v_t1047_usd   NUMERIC := 378.91;
    v_t1048       NUMERIC := 9020.59;
    v_tc          NUMERIC := 3.71;

    -- Deltas
    v_d1041       NUMERIC;
    v_d1044_usd   NUMERIC;
    v_d1044_pen   NUMERIC;
    v_d1047_usd   NUMERIC;
    v_d1047_pen   NUMERIC;
    v_d1048       NUMERIC;
    v_net_pen     NUMERIC;

    v_total_debe  NUMERIC := 0;
    v_total_haber NUMERIC := 0;
BEGIN
    -- ── Saldo PEN para 1041 ──────────────────────────────────────────────────
    SELECT COALESCE(SUM(jel.debe) - SUM(jel.haber), 0) INTO v_s1041_pen
    FROM journal_entry_lines jel
    JOIN journal_entries je ON je.id = jel.journal_entry_id
    WHERE je.status = 'activo' AND jel.account_code = '1041';

    -- ── Saldo USD para 1044 (usa amount_usd, igual que la conciliación) ──────
    SELECT COALESCE(
        SUM(CASE WHEN jel.debe  > 0 THEN COALESCE(jel.amount_usd, 0) ELSE 0 END) -
        SUM(CASE WHEN jel.haber > 0 THEN COALESCE(jel.amount_usd, 0) ELSE 0 END),
        0
    ) INTO v_s1044_usd
    FROM journal_entry_lines jel
    JOIN journal_entries je ON je.id = jel.journal_entry_id
    WHERE je.status = 'activo' AND jel.account_code = '1044';

    -- ── Saldo USD para 1047 ──────────────────────────────────────────────────
    SELECT COALESCE(
        SUM(CASE WHEN jel.debe  > 0 THEN COALESCE(jel.amount_usd, 0) ELSE 0 END) -
        SUM(CASE WHEN jel.haber > 0 THEN COALESCE(jel.amount_usd, 0) ELSE 0 END),
        0
    ) INTO v_s1047_usd
    FROM journal_entry_lines jel
    JOIN journal_entries je ON je.id = jel.journal_entry_id
    WHERE je.status = 'activo' AND jel.account_code = '1047';

    -- ── Saldo PEN para 1048 ──────────────────────────────────────────────────
    SELECT COALESCE(SUM(jel.debe) - SUM(jel.haber), 0) INTO v_s1048_pen
    FROM journal_entry_lines jel
    JOIN journal_entries je ON je.id = jel.journal_entry_id
    WHERE je.status = 'activo' AND jel.account_code = '1048';

    -- ── Calcular deltas ──────────────────────────────────────────────────────
    v_d1041     := v_t1041    - v_s1041_pen;
    v_d1044_usd := v_t1044_usd - v_s1044_usd;
    v_d1044_pen := ROUND(v_d1044_usd * v_tc, 2);
    v_d1047_usd := v_t1047_usd - v_s1047_usd;
    v_d1047_pen := ROUND(v_d1047_usd * v_tc, 2);
    v_d1048     := v_t1048    - v_s1048_pen;

    -- Neto PEN total (contrapartida en 5011)
    v_net_pen := v_d1041 + v_d1044_pen + v_d1047_pen + v_d1048;

    RAISE NOTICE '=== SALDOS ACTUALES (post-eliminación) ===';
    RAISE NOTICE '1041 PEN actual=% | target=% | delta=%', v_s1041_pen, v_t1041, v_d1041;
    RAISE NOTICE '1044 USD actual=% | target=% | delta=% USD (% PEN)', v_s1044_usd, v_t1044_usd, v_d1044_usd, v_d1044_pen;
    RAISE NOTICE '1047 USD actual=% | target=% | delta=% USD (% PEN)', v_s1047_usd, v_t1047_usd, v_d1047_usd, v_d1047_pen;
    RAISE NOTICE '1048 PEN actual=% | target=% | delta=%', v_s1048_pen, v_t1048, v_d1048;
    RAISE NOTICE 'Neto PEN (contrapartida 5011)=%', v_net_pen;

    -- ── Totales para header del asiento ────────────────────────────────────
    IF v_d1041     > 0 THEN v_total_debe  := v_total_debe  + v_d1041;
    ELSIF v_d1041  < 0 THEN v_total_haber := v_total_haber + ABS(v_d1041); END IF;

    IF v_d1044_pen > 0 THEN v_total_debe  := v_total_debe  + v_d1044_pen;
    ELSIF v_d1044_pen < 0 THEN v_total_haber := v_total_haber + ABS(v_d1044_pen); END IF;

    IF v_d1047_pen > 0 THEN v_total_debe  := v_total_debe  + v_d1047_pen;
    ELSIF v_d1047_pen < 0 THEN v_total_haber := v_total_haber + ABS(v_d1047_pen); END IF;

    IF v_d1048     > 0 THEN v_total_debe  := v_total_debe  + v_d1048;
    ELSIF v_d1048  < 0 THEN v_total_haber := v_total_haber + ABS(v_d1048); END IF;

    IF v_net_pen   > 0 THEN v_total_haber := v_total_haber + v_net_pen;
    ELSIF v_net_pen < 0 THEN v_total_debe := v_total_debe  + ABS(v_net_pen); END IF;

    RAISE NOTICE 'Header asiento: DEBE=% HABER=%', v_total_debe, v_total_haber;

    -- ── Obtener período junio 2026 ──────────────────────────────────────────
    SELECT id INTO v_period_id FROM accounting_periods WHERE year = 2026 AND month = 6;

    -- ── Incrementar secuencia ───────────────────────────────────────────────
    UPDATE journal_sequences
    SET last_number = last_number + 1
    WHERE year = 2026
    RETURNING last_number INTO v_seq;

    v_entry_num := 'AS-2026-' || LPAD(v_seq::text, 4, '0');

    -- ── Crear header del asiento ────────────────────────────────────────────
    INSERT INTO journal_entries (
        entry_number, period_id, entry_date, description,
        entry_type, source_type, source_id,
        total_debe, total_haber, status, created_at
    ) VALUES (
        v_entry_num, v_period_id, '2026-06-13',
        'Corrección contable: saldos reales Tesorería vs Libro Diario al 13/06/2026',
        'manual', 'manual', NULL,
        v_total_debe, v_total_haber,
        'activo', NOW()
    ) RETURNING id INTO v_entry_id;

    -- ── Línea 1041 (BCP PEN) ────────────────────────────────────────────────
    IF ABS(v_d1041) >= 0.01 THEN
        INSERT INTO journal_entry_lines (
            journal_entry_id, account_code, description,
            debe, haber, currency, amount_usd, exchange_rate, line_order
        ) VALUES (
            v_entry_id, '1041',
            'BCP PEN — Corrección saldo real',
            GREATEST(v_d1041,  0),
            GREATEST(-v_d1041, 0),
            'PEN', NULL, NULL, v_lo
        );
        v_lo := v_lo + 1;
    END IF;

    -- ── Línea 1044 (BCP USD) ────────────────────────────────────────────────
    IF ABS(v_d1044_usd) >= 0.01 THEN
        INSERT INTO journal_entry_lines (
            journal_entry_id, account_code, description,
            debe, haber, currency, amount_usd, exchange_rate, line_order
        ) VALUES (
            v_entry_id, '1044',
            'BCP USD — Corrección saldo real',
            GREATEST(v_d1044_pen,  0),
            GREATEST(-v_d1044_pen, 0),
            'USD',
            ABS(v_d1044_usd),   -- siempre positivo; debe/haber indica la dirección
            v_tc, v_lo
        );
        v_lo := v_lo + 1;
    END IF;

    -- ── Línea 1047 (IBK USD) ────────────────────────────────────────────────
    IF ABS(v_d1047_usd) >= 0.01 THEN
        INSERT INTO journal_entry_lines (
            journal_entry_id, account_code, description,
            debe, haber, currency, amount_usd, exchange_rate, line_order
        ) VALUES (
            v_entry_id, '1047',
            'IBK USD — Corrección saldo real',
            GREATEST(v_d1047_pen,  0),
            GREATEST(-v_d1047_pen, 0),
            'USD',
            ABS(v_d1047_usd),
            v_tc, v_lo
        );
        v_lo := v_lo + 1;
    END IF;

    -- ── Línea 1048 (IBK PEN) ────────────────────────────────────────────────
    IF ABS(v_d1048) >= 0.01 THEN
        INSERT INTO journal_entry_lines (
            journal_entry_id, account_code, description,
            debe, haber, currency, amount_usd, exchange_rate, line_order
        ) VALUES (
            v_entry_id, '1048',
            'IBK PEN — Corrección saldo real',
            GREATEST(v_d1048,  0),
            GREATEST(-v_d1048, 0),
            'PEN', NULL, NULL, v_lo
        );
        v_lo := v_lo + 1;
    END IF;

    -- ── Contrapartida 5011 (Resultado acumulado) ────────────────────────────
    IF ABS(v_net_pen) >= 0.01 THEN
        INSERT INTO journal_entry_lines (
            journal_entry_id, account_code, description,
            debe, haber, currency, amount_usd, exchange_rate, line_order
        ) VALUES (
            v_entry_id, '5011',
            'Resultado acumulado — diferencia contable',
            GREATEST(-v_net_pen, 0),
            GREATEST(v_net_pen,  0),
            'PEN', NULL, NULL, v_lo
        );
    END IF;

    RAISE NOTICE '✓ Asiento % creado (ID=%). DEBE=% HABER=%',
        v_entry_num, v_entry_id, v_total_debe, v_total_haber;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- PASO 4: Actualizar BankBalance con saldos reales
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE bank_balances
SET balance_pen = 10606.94, updated_at = NOW()
WHERE bank_name ILIKE '%BCP%' AND bank_name ILIKE '%PEN%';

UPDATE bank_balances
SET balance_usd = 3841.70, updated_at = NOW()
WHERE bank_name ILIKE '%BCP%' AND bank_name ILIKE '%USD%';

UPDATE bank_balances
SET balance_usd = 378.91, updated_at = NOW()
WHERE bank_name ILIKE '%INTERBANK%' AND bank_name ILIKE '%USD%';

UPDATE bank_balances
SET balance_pen = 9020.59, updated_at = NOW()
WHERE bank_name ILIKE '%INTERBANK%' AND bank_name ILIKE '%PEN%';

-- BanBif en cero (si existe)
UPDATE bank_balances
SET balance_usd = 0, balance_pen = 0, updated_at = NOW()
WHERE bank_name ILIKE '%BANBIF%';

SELECT 'BankBalance actualizado' AS paso4_log,
       bank_name, balance_usd, balance_pen
FROM bank_balances
WHERE bank_name ILIKE '%BCP%'
   OR bank_name ILIKE '%INTERBANK%'
   OR bank_name ILIKE '%BANBIF%'
ORDER BY bank_name;

-- ─────────────────────────────────────────────────────────────────────────────
-- PASO 5: Verificación final — debe coincidir con Tesorería real
--   1041 PEN  → S/ 10,606.94
--   1044 USD  → $  3,841.70
--   1047 USD  → $    378.91
--   1048 PEN  → S/  9,020.59
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    jel.account_code,
    SUM(jel.debe) - SUM(jel.haber) AS saldo_pen,
    SUM(CASE WHEN jel.debe  > 0 THEN COALESCE(jel.amount_usd, 0) ELSE 0 END)
    - SUM(CASE WHEN jel.haber > 0 THEN COALESCE(jel.amount_usd, 0) ELSE 0 END) AS saldo_usd
FROM journal_entry_lines jel
JOIN journal_entries je ON je.id = jel.journal_entry_id
WHERE je.status = 'activo'
  AND jel.account_code IN ('1041','1044','1047','1048')
GROUP BY jel.account_code
ORDER BY jel.account_code;

COMMIT;

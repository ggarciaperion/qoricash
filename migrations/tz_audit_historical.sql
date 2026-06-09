-- ============================================================
-- AUDITORÍA HISTÓRICA DE TIMEZONE — QoriCash
-- Generado: 2026-06-09
--
-- CONTEXTO:
--   El backend almacena todos los timestamps como datetimes
--   naive en hora de Lima (UTC-5) via now_peru(). El servidor
--   Render corre en UTC. Antes del fix de 2026-06-09, los
--   endpoints legal.py, accounting.py, prospeccion.py,
--   comercial.py y contabilidad.py usaban datetime.now() (UTC)
--   en lugar de now_peru() — produciendo timestamps 5 horas
--   adelantados (UTC en vez de Lima).
--
-- RIESGO:
--   Solo afecta campos de DISPLAY (fechas en emails, nombres
--   de archivos Excel, fechas en documentos legales). No afecta
--   operaciones financieras, montos ni estados.
--
-- DETECCIÓN:
--   Un registro afectado tendría created_at/updated_at entre
--   las 00:00 y 04:59 hora Lima que en realidad deberían ser
--   entre 05:00 y 09:59 (i.e., horas UTC tardías = madrugada
--   Lima — escenario improbable en operación normal 9am-6pm).
--
-- ACCIÓN: No se requiere corrección retroactiva de DB porque:
--   1. Las columnas afectadas son strings de display (emails),
--      no timestamps de DB.
--   2. Los timestamps de DB (created_at, updated_at) siempre
--      usaron now_peru() correctamente.
--   3. El único riesgo retroactivo es: fechas en emails de
--      campaña y nombres de archivos Excel exportados — datos
--      efímeros sin impacto en integridad financiera.
-- ============================================================

-- VERIFICACIÓN: Detectar operaciones con timestamps fuera del
-- horario comercial de Lima (00:00-04:59 Lima = posible UTC leak)
SELECT
    id,
    operation_id,
    status,
    created_at,
    EXTRACT(HOUR FROM created_at) AS hora_lima,
    'Posible UTC leak (hora < 5am Lima)' AS nota
FROM operations
WHERE EXTRACT(HOUR FROM created_at) BETWEEN 0 AND 4
ORDER BY created_at DESC
LIMIT 50;

-- VERIFICACIÓN: Audit logs con hora de madrugada Lima
SELECT
    id,
    action,
    created_at,
    EXTRACT(HOUR FROM created_at) AS hora_lima
FROM audit_log
WHERE EXTRACT(HOUR FROM created_at) BETWEEN 0 AND 4
ORDER BY created_at DESC
LIMIT 20;

-- VERIFICACIÓN: Bank movements con hora de madrugada Lima
SELECT
    id,
    reference_code,
    movement_date,
    EXTRACT(HOUR FROM movement_date) AS hora_lima
FROM bank_movements
WHERE EXTRACT(HOUR FROM movement_date) BETWEEN 0 AND 4
ORDER BY movement_date DESC
LIMIT 20;

-- NOTA: Si los resultados anteriores muestran registros a las
-- 00:00-04:59, revisar individualmente si corresponden a
-- operaciones legítimas nocturnas o a desfase UTC. En la
-- práctica QoriCash opera 9am-8pm Lima, por lo que registros
-- a esas horas son sospechosos.

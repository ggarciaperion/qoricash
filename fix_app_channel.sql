-- Script SQL para actualizar operaciones de origen 'plataforma' a 'app'
-- Ejecutar este script en la base de datos PostgreSQL de producción

-- 1. Primero actualizar los constraints (si aún no se hizo)
ALTER TABLE operations DROP CONSTRAINT IF EXISTS check_operation_origen;
ALTER TABLE operations ADD CONSTRAINT check_operation_origen CHECK (origen IN ('sistema', 'plataforma', 'app'));

ALTER TABLE operations DROP CONSTRAINT IF EXISTS check_operation_status;
ALTER TABLE operations ADD CONSTRAINT check_operation_status CHECK (status IN ('Pendiente', 'En proceso', 'Completada', 'Cancelado', 'Expirada'));

-- 2. Ver cuántas operaciones tienen origen 'plataforma'
SELECT COUNT(*) as total_plataforma FROM operations WHERE origen = 'plataforma';

-- 3. Mostrar las operaciones que se actualizarán
SELECT operation_id, origen, created_at, notes
FROM operations
WHERE origen = 'plataforma'
ORDER BY created_at DESC
LIMIT 10;

-- 4. Actualizar TODAS las operaciones de 'plataforma' a 'app'
UPDATE operations
SET origen = 'app'
WHERE origen = 'plataforma';

-- 5. Verificar que se actualizaron
SELECT operation_id, origen, created_at
FROM operations
WHERE origen = 'app'
ORDER BY created_at DESC
LIMIT 10;

-- 6. Verificar distribución de orígenes
SELECT origen, COUNT(*) as cantidad
FROM operations
GROUP BY origen
ORDER BY cantidad DESC;

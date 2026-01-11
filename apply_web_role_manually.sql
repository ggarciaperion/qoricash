-- ============================================================
-- APLICAR ROL WEB Y CANAL WEB MANUALMENTE
-- Ejecutar este script si la migración automática no funcionó
-- ============================================================

BEGIN;

-- 1. Eliminar constraint antiguo de roles
ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role;

-- 2. Crear nuevo constraint con rol 'Web'
ALTER TABLE users ADD CONSTRAINT check_user_role
CHECK (role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma', 'App', 'Web'));

-- 3. Eliminar constraint antiguo de origen
ALTER TABLE operations DROP CONSTRAINT IF EXISTS check_operation_origen;

-- 4. Crear nuevo constraint con canal 'web'
ALTER TABLE operations ADD CONSTRAINT check_operation_origen
CHECK (origen IN ('sistema', 'plataforma', 'app', 'web'));

-- 5. Crear usuario 'Página Web' si no existe
INSERT INTO users (username, email, password_hash, dni, role, status, created_at, updated_at)
SELECT
    'Página Web',
    'web@qoricash.pe',
    'scrypt:32768:8:1$jRiO7CCyq6Q2WGuq$67eebac4cb6ef08f293a8f301ec061aa39124cfed01e89116ae3e0f5e2991ccda937f18a3454a2ec52f9aa85deb6468172d87b274e10a0b0691cd4d6ec5cfe21',
    '99999997',
    'Web',
    'Activo',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'web@qoricash.pe'
);

-- 6. Registrar la migración en alembic_version (si existe la tabla)
INSERT INTO alembic_version (version_num)
SELECT '20250111_add_web_role'
WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version')
  AND NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = '20250111_add_web_role');

COMMIT;

-- Verificación
SELECT 'Usuario Web creado:' as resultado, id, username, email, role, status
FROM users
WHERE role = 'Web';

-- Migración manual para agregar rol 'App' y renombrar usuario plataforma
-- Ejecutar este script SQL directamente en la base de datos de producción
-- Para ejecutar: psql $DATABASE_URL < manual_migration.sql

BEGIN;

-- Paso 1: Eliminar constraint anterior de roles
ALTER TABLE users DROP CONSTRAINT IF EXISTS check_user_role;

-- Paso 2: Crear nuevo constraint con rol 'App'
ALTER TABLE users ADD CONSTRAINT check_user_role
    CHECK (role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma', 'App'));

-- Paso 3: Actualizar usuario plataforma@qoricash.pe (si existe)
DO $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Buscar usuario plataforma@qoricash.pe
    SELECT id INTO v_user_id FROM users WHERE email = 'plataforma@qoricash.pe' LIMIT 1;

    IF FOUND THEN
        -- Actualizar email, username y rol
        UPDATE users
        SET email = 'app@qoricash.pe',
            username = 'App Móvil',
            role = 'App',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = v_user_id;

        RAISE NOTICE 'Usuario actualizado: plataforma@qoricash.pe -> app@qoricash.pe (Rol: App)';
    ELSE
        RAISE NOTICE 'No se encontró usuario plataforma@qoricash.pe para actualizar';
    END IF;
END $$;

-- Paso 4: Crear usuario 'Web Externa' para canales externos (si no existe)
DO $$
DECLARE
    v_web_user_id INTEGER;
BEGIN
    -- Verificar si existe el usuario web@qoricash.pe
    SELECT id INTO v_web_user_id FROM users WHERE email = 'web@qoricash.pe' LIMIT 1;

    IF NOT FOUND THEN
        -- Crear usuario Web Externa
        -- NOTA: Este password hash corresponde a 'WebExterna2025!' usando Werkzeug
        INSERT INTO users (username, email, password_hash, dni, role, status, created_at, updated_at)
        VALUES (
            'Web Externa',
            'web@qoricash.pe',
            'scrypt:32768:8:1$NyvS07eUuZwL6pIE$0d682851c430f785e670004372b591221f698603c13b56120a21369ab41635c3c6c726fc797cc7843522231f49f3b8919260641b13d709e9f1ed9de332835b67',
            '99999998',
            'Plataforma',
            'Activo',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        );

        RAISE NOTICE 'Usuario "Web Externa" creado para canales externos';
    ELSE
        RAISE NOTICE 'Usuario "Web Externa" ya existe';
    END IF;
END $$;

-- Paso 5: Registrar migración en tabla alembic_version
INSERT INTO alembic_version (version_num)
VALUES ('20250108_add_app_role')
ON CONFLICT (version_num) DO NOTHING;

COMMIT;

-- Verificación final
SELECT 'MIGRACIÓN COMPLETADA' AS status;
SELECT email, username, role FROM users WHERE email IN ('app@qoricash.pe', 'web@qoricash.pe');

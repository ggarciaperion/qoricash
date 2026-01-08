-- Script para actualizar clientes existentes que se registraron antes del rol "App"
-- Actualiza el campo created_by para que apunte al usuario "App Móvil" en lugar del antiguo usuario "Plataforma"

BEGIN;

-- Paso 1: Obtener el ID del nuevo usuario "App Móvil"
DO $$
DECLARE
    v_app_user_id INTEGER;
    v_old_plataforma_user_id INTEGER;
    v_clients_updated INTEGER := 0;
BEGIN
    -- Buscar usuario App Móvil
    SELECT id INTO v_app_user_id FROM users WHERE email = 'app@qoricash.pe' LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Usuario App Móvil (app@qoricash.pe) no encontrado. Ejecuta primero manual_migration.sql';
    END IF;

    RAISE NOTICE 'Usuario App Móvil encontrado: ID = %', v_app_user_id;

    -- Buscar si existe algún usuario con el antiguo email plataforma@qoricash.pe
    -- (Esto probablemente no existe ya que la migración lo renombró)
    SELECT id INTO v_old_plataforma_user_id FROM users WHERE email = 'plataforma@qoricash.pe' LIMIT 1;

    IF FOUND THEN
        RAISE NOTICE 'Usuario antiguo plataforma@qoricash.pe encontrado: ID = %', v_old_plataforma_user_id;

        -- Actualizar clientes que fueron creados por el usuario antiguo
        UPDATE clients
        SET created_by = v_app_user_id,
            updated_at = CURRENT_TIMESTAMP
        WHERE created_by = v_old_plataforma_user_id;

        GET DIAGNOSTICS v_clients_updated = ROW_COUNT;
        RAISE NOTICE 'Clientes actualizados del usuario antiguo: %', v_clients_updated;
    END IF;

    -- Actualizar clientes que tienen created_by = NULL (clientes sin usuario asignado)
    -- Estos probablemente son clientes antiguos del app móvil
    UPDATE clients
    SET created_by = v_app_user_id,
        updated_at = CURRENT_TIMESTAMP
    WHERE created_by IS NULL;

    GET DIAGNOSTICS v_clients_updated = ROW_COUNT;
    RAISE NOTICE 'Clientes sin created_by actualizados: %', v_clients_updated;

    -- Buscar usuarios con rol "Plataforma" que no sean "Web Externa"
    -- y actualizar sus clientes al usuario App Móvil
    FOR v_old_plataforma_user_id IN
        SELECT id FROM users
        WHERE role = 'Plataforma'
        AND email != 'web@qoricash.pe'
        AND email != 'app@qoricash.pe'
    LOOP
        UPDATE clients
        SET created_by = v_app_user_id,
            updated_at = CURRENT_TIMESTAMP
        WHERE created_by = v_old_plataforma_user_id;

        GET DIAGNOSTICS v_clients_updated = ROW_COUNT;

        IF v_clients_updated > 0 THEN
            RAISE NOTICE 'Clientes actualizados del usuario Plataforma ID=%: % clientes',
                v_old_plataforma_user_id, v_clients_updated;
        END IF;
    END LOOP;

    RAISE NOTICE '✅ Proceso de actualización de clientes completado';
END $$;

COMMIT;

-- Verificación: Mostrar resumen de clientes por usuario creador
SELECT
    u.email,
    u.username,
    u.role,
    COUNT(c.id) as total_clientes
FROM users u
LEFT JOIN clients c ON c.created_by = u.id
WHERE u.role IN ('App', 'Plataforma')
GROUP BY u.id, u.email, u.username, u.role
ORDER BY u.role, u.email;

# Scripts de Mantenimiento - QoriCash Trading V2

Este directorio contiene scripts para mantenimiento y gestión de la base de datos.

---

## clean_database.py

### Propósito

Script para eliminar **TODOS** los clientes y operaciones del sistema, dejándolo en estado limpio para realizar pruebas integrales.

### ⚠️ ADVERTENCIAS

- **Esta acción es IRREVERSIBLE**
- Se eliminarán TODOS los clientes registrados desde cualquier canal
- Se eliminarán TODAS las operaciones creadas
- Se eliminarán TODOS los archivos asociados (referencias a Cloudinary)
- Se eliminarán TODOS los datos de compliance relacionados
- **Los usuarios del sistema (Traders, Operadores, Master) NO se eliminan**

### Qué se elimina

El script elimina datos de las siguientes tablas en orden:

1. **ComplianceDocument** - Documentos de compliance (ROS, DD, KYC reports)
2. **ComplianceAlert** - Alertas de compliance generadas
3. **TransactionMonitoring** - Monitoreo de transacciones
4. **RestrictiveListCheck** - Verificaciones de listas restrictivas (OFAC, UIF, etc.)
5. **ClientRiskProfile** - Perfiles de riesgo de clientes
6. **RewardCode** - Códigos de recompensa generados
7. **Invoice** - Facturas electrónicas (NubeFact)
8. **Operation** - Operaciones de cambio de divisas
9. **Client** - Clientes del sistema
10. **ComplianceAudit** - Auditoría de compliance relacionada
11. **AuditLog** - Logs de auditoría relacionados

### Qué NO se elimina

- ✅ Usuarios del sistema (users)
- ✅ Roles y permisos
- ✅ Configuraciones del sistema
- ✅ Tipos de cambio (exchange_rates)
- ✅ Saldos bancarios (bank_balances)
- ✅ Reglas de compliance (compliance_rules)
- ✅ Niveles de riesgo (risk_levels)

### Uso

#### Opción 1: Desde el directorio raíz
```bash
cd C:\Users\ACER\Desktop\Qoricashtrading
python scripts\clean_database.py
```

#### Opción 2: Desde el directorio scripts
```bash
cd C:\Users\ACER\Desktop\Qoricashtrading\scripts
python clean_database.py
```

### Confirmación Requerida

El script solicitará confirmación antes de proceder. Para confirmar, debes escribir exactamente:

```
ELIMINAR TODO
```

Cualquier otra respuesta cancelará la operación.

### Output Esperado

```
================================================================================
                    LIMPIEZA DE BASE DE DATOS
               QoriCash Trading V2 - Clean Database Script
================================================================================

⚠️  ADVERTENCIA: Este script eliminará TODOS los clientes y operaciones
⚠️  Esta acción es IRREVERSIBLE

✅ Los usuarios del sistema (Master, Traders, Operadores) NO se eliminan

================================================================================

📊 Conteo de registros actuales:
--------------------------------------------------------------------------------
  • Clientes                              :      150 registros
  • Operaciones                           :      450 registros
  • Facturas                              :      400 registros
  • Códigos de Recompensa                 :       25 registros
  • Perfiles de Riesgo                    :      150 registros
  • Alertas de Compliance                 :       30 registros
  • Documentos de Compliance              :       15 registros
  • Verificaciones de Listas              :      150 registros
  • Monitoreo de Transacciones            :      450 registros
  • Auditoría de Compliance               :       80 registros
  • Registros de Auditoría                :    1,200 registros
--------------------------------------------------------------------------------
  TOTAL DE REGISTROS A ELIMINAR           :    3,100

⚠️  CONFIRMACIÓN REQUERIDA
--------------------------------------------------------------------------------

Para continuar, escribe exactamente: ELIMINAR TODO

Confirmación: ELIMINAR TODO

✅ Confirmación recibida. Iniciando limpieza...

🗑️  Iniciando proceso de limpieza...
--------------------------------------------------------------------------------

  [1/11] Eliminando Documentos de Compliance...
          ✓ 15 documentos eliminados
  [2/11] Eliminando Alertas de Compliance...
          ✓ 30 alertas eliminadas
  [3/11] Eliminando Monitoreo de Transacciones...
          ✓ 450 registros eliminados
  [4/11] Eliminando Verificaciones de Listas Restrictivas...
          ✓ 150 verificaciones eliminadas
  [5/11] Eliminando Perfiles de Riesgo de Clientes...
          ✓ 150 perfiles eliminados
  [6/11] Eliminando Códigos de Recompensa...
          ✓ 25 códigos eliminados
  [7/11] Eliminando Facturas Electrónicas...
          ✓ 400 facturas eliminadas
  [8/11] Eliminando Operaciones...
          ✓ 450 operaciones eliminadas
  [9/11] Eliminando Clientes...
          ✓ 150 clientes eliminados
  [10/11] Limpiando Auditoría de Compliance...
           ✓ 80 registros de auditoría eliminados
  [11/11] Limpiando Registros de Auditoría...
           ✓ 1,200 registros de auditoría eliminados

--------------------------------------------------------------------------------

✅ LIMPIEZA COMPLETADA EXITOSAMENTE
================================================================================

📊 Resumen de eliminación:
--------------------------------------------------------------------------------
  • ComplianceDocument                    :       15 eliminados
  • ComplianceAlert                       :       30 eliminados
  • TransactionMonitoring                 :      450 eliminados
  • RestrictiveListCheck                  :      150 eliminados
  • ClientRiskProfile                     :      150 eliminados
  • RewardCode                            :       25 eliminados
  • Invoice                               :      400 eliminados
  • Operation                             :      450 eliminados
  • Client                                :      150 eliminados
  • ComplianceAudit                       :       80 eliminados
  • AuditLog                              :    1,200 eliminados
--------------------------------------------------------------------------------
  TOTAL DE REGISTROS ELIMINADOS           :    3,100

🔍 Verificando integridad de usuarios del sistema...
--------------------------------------------------------------------------------
  ✓ Total de usuarios en el sistema: 5
    • master (Master) - Activo
    • trader1 (Trader) - Activo
    • trader2 (Trader) - Activo
    • operador1 (Operador) - Activo
    • middleoffice1 (Middle Office) - Activo

================================================================================

✅ Base de datos limpiada exitosamente

El sistema está listo para realizar pruebas integrales.

Próximos pasos recomendados:
  1. Crear clientes de prueba desde cada canal (app, web, sistema)
  2. Crear operaciones de prueba
  3. Verificar flujos completos (registro, operaciones, compliance)
  4. Validar correos automáticos
  5. Validar facturación electrónica (NubeFact)

================================================================================
```

### Manejo de Errores

Si ocurre algún error durante la limpieza:
- Se realiza un **rollback automático**
- **No se realizan cambios** en la base de datos
- Se muestra el error completo con stack trace

Ejemplo:
```
================================================================================
❌ ERROR DURANTE LA LIMPIEZA
================================================================================

Error: (psycopg2.errors.ForeignKeyViolation) update or delete on table "clients" violates foreign key constraint...

🔄 Realizando rollback...
✓ Rollback completado. No se realizaron cambios en la base de datos.
```

### Verificaciones de Seguridad

El script incluye múltiples capas de seguridad:

1. **Confirmación explícita**: Requiere escribir exactamente "ELIMINAR TODO"
2. **Transacciones**: Usa transacciones de base de datos para garantizar atomicidad
3. **Rollback automático**: Si algo falla, se revierte todo
4. **Orden correcto**: Elimina en orden respetando foreign keys
5. **Verificación final**: Verifica que usuarios no fueron afectados

### Archivos en Cloudinary

**⚠️ IMPORTANTE**: El script elimina las **referencias** a archivos en Cloudinary (URLs), pero **NO elimina** los archivos físicos del CDN.

Para limpiar Cloudinary completamente, deberás:

1. Acceder al panel de Cloudinary
2. Ir a Media Library
3. Eliminar manualmente las carpetas:
   - `/dni/`
   - `/operations/payment_proofs/`
   - `/operations/operator_proofs/`
   - `/compliance/`

O usar la API de Cloudinary para eliminación masiva.

### Casos de Uso

Este script es útil para:

✅ **Pre-producción**: Limpiar datos de prueba antes del lanzamiento
✅ **Testing**: Reset completo para pruebas end-to-end
✅ **Demos**: Preparar entorno limpio para demostraciones
✅ **Desarrollo**: Reset de base de datos durante desarrollo

❌ **NO usar en producción** con datos reales de clientes

### Respaldo Recomendado

Antes de ejecutar este script en un entorno con datos importantes, **SIEMPRE** crea un respaldo:

```bash
# Backup PostgreSQL
pg_dump DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar si es necesario
psql DATABASE_URL < backup_20260122_153045.sql
```

---

## Contribuir

Si necesitas agregar más scripts de mantenimiento, sigue estas convenciones:

1. Usa nombres descriptivos (`clean_`, `migrate_`, `seed_`, etc.)
2. Incluye documentación completa en este README
3. Agrega confirmaciones para operaciones destructivas
4. Usa transacciones y rollback
5. Provee mensajes claros de progreso
6. Incluye manejo de errores robusto

---

**Documentación generada por**: Claude Code
**Fecha**: 22 de enero de 2026

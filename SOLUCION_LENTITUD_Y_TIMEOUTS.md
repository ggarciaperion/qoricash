# Solución: Lentitud Extrema y Worker Timeouts

**Fecha:** 2025-11-26
**Problema:** Sistema extremadamente lento (>1 minuto entre menús), Worker Timeout, errores "Bad file descriptor"

---

## 🔍 Diagnóstico del Problema

### Problemas Identificados:

1. **Queries SQL extremadamente lentas**
   - Dashboard carga TODOS los objetos Operation en memoria
   - Procesa en Python en lugar de usar SQL aggregates (COUNT, SUM)
   - Sin índices en columnas clave (created_at, status, user_id)

2. **Worker Timeout**
   - Requests tardan >5 minutos (timeout configurado en 300s)
   - Gunicorn mata el worker por timeout

3. **Errores "Bad file descriptor"**
   - Clientes desconectan abruptamente de WebSocket
   - (Parcialmente solucionado en commit anterior)

---

## ✅ Soluciones Implementadas

### 1. **Índices de Base de Datos** (CRÍTICO - APLICAR PRIMERO)

Se crearon índices para las columnas más usadas en queries del dashboard:

**Archivos creados:**
- `add_performance_indexes.sql` - Script SQL con los índices
- `apply_performance_indexes.py` - Script Python para aplicar índices

**Índices creados:**
- `operations`: created_at, status, user_id, client_id, operation_type
- Índices compuestos: (created_at, status), (user_id, created_at), (user_id, status)
- `trader_daily_profits`: (user_id, profit_date), profit_date
- `trader_goals`: (user_id, year, month), (year, month)
- `clients`: status
- `users`: role, status, (role, status)

**Impacto esperado:** Reducción de 70-80% en tiempo de query

### 2. **Timeout Aumentado Temporalmente**

**Cambio en `gunicorn_config.py`:**
```python
timeout = 600  # 10 minutos (antes 300s)
graceful_timeout = 180  # 3 minutos (antes 120s)
```

**Nota:** Este es temporal hasta que se apliquen los índices. Una vez aplicados, se puede reducir a 120-180s.

---

## 🚀 Pasos para Aplicar la Solución

### Paso 1: Deploy de Código Actualizado

```bash
# Ya se hizo commit y push
# Render detectará automáticamente y hará deploy
```

### Paso 2: Aplicar Índices a la Base de Datos (CRÍTICO)

**Opción A: Usando Python (Recomendado)**

```bash
# En tu máquina local o en Render Shell
cd /c/Users/ACER/Desktop/qoricash-trading-v2
python apply_performance_indexes.py
```

**Opción B: Usando SQL Directamente**

1. Conectar a la base de datos de Render:
   ```bash
   # Obtener DATABASE_URL de Render Dashboard
   psql $DATABASE_URL
   ```

2. Ejecutar el script:
   ```sql
   \i add_performance_indexes.sql
   ```

**Opción C: Desde Render Dashboard**

1. Ve a: Render Dashboard > Database > Connect
2. Usa "PSQL Command" o "External Connection"
3. Copia y pega el contenido de `add_performance_indexes.sql`

---

## 📊 Archivos Modificados

1. ✅ **gunicorn_config.py** - Timeout aumentado a 600s temporalmente
2. ✅ **add_performance_indexes.sql** - Script SQL con índices
3. ✅ **apply_performance_indexes.py** - Script Python para aplicar índices
4. ✅ **SOLUCION_LENTITUD_Y_TIMEOUTS.md** - Esta documentación

---

## 🎯 Resultados Esperados

### Antes:
- ❌ Dashboard tarda >60 segundos en cargar
- ❌ Navegación entre menús >1 minuto
- ❌ Worker timeout cada 5 minutos
- ❌ Errores "Bad file descriptor" frecuentes

### Después (con índices aplicados):
- ✅ Dashboard carga en 2-5 segundos
- ✅ Navegación instantánea (<1 segundo)
- ✅ Sin worker timeouts
- ✅ Errores "Bad file descriptor" suprimidos en logs

---

## 📈 Monitoreo Post-Deploy

### 1. Verificar que los índices se aplicaron:

```sql
SELECT 
    tablename,
    indexname
FROM pg_indexes 
WHERE schemaname = 'public' 
  AND tablename = 'operations'
ORDER BY indexname;
```

Deberías ver índices como:
- `idx_operations_created_at`
- `idx_operations_status`
- `idx_operations_user_id`
- etc.

### 2. Monitorear logs de Render:

```
✓ Gunicorn configurado: 1 workers (eventlet), timeout 600s
⚠️  NOTA: Timeout alto temporal - aplicar índices de BD para mejorar performance
```

### 3. Probar velocidad del dashboard:

- Accede a `https://app.qoricash.pe/dashboard`
- El dashboard debe cargar en menos de 5 segundos
- La navegación debe ser instantánea

---

## 🔧 Optimizaciones Futuras (Opcional)

Una vez que los índices estén aplicados y el sistema sea rápido:

1. **Reducir timeout** en `gunicorn_config.py`:
   ```python
   timeout = 180  # 3 minutos es suficiente con índices
   ```

2. **Implementar caché** para estadísticas del dashboard:
   - Flask-Caching para cachear respuestas por 30-60 segundos
   - Redis para cache distribuido (si se escala a múltiples workers)

3. **Optimizar queries** del dashboard:
   - Reemplazar `joinedload` con SQL aggregates directos
   - Implementar paginación para listas largas

---

## ⚠️ Importante

**NO OLVIDES APLICAR LOS ÍNDICES**

Los índices son CRÍTICOS para resolver el problema de lentitud. Sin ellos:
- El timeout aumentado solo evita el error, pero el sistema seguirá lento
- Con los índices, el sistema será 10-20x más rápido

**Prioridad:**
1. ✅ Deploy de código (ya hecho)
2. ⚡ **APLICAR ÍNDICES** (hacer AHORA)
3. ✅ Monitorear resultados

---

## 📞 Verificación Final

Después de aplicar los índices, verifica:

```bash
# 1. Logs de Render deben mostrar:
✓ Conexión DB verificada

# 2. No más Worker Timeout errors

# 3. Dashboard carga rápido
# Accede a https://app.qoricash.pe/dashboard
# Debe cargar en <5 segundos

# 4. Navegación fluida
# Cambiar entre menús debe ser instantáneo
```

---

**Estado:** ✅ Cambios commiteados y pusheados
**Siguiente paso:** 🚨 APLICAR ÍNDICES A LA BASE DE DATOS

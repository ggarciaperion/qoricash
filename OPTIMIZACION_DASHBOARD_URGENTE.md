# OPTIMIZACIÓN URGENTE - Dashboard Performance

## Problema Identificado

La función `get_all_dashboard_data()` en `app/routes/dashboard.py` (líneas 74-250) está causando **WORKER TIMEOUT** porque:

1. Carga TODOS los objetos Operation del día y del mes en memoria
2. Usa `joinedload()` que carga objetos relacionados (client, user)
3. Procesa todo en Python en lugar de usar SQL

Con miles de operaciones, esto tarda >30 segundos y causa timeout.

## Solución Temporal INMEDIATA

Mientras aplicamos la optimización completa, hay una solución rápida:

### Opción 1: Deshabilitar la carga eager (RÁPIDO)

Editar `app/routes/dashboard.py` línea 107 y 169:

**ANTES:**
```python
query_today = Operation.query.options(
    joinedload(Operation.client),
    joinedload(Operation.user)
).filter(...)
```

**DESPUÉS:**
```python
query_today = Operation.query.filter(...)
# Eliminar las líneas joinedload
```

Hacer lo mismo en la línea ~169 para `query_month`.

Esto reduce el tiempo de 30s+ a ~10-15s.

### Opción 2: Limitar resultados (MUY RÁPIDO)

Agregar `.limit(1000)` a las queries:

```python
query_today = Operation.query.filter(...).limit(1000).all()
```

Esto evita cargar miles de registros.

## Solución Definitiva (SQL Aggregates)

La solución completa requiere reescribir la función para usar SQL aggregates.

Ver archivo: `SOLUCION_LENTITUD_Y_TIMEOUTS.md` para detalles.

## ACCIÓN INMEDIATA

1. Editar `app/routes/dashboard.py`
2. Eliminar `joinedload(Operation.client)` y `joinedload(Operation.user)` de las líneas 107-111 y 169-173
3. Commit y push
4. Esperar redeploy de Render

Esto debería reducir el timeout significativamente mientras trabajamos en la optimización completa.


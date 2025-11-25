# Actualización de Exportación Excel - Cuentas Bancarias

## Descripción
Se agregaron dos nuevas columnas a las exportaciones Excel de "Operaciones del Día" y "Historial de Operaciones" para mostrar las cuentas bancarias con las que se creó originalmente cada operación.

## Cambios Implementados

### Nuevas Columnas Agregadas

Las siguientes columnas se agregaron a **ambas exportaciones** (Operaciones del Día e Historial):

1. **CUENTA CARGO** - Número de cuenta bancaria de origen (source_account)
2. **CUENTA DESTINO** - Número de cuenta bancaria de destino (destination_account)

Estas columnas se insertaron **después de PEN** y **antes de ESTADO**.

### Archivos Modificados

**Archivo**: `app/routes/operations.py`

Se modificaron dos endpoints:
- `GET /operations/api/export_today` - Exportación de operaciones del día
- `GET /operations/api/export_history` - Exportación de historial

## Estructura Actualizada del Excel

### Para Master y Operador (11 columnas):

| # | Columna | Descripción | Ancho |
|---|---------|-------------|-------|
| 1 | ID OP. | Código de operación | 12 |
| 2 | DOCUMENTO | DNI o RUC del cliente | 15 |
| 3 | CLIENTE | Nombre completo o razón social | 30 |
| 4 | USD | Monto en dólares | 12 |
| 5 | T.C. | Tipo de cambio | 10 |
| 6 | PEN | Monto en soles | 12 |
| 7 | **CUENTA CARGO** | Número de cuenta origen | **20** |
| 8 | **CUENTA DESTINO** | Número de cuenta destino | **20** |
| 9 | ESTADO | Estado de la operación | 15 |
| 10 | FECHA | Fecha y hora de creación | 18 |
| 11 | USUARIO | Email del usuario creador | 30 |

### Para Trader (10 columnas):

| # | Columna | Descripción | Ancho |
|---|---------|-------------|-------|
| 1 | ID OP. | Código de operación | 12 |
| 2 | DOCUMENTO | DNI o RUC del cliente | 15 |
| 3 | CLIENTE | Nombre completo o razón social | 30 |
| 4 | USD | Monto en dólares | 12 |
| 5 | T.C. | Tipo de cambio | 10 |
| 6 | PEN | Monto en soles | 12 |
| 7 | **CUENTA CARGO** | Número de cuenta origen | **20** |
| 8 | **CUENTA DESTINO** | Número de cuenta destino | **20** |
| 9 | ESTADO | Estado de la operación | 15 |
| 10 | FECHA | Fecha y hora de creación | 18 |

## Código de Implementación

### Encabezados Actualizados:

```python
# Para Master y Operador
headers = ['ID OP.', 'DOCUMENTO', 'CLIENTE', 'USD', 'T.C.', 'PEN',
           'CUENTA CARGO', 'CUENTA DESTINO', 'ESTADO', 'FECHA', 'USUARIO']

# Para Trader
headers = ['ID OP.', 'DOCUMENTO', 'CLIENTE', 'USD', 'T.C.', 'PEN',
           'CUENTA CARGO', 'CUENTA DESTINO', 'ESTADO', 'FECHA']
```

### Datos de las Cuentas:

```python
# Escribir datos en las celdas
ws.cell(row=row_num, column=7, value=op.source_account if op.source_account else '-')
ws.cell(row=row_num, column=8, value=op.destination_account if op.destination_account else '-')
```

### Ajuste de Ancho de Columnas:

```python
ws.column_dimensions['G'].width = 20  # CUENTA CARGO
ws.column_dimensions['H'].width = 20  # CUENTA DESTINO
```

## Origen de los Datos

Las cuentas bancarias provienen de los siguientes campos del modelo `Operation`:

- **source_account**: Cuenta de origen almacenada al crear la operación
- **destination_account**: Cuenta de destino almacenada al crear la operación

Estos campos contienen los **números de cuenta** tal como fueron seleccionados al momento de crear la operación.

## Ejemplo de Datos en Excel

| ID OP. | DOCUMENTO | CLIENTE | USD | T.C. | PEN | CUENTA CARGO | CUENTA DESTINO | ESTADO | FECHA | USUARIO |
|--------|-----------|---------|-----|------|-----|--------------|----------------|--------|-------|---------|
| EXP-1001 | 12345678 | Juan Pérez | 1000.00 | 3.7500 | 3750.00 | 123-456-789 | 987-654-321 | Completada | 22/11/2025 14:30 | trader@mail.com |
| EXP-1002 | 87654321 | María García | 500.00 | 3.7200 | 1860.00 | 111-222-333 | 444-555-666 | En proceso | 22/11/2025 15:45 | trader@mail.com |

## Comportamiento con Datos Faltantes

Si una operación no tiene asignadas las cuentas bancarias:
- Se muestra el carácter **"-"** en ambas columnas
- No se produce error ni se deja la celda vacía

```python
value=op.source_account if op.source_account else '-'
```

## Ventajas de la Implementación

✅ **Trazabilidad completa**: Permite conocer exactamente con qué cuentas se realizó cada operación

✅ **Consistencia entre exportaciones**: Ambos archivos Excel (día e historial) tienen la misma estructura

✅ **Información original**: Muestra las cuentas tal como fueron seleccionadas al crear la operación

✅ **Sin duplicación de código**: Los cambios se aplicaron exactamente igual en ambos endpoints

✅ **Compatible con datos históricos**: Operaciones antiguas sin cuentas asignadas muestran "-"

## Impacto en Reportes

Esta actualización beneficia especialmente a:

1. **Master y Operador**: Para auditoría y verificación de cuentas utilizadas
2. **Contabilidad**: Para conciliación bancaria
3. **Análisis de operaciones**: Para identificar patrones de uso de cuentas
4. **Reportes regulatorios**: Para demostrar origen y destino de fondos

## Notas Técnicas

- Las cuentas mostradas son **números de cuenta**, no nombres de bancos
- El ancho de columna de 20 caracteres es suficiente para números de cuenta bancarias peruanas
- Los campos `source_account` y `destination_account` están en la tabla `operations`
- No se requieren JOINs adicionales para obtener esta información
- El orden de las columnas fue diseñado para mantener juntos los datos financieros (USD, TC, PEN) antes de las cuentas

## Archivos Afectados

1. `app/routes/operations.py` - Endpoints modificados:
   - `export_today()` (líneas 63-138)
   - `export_history()` (líneas 141-221)

## Retrocompatibilidad

✅ Los archivos Excel existentes en sistemas de terceros no se ven afectados

✅ Las nuevas columnas se agregaron sin eliminar las existentes

✅ El orden de las columnas previas (ID OP., DOCUMENTO, CLIENTE, USD, T.C., PEN) se mantuvo

## Pruebas Recomendadas

1. **Con cuentas asignadas**:
   - Crear operación con cuentas
   - Exportar Excel
   - Verificar que los números de cuenta aparecen correctamente

2. **Sin cuentas asignadas**:
   - Exportar operaciones antiguas (sin cuentas)
   - Verificar que aparece "-" en ambas columnas

3. **Para todos los roles**:
   - Exportar como Master
   - Exportar como Operador
   - Exportar como Trader
   - Verificar que las columnas están presentes en todos los casos

4. **Ambas exportaciones**:
   - Exportar desde "Operaciones" (del día)
   - Exportar desde "Historial"
   - Verificar que ambas tienen la misma estructura

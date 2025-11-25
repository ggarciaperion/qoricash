# Implementación: Bancos en Cuentas y Filtro de Fechas

## Descripción General
Se implementaron dos mejoras importantes en las exportaciones Excel:
1. **Mostrar nombre del banco junto al número de cuenta** (ambas exportaciones)
2. **Modal de filtrado por fechas para el historial** (solo historial)

---

## PARTE 1: Nombres de Bancos en Cuentas

### Cambio Implementado
Las columnas **CUENTA CARGO** y **CUENTA DESTINO** ahora muestran el formato:
```
BANCO - NUMERO_CUENTA
```

**Ejemplo**:
- Antes: `123-456-789`
- Ahora: `BCP - 123-456-789`

### Archivos Modificados

#### 1. `app/routes/operations.py`

**Nueva función auxiliar**:
```python
def get_bank_account_info(operation, account_number):
    """
    Obtener información completa de una cuenta bancaria (Banco - Número)

    Args:
        operation: Objeto Operation
        account_number: Número de cuenta a buscar

    Returns:
        str: Formato "BANCO - NUMERO" o "-" si no existe
    """
    if not account_number or not operation.client:
        return '-'

    bank_accounts = operation.client.bank_accounts or []
    for account in bank_accounts:
        if account.get('account_number') == account_number:
            bank_name = account.get('bank_name', 'N/A')
            return f"{bank_name} - {account_number}"

    # Si no se encuentra en las cuentas del cliente, solo retornar el número
    return account_number
```

**Uso en export_today()**:
```python
ws.cell(row=row_num, column=7, value=get_bank_account_info(op, op.source_account))
ws.cell(row=row_num, column=8, value=get_bank_account_info(op, op.destination_account))
```

**Uso en export_history()**:
```python
ws.cell(row=row_num, column=7, value=get_bank_account_info(op, op.source_account))
ws.cell(row=row_num, column=8, value=get_bank_account_info(op, op.destination_account))
```

**Ajuste de ancho de columnas**:
```python
ws.column_dimensions['G'].width = 35  # CUENTA CARGO (más ancho para banco + número)
ws.column_dimensions['H'].width = 35  # CUENTA DESTINO (más ancho para banco + número)
```

### Lógica de la Función

1. **Si no hay número de cuenta**: Retorna `-`
2. **Si no hay cliente asociado**: Retorna `-`
3. **Si encuentra el número en las cuentas del cliente**: Retorna `BANCO - NUMERO`
4. **Si no encuentra en las cuentas**: Retorna solo el número de cuenta

### Ejemplo de Datos en Excel

| CUENTA CARGO | CUENTA DESTINO |
|--------------|----------------|
| BCP - 123-456-789 | Interbank - 987-654-321 |
| BBVA - 111-222-333 | Scotiabank - 444-555-666 |
| - | - |

---

## PARTE 2: Filtro de Fechas para Historial

### Cambio Implementado
Al hacer clic en "Descargar Excel" en el menú **Historial de Operaciones**, se abre un modal que permite:
- Seleccionar fecha de inicio
- Seleccionar fecha de fin
- Descargar solo operaciones en ese rango
- O descargar todo si no se seleccionan fechas

### Archivos Modificados

#### 1. `app/routes/operations.py` - Endpoint Actualizado

**Endpoint**: `GET /operations/api/export_history`

**Parámetros query opcionales**:
- `start_date`: Fecha inicio (formato: YYYY-MM-DD)
- `end_date`: Fecha fin (formato: YYYY-MM-DD)

**Código**:
```python
@operations_bp.route('/api/export_history')
@login_required
def export_history():
    """
    API: Exportar historial de operaciones a Excel con filtro de fechas

    Query params opcionales:
        start_date: Fecha inicio (formato: YYYY-MM-DD)
        end_date: Fecha fin (formato: YYYY-MM-DD)
    """
    from app.models.operation import Operation
    from datetime import datetime

    # Obtener parámetros de filtro de fechas
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Construir query base
    query = Operation.query

    # Aplicar filtros de fecha si existen
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Operation.created_at >= start)
        except ValueError:
            pass

    if end_date:
        try:
            # Agregar 23:59:59 al final del día
            end = datetime.strptime(end_date, '%Y-%m-%d')
            end = end.replace(hour=23, minute=59, second=59)
            query = query.filter(Operation.created_at <= end)
        except ValueError:
            pass

    # Ordenar por fecha descendente
    operations = query.order_by(Operation.created_at.desc()).all()

    # ... resto del código para generar Excel
```

#### 2. `app/templates/operations/history.html`

**Botón modificado**:
```html
<button class="btn btn-success" data-bs-toggle="modal" data-bs-target="#exportDateFilterModal">
    <i class="bi bi-file-earmark-excel"></i> Descargar Excel
</button>
```

**Modal agregado**:
```html
<!-- Modal: Filtro de Fechas para Exportar -->
<div class="modal fade" id="exportDateFilterModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">
                    <i class="bi bi-calendar-range"></i> Exportar Historial a Excel
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <p class="text-muted">
                    Selecciona el rango de fechas para exportar.
                    Si no seleccionas fechas, se exportarán todas las operaciones.
                </p>

                <div class="mb-3">
                    <label for="export_start_date" class="form-label">
                        Fecha Inicio (Opcional)
                    </label>
                    <input type="date" class="form-control" id="export_start_date">
                </div>

                <div class="mb-3">
                    <label for="export_end_date" class="form-label">
                        Fecha Fin (Opcional)
                    </label>
                    <input type="date" class="form-control" id="export_end_date">
                </div>

                <div class="alert alert-info small mb-0">
                    <i class="bi bi-info-circle"></i>
                    Si dejas ambos campos vacíos, se descargará el historial completo.
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                    Cancelar
                </button>
                <button type="button" class="btn btn-success" onclick="downloadExcelWithDates()">
                    <i class="bi bi-download"></i> Descargar
                </button>
            </div>
        </div>
    </div>
</div>
```

**Función JavaScript**:
```javascript
function downloadExcelWithDates() {
    const startDate = $('#export_start_date').val();
    const endDate = $('#export_end_date').val();

    // Validar que si hay fecha inicio, también haya fecha fin (y viceversa)
    if (startDate && endDate && startDate > endDate) {
        showAlert('La fecha de inicio no puede ser mayor que la fecha fin', 'warning');
        return;
    }

    // Construir URL con parámetros
    let url = '/operations/api/export_history';
    const params = [];

    if (startDate) {
        params.push(`start_date=${startDate}`);
    }

    if (endDate) {
        params.push(`end_date=${endDate}`);
    }

    if (params.length > 0) {
        url += '?' + params.join('&');
    }

    // Cerrar modal
    $('#exportDateFilterModal').modal('hide');

    // Mostrar mensaje
    if (startDate || endDate) {
        showAlert('Preparando descarga del rango seleccionado...', 'info');
    } else {
        showAlert('Preparando descarga del historial completo...', 'info');
    }

    // Descargar
    window.location.href = url;

    // Limpiar campos después de 1 segundo
    setTimeout(() => {
        $('#export_start_date').val('');
        $('#export_end_date').val('');
    }, 1000);
}
```

---

## Casos de Uso

### Filtro de Fechas

#### Caso 1: Descargar rango específico
1. Click en "Descargar Excel"
2. Seleccionar Fecha Inicio: `2025-01-01`
3. Seleccionar Fecha Fin: `2025-01-31`
4. Click en "Descargar"
5. **Resultado**: Excel con operaciones de enero 2025

#### Caso 2: Solo desde una fecha
1. Click en "Descargar Excel"
2. Seleccionar Fecha Inicio: `2025-11-01`
3. Dejar Fecha Fin vacía
4. Click en "Descargar"
5. **Resultado**: Excel con operaciones desde el 1 de noviembre hasta hoy

#### Caso 3: Solo hasta una fecha
1. Click en "Descargar Excel"
2. Dejar Fecha Inicio vacía
3. Seleccionar Fecha Fin: `2025-10-31`
4. Click en "Descargar"
5. **Resultado**: Excel con todas las operaciones hasta el 31 de octubre

#### Caso 4: Sin filtro (todo el historial)
1. Click en "Descargar Excel"
2. Dejar ambos campos vacíos
3. Click en "Descargar"
4. **Resultado**: Excel con TODAS las operaciones históricas

### Validaciones Implementadas

✅ **Fecha inicio > Fecha fin**: Muestra alerta de error
✅ **Formato de fecha inválido**: Se ignora el filtro
✅ **Campos vacíos**: Se exporta todo el historial
✅ **Solo una fecha**: Funciona como filtro desde/hasta

---

## Ventajas de las Implementaciones

### Nombres de Bancos:
✅ **Mejor legibilidad**: No es necesario recordar qué banco corresponde a cada número
✅ **Información completa**: Banco + número en una sola celda
✅ **Auditoría mejorada**: Fácil verificación de cuentas utilizadas
✅ **Sin queries adicionales**: Usa datos ya cargados en `bank_accounts`

### Filtro de Fechas:
✅ **Evita descargas masivas**: No descarga innecesariamente todas las operaciones
✅ **Reportes personalizados**: Permite generar reportes por periodo
✅ **Mejor rendimiento**: Menos datos procesados cuando se filtra
✅ **Interfaz amigable**: Modal intuitivo con inputs de fecha nativos
✅ **Flexibilidad**: Permite combinar fechas o dejar todo abierto

---

## Estructura Actualizada del Excel

### Columnas (Master/Operador):

| # | Columna | Ejemplo | Ancho |
|---|---------|---------|-------|
| 1 | ID OP. | EXP-1001 | 12 |
| 2 | DOCUMENTO | 12345678 | 15 |
| 3 | CLIENTE | Juan Pérez | 30 |
| 4 | USD | 1000.00 | 12 |
| 5 | T.C. | 3.7500 | 10 |
| 6 | PEN | 3750.00 | 12 |
| 7 | **CUENTA CARGO** | **BCP - 123-456-789** | **35** |
| 8 | **CUENTA DESTINO** | **Interbank - 987-654-321** | **35** |
| 9 | ESTADO | Completada | 15 |
| 10 | FECHA | 22/11/2025 14:30 | 18 |
| 11 | USUARIO | trader@mail.com | 30 |

---

## Ejemplos de URLs Generadas

### Sin filtro:
```
/operations/api/export_history
```

### Con fecha inicio:
```
/operations/api/export_history?start_date=2025-01-01
```

### Con fecha fin:
```
/operations/api/export_history?end_date=2025-12-31
```

### Con ambas fechas:
```
/operations/api/export_history?start_date=2025-01-01&end_date=2025-12-31
```

---

## Notas Técnicas

### Filtrado de Fechas:
- El endpoint filtra por `created_at` de la operación
- La fecha de fin incluye todo el día (hasta las 23:59:59)
- Si el formato de fecha es inválido, se ignora el parámetro
- Las fechas deben estar en formato ISO (YYYY-MM-DD)

### Nombres de Bancos:
- Se busca en `client.bank_accounts` (JSON)
- Si no se encuentra, retorna solo el número de cuenta
- Si no hay cuenta asignada, retorna "-"
- El formato es siempre: `BANCO - NUMERO`

### Compatibilidad:
- La función `downloadExcel()` antigua se mantiene como legacy
- Ambas exportaciones (día e historial) usan `get_bank_account_info()`
- El modal es exclusivo del historial
- La exportación del día NO tiene filtro de fechas

---

## Archivos Modificados

1. `app/routes/operations.py`:
   - Nueva función `get_bank_account_info()`
   - Actualizado `export_today()` para usar nombres de bancos
   - Actualizado `export_history()` para filtro de fechas y nombres de bancos

2. `app/templates/operations/history.html`:
   - Modificado botón "Descargar Excel"
   - Agregado modal `exportDateFilterModal`
   - Agregada función `downloadExcelWithDates()`

---

## Pruebas Recomendadas

### Para Nombres de Bancos:
1. Crear operación con cuentas que tienen banco asignado
2. Exportar Excel
3. Verificar formato "BANCO - NUMERO"

### Para Filtro de Fechas:
1. Probar con rango específico (ej: enero 2025)
2. Probar solo con fecha inicio
3. Probar solo con fecha fin
4. Probar sin fechas (todo el historial)
5. Probar con fecha inicio > fecha fin (debe alertar)
6. Verificar que el modal se cierra después de descargar
7. Verificar que los campos se limpian automáticamente

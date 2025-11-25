# Implementación de Exportación Excel - Operaciones del Día

## Descripción
Se implementó un botón de descarga Excel en el menú "Operaciones" que permite exportar todas las operaciones del día actual en todos los estados (Pendiente, En proceso, Completada, Cancelado). La estructura del archivo Excel es idéntica a la del historial de operaciones.

## Cambios Implementados

### 1. Backend - Nuevo Endpoint
**Archivo**: `app/routes/operations.py`

Se agregó el endpoint `GET /operations/api/export_today`:

```python
@operations_bp.route('/api/export_today')
@login_required
def export_today():
    """
    API: Exportar operaciones del día actual a Excel

    Las columnas varían según el rol:
    - Master y Operador: Incluyen columna de Usuario (email)
    - Trader: No incluye columna de Usuario
    """
    operations = OperationService.get_today_operations()

    # Crear libro de Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Operaciones del Día"

    # Estilos
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    header_alignment = Alignment(horizontal="center", vertical="center")

    # Definir encabezados según el rol
    if current_user.role in ['Master', 'Operador']:
        headers = ['ID OP.', 'DOCUMENTO', 'CLIENTE', 'USD', 'T.C.', 'PEN', 'ESTADO', 'FECHA', 'USUARIO']
    else:
        headers = ['ID OP.', 'DOCUMENTO', 'CLIENTE', 'USD', 'T.C.', 'PEN', 'ESTADO', 'FECHA']

    # Escribir encabezados
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment

    # Escribir datos
    for row_num, op in enumerate(operations, 2):
        ws.cell(row=row_num, column=1, value=op.operation_id)
        ws.cell(row=row_num, column=2, value=op.client.dni if op.client else '-')
        ws.cell(row=row_num, column=3, value=op.client.full_name if op.client else '-')
        ws.cell(row=row_num, column=4, value=float(op.amount_usd))
        ws.cell(row=row_num, column=5, value=float(op.exchange_rate))
        ws.cell(row=row_num, column=6, value=float(op.amount_pen))
        ws.cell(row=row_num, column=7, value=op.status)
        ws.cell(row=row_num, column=8, value=op.created_at.strftime('%d/%m/%Y %H:%M') if op.created_at else '-')

        # Solo agregar columna de usuario para Master y Operador
        if current_user.role in ['Master', 'Operador']:
            ws.cell(row=row_num, column=9, value=op.user.email if op.user else '-')

    # Ajustar ancho de columnas
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 30
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 10
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 18
    if current_user.role in ['Master', 'Operador']:
        ws.column_dimensions['I'].width = 30

    # Guardar en memoria
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    # Nombre del archivo con fecha actual
    filename = f"operaciones_del_dia_{now_peru().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )
```

### 2. Frontend - Botón de Exportación
**Archivo**: `app/templates/operations/list.html`

Se agregó un botón verde con icono de Excel en el header de la página:

```html
<!-- Header -->
<div class="row mb-4">
    <div class="col-md-8">
        <h2><i class="bi bi-list-ul"></i> Gestión de Operaciones</h2>
        <p class="text-muted">Operaciones del día actual</p>
    </div>
    <div class="col-md-4 text-end">
        <!-- Botón Exportar Excel (para todos los roles) -->
        <a href="/operations/api/export_today" class="btn btn-success me-2">
            <i class="bi bi-file-earmark-excel"></i> Exportar Excel
        </a>

        {% if user.role in ['Master', 'Trader'] %}
        <button type="button" class="btn btn-primary" onclick="openCreateOperationModal()">
            <i class="bi bi-plus-circle"></i> Nueva Operación
        </button>
        {% endif %}
    </div>
</div>
```

## Estructura del Archivo Excel

### Columnas para Master y Operador:
1. **ID OP.** - Código de la operación (Ej: EXP-1001)
2. **DOCUMENTO** - DNI o RUC del cliente
3. **CLIENTE** - Nombre completo o razón social
4. **USD** - Monto en dólares
5. **T.C.** - Tipo de cambio
6. **PEN** - Monto en soles
7. **ESTADO** - Pendiente / En proceso / Completada / Cancelado
8. **FECHA** - Fecha y hora de creación (formato: dd/mm/yyyy HH:MM)
9. **USUARIO** - Email del usuario que creó la operación

### Columnas para Trader:
1. **ID OP.** - Código de la operación
2. **DOCUMENTO** - DNI o RUC del cliente
3. **CLIENTE** - Nombre completo o razón social
4. **USD** - Monto en dólares
5. **T.C.** - Tipo de cambio
6. **PEN** - Monto en soles
7. **ESTADO** - Pendiente / En proceso / Completada / Cancelado
8. **FECHA** - Fecha y hora de creación

## Estilos del Excel

- **Encabezados**:
  - Fondo: Azul (#366092)
  - Texto: Blanco, Negrita
  - Alineación: Centrado

- **Datos**:
  - Formato de moneda para USD y PEN (números con 2 decimales)
  - Formato de tipo de cambio con 4 decimales
  - Fechas en formato dd/mm/yyyy HH:MM

- **Ancho de columnas**: Ajustado automáticamente para cada tipo de dato

## Nombre del Archivo

El archivo se descarga con el siguiente formato de nombre:
```
operaciones_del_dia_YYYYMMDD_HHMMSS.xlsx
```

Ejemplo:
```
operaciones_del_dia_20251122_143052.xlsx
```

## Diferencias con Exportación de Historial

| Característica | Operaciones del Día | Historial |
|----------------|---------------------|-----------|
| **Datos exportados** | Solo operaciones del día actual | Todas las operaciones históricas |
| **Nombre del archivo** | `operaciones_del_dia_...` | `historial_operaciones_...` |
| **Título de la hoja** | "Operaciones del Día" | "Historial de Operaciones" |
| **Estructura** | Idéntica | Idéntica |
| **Columnas** | Mismas columnas según rol | Mismas columnas según rol |
| **Ubicación del botón** | Menú "Operaciones" | Menú "Historial" |

## Accesibilidad

- ✅ **Disponible para todos los roles**: Master, Trader, Operador
- ✅ **No requiere permisos especiales**: Solo autenticación
- ✅ **Visible siempre**: El botón está disponible aunque no haya operaciones del día

## Comportamiento

1. **Con operaciones del día**:
   - Se descarga un archivo Excel con todas las operaciones del día
   - Incluye operaciones en todos los estados (Pendiente, En proceso, Completada, Cancelado)

2. **Sin operaciones del día**:
   - Se descarga un archivo Excel solo con los encabezados
   - El archivo no contiene filas de datos

## Ventajas de la Implementación

✅ **Reutilización de código**: Usa la misma lógica que la exportación de historial
✅ **Consistencia**: Misma estructura y estilos en ambas exportaciones
✅ **Filtrado automático**: Solo exporta operaciones del día actual
✅ **Diferenciación por rol**: Los roles Master y Operador ven la columna de Usuario
✅ **Descarga directa**: No requiere JavaScript, es un enlace simple
✅ **Sin límite de filas**: Exporta todas las operaciones sin paginación

## Archivos Modificados

1. `app/routes/operations.py` - Nuevo endpoint `/api/export_today`
2. `app/templates/operations/list.html` - Botón de exportación

## Cómo Usar

1. Ir al menú "Operaciones"
2. Hacer clic en el botón verde "Exportar Excel"
3. El navegador descargará automáticamente el archivo Excel
4. Abrir el archivo con Excel, LibreOffice Calc o cualquier programa compatible

## Notas Técnicas

- Usa la función `OperationService.get_today_operations()` para obtener solo operaciones del día actual
- El filtrado por fecha se hace en el servidor (Python/SQLAlchemy)
- El archivo se genera en memoria (BytesIO) sin guardarse en disco
- Compatible con Excel 2007+ (.xlsx)
- La zona horaria usada es America/Lima (Perú)

"""
Generador de MOF (Manual de Organización y Funciones) — QoriCash
Genera 3 PDFs independientes: Trader, Operador (Back Office), Middle Office
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, KeepTogether, Image
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'app', 'static', 'images', 'logo-principal.png'
)
W_UTIL = A4[0] - 4.4 * cm

# ─── Paleta de colores (minimalista) ───────────────────────────────────────────
BLACK      = colors.HexColor('#0D1B2A')
DARK_GRAY  = colors.HexColor('#374151')
MID_GRAY   = colors.HexColor('#6B7280')
LIGHT_GRAY = colors.HexColor('#9CA3AF')
RULE_GRAY  = colors.HexColor('#E5E7EB')
WHITE      = colors.white

# ─── Estilos de párrafo ────────────────────────────────────────────────────────
def build_styles():
    return {
        'company': ParagraphStyle(
            'company',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=LIGHT_GRAY,
            leading=13,
            alignment=TA_LEFT,
            letterSpacing=1.5,
        ),
        'role_label': ParagraphStyle(
            'role_label',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=MID_GRAY,
            leading=12,
            spaceAfter=4,
            letterSpacing=1.2,
        ),
        'role_title': ParagraphStyle(
            'role_title',
            fontName='Helvetica-Bold',
            fontSize=26,
            textColor=BLACK,
            leading=32,
            spaceAfter=6,
        ),
        'role_subtitle': ParagraphStyle(
            'role_subtitle',
            fontName='Helvetica',
            fontSize=13,
            textColor=DARK_GRAY,
            leading=19,
            spaceAfter=0,
        ),
        'section_title': ParagraphStyle(
            'section_title',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=BLACK,
            leading=14,
            spaceBefore=18,
            spaceAfter=8,
            letterSpacing=0.8,
        ),
        'body': ParagraphStyle(
            'body',
            fontName='Helvetica',
            fontSize=9.5,
            textColor=DARK_GRAY,
            leading=15,
            spaceAfter=4,
        ),
        'body_bold': ParagraphStyle(
            'body_bold',
            fontName='Helvetica-Bold',
            fontSize=9.5,
            textColor=BLACK,
            leading=15,
            spaceAfter=2,
        ),
        'bullet': ParagraphStyle(
            'bullet',
            fontName='Helvetica',
            fontSize=9.5,
            textColor=DARK_GRAY,
            leading=15,
            leftIndent=12,
            spaceAfter=3,
        ),
        'kpi_label': ParagraphStyle(
            'kpi_label',
            fontName='Helvetica-Bold',
            fontSize=8.5,
            textColor=BLACK,
            leading=12,
        ),
        'kpi_value': ParagraphStyle(
            'kpi_value',
            fontName='Helvetica',
            fontSize=8.5,
            textColor=DARK_GRAY,
            leading=12,
        ),
        'footer': ParagraphStyle(
            'footer',
            fontName='Helvetica',
            fontSize=7.5,
            textColor=LIGHT_GRAY,
            leading=11,
            alignment=TA_CENTER,
        ),
        'tag': ParagraphStyle(
            'tag',
            fontName='Helvetica',
            fontSize=8,
            textColor=MID_GRAY,
            leading=11,
        ),
    }

def rule(width_pct=1.0):
    return HRFlowable(
        width=f'{int(width_pct*100)}%',
        thickness=0.5,
        color=RULE_GRAY,
        spaceAfter=0,
        spaceBefore=0,
    )

def section_rule():
    return HRFlowable(
        width='100%',
        thickness=0.5,
        color=RULE_GRAY,
        spaceAfter=0,
        spaceBefore=14,
    )

def bullet_item(text, styles):
    return Paragraph(f'<font color="#9CA3AF">—</font>&nbsp;&nbsp;{text}', styles['bullet'])

def kpi_table(rows, styles):
    """rows: list of (kpi_name, descripcion)"""
    data = [[
        Paragraph(k, styles['kpi_label']),
        Paragraph(v, styles['kpi_value']),
    ] for k, v in rows]

    t = Table(data, colWidths=[5.5*cm, 11*cm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, colors.HexColor('#F9FAFB')]),
        ('BOX', (0, 0), (-1, -1), 0.5, RULE_GRAY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, RULE_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t

def relation_table(rows, styles):
    """rows: list of (area, descripcion)"""
    data = [[
        Paragraph(f'<b>{a}</b>', styles['kpi_label']),
        Paragraph(v, styles['kpi_value']),
    ] for a, v in rows]

    t = Table(data, colWidths=[4*cm, 12.5*cm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, colors.HexColor('#F9FAFB')]),
        ('BOX', (0, 0), (-1, -1), 0.5, RULE_GRAY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, RULE_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t

def build_header(role_area, role_title, role_subtitle, styles):
    """Construye el encabezado del documento."""
    logo = Image(LOGO_PATH, width=1.1*cm, height=1.1*cm) if os.path.exists(LOGO_PATH) else Spacer(1.1*cm, 1.1*cm)
    logo_row = Table(
        [[logo, Paragraph('QORICASH SAC  ·  RUC 20615113698', styles['company'])]],
        colWidths=[1.4*cm, W_UTIL - 1.4*cm],
    )
    logo_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [
        logo_row,
        Spacer(1, 0.15*cm),
        rule(),
        Spacer(1, 0.6*cm),
        Paragraph(f'MANUAL DE ORGANIZACIÓN Y FUNCIONES  ·  {role_area.upper()}', styles['role_label']),
        Spacer(1, 0.2*cm),
        Paragraph(role_title, styles['role_title']),
        Paragraph(role_subtitle, styles['role_subtitle']),
        Spacer(1, 0.5*cm),
        rule(),
    ]

def add_section(title, elements, styles, items_or_paragraphs):
    """Agrega una sección con título y contenido."""
    block = [
        section_rule(),
        Spacer(1, 0.1*cm),
        Paragraph(title.upper(), styles['section_title']),
    ]
    for item in items_or_paragraphs:
        block.append(item)
    elements.append(KeepTogether(block))

def build_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(LIGHT_GRAY)
    width, height = A4
    canvas.drawCentredString(
        width / 2, 1.2*cm,
        f'QORICASH SAC  ·  Manual de Organización y Funciones  ·  Uso Interno  ·  Página {doc.page}'
    )
    canvas.restoreState()


# ════════════════════════════════════════════════════════════════════════════════
# MOF 1: TRADER (COMERCIAL)
# ════════════════════════════════════════════════════════════════════════════════
def generate_trader_mof(output_path, styles):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2.2*cm,
        rightMargin=2.2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )
    elements = []
    elements += build_header(
        role_area='ÁREA COMERCIAL',
        role_title='Trader',
        role_subtitle='Ejecutivo comercial responsable de la relación con el cliente y la generación de volumen operativo.',
        styles=styles,
    )

    # 1. Descripción del rol
    add_section('1. Descripción del Rol', elements, styles, [
        Paragraph(
            'El Trader es el eje central del negocio. Gestiona la cartera de clientes asignada, '
            'registra operaciones de cambio de divisas (compra/venta de USD), coordina el proceso '
            'con el equipo de Back Office y mantiene una relación comercial sólida con cada cliente. '
            'Su desempeño impacta directamente en el volumen, la rentabilidad y la retención de clientes.',
            styles['body']
        ),
    ])

    # 2. Funciones principales
    add_section('2. Funciones Principales', elements, styles, [
        bullet_item('Captar y registrar nuevos clientes en el sistema QoriCash.', styles),
        bullet_item('Registrar operaciones de compra/venta de dólares en nombre del cliente.', styles),
        bullet_item('Negociar y fijar el tipo de cambio aplicable a cada operación dentro de los márgenes autorizados.', styles),
        bullet_item('Informar al cliente sobre las cuentas bancarias de destino para la transferencia.', styles),
        bullet_item('Monitorear el estado de las operaciones pendientes y hacer seguimiento proactivo.', styles),
        bullet_item('Comunicar al Back Office el inicio de cada operación para su procesamiento.', styles),
        bullet_item('Resolver dudas y reclamos de primer nivel de los clientes a su cargo.', styles),
        bullet_item('Mantener actualizada la información del cliente (cuentas bancarias, datos de contacto).', styles),
        bullet_item('Cumplir con la meta de volumen mensual asignada por la Gerencia.', styles),
        bullet_item('Reportar al Middle Office cualquier situación inusual o cliente de riesgo.', styles),
    ])

    # 3. Responsabilidades
    add_section('3. Responsabilidades', elements, styles, [
        bullet_item('Velar por la satisfacción y fidelización de los clientes asignados.', styles),
        bullet_item('Garantizar la exactitud de los datos ingresados en cada operación (monto, tipo de cambio, cuentas).', styles),
        bullet_item('Mantener la confidencialidad de la información financiera de los clientes.', styles),
        bullet_item('Cumplir con los procedimientos de KYC (Conoce a tu Cliente) establecidos por Compliance.', styles),
        bullet_item('No fijar tipos de cambio fuera del rango autorizado sin aprobación previa.', styles),
        bullet_item('Informar oportunamente cualquier operación inusual al Middle Office.', styles),
    ])

    # 4. Perfil del puesto
    add_section('4. Perfil del Puesto', elements, styles, [
        Paragraph('Hard Skills', styles['body_bold']),
        bullet_item('Conocimiento del mercado cambiario (USD/PEN) y factores que influyen en el tipo de cambio.', styles),
        bullet_item('Manejo de plataformas digitales y sistemas de gestión operativa.', styles),
        bullet_item('Dominio de transferencias bancarias y plataformas de banca online.', styles),
        bullet_item('Capacidad de negociación y cálculo financiero básico.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('Soft Skills', styles['body_bold']),
        bullet_item('Orientación al cliente y habilidades de comunicación efectiva.', styles),
        bullet_item('Proactividad y autonomía para la gestión de su cartera.', styles),
        bullet_item('Capacidad de trabajo bajo presión y en entornos de ritmo rápido.', styles),
        bullet_item('Honestidad, discreción y manejo ético de información financiera.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('Experiencia deseable', styles['body_bold']),
        bullet_item('Experiencia previa en casa de cambio, banco o fintech (1+ año preferible).', styles),
        bullet_item('Cartera de clientes propia o capacidad comprobada de prospección.', styles),
    ])

    # 5. KPIs
    add_section('5. Indicadores de Desempeño (KPIs)', elements, styles, [
        Spacer(1, 0.1*cm),
        kpi_table([
            ('Volumen mensual (USD)', 'Monto total operado en el mes vs. meta asignada.'),
            ('N° de operaciones', 'Cantidad de operaciones registradas en el período.'),
            ('Tasa de retención', 'Porcentaje de clientes activos vs. cartera total asignada.'),
            ('Tiempo de respuesta', 'Tiempo promedio entre el contacto del cliente y el registro de la operación.'),
            ('Captación de clientes', 'Nuevos clientes activados en el mes.'),
            ('Satisfacción del cliente', 'Nivel de incidencias o reclamos relacionados con su cartera.'),
        ], styles),
    ])

    # 6. Relación con otras áreas
    add_section('6. Relación con Otras Áreas', elements, styles, [
        Spacer(1, 0.1*cm),
        relation_table([
            ('Back Office', 'Coordina el procesamiento de cada operación registrada; le notifica depósitos recibidos y solicita confirmación del pago al cliente.'),
            ('Middle Office', 'Escala situaciones irregulares, consultas de compliance y soporte operativo de segundo nivel.'),
            ('Gerencia', 'Recibe metas mensuales, reporta desempeño comercial y solicita autorización para tipos de cambio especiales.'),
            ('Cliente', 'Punto de contacto principal; gestiona la relación comercial, coordina transferencias y mantiene informado al cliente durante todo el proceso.'),
        ], styles),
    ])

    doc.build(elements, onFirstPage=build_footer, onLaterPages=build_footer)
    print(f'✅ MOF Trader generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# MOF 2: OPERADOR / BACK OFFICE
# ════════════════════════════════════════════════════════════════════════════════
def generate_operator_mof(output_path, styles):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2.2*cm,
        rightMargin=2.2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )
    elements = []
    elements += build_header(
        role_area='ÁREA DE OPERACIONES — BACK OFFICE',
        role_title='Operador',
        role_subtitle='Responsable de la ejecución y verificación de las transferencias bancarias dentro del flujo de cada operación.',
        styles=styles,
    )

    # 1. Descripción del rol
    add_section('1. Descripción del Rol', elements, styles, [
        Paragraph(
            'El Operador es el ejecutor del proceso de cambio de divisas. Una vez que el Trader registra '
            'una operación, el Operador valida la recepción del abono del cliente, ejecuta la transferencia '
            'correspondiente y cierra la operación en el sistema. Su trabajo garantiza que cada transacción '
            'se complete de forma correcta, oportuna y con la documentación respaldatoria adecuada.',
            styles['body']
        ),
    ])

    # 2. Funciones principales
    add_section('2. Funciones Principales', elements, styles, [
        bullet_item('Revisar la cola de operaciones pendientes asignadas en el sistema QoriCash.', styles),
        bullet_item('Verificar la recepción del abono del cliente en la cuenta bancaria correspondiente (USD o PEN según el tipo de operación).', styles),
        bullet_item('Confirmar montos, cuentas de origen y datos del cliente antes de proceder.', styles),
        bullet_item('Ejecutar la transferencia al cliente por el monto y moneda acordados.', styles),
        bullet_item('Cargar el comprobante de transferencia (voucher) en el sistema.', styles),
        bullet_item('Marcar la operación como "Completada" en el sistema una vez verificado el envío.', styles),
        bullet_item('Coordinar con el Trader ante discrepancias en montos, cuentas o datos del cliente.', styles),
        bullet_item('Gestionar las cuentas bancarias propias de QoriCash: saldos, movimientos y conciliación diaria.', styles),
        bullet_item('Reportar al Middle Office cualquier operación con inconsistencias o señales de alerta.', styles),
        bullet_item('Mantener un registro ordenado de comprobantes y evidencia de cada operación procesada.', styles),
    ])

    # 3. Responsabilidades
    add_section('3. Responsabilidades', elements, styles, [
        bullet_item('Procesar cada operación dentro de los tiempos de respuesta establecidos.', styles),
        bullet_item('Verificar con rigor los datos antes de ejecutar cualquier transferencia (validación doble: monto y cuenta destino).', styles),
        bullet_item('Custodiar el acceso a las plataformas bancarias de la empresa.', styles),
        bullet_item('No ejecutar transferencias sin el comprobante de abono previo del cliente.', styles),
        bullet_item('Mantener la confidencialidad de los saldos y movimientos de cuentas de QoriCash.', styles),
        bullet_item('Registrar toda evidencia de las operaciones procesadas para auditoría.', styles),
    ])

    # 4. Perfil del puesto
    add_section('4. Perfil del Puesto', elements, styles, [
        Paragraph('Hard Skills', styles['body_bold']),
        bullet_item('Dominio de banca online (BCP, Interbank, BBVA, Scotiabank u otros).', styles),
        bullet_item('Manejo del sistema QoriCash para gestión de operaciones y carga de comprobantes.', styles),
        bullet_item('Conocimiento de transferencias interbancarias (CCI, CCE, transferencias en tiempo real).', styles),
        bullet_item('Capacidad de conciliación bancaria básica.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('Soft Skills', styles['body_bold']),
        bullet_item('Alta atención al detalle y precisión en el manejo de datos financieros.', styles),
        bullet_item('Capacidad para trabajar bajo presión y con múltiples operaciones simultáneas.', styles),
        bullet_item('Responsabilidad y ética en el manejo de fondos de terceros.', styles),
        bullet_item('Comunicación efectiva con el equipo de Traders y Middle Office.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('Experiencia deseable', styles['body_bold']),
        bullet_item('Experiencia en operaciones bancarias, tesorería o caja (1+ año preferible).', styles),
        bullet_item('Familiaridad con procesos de cambio de divisas o similar.', styles),
    ])

    # 5. KPIs
    add_section('5. Indicadores de Desempeño (KPIs)', elements, styles, [
        Spacer(1, 0.1*cm),
        kpi_table([
            ('Tiempo de procesamiento', 'Tiempo promedio entre la recepción del abono y la ejecución del pago al cliente.'),
            ('N° de operaciones/día', 'Cantidad de operaciones completadas por jornada de trabajo.'),
            ('Tasa de error', 'Porcentaje de operaciones con errores de transferencia (monto o cuenta incorrectos).'),
            ('Operaciones en mora', 'Operaciones que exceden el tiempo de procesamiento esperado.'),
            ('Conciliación diaria', 'Cumplimiento del cierre de caja y cuadre de saldos al final de cada jornada.'),
        ], styles),
    ])

    # 6. Relación con otras áreas
    add_section('6. Relación con Otras Áreas', elements, styles, [
        Spacer(1, 0.1*cm),
        relation_table([
            ('Trader', 'Recibe las operaciones registradas; coordina ante discrepancias en datos del cliente o montos.'),
            ('Middle Office', 'Reporta operaciones con alertas o irregularidades; recibe soporte ante situaciones fuera del procedimiento estándar.'),
            ('Gerencia', 'Rinde cuenta del volumen procesado, errores detectados y disponibilidad de liquidez en cuentas.'),
            ('Banco / Entidades financieras', 'Interactúa directamente para ejecutar transferencias y resolver incidencias bancarias.'),
        ], styles),
    ])

    doc.build(elements, onFirstPage=build_footer, onLaterPages=build_footer)
    print(f'✅ MOF Operador generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# MOF 3: MIDDLE OFFICE
# ════════════════════════════════════════════════════════════════════════════════
def generate_middle_office_mof(output_path, styles):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2.2*cm,
        rightMargin=2.2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )
    elements = []
    elements += build_header(
        role_area='ÁREA DE SOPORTE Y CONTROL — MIDDLE OFFICE',
        role_title='Middle Office',
        role_subtitle='Enlace entre el área comercial y operativa; responsable del control de calidad, compliance y gestión de incidencias.',
        styles=styles,
    )

    # 1. Descripción del rol
    add_section('1. Descripción del Rol', elements, styles, [
        Paragraph(
            'El Middle Office actúa como puente entre el Trader (Front Office) y el Operador (Back Office). '
            'Su función es garantizar que el flujo de operaciones se ejecute correctamente, que los riesgos '
            'estén controlados, y que cualquier incidencia sea resuelta con rapidez. Además, lidera la '
            'gestión de reclamos y el cumplimiento de procedimientos de compliance (KYC, AML), aportando '
            'control de calidad al ecosistema operativo de QoriCash.',
            styles['body']
        ),
    ])

    # 2. Funciones principales
    add_section('2. Funciones Principales', elements, styles, [
        bullet_item('Monitorear el estado general de operaciones en tiempo real desde el panel de control.', styles),
        bullet_item('Detectar y gestionar operaciones con demoras, errores o señales de alerta.', styles),
        bullet_item('Gestionar el Libro de Reclamaciones: recepción, seguimiento y cierre de reclamos dentro del plazo legal.', styles),
        bullet_item('Revisar y validar la documentación KYC de clientes nuevos o de alto riesgo.', styles),
        bullet_item('Realizar el screening de clientes en listas restrictivas (OFAC, ONU, PEP, etc.).', styles),
        bullet_item('Coordinar con el Trader la corrección de datos incorrectos en operaciones registradas.', styles),
        bullet_item('Autorizar modificaciones de importe en operaciones que requieran ajustes.', styles),
        bullet_item('Atender consultas de segundo nivel que el Trader no pueda resolver de forma autónoma.', styles),
        bullet_item('Elaborar reportes de incidencias, reclamos y alertas de compliance para la Gerencia.', styles),
        bullet_item('Velar por el cumplimiento de los procedimientos internos en todo el flujo operativo.', styles),
    ])

    # 3. Responsabilidades
    add_section('3. Responsabilidades', elements, styles, [
        bullet_item('Garantizar que todos los reclamos sean atendidos dentro del plazo establecido (máx. 30 días calendario).', styles),
        bullet_item('Asegurar que ningún cliente de alto riesgo o en lista restrictiva opere sin una revisión previa.', styles),
        bullet_item('Documentar todas las incidencias gestionadas con su respectiva resolución.', styles),
        bullet_item('Notificar a la Gerencia ante cualquier señal de actividad sospechosa o inusual.', styles),
        bullet_item('Mantener actualizado el perfil de riesgo de la cartera de clientes.', styles),
        bullet_item('Custodiar la confidencialidad de la información de clientes y operaciones sensibles.', styles),
    ])

    # 4. Perfil del puesto
    add_section('4. Perfil del Puesto', elements, styles, [
        Paragraph('Hard Skills', styles['body_bold']),
        bullet_item('Conocimiento de normativas AML/KYC aplicables a casas de cambio en Perú (SBS, UIF).', styles),
        bullet_item('Manejo del sistema QoriCash: panel de compliance, alertas, reclamos y auditoría.', styles),
        bullet_item('Capacidad de análisis y elaboración de reportes de gestión.', styles),
        bullet_item('Conocimiento básico de legislación sobre Libro de Reclamaciones (Decreto Legislativo 1096).', styles),
        Spacer(1, 0.2*cm),
        Paragraph('Soft Skills', styles['body_bold']),
        bullet_item('Pensamiento crítico y criterio para evaluar situaciones de riesgo.', styles),
        bullet_item('Habilidad para gestionar conflictos y mediar entre áreas.', styles),
        bullet_item('Capacidad de organización y seguimiento de múltiples casos simultáneos.', styles),
        bullet_item('Comunicación asertiva y capacidad de redacción formal.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('Experiencia deseable', styles['body_bold']),
        bullet_item('Experiencia en compliance, operaciones bancarias o control interno (1–2 años).', styles),
        bullet_item('Familiaridad con procesos de cambio de divisas y normativa SBS.', styles),
    ])

    # 5. KPIs
    add_section('5. Indicadores de Desempeño (KPIs)', elements, styles, [
        Spacer(1, 0.1*cm),
        kpi_table([
            ('Resolución de reclamos', 'Porcentaje de reclamos cerrados dentro del plazo legal (30 días).'),
            ('Alertas de compliance', 'N° de alertas detectadas y escaladas a Gerencia en el período.'),
            ('Tiempo de respuesta', 'Tiempo promedio de atención a incidencias reportadas por Traders u Operadores.'),
            ('Operaciones auditadas', 'Porcentaje de operaciones revisadas en los procesos de control de calidad.'),
            ('Clientes perfilados', 'Porcentaje de clientes activos con perfil de riesgo actualizado en el sistema.'),
            ('Cobertura de screening', 'Porcentaje de clientes nuevos sometidos a revisión en listas restrictivas.'),
        ], styles),
    ])

    # 6. Relación con otras áreas
    add_section('6. Relación con Otras Áreas', elements, styles, [
        Spacer(1, 0.1*cm),
        relation_table([
            ('Trader', 'Recibe escalaciones de clientes o situaciones que requieren revisión; valida documentación KYC; autoriza ajustes de operaciones.'),
            ('Back Office', 'Coordina ante operaciones bloqueadas, errores de procesamiento o alertas detectadas en el flujo.'),
            ('Gerencia', 'Reporta el estado de compliance, reclamos y riesgos; recibe lineamientos de política interna.'),
            ('Cliente (indirecto)', 'Gestiona reclamos directamente cuando el nivel de complejidad lo requiere; emite respuestas formales del Libro de Reclamaciones.'),
            ('Regulador / SBS', 'Garantiza que los procesos internos cumplan con la normativa vigente (AML/KYC); prepara información ante eventuales requerimientos.'),
        ], styles),
    ])

    doc.build(elements, onFirstPage=build_footer, onLaterPages=build_footer)
    print(f'✅ MOF Middle Office generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mof_docs')
    os.makedirs(output_dir, exist_ok=True)

    styles = build_styles()

    generate_trader_mof(os.path.join(output_dir, 'MOF_Trader_QoriCash.pdf'), styles)
    generate_operator_mof(os.path.join(output_dir, 'MOF_Operador_BackOffice_QoriCash.pdf'), styles)
    generate_middle_office_mof(os.path.join(output_dir, 'MOF_MiddleOffice_QoriCash.pdf'), styles)

    print(f'\n📁 PDFs generados en: {output_dir}')

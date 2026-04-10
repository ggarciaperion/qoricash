"""
Generador de Políticas Corporativas — QoriCash
PDFs: (1) Política General y Código de Conducta
      (2) Política de Confidencialidad y Seguridad de la Información
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, KeepTogether, PageBreak, Image
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'app', 'static', 'images', 'logo-principal.png'
)

# ─── Paleta ────────────────────────────────────────────────────────────────────
BLACK      = colors.HexColor('#0D1B2A')
DARK_GRAY  = colors.HexColor('#374151')
MID_GRAY   = colors.HexColor('#6B7280')
LIGHT_GRAY = colors.HexColor('#9CA3AF')
RULE_GRAY  = colors.HexColor('#E5E7EB')
WARN_GRAY  = colors.HexColor('#F3F4F6')
WHITE      = colors.white

W = A4[0] - 4.4*cm   # ancho útil

# ─── Estilos ───────────────────────────────────────────────────────────────────
def build_styles():
    return {
        'company': ParagraphStyle('company', fontName='Helvetica-Bold', fontSize=8,
                                  textColor=LIGHT_GRAY, leading=12, letterSpacing=1.5),
        'doc_label': ParagraphStyle('doc_label', fontName='Helvetica-Bold', fontSize=8,
                                    textColor=MID_GRAY, leading=12, letterSpacing=1.2, spaceAfter=4),
        'doc_title': ParagraphStyle('doc_title', fontName='Helvetica-Bold', fontSize=24,
                                    textColor=BLACK, leading=30, spaceAfter=6),
        'doc_subtitle': ParagraphStyle('doc_subtitle', fontName='Helvetica', fontSize=11,
                                       textColor=DARK_GRAY, leading=17, spaceAfter=0),
        'meta': ParagraphStyle('meta', fontName='Helvetica', fontSize=8,
                               textColor=LIGHT_GRAY, leading=12),
        'chapter': ParagraphStyle('chapter', fontName='Helvetica-Bold', fontSize=11,
                                  textColor=BLACK, leading=15, spaceBefore=20, spaceAfter=8,
                                  letterSpacing=0.6),
        'subsection': ParagraphStyle('subsection', fontName='Helvetica-Bold', fontSize=9.5,
                                     textColor=BLACK, leading=14, spaceBefore=10, spaceAfter=5),
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9.5,
                               textColor=DARK_GRAY, leading=15, spaceAfter=4, alignment=TA_JUSTIFY),
        'bullet': ParagraphStyle('bullet', fontName='Helvetica', fontSize=9.5,
                                 textColor=DARK_GRAY, leading=15, leftIndent=14, spaceAfter=3),
        'bullet_red': ParagraphStyle('bullet_red', fontName='Helvetica', fontSize=9.5,
                                     textColor=colors.HexColor('#374151'), leading=15,
                                     leftIndent=14, spaceAfter=3),
        'footer': ParagraphStyle('footer', fontName='Helvetica', fontSize=7,
                                 textColor=LIGHT_GRAY, leading=10, alignment=TA_CENTER),
        'notice': ParagraphStyle('notice', fontName='Helvetica-Bold', fontSize=8.5,
                                 textColor=colors.HexColor('#374151'), leading=13,
                                 alignment=TA_CENTER),
        'table_h': ParagraphStyle('table_h', fontName='Helvetica-Bold', fontSize=8.5,
                                  textColor=BLACK, leading=12),
        'table_b': ParagraphStyle('table_b', fontName='Helvetica', fontSize=8.5,
                                  textColor=DARK_GRAY, leading=12),
        'table_warn': ParagraphStyle('table_warn', fontName='Helvetica-Bold', fontSize=8.5,
                                     textColor=colors.HexColor('#B91C1C'), leading=12),
    }


def rule(color=RULE_GRAY, thickness=0.5):
    return HRFlowable(width='100%', thickness=thickness, color=color,
                      spaceAfter=0, spaceBefore=0)

def section_rule(s):
    return HRFlowable(width='100%', thickness=0.5, color=RULE_GRAY,
                      spaceBefore=14, spaceAfter=0)

def b(text, styles):
    return Paragraph(f'<font color="#9CA3AF">—</font>&nbsp;&nbsp;{text}', styles['bullet'])

def bx(text, styles):
    """Bullet con ✕ para prohibiciones."""
    return Paragraph(f'<font color="#6B7280">✕</font>&nbsp;&nbsp;{text}', styles['bullet_red'])

def chapter(num, title, elements, styles, content_blocks):
    block = [
        section_rule(styles),
        Spacer(1, 0.1*cm),
        Paragraph(f'{num}.&nbsp;&nbsp;{title.upper()}', styles['chapter']),
    ]
    for c in content_blocks:
        block.append(c)
    elements.append(KeepTogether(block[:4]))   # título + primeros párrafos juntos
    for c in block[4:]:
        elements.append(c)

def sanction_table(rows, styles):
    data = [
        [Paragraph('Gravedad', styles['table_h']),
         Paragraph('Ejemplo de falta', styles['table_h']),
         Paragraph('Consecuencia', styles['table_h'])],
    ]
    for g, e, c in rows:
        data.append([
            Paragraph(g, styles['table_warn'] if 'Grave' in g else styles['table_h']),
            Paragraph(e, styles['table_b']),
            Paragraph(c, styles['table_b']),
        ])
    t = Table(data, colWidths=[2.8*cm, 8*cm, 5.8*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F9FAFB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, colors.HexColor('#F9FAFB')]),
        ('BOX', (0, 0), (-1, -1), 0.5, RULE_GRAY),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, RULE_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
    ]))
    return t

def build_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(LIGHT_GRAY)
    w, h = A4
    canvas.drawCentredString(
        w / 2, 1.2*cm,
        f'QORICASH SAC  ·  Documento de Uso Interno Confidencial  ·  Página {doc.page}'
    )
    canvas.restoreState()

def build_header(doc_label, doc_title, doc_subtitle, version, styles):
    logo = Image(LOGO_PATH, width=1.1*cm, height=1.1*cm) if os.path.exists(LOGO_PATH) else Spacer(1.1*cm, 1.1*cm)
    logo_row = Table(
        [[logo, Paragraph('QORICASH SAC  ·  RUC 20615113698', styles['company'])]],
        colWidths=[1.4*cm, W - 1.4*cm],
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
        Paragraph(doc_label, styles['doc_label']),
        Spacer(1, 0.2*cm),
        Paragraph(doc_title, styles['doc_title']),
        Paragraph(doc_subtitle, styles['doc_subtitle']),
        Spacer(1, 0.35*cm),
        Paragraph(f'Versión {version}  ·  Lima, Perú  ·  Año 2025  ·  Confidencial — Uso Interno', styles['meta']),
        Spacer(1, 0.3*cm),
        rule(),
    ]


# ════════════════════════════════════════════════════════════════════════════════
# DOCUMENTO 1: POLÍTICA GENERAL Y CÓDIGO DE CONDUCTA
# ════════════════════════════════════════════════════════════════════════════════
def generate_politica_conducta(output_path, styles):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []

    E += build_header(
        doc_label='DOCUMENTO DE POLÍTICA CORPORATIVA',
        doc_title='Política General y Código de Conducta',
        doc_subtitle='Normas de comportamiento, ética profesional y obligaciones de todos los colaboradores de QoriCash.',
        version='1.0',
        styles=styles,
    )

    # ── PROPÓSITO ───────────────────────────────────────────────────────────────
    chapter('1', 'Propósito y Ámbito de Aplicación', E, styles, [
        Paragraph(
            'El presente documento establece las normas de conducta, principios éticos y obligaciones '
            'que rigen el comportamiento de todos los colaboradores de QORICASH SAC, con independencia '
            'de su cargo, modalidad de contratación o área de trabajo.',
            styles['body']),
        Paragraph(
            'Su cumplimiento es obligatorio desde el primer día de vinculación con la empresa. '
            'La ignorancia de su contenido no exime de responsabilidad ante incumplimientos.',
            styles['body']),
    ])

    # ── VALORES ─────────────────────────────────────────────────────────────────
    chapter('2', 'Valores Fundamentales de QoriCash', E, styles, [
        Paragraph(
            'Toda acción de los colaboradores debe estar alineada con los siguientes valores corporativos:',
            styles['body']),
        b('<b>Integridad:</b> actuar siempre con honestidad, transparencia y coherencia entre el discurso y la acción.', styles),
        b('<b>Responsabilidad:</b> cumplir con las funciones asignadas dentro del plazo y con la calidad esperada.', styles),
        b('<b>Confidencialidad:</b> proteger la información de la empresa y de los clientes como un activo estratégico.', styles),
        b('<b>Profesionalismo:</b> mantener una conducta respetuosa, puntual y orientada al resultado.', styles),
        b('<b>Cumplimiento:</b> acatar la normativa legal vigente, las regulaciones del sector y las políticas internas.', styles),
    ])

    # ── CONDUCTA EN EL TRABAJO ──────────────────────────────────────────────────
    chapter('3', 'Conducta Esperada en el Entorno Laboral', E, styles, [
        Paragraph(
            'Todo colaborador está obligado a mantener una conducta profesional dentro y fuera de las instalaciones '
            'de la empresa cuando actúe en nombre de QoriCash. Se espera:',
            styles['body']),
        b('Puntualidad y asistencia responsable.', styles),
        b('Trato respetuoso y cordial hacia compañeros, clientes y proveedores.', styles),
        b('Comunicación honesta y precisa sobre el estado de operaciones y tareas.', styles),
        b('Uso adecuado de los recursos de la empresa (equipos, sistemas, credenciales).', styles),
        b('Reportar errores o irregularidades de manera oportuna, sin ocultarlos.', styles),
        b('Mantener el orden y la discreción en espacios compartidos y conversaciones internas.', styles),
    ])

    # ── COMPORTAMIENTOS PROHIBIDOS ───────────────────────────────────────────────
    chapter('4', 'Comportamientos Estrictamente Prohibidos', E, styles, [
        Paragraph(
            'Las siguientes conductas constituyen faltas graves y pueden derivar en medidas disciplinarias '
            'inmediatas, incluyendo la desvinculación:',
            styles['body']),

        Paragraph('4.1  En el ejercicio del rol', styles['subsection']),
        bx('Registrar operaciones con datos incorrectos de manera intencional (montos, cuentas, tipos de cambio).', styles),
        bx('Fijar tipos de cambio fuera del rango autorizado sin aprobación previa de la Gerencia.', styles),
        bx('Completar operaciones en el sistema sin haber verificado la transferencia real del cliente.', styles),
        bx('Manipular el estado de una operación para encubrir errores o retrasos.', styles),
        bx('Registrar clientes o operaciones ficticias bajo cualquier justificación.', styles),
        bx('Alterar o eliminar evidencia (comprobantes, registros, imágenes) de operaciones procesadas.', styles),

        Spacer(1, 0.3*cm),
        Paragraph('4.2  En la relación con clientes', styles['subsection']),
        bx('Ofrecer tipos de cambio o condiciones no autorizadas para captar o retener clientes.', styles),
        bx('Aceptar comisiones, regalos o beneficios personales de clientes al margen del proceso formal.', styles),
        bx('Operar a título personal con clientes de la cartera de QoriCash sin autorización de la Gerencia.', styles),
        bx('Generar expectativas falsas o información engañosa sobre el proceso operativo.', styles),
        bx('Discriminar o dar trato diferenciado a clientes por razones no justificadas.', styles),

        Spacer(1, 0.3*cm),
        Paragraph('4.3  En el entorno digital y sistemas', styles['subsection']),
        bx('Acceder al sistema QoriCash con credenciales de otro colaborador.', styles),
        bx('Compartir usuario, contraseña o token de acceso a plataformas bancarias o al sistema.', styles),
        bx('Instalar software no autorizado en equipos de la empresa o con acceso a sistemas internos.', styles),
        bx('Usar el sistema para consultar operaciones o clientes fuera del alcance de su rol.', styles),
        bx('Exportar o descargar información de la base de datos sin autorización expresa.', styles),

        Spacer(1, 0.3*cm),
        Paragraph('4.4  En relaciones interpersonales y ambiente laboral', styles['subsection']),
        bx('Cualquier forma de acoso, hostigamiento, discriminación o violencia (física o verbal).', styles),
        bx('Comentarios despectivos sobre compañeros, clientes o directivos en cualquier canal.', styles),
        bx('Crear o difundir rumores internos que afecten la reputación de personas o de la empresa.', styles),
        bx('Realizar actividades personales o de negocio propio durante el horario de trabajo.', styles),
        bx('Competencia desleal: asesorar, derivar o captar clientes de QoriCash para beneficio propio o de terceros.', styles),
    ])

    # ── CONFLICTO DE INTERÉS ─────────────────────────────────────────────────────
    chapter('5', 'Conflicto de Interés', E, styles, [
        Paragraph(
            'Existe conflicto de interés cuando un colaborador tiene intereses personales, familiares o '
            'económicos que pueden influir —o parecer que influyen— en sus decisiones laborales.',
            styles['body']),
        Paragraph('Se considera conflicto de interés, entre otros:', styles['body']),
        bx('Trabajar simultáneamente (o tener participación) en una empresa competidora o casa de cambio.', styles),
        bx('Gestionar operaciones propias o de familiares directos a través del sistema de QoriCash.', styles),
        bx('Participar en decisiones que afecten a proveedores o clientes con los que se tenga vínculo personal o económico.', styles),
        bx('Recibir beneficios económicos de clientes o proveedores de la empresa.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'Cualquier situación que pueda configurar un conflicto de interés debe ser declarada '
            'de forma inmediata y por escrito a la Gerencia, independientemente de si se considera '
            'que afecta o no la toma de decisiones.',
            styles['body']),
    ])

    # ── RELACIONES CON CLIENTES ──────────────────────────────────────────────────
    chapter('6', 'Ética en la Relación con Clientes', E, styles, [
        Paragraph(
            'Los clientes son el activo más valioso de QoriCash. Toda interacción con ellos debe '
            'regirse por los principios de honestidad, trato justo y respeto a sus intereses.',
            styles['body']),
        b('Informar con precisión las condiciones de cada operación (tipo de cambio, tiempos, cuentas).', styles),
        b('No presionar al cliente para cerrar una operación en condiciones que no le favorecen.', styles),
        b('Respetar la decisión del cliente si decide no operar o cancelar una operación.', styles),
        b('Escalar oportunamente al Middle Office cualquier reclamo o situación de insatisfacción.', styles),
        b('Guardar absoluta reserva sobre las operaciones, montos e información personal de cada cliente.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            '<b>Prohibición específica:</b> está terminantemente prohibido revelar a un cliente información sobre '
            'las operaciones, tipos de cambio, saldos o datos personales de <i>otros</i> clientes.',
            styles['body']),
    ])

    # ── COMPLIANCE Y AML ─────────────────────────────────────────────────────────
    chapter('7', 'Cumplimiento Normativo (Compliance / AML)', E, styles, [
        Paragraph(
            'QoriCash opera como empresa de cambio de moneda sujeta a supervisión por parte de la '
            'SBS y obligada a cumplir las normas de prevención de Lavado de Activos y Financiamiento '
            'del Terrorismo (AML/CFT) establecidas en la legislación peruana.',
            styles['body']),
        Paragraph('Obligaciones de todos los colaboradores:', styles['body']),
        b('Solicitar y verificar la identidad del cliente antes de registrar cualquier operación (KYC).', styles),
        b('No operar con clientes cuya identidad no haya sido debidamente verificada.', styles),
        b('Reportar de forma inmediata al Middle Office o Gerencia cualquier operación que genere sospechas '
          '(montos inusuales, clientes reticentes a identificarse, operaciones fraccionadas, etc.).', styles),
        b('No alertar al cliente sobre el hecho de que su operación ha sido reportada como sospechosa.', styles),
        b('Cooperar plenamente con cualquier revisión interna o requerimiento de auditoría.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            '<b>El incumplimiento de las obligaciones AML puede derivar en responsabilidad penal '
            'para el colaborador involucrado, con independencia de las sanciones internas.</b>',
            styles['body']),
    ])

    # ── SANCIONES ────────────────────────────────────────────────────────────────
    chapter('8', 'Régimen de Sanciones', E, styles, [
        Paragraph(
            'El incumplimiento de las normas establecidas en este documento será evaluado '
            'y sancionado de forma proporcional a la gravedad de la falta:',
            styles['body']),
        Spacer(1, 0.2*cm),
        sanction_table([
            ('Leve',
             'Impuntualidad reiterada, uso inadecuado de recursos, descuidos menores en el sistema.',
             'Amonestación verbal o escrita.'),
            ('Moderada',
             'Incumplimiento de procedimientos, demoras injustificadas, errores no reportados.',
             'Amonestación escrita formal. Puede implicar suspensión temporal.'),
            ('Grave',
             'Violación de confidencialidad, manipulación de datos, conflicto de interés no declarado, acoso.',
             'Desvinculación inmediata. Posible acción legal.'),
            ('Muy grave',
             'Fraude, lavado de activos, apropiación de fondos, revelación de información a la competencia.',
             'Desvinculación inmediata y denuncia ante las autoridades competentes.'),
        ], styles),
    ])

    # ── DECLARACIÓN DE RECEPCIÓN ─────────────────────────────────────────────────
    E.append(Spacer(1, 0.6*cm))
    E.append(rule())
    E.append(Spacer(1, 0.4*cm))
    E.append(Paragraph(
        'DECLARACIÓN DE RECEPCIÓN Y ACEPTACIÓN',
        ParagraphStyle('decl_title', fontName='Helvetica-Bold', fontSize=9,
                       textColor=BLACK, leading=13, alignment=TA_CENTER, letterSpacing=0.8)
    ))
    E.append(Spacer(1, 0.3*cm))
    E.append(Paragraph(
        'El colaborador declara haber recibido, leído y comprendido el presente documento, '
        'aceptando su cumplimiento como condición de su vinculación con QORICASH SAC.',
        ParagraphStyle('decl_body', fontName='Helvetica', fontSize=9,
                       textColor=DARK_GRAY, leading=14, alignment=TA_CENTER)
    ))
    E.append(Spacer(1, 1.2*cm))
    sig_data = [
        [Paragraph('_______________________________', styles['body']),
         Paragraph('_______________________________', styles['body'])],
        [Paragraph('Nombre completo del colaborador', styles['meta']),
         Paragraph('Firma y fecha', styles['meta'])],
    ]
    sig_t = Table(sig_data, colWidths=[8*cm, 8*cm])
    sig_t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    E.append(sig_t)

    doc.build(E, onFirstPage=build_footer, onLaterPages=build_footer)
    print(f'✅ Política General generada: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# DOCUMENTO 2: POLÍTICA DE CONFIDENCIALIDAD Y SEGURIDAD DE LA INFORMACIÓN
# ════════════════════════════════════════════════════════════════════════════════
def generate_politica_confidencialidad(output_path, styles):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []

    E += build_header(
        doc_label='DOCUMENTO DE POLÍTICA CORPORATIVA',
        doc_title='Política de Confidencialidad y\nSeguridad de la Información',
        doc_subtitle='Qué información está prohibido compartir, cómo proteger los datos de clientes y sistemas de QoriCash.',
        version='1.0',
        styles=styles,
    )

    # ── PROPÓSITO ───────────────────────────────────────────────────────────────
    chapter('1', 'Propósito', E, styles, [
        Paragraph(
            'QoriCash maneja información financiera altamente sensible: datos personales de clientes, '
            'montos de operaciones, saldos de cuentas, tipos de cambio aplicados y estrategias comerciales. '
            'Esta política establece los principios y restricciones que todos los colaboradores deben cumplir '
            'para proteger dicha información, garantizar la privacidad de los clientes y preservar la '
            'reputación e integridad operativa de la empresa.',
            styles['body']),
    ])

    # ── CLASIFICACIÓN DE INFORMACIÓN ─────────────────────────────────────────────
    chapter('2', 'Clasificación de la Información', E, styles, [
        Paragraph(
            'Toda información generada, recibida o administrada en QoriCash se clasifica en tres niveles:',
            styles['body']),
        Spacer(1, 0.15*cm),

        # Tabla de clasificación
        Table([
            [Paragraph('Nivel', styles['table_h']),
             Paragraph('Descripción', styles['table_h']),
             Paragraph('Ejemplos', styles['table_h'])],
            [Paragraph('CONFIDENCIAL', styles['table_warn']),
             Paragraph('Solo puede acceder quien tenga necesidad directa de negocio.', styles['table_b']),
             Paragraph('Datos de clientes, saldos de cuentas, tipos de cambio aplicados, operaciones individuales, credenciales de sistemas.', styles['table_b'])],
            [Paragraph('INTERNO', styles['table_h']),
             Paragraph('Circula libremente entre colaboradores pero no debe salir de la empresa.', styles['table_b']),
             Paragraph('Procedimientos internos, metas de volumen, estructura de comisiones, reportes de desempeño.', styles['table_b'])],
            [Paragraph('PÚBLICO', styles['table_h']),
             Paragraph('Puede comunicarse al exterior sin restricciones.', styles['table_b']),
             Paragraph('Tipos de cambio publicados en la web, datos de contacto, información legal de la empresa.', styles['table_b'])],
        ],
        colWidths=[3.2*cm, 6.3*cm, 7.1*cm],
        style=TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F9FAFB')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, colors.HexColor('#F9FAFB')]),
            ('BOX', (0, 0), (-1, -1), 0.5, RULE_GRAY),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, RULE_GRAY),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ])),
    ])

    # ── INFORMACIÓN PROHIBIDA ────────────────────────────────────────────────────
    chapter('3', 'Información Estrictamente Prohibida de Compartir', E, styles, [
        Paragraph(
            'Queda absolutamente prohibido revelar, filtrar, comentar, reenviar o hacer accesible '
            'a terceros no autorizados —incluidos familiares, amistades o ex colaboradores— cualquiera '
            'de los siguientes elementos:',
            styles['body']),

        Paragraph('3.1  Datos de clientes', styles['subsection']),
        bx('Nombre completo, DNI/RUC, correo electrónico, teléfono o dirección de cualquier cliente.', styles),
        bx('Números de cuentas bancarias del cliente (ahorros, corriente, CCI).', styles),
        bx('Montos operados, frecuencia de operaciones o historial de transacciones.', styles),
        bx('Tipo de cambio pactado en operaciones individuales.', styles),
        bx('Condiciones especiales, descuentos o acuerdos comerciales pactados con un cliente específico.', styles),
        bx('Perfil de riesgo, clasificación KYC o alertas de compliance asociadas al cliente.', styles),

        Spacer(1, 0.3*cm),
        Paragraph('3.2  Información financiera y operativa de la empresa', styles['subsection']),
        bx('Saldos disponibles en cuentas bancarias de QoriCash en cualquier divisa.', styles),
        bx('Volumen diario, semanal o mensual de operaciones procesadas.', styles),
        bx('Márgenes de ganancia o rentabilidad por operación o por cartera.', styles),
        bx('Metas asignadas por trader o área, y nivel de cumplimiento.', styles),
        bx('Posición de cambio o exposición en divisas de la empresa.', styles),
        bx('Precios de compra/venta aplicados internamente antes de su publicación oficial.', styles),

        Spacer(1, 0.3*cm),
        Paragraph('3.3  Información de sistemas y accesos', styles['subsection']),
        bx('Credenciales de acceso al sistema QoriCash (usuario y contraseña).', styles),
        bx('Credenciales de plataformas bancarias de la empresa.', styles),
        bx('Estructura, lógica o configuración interna del sistema operativo de QoriCash.', styles),
        bx('Datos extraídos de reportes, exportaciones o bases de datos del sistema.', styles),
        bx('Cualquier información obtenida al utilizar accesos privilegiados del sistema.', styles),

        Spacer(1, 0.3*cm),
        Paragraph('3.4  Información estratégica y comercial', styles['subsection']),
        bx('Identidad de proveedores, corresponsales o contrapartes estratégicas.', styles),
        bx('Estrategias de fijación de precios, captación o retención de clientes.', styles),
        bx('Planes de expansión, nuevos servicios o proyectos en desarrollo.', styles),
        bx('Información sobre incidencias, disputas legales o reclamos formales en curso.', styles),
        bx('Conversaciones, acuerdos o negociaciones internas con la Gerencia.', styles),
    ])

    # ── CANALES PROHIBIDOS ───────────────────────────────────────────────────────
    chapter('4', 'Canales de Comunicación — Restricciones', E, styles, [
        Paragraph(
            'La información confidencial no debe transmitirse por canales no seguros o no autorizados. '
            'Se prohíbe específicamente:',
            styles['body']),
        bx('Enviar datos de clientes u operaciones por WhatsApp personal, Telegram, Instagram o cualquier red social.', styles),
        bx('Comentar información de operaciones en grupos de WhatsApp o chats que incluyan personas externas a QoriCash.', styles),
        bx('Reenviar correos internos con información de clientes o reportes a cuentas de correo personales.', styles),
        bx('Fotografiar o capturar pantallas del sistema QoriCash para compartirlas fuera de la empresa.', styles),
        bx('Comentar públicamente sobre clientes, operaciones o situaciones internas en redes sociales.', styles),
        bx('Almacenar información confidencial en servicios de nube personales (Google Drive personal, Dropbox, etc.).', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'Los únicos canales autorizados para la comunicación de información interna son: '
            'el correo corporativo de QoriCash, el sistema interno y los canales definidos por la Gerencia.',
            styles['body']),
    ])

    # ── USO DEL SISTEMA ──────────────────────────────────────────────────────────
    chapter('5', 'Uso Correcto del Sistema QoriCash', E, styles, [
        Paragraph(
            'El acceso al sistema es personal, intransferible y limitado al rol asignado. '
            'Cada colaborador es responsable de todas las acciones realizadas con sus credenciales.',
            styles['body']),
        b('Usar el sistema únicamente para las funciones propias del rol.', styles),
        b('Cerrar sesión al finalizar la jornada o al alejarse del equipo.', styles),
        b('Usar contraseñas robustas y cambiarlas si existe sospecha de compromiso.', styles),
        b('Reportar de inmediato al responsable de sistemas si se detecta un acceso no autorizado.', styles),
        Spacer(1, 0.2*cm),
        bx('Compartir credenciales de acceso bajo ninguna circunstancia.', styles),
        bx('Consultar información de clientes o operaciones que no correspondan al rol o cartera asignada.', styles),
        bx('Realizar modificaciones en registros sin autorización expresa.', styles),
        bx('Intentar acceder a módulos del sistema para los que no se tienen permisos.', styles),
    ])

    # ── REDES SOCIALES ───────────────────────────────────────────────────────────
    chapter('6', 'Política de Redes Sociales', E, styles, [
        Paragraph(
            'Los colaboradores pueden usar redes sociales de forma personal, pero deben tener en cuenta '
            'que su conducta pública puede afectar la imagen de QoriCash.',
            styles['body']),
        bx('Publicar o comentar información de clientes, operaciones o situaciones internas de la empresa.', styles),
        bx('Mencionar a QoriCash o sus marcas en publicaciones que dañen su reputación.', styles),
        bx('Simular representar oficialmente a la empresa sin autorización expresa.', styles),
        bx('Publicar tipos de cambio, promociones o condiciones comerciales no oficiales.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'Cualquier publicación que involucre a QoriCash de forma profesional debe ser coordinada '
            'previamente con la Gerencia.',
            styles['body']),
    ])

    # ── RESPONSABILIDAD POST DESVINCULACIÓN ──────────────────────────────────────
    chapter('7', 'Obligaciones Tras la Desvinculación', E, styles, [
        Paragraph(
            'La obligación de confidencialidad se extiende indefinidamente después de que el colaborador '
            'deje de trabajar en QoriCash. Al momento de la desvinculación:',
            styles['body']),
        b('El colaborador deberá devolver todos los equipos, accesos y documentación de la empresa.', styles),
        b('Se revocarán de inmediato todos los accesos al sistema, correo corporativo y plataformas.', styles),
        b('Queda prohibido retener, copiar o hacer uso de cualquier información obtenida durante la relación laboral.', styles),
        b('La cartera de clientes, contactos y datos obtenidos son propiedad exclusiva de QoriCash.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'El incumplimiento de estas obligaciones puede derivar en acciones legales civiles y penales '
            'por parte de QORICASH SAC, incluyendo reclamación de daños y perjuicios.',
            styles['body']),
    ])

    # ── SANCIONES ────────────────────────────────────────────────────────────────
    chapter('8', 'Consecuencias del Incumplimiento', E, styles, [
        Paragraph(
            'Cualquier violación a esta política será considerada una falta grave y podrá derivar en:',
            styles['body']),
        bx('Desvinculación inmediata sin reconocimiento de beneficios adicionales.', styles),
        bx('Denuncia ante la Unidad de Inteligencia Financiera (UIF) en caso de filtración de información vinculada a operaciones sospechosas.', styles),
        bx('Acción civil por daños y perjuicios derivados de la revelación de información confidencial.', styles),
        bx('Acción penal por violación de secreto de empresa o delitos informáticos, según corresponda.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'La gravedad de la sanción dependerá del impacto real o potencial de la violación, '
            'independientemente de si la filtración fue intencional o negligente.',
            styles['body']),
    ])

    # ── DECLARACIÓN ──────────────────────────────────────────────────────────────
    E.append(Spacer(1, 0.6*cm))
    E.append(rule())
    E.append(Spacer(1, 0.4*cm))
    E.append(Paragraph(
        'DECLARACIÓN DE CONFIDENCIALIDAD Y ACEPTACIÓN',
        ParagraphStyle('decl_title2', fontName='Helvetica-Bold', fontSize=9,
                       textColor=BLACK, leading=13, alignment=TA_CENTER, letterSpacing=0.8)
    ))
    E.append(Spacer(1, 0.3*cm))
    E.append(Paragraph(
        'El colaborador declara haber leído, comprendido y aceptado la Política de Confidencialidad '
        'y Seguridad de la Información de QORICASH SAC, comprometiéndose a su cumplimiento estricto '
        'durante y después de su vinculación con la empresa.',
        ParagraphStyle('decl_body2', fontName='Helvetica', fontSize=9,
                       textColor=DARK_GRAY, leading=14, alignment=TA_CENTER)
    ))
    E.append(Spacer(1, 1.2*cm))
    sig_data = [
        [Paragraph('_______________________________', styles['body']),
         Paragraph('_______________________________', styles['body'])],
        [Paragraph('Nombre completo del colaborador', styles['meta']),
         Paragraph('Firma y fecha', styles['meta'])],
    ]
    sig_t = Table(sig_data, colWidths=[8*cm, 8*cm])
    sig_t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    E.append(sig_t)

    doc.build(E, onFirstPage=build_footer, onLaterPages=build_footer)
    print(f'✅ Política de Confidencialidad generada: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mof_docs')
    os.makedirs(output_dir, exist_ok=True)

    styles = build_styles()

    generate_politica_conducta(
        os.path.join(output_dir, 'POL_ConductaYEtica_QoriCash.pdf'), styles)

    generate_politica_confidencialidad(
        os.path.join(output_dir, 'POL_Confidencialidad_QoriCash.pdf'), styles)

    print(f'\n📁 PDFs generados en: {output_dir}')

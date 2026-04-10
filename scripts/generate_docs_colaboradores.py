"""
Generador de Documentos para Colaboradores — QoriCash
PDFs:
  1. RIT_ReglamentoInterno_QoriCash.pdf
  2. MANUAL_Bienvenida_QoriCash.pdf
  3. POL_SeguridadTI_QoriCash.pdf
  4. PROT_AtencionCliente_QoriCash.pdf
  5. PROC_GestionIncidentes_QoriCash.pdf
  6. FORM_Compromisos_QoriCash.pdf
  7. PLAN_Capacitacion_QoriCash.pdf
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

W = A4[0] - 4.4 * cm

# ─── Estilos ───────────────────────────────────────────────────────────────────
def build_styles():
    return {
        'company':    ParagraphStyle('company',    fontName='Helvetica-Bold', fontSize=8,
                                     textColor=LIGHT_GRAY, leading=12, letterSpacing=1.5),
        'doc_label':  ParagraphStyle('doc_label',  fontName='Helvetica-Bold', fontSize=8,
                                     textColor=MID_GRAY,   leading=12, letterSpacing=1.2, spaceAfter=4),
        'doc_title':  ParagraphStyle('doc_title',  fontName='Helvetica-Bold', fontSize=24,
                                     textColor=BLACK,       leading=30, spaceAfter=6),
        'doc_subtitle':ParagraphStyle('doc_subtitle',fontName='Helvetica',    fontSize=11,
                                     textColor=DARK_GRAY,  leading=17, spaceAfter=0),
        'meta':       ParagraphStyle('meta',       fontName='Helvetica',    fontSize=8,
                                     textColor=LIGHT_GRAY, leading=12),
        'chapter':    ParagraphStyle('chapter',    fontName='Helvetica-Bold', fontSize=11,
                                     textColor=BLACK, leading=15, spaceBefore=20, spaceAfter=8,
                                     letterSpacing=0.6),
        'subsection': ParagraphStyle('subsection', fontName='Helvetica-Bold', fontSize=9.5,
                                     textColor=BLACK, leading=14, spaceBefore=10, spaceAfter=5),
        'body':       ParagraphStyle('body',       fontName='Helvetica',    fontSize=9.5,
                                     textColor=DARK_GRAY, leading=15, spaceAfter=4, alignment=TA_JUSTIFY),
        'body_c':     ParagraphStyle('body_c',     fontName='Helvetica',    fontSize=9.5,
                                     textColor=DARK_GRAY, leading=15, spaceAfter=4, alignment=TA_CENTER),
        'bullet':     ParagraphStyle('bullet',     fontName='Helvetica',    fontSize=9.5,
                                     textColor=DARK_GRAY, leading=15, leftIndent=14, spaceAfter=3),
        'bullet_x':   ParagraphStyle('bullet_x',   fontName='Helvetica',    fontSize=9.5,
                                     textColor=DARK_GRAY, leading=15, leftIndent=14, spaceAfter=3),
        'footer':     ParagraphStyle('footer',     fontName='Helvetica',    fontSize=7,
                                     textColor=LIGHT_GRAY, leading=10, alignment=TA_CENTER),
        'table_h':    ParagraphStyle('table_h',    fontName='Helvetica-Bold', fontSize=8.5,
                                     textColor=BLACK, leading=12),
        'table_b':    ParagraphStyle('table_b',    fontName='Helvetica',    fontSize=8.5,
                                     textColor=DARK_GRAY, leading=12),
        'table_w':    ParagraphStyle('table_w',    fontName='Helvetica-Bold', fontSize=8.5,
                                     textColor=colors.HexColor('#B91C1C'), leading=12),
        'notice':     ParagraphStyle('notice',     fontName='Helvetica-Bold', fontSize=9,
                                     textColor=BLACK, leading=14, alignment=TA_CENTER, letterSpacing=0.8),
        'notice_sub': ParagraphStyle('notice_sub', fontName='Helvetica',    fontSize=9,
                                     textColor=DARK_GRAY, leading=14, alignment=TA_CENTER),
        'sig_line':   ParagraphStyle('sig_line',   fontName='Helvetica',    fontSize=9.5,
                                     textColor=DARK_GRAY, leading=14, alignment=TA_CENTER),
        'sig_label':  ParagraphStyle('sig_label',  fontName='Helvetica',    fontSize=8,
                                     textColor=LIGHT_GRAY, leading=12, alignment=TA_CENTER),
    }

def rule():
    return HRFlowable(width='100%', thickness=0.5, color=RULE_GRAY, spaceAfter=0, spaceBefore=0)

def srule():
    return HRFlowable(width='100%', thickness=0.5, color=RULE_GRAY, spaceBefore=14, spaceAfter=0)

def b(text, styles):
    return Paragraph(f'<font color="#9CA3AF">—</font>&nbsp;&nbsp;{text}', styles['bullet'])

def bx(text, styles):
    return Paragraph(f'<font color="#6B7280">✕</font>&nbsp;&nbsp;{text}', styles['bullet_x'])

def bc(text, styles):
    return Paragraph(f'<font color="#374151">✓</font>&nbsp;&nbsp;{text}', styles['bullet'])

def chapter(num, title, elements, styles, content_blocks):
    block = [
        srule(),
        Spacer(1, 0.1*cm),
        Paragraph(f'{num}.&nbsp;&nbsp;{title.upper()}', styles['chapter']),
    ]
    for c in content_blocks:
        block.append(c)
    elements.append(KeepTogether(block[:4]))
    for c in block[4:]:
        elements.append(c)

def std_table(data, col_widths, styles):
    t = Table(data, colWidths=col_widths)
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

def build_header(doc_label, doc_title, doc_subtitle, version, footer_name, styles):
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
    ], footer_name

def signature_block(elements, styles, title, body_text):
    elements.append(Spacer(1, 0.6*cm))
    elements.append(rule())
    elements.append(Spacer(1, 0.4*cm))
    elements.append(Paragraph(title, styles['notice']))
    elements.append(Spacer(1, 0.25*cm))
    elements.append(Paragraph(body_text, styles['notice_sub']))
    elements.append(Spacer(1, 1.1*cm))
    sig = Table([
        [Paragraph('_______________________________', styles['sig_line']),
         Paragraph('_______________________________', styles['sig_line'])],
        [Paragraph('Nombre completo del colaborador', styles['sig_label']),
         Paragraph('Firma y fecha', styles['sig_label'])],
    ], colWidths=[8*cm, 8*cm])
    sig.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(sig)


def make_footer(doc_name):
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(LIGHT_GRAY)
        w, h = A4
        canvas.drawCentredString(
            w / 2, 1.2*cm,
            f'QORICASH SAC  ·  {doc_name}  ·  Uso Interno Confidencial  ·  Página {doc.page}'
        )
        canvas.restoreState()
    return footer


# ════════════════════════════════════════════════════════════════════════════════
# 1. REGLAMENTO INTERNO DE TRABAJO
# ════════════════════════════════════════════════════════════════════════════════
def generate_rit(output_path, styles):
    fn = 'Reglamento Interno de Trabajo'
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []
    header, _ = build_header(
        doc_label='REGLAMENTO INTERNO DE TRABAJO — D.S. 039-91-TR',
        doc_title='Reglamento Interno\nde Trabajo',
        doc_subtitle='QORICASH SAC — Normas de orden, asistencia, disciplina y convivencia interna aplicables a todos los trabajadores.',
        version='1.0',
        footer_name=fn,
        styles=styles,
    )
    E += header

    # ── CAP. I — GENERALIDADES ────────────────────────────────────────────────
    chapter('I', 'Generalidades', E, styles, [
        Paragraph(
            'El presente Reglamento Interno de Trabajo (en adelante, el Reglamento) ha sido elaborado '
            'conforme al artículo 104° del Decreto Legislativo N° 728 y el D.S. N° 039-91-TR, y es de '
            'cumplimiento obligatorio para todos los trabajadores de QORICASH SAC, cualquiera sea su '
            'cargo, modalidad contractual o área de trabajo, desde el primer día de labores.',
            styles['body']),
        Paragraph(
            'El desconocimiento de su contenido no exime de responsabilidad. El trabajador declara '
            'haber recibido y leído el presente documento al momento de su incorporación.',
            styles['body']),
        Paragraph(
            '<b>Base legal:</b> D.Leg. N° 728 — Ley de Productividad y Competitividad Laboral · '
            'D.S. N° 039-91-TR · Ley N° 29783 — Ley de Seguridad y Salud en el Trabajo · '
            'D.Leg. N° 1057 (CAS) · demás normas laborales vigentes.',
            styles['body']),
    ])

    # ── CAP. II — ADMISIÓN E INGRESO ─────────────────────────────────────────
    chapter('II', 'Admisión e Ingreso del Personal', E, styles, [
        Paragraph(
            'La selección y contratación del personal es facultad exclusiva de la Gerencia de '
            'QORICASH SAC. Para el ingreso se requerirá como mínimo:',
            styles['body']),
        b('Presentación de DNI vigente y documentos que acrediten formación o experiencia.', styles),
        b('Suscripción del contrato individual de trabajo y documentos de incorporación.', styles),
        b('Lectura y firma del presente Reglamento, la Política de Conducta y demás políticas internas.', styles),
        b('Apertura de cuenta de ahorros en la entidad bancaria que indique la empresa para el pago de haberes.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('Período de prueba:', styles['subsection']),
        Paragraph(
            'El período de prueba es de <b>3 meses</b> para trabajadores en general, durante el cual '
            'cualquiera de las partes puede resolver el vínculo sin expresión de causa ni indemnización. '
            'Para cargos de confianza o dirección el período podrá extenderse hasta 6 meses conforme a ley.',
            styles['body']),
    ])

    # ── CAP. III — JORNADA Y HORARIO DE TRABAJO ───────────────────────────────
    chapter('III', 'Jornada y Horario de Trabajo', E, styles, [
        Paragraph(
            'La jornada máxima es de 8 horas diarias o 48 horas semanales. El horario de trabajo '
            'de QORICASH SAC es el siguiente:',
            styles['body']),
        Spacer(1, 0.15*cm),
        std_table([
            [Paragraph('Días', styles['table_h']),
             Paragraph('Ingreso', styles['table_h']),
             Paragraph('Refrigerio', styles['table_h']),
             Paragraph('Salida', styles['table_h'])],
            [Paragraph('Lunes a Viernes', styles['table_b']),
             Paragraph('09:00 a.m.', styles['table_b']),
             Paragraph('01:00 – 02:00 p.m.', styles['table_b']),
             Paragraph('06:00 p.m.', styles['table_b'])],
            [Paragraph('Sábado', styles['table_b']),
             Paragraph('09:00 a.m.', styles['table_b']),
             Paragraph('No aplica', styles['table_b']),
             Paragraph('01:00 p.m. (según rol)', styles['table_b'])],
        ], [4.5*cm, 3*cm, 4.5*cm, 4.6*cm], styles),
        Spacer(1, 0.25*cm),
        Paragraph(
            'La Gerencia podrá modificar los horarios mediante comunicación escrita con un mínimo de '
            '48 horas de anticipación, siempre dentro de los límites legales.',
            styles['body']),
        Spacer(1, 0.1*cm),
        Paragraph('Trabajo en sobretiempo:', styles['subsection']),
        Paragraph(
            'El trabajo en horas extras es voluntario y debe ser autorizado previamente por la Gerencia. '
            'Su compensación se rige por el D.Leg. N° 854 y sus modificatorias. El trabajador que se '
            'niegue a laborar horas extras no podrá ser sancionado por ello.',
            styles['body']),
        Paragraph('Trabajo remoto:', styles['subsection']),
        Paragraph(
            'El trabajo remoto requiere autorización expresa de la Gerencia para cada caso. '
            'Bajo esta modalidad rigen las mismas normas de horario, disponibilidad y obligaciones '
            'que en el trabajo presencial.',
            styles['body']),
    ])

    # ── CAP. IV — ASISTENCIA, PUNTUALIDAD Y CONTROL ───────────────────────────
    chapter('IV', 'Asistencia, Puntualidad y Control de Presencia', E, styles, [
        Paragraph(
            'El trabajador está obligado a registrar su ingreso y salida diariamente mediante el '
            'mecanismo dispuesto por la empresa (registro digital, aplicativo u otro). '
            'La omisión del registro sin justificación se considerará inasistencia.',
            styles['body']),
        Spacer(1, 0.1*cm),
        Paragraph('Tardanza:', styles['subsection']),
        Paragraph(
            'Se considera tardanza el ingreso después de los 5 minutos de tolerancia del horario '
            'establecido. Tres tardanzas injustificadas en un mes calendario equivalen a una falta '
            'injustificada. Las tardanzas son descontables de forma proporcional al tiempo no laborado.',
            styles['body']),
        Paragraph('Inasistencia:', styles['subsection']),
        Paragraph(
            'Toda inasistencia debe ser comunicada a la Gerencia antes de las 9:00 a.m. del día '
            'de la ausencia, indicando el motivo. La inasistencia injustificada genera descuento '
            'de haberes y, si se repite, puede configurar causal de sanción disciplinaria.',
            styles['body']),
        Paragraph('Inasistencias justificadas — documentación requerida:', styles['subsection']),
        std_table([
            [Paragraph('Motivo', styles['table_h']),
             Paragraph('Documento que acredita', styles['table_h']),
             Paragraph('Plazo para presentar', styles['table_h'])],
            [Paragraph('Enfermedad', styles['table_b']),
             Paragraph('Descanso médico EsSalud o certificado médico de clínica reconocida.', styles['table_b']),
             Paragraph('Máx. 3 días hábiles luego de reincorporarse.', styles['table_b'])],
            [Paragraph('Fallecimiento familiar directo', styles['table_b']),
             Paragraph('Partida de defunción o esquela.', styles['table_b']),
             Paragraph('Al reincorporarse.', styles['table_b'])],
            [Paragraph('Citación judicial o policial', styles['table_b']),
             Paragraph('Cédula de notificación original.', styles['table_b']),
             Paragraph('Antes o el mismo día de la citación.', styles['table_b'])],
            [Paragraph('Accidente o emergencia', styles['table_b']),
             Paragraph('Documento de atención de emergencia o declaración jurada.', styles['table_b']),
             Paragraph('Máx. 2 días hábiles.', styles['table_b'])],
        ], [4*cm, 7.5*cm, 5.1*cm], styles),
    ])

    # ── CAP. V — PERMISOS Y LICENCIAS ─────────────────────────────────────────
    chapter('V', 'Permisos y Licencias', E, styles, [
        Paragraph(
            'Los permisos deben solicitarse con un mínimo de <b>24 horas de anticipación</b> —salvo '
            'emergencia debidamente justificada— mediante comunicación directa a la Gerencia. '
            'No se otorgarán permisos verbales sin registro. La Gerencia podrá aprobar o denegar '
            'el permiso considerando las necesidades operativas de la empresa.',
            styles['body']),
        Spacer(1, 0.15*cm),
        std_table([
            [Paragraph('Tipo de permiso', styles['table_h']),
             Paragraph('Duración máxima', styles['table_h']),
             Paragraph('Procedimiento', styles['table_h'])],
            [Paragraph('Cita médica o trámite de salud', styles['table_b']),
             Paragraph('Horas necesarias.', styles['table_b']),
             Paragraph('Comunicación previa + presentación de comprobante.', styles['table_b'])],
            [Paragraph('Trámite administrativo o judicial', styles['table_b']),
             Paragraph('Medio día.', styles['table_b']),
             Paragraph('Solicitud escrita con 24 h de anticipación.', styles['table_b'])],
            [Paragraph('Diligencia personal urgente', styles['table_b']),
             Paragraph('Medio día, máx. 1 vez al mes.', styles['table_b']),
             Paragraph('Solicitud y aprobación de Gerencia.', styles['table_b'])],
            [Paragraph('Capacitación o estudios', styles['table_b']),
             Paragraph('Según cronograma del programa.', styles['table_b']),
             Paragraph('Aprobación de Gerencia; coordinación previa.', styles['table_b'])],
            [Paragraph('Matrimonio civil', styles['table_b']),
             Paragraph('5 días calendario (Ley N° 27942).', styles['table_b']),
             Paragraph('Acta de matrimonio al reincorporarse.', styles['table_b'])],
            [Paragraph('Fallecimiento de familiar directo', styles['table_b']),
             Paragraph('5 días calendario.', styles['table_b']),
             Paragraph('Documentación sustentatoria al reincorporarse.', styles['table_b'])],
            [Paragraph('Maternidad / Paternidad', styles['table_b']),
             Paragraph('Según Ley N° 26644 y N° 29409.', styles['table_b']),
             Paragraph('Constancia médica o acta de nacimiento.', styles['table_b'])],
        ], [4.5*cm, 4*cm, 8.1*cm], styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'Los permisos no remunerados deberán acordarse expresamente por escrito. '
            'Todo permiso no autorizado se registrará como inasistencia injustificada.',
            styles['body']),
    ])

    # ── CAP. VI — NORMAS DE CONDUCTA Y ORDEN INTERNO ─────────────────────────
    chapter('VI', 'Normas de Conducta y Orden Interno', E, styles, [
        Paragraph(
            'Durante la jornada de trabajo y en las instalaciones de la empresa, '
            'el trabajador debe observar las siguientes normas:',
            styles['body']),
        Spacer(1, 0.1*cm),
        Paragraph('Presentación y permanencia:', styles['subsection']),
        b('Presentarse con vestimenta apropiada al rol desempeñado y al trato con clientes.', styles),
        b('Permanecer en el puesto de trabajo durante la jornada, salvo autorización para ausentarse.', styles),
        b('Comunicar a la Gerencia antes de salir de las instalaciones durante el horario de trabajo.', styles),
        b('No ausentarse del área de trabajo para actividades personales sin autorización previa.', styles),
        Spacer(1, 0.15*cm),
        Paragraph('Trato y convivencia:', styles['subsection']),
        b('Mantener trato respetuoso y cordial con todos los compañeros de trabajo, clientes y proveedores.', styles),
        b('Evitar conversaciones, bromas o comportamientos que generen incomodidad en el ambiente laboral.', styles),
        b('No introducir personas ajenas a la empresa en las áreas de trabajo sin autorización.', styles),
        Spacer(1, 0.15*cm),
        Paragraph('Uso del espacio de trabajo:', styles['subsection']),
        b('Mantener el área de trabajo ordenada y limpia al iniciar y al finalizar la jornada.', styles),
        b('No consumir alimentos en las áreas de trabajo que interfieran con la operación o el orden.', styles),
        b('Está prohibido el consumo de bebidas alcohólicas o sustancias psicoactivas en horario de trabajo o dentro de las instalaciones.', styles),
        b('No realizar actividades personales (llamadas extensas, compras online, redes sociales) en horario de trabajo.', styles),
    ])

    # ── CAP. VII — USO DE BIENES E INSTALACIONES DE LA EMPRESA ───────────────
    chapter('VII', 'Uso de Bienes, Sistemas e Instalaciones de la Empresa', E, styles, [
        Paragraph(
            'Los equipos, sistemas, credenciales y demás activos de la empresa son de uso '
            'exclusivamente laboral. El trabajador es responsable de los bienes a su cargo desde '
            'el momento de su entrega hasta su devolución.',
            styles['body']),
        b('Usar los equipos y sistemas solo para funciones propias del cargo.', styles),
        b('Reportar de inmediato cualquier daño, mal funcionamiento o pérdida de un bien de la empresa.', styles),
        b('No instalar programas, aplicaciones ni extensiones en equipos de la empresa sin autorización.', styles),
        b('No utilizar las conexiones o cuentas de la empresa para fines personales.', styles),
        b('Al término de la jornada, cerrar sesión en todos los sistemas y dejar los equipos en el estado y lugar asignados.', styles),
        b('Al producirse el cese laboral, el trabajador deberá devolver todos los bienes asignados el último día de trabajo.', styles),
        Spacer(1, 0.15*cm),
        Paragraph(
            'El deterioro o pérdida por negligencia o mal uso podrá generar responsabilidad '
            'económica a cargo del trabajador, de acuerdo con el valor del bien afectado.',
            styles['body']),
    ])

    # ── CAP. VIII — INFRACCIONES Y SANCIONES ─────────────────────────────────
    chapter('VIII', 'Infracciones y Sanciones', E, styles, [
        Paragraph(
            'Las infracciones al presente Reglamento y a las políticas internas serán sancionadas '
            'de forma proporcional a su gravedad. La empresa clasifica las infracciones en tres niveles:',
            styles['body']),
        Spacer(1, 0.2*cm),

        Paragraph('Infracciones leves:', styles['subsection']),
        std_table([
            [Paragraph('Infracción', styles['table_h']),
             Paragraph('Sanción aplicable', styles['table_h'])],
            [Paragraph('Tardanza injustificada (1 a 2 en el mes).', styles['table_b']),
             Paragraph('Descuento proporcional al tiempo no laborado. Registro en legajo.', styles['table_b'])],
            [Paragraph('Incumplimiento del registro de asistencia sin justificación.', styles['table_b']),
             Paragraph('Amonestación verbal. Registro en legajo.', styles['table_b'])],
            [Paragraph('Desorden o falta de limpieza en el área de trabajo.', styles['table_b']),
             Paragraph('Amonestación verbal.', styles['table_b'])],
            [Paragraph('Uso de redes sociales o actividades personales en horario de trabajo.', styles['table_b']),
             Paragraph('Amonestación verbal. Segunda vez: amonestación escrita.', styles['table_b'])],
            [Paragraph('No comunicar una ausencia antes de las 9:00 a.m.', styles['table_b']),
             Paragraph('Descuento del día. Amonestación verbal si se repite.', styles['table_b'])],
        ], [9*cm, 7.6*cm], styles),

        Spacer(1, 0.3*cm),
        Paragraph('Infracciones graves:', styles['subsection']),
        std_table([
            [Paragraph('Infracción', styles['table_h']),
             Paragraph('Sanción aplicable', styles['table_h'])],
            [Paragraph('Tres o más tardanzas injustificadas en el mismo mes.', styles['table_b']),
             Paragraph('Amonestación escrita. Reincidencia: suspensión 1-3 días.', styles['table_b'])],
            [Paragraph('Inasistencia injustificada.', styles['table_b']),
             Paragraph('Descuento del día. Amonestación escrita. Segunda vez: suspensión.', styles['table_b'])],
            [Paragraph('Incumplimiento reiterado de instrucciones o procedimientos de trabajo.', styles['table_b']),
             Paragraph('Amonestación escrita. Suspensión de 1 a 5 días según gravedad.', styles['table_b'])],
            [Paragraph('Uso inadecuado o negligente de bienes de la empresa.', styles['table_b']),
             Paragraph('Amonestación escrita. Responsabilidad económica por daños.', styles['table_b'])],
            [Paragraph('Trato irrespetuoso o agresivo hacia un compañero o cliente.', styles['table_b']),
             Paragraph('Suspensión de 1 a 5 días. Reincidencia: causal de despido.', styles['table_b'])],
            [Paragraph('Divulgación de información interna sin autorización.', styles['table_b']),
             Paragraph('Suspensión inmediata. Evaluación de causal de despido.', styles['table_b'])],
        ], [9*cm, 7.6*cm], styles),

        Spacer(1, 0.3*cm),
        Paragraph('Infracciones muy graves (causales de despido justificado — Art. 25° D.Leg. 728):', styles['subsection']),
        std_table([
            [Paragraph('Infracción', styles['table_h']),
             Paragraph('Consecuencia', styles['table_h'])],
            [Paragraph('Inasistencia injustificada por 3 días consecutivos o más de 5 en 30 días.', styles['table_b']),
             Paragraph('Despido justificado por abandono.', styles['table_b'])],
            [Paragraph('Falsificación de documentos o datos en el sistema.', styles['table_b']),
             Paragraph('Despido justificado. Denuncia penal si aplica.', styles['table_b'])],
            [Paragraph('Apropiación de dinero, bienes o información de la empresa o de clientes.', styles['table_b']),
             Paragraph('Despido justificado. Denuncia penal.', styles['table_b'])],
            [Paragraph('Revelación de información confidencial a terceros no autorizados.', styles['table_b']),
             Paragraph('Despido justificado. Acción civil y/o penal por daños.', styles['table_b'])],
            [Paragraph('Acoso sexual o laboral debidamente comprobado.', styles['table_b']),
             Paragraph('Despido justificado. Comunicación a la autoridad competente.', styles['table_b'])],
            [Paragraph('Concurrencia al trabajo en estado de ebriedad o bajo efecto de sustancias.', styles['table_b']),
             Paragraph('Suspensión inmediata. Segunda vez: despido justificado.', styles['table_b'])],
            [Paragraph('Conducta dolosa que cause perjuicio económico a la empresa.', styles['table_b']),
             Paragraph('Despido justificado. Acción civil.', styles['table_b'])],
        ], [9*cm, 7.6*cm], styles),
    ])

    # ── CAP. IX — PROCEDIMIENTO DISCIPLINARIO ─────────────────────────────────
    chapter('IX', 'Procedimiento Disciplinario', E, styles, [
        Paragraph(
            'Ninguna sanción se aplicará sin seguir el procedimiento establecido a continuación, '
            'respetando el derecho de defensa del trabajador:',
            styles['body']),
        Spacer(1, 0.15*cm),
        std_table([
            [Paragraph('Paso', styles['table_h']),
             Paragraph('Acción', styles['table_h']),
             Paragraph('Responsable', styles['table_h'])],
            [Paragraph('1. Detección', styles['table_b']),
             Paragraph('Identificación de la infracción. Registro de los hechos con fecha, hora y descripción.', styles['table_b']),
             Paragraph('Supervisor / Gerencia.', styles['table_b'])],
            [Paragraph('2. Imputación', styles['table_b']),
             Paragraph('Comunicación escrita al trabajador describiendo la falta imputada y la sanción provisional considerada.', styles['table_b']),
             Paragraph('Gerencia.', styles['table_b'])],
            [Paragraph('3. Descargo', styles['table_b']),
             Paragraph('El trabajador tiene un plazo mínimo de 3 días hábiles para presentar su descargo por escrito.', styles['table_b']),
             Paragraph('Trabajador.', styles['table_b'])],
            [Paragraph('4. Evaluación', styles['table_b']),
             Paragraph('La Gerencia evalúa el descargo, los antecedentes del trabajador y la gravedad de la falta.', styles['table_b']),
             Paragraph('Gerencia.', styles['table_b'])],
            [Paragraph('5. Resolución', styles['table_b']),
             Paragraph('Comunicación escrita de la sanción definitiva o del archivo del caso. El trabajador firma en señal de notificación (sin que ello implique aceptación).', styles['table_b']),
             Paragraph('Gerencia.', styles['table_b'])],
        ], [3*cm, 9.5*cm, 4.1*cm], styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'La negativa del trabajador a recibir la comunicación no invalida el procedimiento. '
            'En ese caso, se dejará constancia mediante acta con la firma de dos testigos.',
            styles['body']),
    ])

    # ── CAP. X — QUEJAS Y RECLAMOS DEL TRABAJADOR ────────────────────────────
    chapter('X', 'Quejas y Consultas del Trabajador', E, styles, [
        Paragraph(
            'El trabajador tiene derecho a presentar quejas, consultas o reclamos relacionados con '
            'su condición laboral sin temor a represalias. El procedimiento es el siguiente:',
            styles['body']),
        b('<b>Paso 1:</b> Comunicación directa al supervisor inmediato o a la Gerencia, de forma oral o escrita.', styles),
        b('<b>Paso 2:</b> La Gerencia acusará recibo de la queja dentro de los 2 días hábiles siguientes.', styles),
        b('<b>Paso 3:</b> Se investigará el caso y se emitirá una respuesta en un plazo máximo de 10 días hábiles.', styles),
        b('<b>Paso 4:</b> Si el trabajador no está conforme, puede recurrir a la Autoridad Administrativa de Trabajo (AAT) o al Poder Judicial.', styles),
        Spacer(1, 0.15*cm),
        Paragraph(
            'Las quejas relacionadas con acoso u hostigamiento sexual se tramitarán conforme '
            'al protocolo específico establecido en la Ley N° 27942 y su reglamento.',
            styles['body']),
    ])

    # ── CAP. XI — SEGURIDAD Y SALUD EN EL TRABAJO ────────────────────────────
    chapter('XI', 'Seguridad y Salud en el Trabajo', E, styles, [
        Paragraph(
            'QORICASH SAC cumple la Ley N° 29783 y su Reglamento (D.S. N° 005-2012-TR). '
            'Los trabajadores tienen las siguientes obligaciones en materia de SST:',
            styles['body']),
        b('Cumplir las normas de seguridad y salud dispuestas por la empresa.', styles),
        b('Usar correctamente los equipos o implementos de seguridad proporcionados por la empresa.', styles),
        b('Reportar de forma inmediata a la Gerencia cualquier condición de riesgo, accidente o incidente, por menor que parezca.', styles),
        b('No manipular, alterar ni retirar los sistemas o dispositivos de seguridad instalados en las instalaciones.', styles),
        b('Participar en las capacitaciones y simulacros de seguridad que la empresa programe.', styles),
        b('No presentarse al trabajo bajo los efectos de alcohol, medicamentos que afecten el desempeño o sustancias psicoactivas.', styles),
        Spacer(1, 0.15*cm),
        Paragraph(
            'Todo accidente de trabajo, ocurrido en las instalaciones o durante la jornada laboral, '
            'debe ser reportado de inmediato. La empresa gestionará la atención médica a través de EsSalud '
            'y completará el registro obligatorio en el plazo establecido por ley.',
            styles['body']),
    ])

    # ── CAP. XII — DISPOSICIONES FINALES ─────────────────────────────────────
    chapter('XII', 'Disposiciones Finales', E, styles, [
        Paragraph(
            'Todo lo no previsto en el presente Reglamento se regirá por las normas laborales '
            'peruanas vigentes y los principios generales del Derecho del Trabajo.',
            styles['body']),
        Paragraph(
            'El presente Reglamento puede ser modificado por la Gerencia cuando las necesidades '
            'operativas o cambios normativos así lo requieran, con comunicación previa a los trabajadores '
            'con un mínimo de 5 días hábiles de anticipación.',
            styles['body']),
        Paragraph(
            'El presente Reglamento Interno de Trabajo entra en vigencia a partir de la fecha '
            'de su aprobación por la Gerencia General de QORICASH SAC.',
            styles['body']),
        Spacer(1, 0.3*cm),
        std_table([
            [Paragraph('Versión', styles['table_h']),
             Paragraph('Fecha de aprobación', styles['table_h']),
             Paragraph('Aprobado por', styles['table_h']),
             Paragraph('Vigencia desde', styles['table_h'])],
            [Paragraph('1.0', styles['table_b']),
             Paragraph('Enero 2025', styles['table_b']),
             Paragraph('Gerencia General — QoriCash SAC', styles['table_b']),
             Paragraph('Enero 2025', styles['table_b'])],
        ], [2.5*cm, 4*cm, 7.5*cm, 3*cm], styles),
    ])

    signature_block(E, styles,
        'CARGO DE RECEPCIÓN — REGLAMENTO INTERNO DE TRABAJO',
        'El trabajador declara haber recibido un ejemplar del Reglamento Interno de Trabajo de QORICASH SAC, '
        'haberlo leído en su totalidad y aceptar su cumplimiento como condición de su vínculo laboral.')

    doc.build(E, onFirstPage=make_footer(fn), onLaterPages=make_footer(fn))
    print(f'✅ RIT generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# 2. MANUAL DE BIENVENIDA / ONBOARDING
# ════════════════════════════════════════════════════════════════════════════════
def generate_bienvenida(output_path, styles):
    fn = 'Manual de Bienvenida'
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []
    header, _ = build_header(
        doc_label='DOCUMENTO DE INCORPORACIÓN — ONBOARDING',
        doc_title='Manual de Bienvenida\na QoriCash',
        doc_subtitle='Todo lo que necesitas saber para comenzar con el pie derecho en el equipo.',
        version='1.0',
        footer_name=fn,
        styles=styles,
    )
    E += header

    chapter('1', 'Mensaje de Bienvenida', E, styles, [
        Paragraph(
            'Bienvenido al equipo de QoriCash.',
            styles['body']),
        Paragraph(
            'Nos alegra que formes parte de nuestra empresa. QoriCash nació con la convicción de que '
            'el cambio de moneda puede ser simple, rápido y confiable. Hoy somos un equipo comprometido '
            'con la excelencia operativa y la confianza de nuestros clientes.',
            styles['body']),
        Paragraph(
            'Este manual fue preparado para que tu ingreso sea ordenado, claro y cómodo. '
            'Encontrarás aquí la información esencial sobre quiénes somos, cómo trabajamos y '
            'qué esperamos de ti — y lo que tú puedes esperar de nosotros.',
            styles['body']),
        Spacer(1, 0.2*cm),
        Paragraph('<i>— La Gerencia de QoriCash</i>', styles['body']),
    ])

    chapter('2', 'Quiénes Somos', E, styles, [
        Paragraph('2.1  Historia', styles['subsection']),
        Paragraph(
            'QoriCash SAC es una empresa peruana dedicada al cambio de divisas, especializada en la '
            'compra y venta de dólares americanos (USD) para personas naturales y jurídicas. '
            'Operamos de forma digital, con un modelo ágil centrado en la confianza y la rapidez.',
            styles['body']),
        Paragraph('2.2  Misión', styles['subsection']),
        Paragraph(
            '<i>"Facilitar el acceso al mercado de cambio de divisas con transparencia, velocidad '
            'y trato personalizado, siendo el aliado financiero de confianza de nuestros clientes."</i>',
            styles['body']),
        Paragraph('2.3  Visión', styles['subsection']),
        Paragraph(
            '<i>"Ser la casa de cambio de referencia en el Perú para clientes que valoran la seguridad, '
            'la tecnología y la atención de calidad."</i>',
            styles['body']),
        Paragraph('2.4  Valores', styles['subsection']),
        b('<b>Integridad:</b> actuamos con honestidad en cada operación.', styles),
        b('<b>Velocidad:</b> procesamos con eficiencia sin sacrificar la seguridad.', styles),
        b('<b>Confianza:</b> construimos relaciones a largo plazo con cada cliente.', styles),
        b('<b>Responsabilidad:</b> cumplimos lo que prometemos.', styles),
        b('<b>Mejora continua:</b> aprendemos, ajustamos y crecemos.', styles),
    ])

    chapter('3', 'Estructura Organizacional', E, styles, [
        Paragraph(
            'QoriCash opera con tres áreas principales, cada una con un rol específico en el flujo de operaciones:',
            styles['body']),
        std_table([
            [Paragraph('Área', styles['table_h']),
             Paragraph('Rol principal', styles['table_h']),
             Paragraph('Interactúa con', styles['table_h'])],
            [Paragraph('Gerencia', styles['table_b']),
             Paragraph('Dirección estratégica, aprobaciones, metas y compliance de alto nivel.', styles['table_b']),
             Paragraph('Todas las áreas.', styles['table_b'])],
            [Paragraph('Trader (Front Office)', styles['table_b']),
             Paragraph('Contacto con clientes, registro de operaciones, negociación de tipo de cambio.', styles['table_b']),
             Paragraph('Cliente, Operador, Middle Office.', styles['table_b'])],
            [Paragraph('Operador (Back Office)', styles['table_b']),
             Paragraph('Verificación de abonos, ejecución de transferencias, cierre de operaciones.', styles['table_b']),
             Paragraph('Trader, Middle Office, Banca.', styles['table_b'])],
            [Paragraph('Middle Office', styles['table_b']),
             Paragraph('Control de calidad, reclamos, compliance KYC/AML, soporte de segundo nivel.', styles['table_b']),
             Paragraph('Trader, Operador, Gerencia.', styles['table_b'])],
        ], [3.5*cm, 7*cm, 5.1*cm], styles),
    ])

    chapter('4', 'Cómo Operamos', E, styles, [
        Paragraph(
            'El flujo estándar de una operación de cambio en QoriCash sigue estos pasos:',
            styles['body']),
        std_table([
            [Paragraph('Paso', styles['table_h']), Paragraph('Responsable', styles['table_h']),
             Paragraph('Acción', styles['table_h'])],
            [Paragraph('1', styles['table_b']), Paragraph('Trader', styles['table_b']),
             Paragraph('Cliente contacta al Trader → se negocia el tipo de cambio → se registra la operación en el sistema.', styles['table_b'])],
            [Paragraph('2', styles['table_b']), Paragraph('Cliente', styles['table_b']),
             Paragraph('Transfiere el monto en la divisa de origen a la cuenta bancaria de QoriCash indicada.', styles['table_b'])],
            [Paragraph('3', styles['table_b']), Paragraph('Operador', styles['table_b']),
             Paragraph('Verifica la recepción del abono → ejecuta la transferencia al cliente en la divisa destino.', styles['table_b'])],
            [Paragraph('4', styles['table_b']), Paragraph('Operador', styles['table_b']),
             Paragraph('Carga el comprobante → cierra la operación como "Completada" en el sistema.', styles['table_b'])],
            [Paragraph('5', styles['table_b']), Paragraph('Trader', styles['table_b']),
             Paragraph('Confirma con el cliente la recepción. Cierra el ciclo comercial.', styles['table_b'])],
        ], [1.5*cm, 3.5*cm, 11.6*cm], styles),
    ])

    chapter('5', 'Tu Primer Día', E, styles, [
        Paragraph('Lo que ocurrirá en tus primeros días:', styles['body']),
        bc('<b>Día 1:</b> Recepción por Gerencia. Firma de contratos y documentos. Entrega de equipos y credenciales.', styles),
        bc('<b>Día 1-2:</b> Lectura y firma de políticas internas (Conducta, Confidencialidad, RIT, Compromisos).', styles),
        bc('<b>Día 2-3:</b> Capacitación inicial en el sistema QoriCash (acceso, módulos, flujo de operaciones).', styles),
        bc('<b>Día 3-5:</b> Acompañamiento supervisado en operaciones reales o simuladas según tu rol.', styles),
        bc('<b>Semana 2:</b> Operación autónoma con seguimiento. Primera retroalimentación con tu supervisor.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'Ante cualquier duda durante tu período de inducción, no dudes en consultar a tu supervisor directo o a la Gerencia.',
            styles['body']),
    ])

    chapter('6', 'Herramientas y Accesos', E, styles, [
        std_table([
            [Paragraph('Herramienta', styles['table_h']),
             Paragraph('Uso', styles['table_h']),
             Paragraph('Acceso otorgado por', styles['table_h'])],
            [Paragraph('Sistema QoriCash', styles['table_b']),
             Paragraph('Registro y gestión de operaciones, clientes y reportes.', styles['table_b']),
             Paragraph('Gerencia / Administrador del sistema.', styles['table_b'])],
            [Paragraph('Correo corporativo', styles['table_b']),
             Paragraph('Comunicación interna y con clientes institucionales.', styles['table_b']),
             Paragraph('Gerencia.', styles['table_b'])],
            [Paragraph('WhatsApp Business', styles['table_b']),
             Paragraph('Coordinación de operaciones y atención al cliente.', styles['table_b']),
             Paragraph('Según rol asignado.', styles['table_b'])],
            [Paragraph('Plataformas bancarias', styles['table_b']),
             Paragraph('Solo para Operadores: verificación y ejecución de transferencias.', styles['table_b']),
             Paragraph('Gerencia (credenciales exclusivas).', styles['table_b'])],
        ], [4*cm, 7.5*cm, 5.1*cm], styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'Los accesos son personales e intransferibles. Reportar de inmediato cualquier problema '
            'de acceso a la Gerencia.',
            styles['body']),
    ])

    chapter('7', 'Documentos que Debes Conocer y Firmar', E, styles, [
        Paragraph(
            'Como parte de tu incorporación, deberás leer y firmar los siguientes documentos:',
            styles['body']),
        std_table([
            [Paragraph('Documento', styles['table_h']),
             Paragraph('Contenido resumido', styles['table_h'])],
            [Paragraph('Reglamento Interno de Trabajo', styles['table_b']),
             Paragraph('Horarios, descansos, beneficios, obligaciones laborales y régimen disciplinario.', styles['table_b'])],
            [Paragraph('Política de Conducta y Ética', styles['table_b']),
             Paragraph('Valores, conducta esperada, comportamientos prohibidos y régimen de sanciones.', styles['table_b'])],
            [Paragraph('Política de Confidencialidad', styles['table_b']),
             Paragraph('Qué información no puedes compartir, cómo proteger datos de clientes y sistemas.', styles['table_b'])],
            [Paragraph('Política de Seguridad TI', styles['table_b']),
             Paragraph('Dispositivos, contraseñas, correo corporativo y gestión de incidentes de seguridad.', styles['table_b'])],
            [Paragraph('Formulario de Compromisos', styles['table_b']),
             Paragraph('Declaración jurada de conflicto de interés y acuerdo de confidencialidad (NDA).', styles['table_b'])],
            [Paragraph('Manual PLAFT', styles['table_b']),
             Paragraph('Prevención de lavado de activos y financiamiento del terrorismo.', styles['table_b'])],
            [Paragraph('MOF de tu rol', styles['table_b']),
             Paragraph('Funciones específicas, responsabilidades y KPIs de tu puesto.', styles['table_b'])],
        ], [5.5*cm, 11.1*cm], styles),
    ])

    chapter('8', 'Contactos Clave', E, styles, [
        Paragraph('Ante dudas, incidencias o situaciones que requieran escalamiento:', styles['body']),
        std_table([
            [Paragraph('Situación', styles['table_h']),
             Paragraph('A quién acudir', styles['table_h'])],
            [Paragraph('Duda sobre una operación', styles['table_b']),
             Paragraph('Tu supervisor directo (Middle Office o Gerencia según rol).', styles['table_b'])],
            [Paragraph('Problema de acceso al sistema', styles['table_b']),
             Paragraph('Gerencia / Administrador del sistema.', styles['table_b'])],
            [Paragraph('Reclamo de un cliente', styles['table_b']),
             Paragraph('Middle Office.', styles['table_b'])],
            [Paragraph('Incidente de seguridad o fraude', styles['table_b']),
             Paragraph('Gerencia de forma inmediata y directa.', styles['table_b'])],
            [Paragraph('Consulta laboral o de RR.HH.', styles['table_b']),
             Paragraph('Gerencia.', styles['table_b'])],
            [Paragraph('Operación sospechosa (AML)', styles['table_b']),
             Paragraph('Middle Office y Gerencia — sin alertar al cliente.', styles['table_b'])],
        ], [5.5*cm, 11.1*cm], styles),
    ])

    doc.build(E, onFirstPage=make_footer(fn), onLaterPages=make_footer(fn))
    print(f'✅ Manual de Bienvenida generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# 3. POLÍTICA DE SEGURIDAD TI Y USO ACEPTABLE DE RECURSOS
# ════════════════════════════════════════════════════════════════════════════════
def generate_seguridad_ti(output_path, styles):
    fn = 'Política de Seguridad TI'
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []
    header, _ = build_header(
        doc_label='POLÍTICA CORPORATIVA — TECNOLOGÍA Y SEGURIDAD',
        doc_title='Política de Seguridad TI\ny Uso Aceptable de Recursos',
        doc_subtitle='Normas para el uso correcto de dispositivos, sistemas y activos tecnológicos de QoriCash.',
        version='1.0',
        footer_name=fn,
        styles=styles,
    )
    E += header

    chapter('1', 'Propósito y Alcance', E, styles, [
        Paragraph(
            'Esta política complementa la Política de Confidencialidad y establece los controles '
            'técnicos y conductuales para proteger la infraestructura tecnológica de QoriCash. '
            'Aplica a todos los colaboradores que utilicen dispositivos, sistemas o redes de la empresa.',
            styles['body']),
        Paragraph(
            'La Política de Confidencialidad ya regula <i>qué información no puede compartirse</i>. '
            'Este documento regula <i>cómo deben usarse los recursos tecnológicos</i> para mantener '
            'la seguridad operativa.',
            styles['body']),
    ])

    chapter('2', 'Dispositivos y Equipos de Trabajo', E, styles, [
        Paragraph('2.1  Equipos proporcionados por la empresa', styles['subsection']),
        bc('Los equipos son de uso exclusivo laboral. No deben utilizarse para actividades personales intensivas (streaming, juegos, almacenamiento personal masivo).', styles),
        bc('Mantener el equipo en buen estado físico y reportar cualquier daño de forma inmediata.', styles),
        bc('Al finalizar la jornada, los equipos deben quedar bloqueados o apagados.', styles),
        bc('En caso de robo o pérdida, notificar a la Gerencia dentro de las 2 horas siguientes.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('2.2  Uso de dispositivos personales (BYOD)', styles['subsection']),
        Paragraph(
            'El uso de dispositivos personales para acceder a sistemas de la empresa debe ser autorizado '
            'expresamente por la Gerencia. Cuando sea autorizado:',
            styles['body']),
        b('El dispositivo debe contar con bloqueo de pantalla activo y antivirus actualizado.', styles),
        b('No instalar aplicaciones no autorizadas que puedan comprometer el acceso a sistemas internos.', styles),
        bx('Queda prohibido acceder al sistema QoriCash desde redes Wi-Fi públicas no seguras.', styles),
    ])

    chapter('3', 'Gestión de Contraseñas', E, styles, [
        Paragraph(
            'Las contraseñas son la primera línea de defensa de los sistemas. Todo colaborador debe:',
            styles['body']),
        bc('Usar contraseñas de <b>mínimo 10 caracteres</b> combinando letras (mayúsculas y minúsculas), números y símbolos.', styles),
        bc('Cambiar la contraseña entregada por la empresa en el primer inicio de sesión.', styles),
        bc('Renovar contraseñas cada <b>90 días</b> como máximo.', styles),
        bc('No reutilizar las últimas 5 contraseñas anteriores.', styles),
        bc('Usar contraseñas distintas para el sistema QoriCash, correo y plataformas bancarias.', styles),
        Spacer(1, 0.2*cm),
        bx('Está terminantemente prohibido anotar contraseñas en papel, notas adhesivas o archivos sin cifrar.', styles),
        bx('No compartir contraseñas bajo ninguna circunstancia, ni con supervisores ni con soporte técnico.', styles),
        bx('No usar contraseñas predecibles: fechas de nacimiento, nombres propios, secuencias numéricas.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'Si existe sospecha de que una contraseña ha sido comprometida, cambiarla de inmediato '
            'y reportar el incidente a la Gerencia.',
            styles['body']),
    ])

    chapter('4', 'Correo Electrónico Corporativo', E, styles, [
        Paragraph(
            'El correo corporativo es una herramienta de trabajo. Su uso debe ser profesional y seguro:',
            styles['body']),
        bc('Usarlo exclusivamente para comunicaciones relacionadas con el trabajo.', styles),
        bc('Verificar el remitente antes de hacer clic en enlaces o descargar adjuntos.', styles),
        bc('No abrir correos de origen desconocido o con asuntos sospechosos — reportarlos a Gerencia.', styles),
        bx('No enviar información de clientes u operaciones a correos personales externos.', styles),
        bx('No usar el correo corporativo para suscripciones, concursos o servicios personales.', styles),
        bx('No reenviar comunicaciones internas a destinatarios externos sin autorización.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            '<b>Phishing:</b> si recibes un correo solicitando credenciales, datos bancarios o accesos, '
            'no respondas y notifica a Gerencia de inmediato. QoriCash <i>nunca</i> solicitará '
            'contraseñas por correo.',
            styles['body']),
    ])

    chapter('5', 'Software y Aplicaciones', E, styles, [
        Paragraph(
            'Solo está permitido instalar y usar software que haya sido previamente autorizado por la Gerencia. '
            'No se permite:',
            styles['body']),
        bx('Instalar software de fuentes no oficiales o sin licencia.', styles),
        bx('Usar herramientas de acceso remoto no autorizadas (TeamViewer personal, AnyDesk no corporativo, etc.).', styles),
        bx('Instalar extensiones de navegador no autorizadas en los equipos con acceso al sistema QoriCash.', styles),
        bx('Descargar y almacenar contenido multimedia o personal en volúmenes que afecten el rendimiento del equipo.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('Software autorizado base:', styles['subsection']),
        b('Navegadores: Google Chrome o Microsoft Edge (versiones actualizadas).', styles),
        b('Comunicación: WhatsApp Web y correo corporativo.', styles),
        b('Ofimática: paquete Google Workspace o Microsoft 365 según asignación.', styles),
        b('Sistema QoriCash: acceso vía navegador autorizado.', styles),
    ])

    chapter('6', 'Redes y Conectividad', E, styles, [
        bc('Usar preferentemente la red de la empresa o redes Wi-Fi de confianza.', styles),
        bc('Al conectarse desde fuera de la oficina, usar únicamente redes seguras (red personal del hogar con contraseña).', styles),
        bx('Prohibido conectar dispositivos de la empresa a redes públicas no seguras (cafeterías, aeropuertos, centros comerciales) para acceder al sistema.', styles),
        bx('No conectar memorias USB, discos externos u otros dispositivos de almacenamiento externo sin autorización de la Gerencia.', styles),
        bx('No desactivar el firewall o el antivirus del equipo bajo ninguna circunstancia.', styles),
    ])

    chapter('7', 'Gestión de Incidentes de Seguridad TI', E, styles, [
        Paragraph(
            'Un incidente de seguridad TI es cualquier evento que comprometa o ponga en riesgo '
            'la confidencialidad, integridad o disponibilidad de los sistemas o datos de QoriCash.',
            styles['body']),
        Paragraph('Ejemplos de incidentes:', styles['subsection']),
        b('Acceso no autorizado al sistema QoriCash o plataformas bancarias.', styles),
        b('Pérdida o robo de un dispositivo con acceso a sistemas internos.', styles),
        b('Correo de phishing o intento de ingeniería social.', styles),
        b('Instalación de malware o comportamiento anómalo del equipo.', styles),
        b('Contraseña comprometida o compartida sin autorización.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('<b>Ante cualquier incidente:</b>', styles['body']),
        bc('Notificar a la Gerencia de forma inmediata (mismo día).', styles),
        bc('No intentar resolver el incidente por cuenta propia sin consultar.', styles),
        bc('Documentar lo observado: hora, qué ocurrió, qué sistema estaba usando.', styles),
        bc('Cooperar con la investigación sin eliminar evidencia (registros, correos, archivos).', styles),
    ])

    chapter('8', 'Consecuencias del Incumplimiento', E, styles, [
        Paragraph(
            'El uso inadecuado o irresponsable de los recursos tecnológicos de la empresa será '
            'tratado como falta disciplinaria, con las siguientes consecuencias posibles:',
            styles['body']),
        bx('Amonestación escrita por uso indebido de equipos o accesos.', styles),
        bx('Suspensión temporal del acceso a sistemas mientras se investiga un incidente.', styles),
        bx('Desvinculación inmediata en casos de sabotaje, acceso no autorizado o violación grave de seguridad.', styles),
        bx('Responsabilidad civil o penal en casos de daño económico o exposición de datos de clientes.', styles),
    ])

    signature_block(E, styles,
        'RECEPCIÓN Y ACEPTACIÓN — POLÍTICA DE SEGURIDAD TI',
        'El colaborador declara haber leído y comprendido la Política de Seguridad TI y Uso Aceptable de Recursos de QORICASH SAC.')

    doc.build(E, onFirstPage=make_footer(fn), onLaterPages=make_footer(fn))
    print(f'✅ Política de Seguridad TI generada: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# 4. PROTOCOLO DE ATENCIÓN AL CLIENTE
# ════════════════════════════════════════════════════════════════════════════════
def generate_protocolo_cliente(output_path, styles):
    fn = 'Protocolo de Atención al Cliente'
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []
    header, _ = build_header(
        doc_label='DOCUMENTO OPERATIVO — ATENCIÓN AL CLIENTE',
        doc_title='Protocolo de Atención\nal Cliente',
        doc_subtitle='Estándares de servicio, tiempos de respuesta y procedimientos para una atención excelente en QoriCash.',
        version='1.0',
        footer_name=fn,
        styles=styles,
    )
    E += header

    chapter('1', 'Propósito', E, styles, [
        Paragraph(
            'QoriCash diferencia su servicio por la calidad y rapidez de la atención. '
            'Este protocolo establece los estándares mínimos de servicio que todo colaborador '
            'con contacto con el cliente debe cumplir, independientemente del canal utilizado.',
            styles['body']),
    ])

    chapter('2', 'Principios de Atención', E, styles, [
        bc('<b>Rapidez:</b> el cliente no debe esperar. Responder en los tiempos establecidos es prioritario.', styles),
        bc('<b>Claridad:</b> comunicar con precisión el tipo de cambio, cuentas, tiempos y pasos del proceso.', styles),
        bc('<b>Cordialidad:</b> trato siempre amable y profesional, independientemente del estado de ánimo del cliente.', styles),
        bc('<b>Proactividad:</b> anticipar dudas, informar el estado de la operación sin que el cliente tenga que preguntar.', styles),
        bc('<b>Honestidad:</b> si algo no está dentro del proceso esperado, decirlo con claridad y sin excusas.', styles),
    ])

    chapter('3', 'Canales de Atención y Tiempos Máximos de Respuesta', E, styles, [
        std_table([
            [Paragraph('Canal', styles['table_h']),
             Paragraph('Tiempo máx. de primera respuesta', styles['table_h']),
             Paragraph('Horario de atención', styles['table_h'])],
            [Paragraph('WhatsApp (mensajes)', styles['table_b']),
             Paragraph('5 minutos en horario de atención.', styles['table_b']),
             Paragraph('Lun–Vie 9:00 a.m. – 6:00 p.m. / Sáb 9:00 a.m. – 1:00 p.m.', styles['table_b'])],
            [Paragraph('Llamada telefónica', styles['table_b']),
             Paragraph('Atender al tercer tono. Si no es posible, devolver en máx. 10 min.', styles['table_b']),
             Paragraph('Mismo horario.', styles['table_b'])],
            [Paragraph('Correo electrónico', styles['table_b']),
             Paragraph('Máx. 2 horas en horario hábil.', styles['table_b']),
             Paragraph('Horario hábil.', styles['table_b'])],
            [Paragraph('Presencial', styles['table_b']),
             Paragraph('Atención inmediata o coordinar cita con max. 24 h de anticipación.', styles['table_b']),
             Paragraph('Previa coordinación.', styles['table_b'])],
        ], [4*cm, 6*cm, 6.6*cm], styles),
    ])

    chapter('4', 'Flujo de Atención Estándar', E, styles, [
        Paragraph('4.1  Saludo inicial', styles['subsection']),
        Paragraph(
            'Todo primer contacto con el cliente debe comenzar identificándose y ofreciendo ayuda:',
            styles['body']),
        Paragraph(
            '<i>"Hola, buen día [nombre del cliente], soy [nombre], trader de QoriCash. '
            '¿En qué puedo ayudarte hoy?"</i>',
            ParagraphStyle('quote', fontName='Helvetica', fontSize=9.5, textColor=MID_GRAY,
                           leading=15, leftIndent=20, spaceAfter=6, alignment=TA_JUSTIFY)),
        Paragraph('4.2  Durante la operación', styles['subsection']),
        bc('Confirmar verbalmente (o por escrito en WhatsApp) el tipo de cambio, el monto en ambas monedas y la cuenta de depósito.', styles),
        bc('Enviar la cuenta bancaria de destino de forma clara y legible (número de cuenta + CCI si aplica).', styles),
        bc('Informar el tiempo estimado de procesamiento una vez recibida la transferencia.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('4.3  Seguimiento y cierre', styles['subsection']),
        bc('Una vez ejecutada la transferencia al cliente, notificarle y adjuntar el comprobante.', styles),
        bc('Mensaje de cierre: <i>"Ya te enviamos [monto] [moneda] a tu cuenta [últimos 4 dígitos]. ¡Listo! Cualquier cosa, aquí estamos."</i>', styles),
        bc('Si el cliente no confirma la recepción en 30 minutos, hacer seguimiento proactivo.', styles),
    ])

    chapter('5', 'Tiempos de Procesamiento Esperados (SLA Interno)', E, styles, [
        std_table([
            [Paragraph('Etapa', styles['table_h']),
             Paragraph('Tiempo objetivo', styles['table_h']),
             Paragraph('Responsable', styles['table_h'])],
            [Paragraph('Registro de operación en sistema', styles['table_b']),
             Paragraph('Inmediato (máx. 3 minutos después del acuerdo)', styles['table_b']),
             Paragraph('Trader', styles['table_b'])],
            [Paragraph('Verificación del abono del cliente', styles['table_b']),
             Paragraph('Máx. 15 minutos desde que el cliente confirma la transferencia', styles['table_b']),
             Paragraph('Operador', styles['table_b'])],
            [Paragraph('Ejecución del pago al cliente', styles['table_b']),
             Paragraph('Máx. 20 minutos desde la verificación del abono', styles['table_b']),
             Paragraph('Operador', styles['table_b'])],
            [Paragraph('Cierre total de la operación', styles['table_b']),
             Paragraph('Máx. 45 minutos desde el inicio (en condiciones normales)', styles['table_b']),
             Paragraph('Operador + Trader', styles['table_b'])],
        ], [5*cm, 6.3*cm, 5.3*cm], styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'Si una operación supera estos tiempos, el Trader debe informar proactivamente al cliente '
            'la causa y el tiempo estimado de resolución.',
            styles['body']),
    ])

    chapter('6', 'Gestión de Clientes Molestos o Situaciones Difíciles', E, styles, [
        Paragraph('6.1  Actitud ante un cliente insatisfecho', styles['subsection']),
        bc('Escuchar sin interrumpir. Dejar que el cliente exprese su malestar completo.', styles),
        bc('Empatizar antes de dar respuestas: <i>"Entiendo tu preocupación, permíteme revisar ahora mismo."</i>', styles),
        bc('No argumentar ni justificarse en exceso. El cliente quiere solución, no explicaciones.', styles),
        bc('Dar un tiempo concreto de respuesta y cumplirlo.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('6.2  Escalación obligatoria', styles['subsection']),
        Paragraph('Escalar al Middle Office o Gerencia de inmediato cuando:', styles['body']),
        b('El cliente amenaza con una denuncia formal, reclamo o acción legal.', styles),
        b('La operación lleva más de 1 hora sin resolverse.', styles),
        b('El cliente reporta no haber recibido el dinero pese a que la operación está marcada como completada.', styles),
        b('El cliente presenta una conducta agresiva, amenazante o sospechosa.', styles),
        Spacer(1, 0.2*cm),
        Paragraph('6.3  Libro de Reclamaciones', styles['subsection']),
        Paragraph(
            'Todo cliente tiene derecho a presentar un reclamo formal. Al solicitarlo, el Trader '
            'debe derivarlo de inmediato al Middle Office, quien gestionará el proceso completo '
            'en un plazo máximo de 30 días calendario según ley.',
            styles['body']),
    ])

    chapter('7', 'Lo que Nunca Debes Hacer Frente a un Cliente', E, styles, [
        bx('Discutir o elevar el tono de voz.', styles),
        bx('Prometer tiempos o condiciones que no puedes garantizar.', styles),
        bx('Culpar a otro área o colaborador frente al cliente.', styles),
        bx('Ignorar mensajes o llamadas de un cliente con operación en curso.', styles),
        bx('Cerrar una operación como "completada" sin haber ejecutado el pago real.', styles),
        bx('Revelar información de otros clientes en cualquier conversación.', styles),
        bx('Negociar tipos de cambio fuera del rango autorizado para "cerrar" una operación.', styles),
    ])

    doc.build(E, onFirstPage=make_footer(fn), onLaterPages=make_footer(fn))
    print(f'✅ Protocolo de Atención al Cliente generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# 5. PROCEDIMIENTO DE GESTIÓN DE INCIDENTES
# ════════════════════════════════════════════════════════════════════════════════
def generate_gestion_incidentes(output_path, styles):
    fn = 'Procedimiento de Gestión de Incidentes'
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []
    header, _ = build_header(
        doc_label='DOCUMENTO OPERATIVO — CONTROL INTERNO',
        doc_title='Procedimiento de\nGestión de Incidentes',
        doc_subtitle='Cómo identificar, reportar y escalar incidentes operativos, de seguridad y de compliance en QoriCash.',
        version='1.0',
        footer_name=fn,
        styles=styles,
    )
    E += header

    chapter('1', 'Propósito', E, styles, [
        Paragraph(
            'Este procedimiento establece el proceso estándar para la detección, reporte, '
            'escalamiento y cierre de incidentes que puedan afectar la operación, la seguridad, '
            'la imagen o el cumplimiento normativo de QoriCash.',
            styles['body']),
        Paragraph(
            'Un incidente no reportado o mal gestionado puede convertirse en un problema mayor. '
            'La cultura de QoriCash premia la transparencia y la rapidez de reporte, '
            '<b>no el ocultamiento</b>.',
            styles['body']),
    ])

    chapter('2', 'Tipos de Incidente', E, styles, [
        std_table([
            [Paragraph('Tipo', styles['table_h']),
             Paragraph('Descripción', styles['table_h']),
             Paragraph('Ejemplos', styles['table_h'])],
            [Paragraph('Operativo', styles['table_b']),
             Paragraph('Error en el flujo normal de una operación de cambio.', styles['table_b']),
             Paragraph('Transferencia enviada a cuenta incorrecta, monto equivocado, operación duplicada.', styles['table_b'])],
            [Paragraph('Seguridad TI', styles['table_b']),
             Paragraph('Evento que compromete sistemas, datos o accesos.', styles['table_b']),
             Paragraph('Acceso no autorizado, robo de dispositivo, phishing exitoso, malware.', styles['table_b'])],
            [Paragraph('Compliance / AML', styles['table_b']),
             Paragraph('Situación que puede violar normas regulatorias.', styles['table_b']),
             Paragraph('Operación sospechosa, cliente en lista restrictiva, transacción fraccionada.', styles['table_b'])],
            [Paragraph('Laboral / Conducta', styles['table_b']),
             Paragraph('Comportamiento que viola el Reglamento o las políticas internas.', styles['table_b']),
             Paragraph('Acoso, fraude interno, filtración de información, conflicto de interés.', styles['table_b'])],
            [Paragraph('Reputacional', styles['table_b']),
             Paragraph('Evento que puede dañar la imagen pública de QoriCash.', styles['table_b']),
             Paragraph('Publicación en redes sociales de información interna, queja pública masiva.', styles['table_b'])],
        ], [3.2*cm, 5.5*cm, 7.9*cm], styles),
    ])

    chapter('3', 'Clasificación por Severidad', E, styles, [
        std_table([
            [Paragraph('Severidad', styles['table_h']),
             Paragraph('Criterio', styles['table_h']),
             Paragraph('Tiempo de escalamiento', styles['table_h'])],
            [Paragraph('CRÍTICA', styles['table_w']),
             Paragraph('Pérdida económica real, acceso no autorizado activo, riesgo legal inmediato.', styles['table_b']),
             Paragraph('Inmediato — llamada a Gerencia en el acto.', styles['table_b'])],
            [Paragraph('ALTA', styles['table_h']),
             Paragraph('Operación con error que afecta a un cliente, incidente de seguridad contenido.', styles['table_b']),
             Paragraph('Máx. 30 minutos.', styles['table_b'])],
            [Paragraph('MEDIA', styles['table_h']),
             Paragraph('Demora inusual, sospecha de irregularidad sin impacto confirmado.', styles['table_b']),
             Paragraph('Antes de finalizar la jornada.', styles['table_b'])],
            [Paragraph('BAJA', styles['table_h']),
             Paragraph('Error menor ya resuelto, situación que podría ser preventiva.', styles['table_b']),
             Paragraph('Registro en el día, comunicación en reunión de equipo.', styles['table_b'])],
        ], [2.5*cm, 7.8*cm, 6.3*cm], styles),
    ])

    chapter('4', 'Procedimiento de Reporte', E, styles, [
        Paragraph('Ante cualquier incidente, el colaborador debe:', styles['body']),
        Spacer(1, 0.1*cm),
        std_table([
            [Paragraph('Paso', styles['table_h']),
             Paragraph('Acción', styles['table_h']),
             Paragraph('Quién', styles['table_h'])],
            [Paragraph('1. DETENER', styles['table_b']),
             Paragraph('Si el incidente está en curso, detener la acción que lo genera (pausar la operación, cerrar el acceso, etc.).', styles['table_b']),
             Paragraph('Quien detecta el incidente.', styles['table_b'])],
            [Paragraph('2. DOCUMENTAR', styles['table_b']),
             Paragraph('Anotar: qué ocurrió, cuándo, con qué sistema o cliente, qué se hizo hasta ahora.', styles['table_b']),
             Paragraph('Quien detecta el incidente.', styles['table_b'])],
            [Paragraph('3. REPORTAR', styles['table_b']),
             Paragraph('Notificar al supervisor directo (Middle Office) o Gerencia según severidad. No gestionar solo.', styles['table_b']),
             Paragraph('Quien detecta + supervisor.', styles['table_b'])],
            [Paragraph('4. COOPERAR', styles['table_b']),
             Paragraph('Facilitar toda la información solicitada durante la investigación. No eliminar evidencia.', styles['table_b']),
             Paragraph('Todo el equipo involucrado.', styles['table_b'])],
            [Paragraph('5. CERRAR', styles['table_b']),
             Paragraph('La Gerencia o Middle Office declara el cierre del incidente con la resolución documentada.', styles['table_b']),
             Paragraph('Gerencia / Middle Office.', styles['table_b'])],
        ], [2.8*cm, 9.5*cm, 4.3*cm], styles),
    ])

    chapter('5', 'Escalamiento por Tipo de Incidente', E, styles, [
        std_table([
            [Paragraph('Tipo de incidente', styles['table_h']),
             Paragraph('Primer reporte a', styles['table_h']),
             Paragraph('Escalamiento si no se resuelve', styles['table_h'])],
            [Paragraph('Operativo (error de transferencia)', styles['table_b']),
             Paragraph('Middle Office.', styles['table_b']),
             Paragraph('Gerencia.', styles['table_b'])],
            [Paragraph('Seguridad TI', styles['table_b']),
             Paragraph('Gerencia directamente.', styles['table_b']),
             Paragraph('Soporte técnico externo si aplica.', styles['table_b'])],
            [Paragraph('Compliance / AML', styles['table_b']),
             Paragraph('Middle Office.', styles['table_b']),
             Paragraph('Gerencia → UIF si corresponde.', styles['table_b'])],
            [Paragraph('Laboral / Conducta', styles['table_b']),
             Paragraph('Gerencia.', styles['table_b']),
             Paragraph('Asesoría legal si aplica.', styles['table_b'])],
            [Paragraph('Reputacional', styles['table_b']),
             Paragraph('Gerencia.', styles['table_b']),
             Paragraph('Gerencia gestiona comunicación externa.', styles['table_b'])],
        ], [4.5*cm, 4.5*cm, 7.6*cm], styles),
    ])

    chapter('6', 'Principios de Gestión de Incidentes', E, styles, [
        bc('<b>Transparencia:</b> reportar siempre, incluso si el error fue propio.', styles),
        bc('<b>Rapidez:</b> cada minuto cuenta, especialmente en incidentes críticos.', styles),
        bc('<b>No improvisación:</b> no intentar resolver incidentes graves sin escalar.', styles),
        bc('<b>Preservación de evidencia:</b> no eliminar registros, chats, correos ni comprobantes relacionados.', styles),
        bc('<b>Confidencialidad del proceso:</b> los incidentes se gestionan internamente — no comentar con el cliente ni en redes sociales.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'El colaborador que reporte un incidente de buena fe, aunque haya cometido el error, '
            'será tratado con proporcionalidad. El ocultamiento de incidentes, en cambio, '
            'siempre será considerado una falta grave.',
            styles['body']),
    ])

    doc.build(E, onFirstPage=make_footer(fn), onLaterPages=make_footer(fn))
    print(f'✅ Procedimiento de Gestión de Incidentes generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# 6. FORMULARIO DE COMPROMISOS (Declaración Jurada + NDA)
# ════════════════════════════════════════════════════════════════════════════════
def generate_form_compromisos(output_path, styles):
    fn = 'Formulario de Compromisos del Colaborador'
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []
    header, _ = build_header(
        doc_label='FORMULARIO DE FIRMAS — DOCUMENTOS DE INCORPORACIÓN',
        doc_title='Formulario de Compromisos\ndel Colaborador',
        doc_subtitle='Declaración Jurada de Conflicto de Interés y Acuerdo de Confidencialidad y No Competencia.',
        version='1.0',
        footer_name=fn,
        styles=styles,
    )
    E += header

    # DATOS DEL COLABORADOR
    E.append(Spacer(1, 0.3*cm))
    E.append(Paragraph('DATOS DEL COLABORADOR', styles['notice']))
    E.append(Spacer(1, 0.3*cm))
    datos = Table([
        [Paragraph('Nombre completo:', styles['table_h']),
         Paragraph('___________________________________________', styles['table_b']),
         Paragraph('DNI:', styles['table_h']),
         Paragraph('________________', styles['table_b'])],
        [Paragraph('Cargo / Rol:', styles['table_h']),
         Paragraph('___________________________________________', styles['table_b']),
         Paragraph('Área:', styles['table_h']),
         Paragraph('________________', styles['table_b'])],
        [Paragraph('Fecha de inicio:', styles['table_h']),
         Paragraph('___________________________________________', styles['table_b']),
         Paragraph('', styles['table_b']),
         Paragraph('', styles['table_b'])],
    ], colWidths=[3.5*cm, 7*cm, 1.8*cm, 4.3*cm])
    datos.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    E.append(datos)
    E.append(Spacer(1, 0.3*cm))
    E.append(rule())

    # SECCIÓN 1: DECLARACIÓN JURADA DE CONFLICTO DE INTERÉS
    E.append(Spacer(1, 0.3*cm))
    E.append(Paragraph('SECCIÓN 1 — DECLARACIÓN JURADA DE CONFLICTO DE INTERÉS', styles['notice']))
    E.append(Spacer(1, 0.2*cm))
    E.append(Paragraph(
        'El colaborador suscrito declara bajo juramento que, a la fecha de inicio de su vinculación '
        'con QORICASH SAC, la información que se detalla a continuación es veraz y completa.',
        styles['body']))
    E.append(Spacer(1, 0.3*cm))

    E.append(Paragraph(
        '¿Tienes actualmente relación laboral, comercial, de sociedad o económica con alguna empresa '
        'del sector cambiario o financiero (casa de cambio, banco, fintech)?',
        styles['body']))
    E.append(Table([
        [Paragraph('☐  No tengo ninguna relación de este tipo.', styles['table_b']),
         Paragraph('☐  Sí, detallo a continuación:', styles['table_b'])],
    ], colWidths=[8*cm, 8.6*cm]))
    E.append(Spacer(1, 0.15*cm))
    E.append(Paragraph('Empresa / Rol / Relación: _______________________________________________', styles['body']))
    E.append(Spacer(1, 0.3*cm))

    E.append(Paragraph(
        '¿Tienes familiares directos (cónyuge, hijos, padres, hermanos) que trabajen en una empresa '
        'competidora o que sean clientes frecuentes de QoriCash?',
        styles['body']))
    E.append(Table([
        [Paragraph('☐  No.', styles['table_b']),
         Paragraph('☐  Sí, detallo: ___________________________________________', styles['table_b'])],
    ], colWidths=[3*cm, 13.6*cm]))
    E.append(Spacer(1, 0.3*cm))

    E.append(Paragraph(
        '¿Tienes conocimiento de alguna situación personal que pudiera generar un conflicto de interés '
        'con tus funciones en QoriCash?',
        styles['body']))
    E.append(Table([
        [Paragraph('☐  No.', styles['table_b']),
         Paragraph('☐  Sí, detallo: ___________________________________________', styles['table_b'])],
    ], colWidths=[3*cm, 13.6*cm]))
    E.append(Spacer(1, 0.3*cm))
    E.append(Paragraph(
        'El colaborador se compromete a comunicar de forma inmediata y por escrito a la Gerencia '
        'cualquier nueva situación que pudiera configurar un conflicto de interés durante su vinculación.',
        styles['body']))

    E.append(Spacer(1, 0.4*cm))
    E.append(rule())

    # SECCIÓN 2: ACUERDO DE CONFIDENCIALIDAD Y NO COMPETENCIA
    E.append(Spacer(1, 0.3*cm))
    E.append(Paragraph('SECCIÓN 2 — ACUERDO DE CONFIDENCIALIDAD Y NO COMPETENCIA', styles['notice']))
    E.append(Spacer(1, 0.2*cm))
    E.append(Paragraph(
        'En complemento a la Política de Confidencialidad de QoriCash, el colaborador se compromete '
        'expresamente a:',
        styles['body']))
    E.append(Spacer(1, 0.1*cm))
    E.append(bc('Mantener estricta confidencialidad sobre toda la información a la que acceda en el ejercicio de sus funciones, incluyendo datos de clientes, operaciones, sistemas y estrategias comerciales.', styles))
    E.append(bc('No revelar, transferir, copiar ni hacer uso de dicha información fuera del ámbito estrictamente laboral, durante ni después de su vinculación con QoriCash.', styles))
    E.append(bc('No utilizar los contactos, cartera de clientes, datos de operaciones ni conocimiento interno adquirido en QoriCash para beneficio propio o de terceros.', styles))
    E.append(bc('Durante un período de <b>6 meses posteriores</b> a su desvinculación, abstenerse de contactar activamente a clientes de la cartera de QoriCash con fines comerciales en el sector cambiario.', styles))
    E.append(bc('Devolver todos los equipos, accesos, documentos y materiales de la empresa el último día de trabajo.', styles))
    E.append(Spacer(1, 0.3*cm))
    E.append(Paragraph(
        'El incumplimiento de este acuerdo faculta a QORICASH SAC a ejercer las acciones legales '
        'correspondientes, incluyendo la reclamación de daños y perjuicios por vía civil o penal.',
        styles['body']))

    E.append(Spacer(1, 0.4*cm))
    E.append(rule())
    E.append(Spacer(1, 0.3*cm))
    E.append(Paragraph('FIRMA Y ACEPTACIÓN', styles['notice']))
    E.append(Spacer(1, 0.2*cm))
    E.append(Paragraph(
        'El colaborador declara que la información consignada en la Sección 1 es verídica, '
        'y acepta los compromisos establecidos en la Sección 2 de forma voluntaria y consciente.',
        styles['notice_sub']))
    E.append(Spacer(1, 1.1*cm))

    sig2 = Table([
        [Paragraph('_______________________________', styles['sig_line']),
         Paragraph('_______________________________', styles['sig_line']),
         Paragraph('_______________________________', styles['sig_line'])],
        [Paragraph('Nombre completo', styles['sig_label']),
         Paragraph('Firma del colaborador', styles['sig_label']),
         Paragraph('Fecha', styles['sig_label'])],
    ], colWidths=[5.5*cm, 5.5*cm, 5.6*cm])
    sig2.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    E.append(sig2)
    E.append(Spacer(1, 1.2*cm))

    sig3 = Table([
        [Paragraph('_______________________________', styles['sig_line']),
         Paragraph('_______________________________', styles['sig_line'])],
        [Paragraph('Firma del representante de QoriCash', styles['sig_label']),
         Paragraph('Cargo y fecha', styles['sig_label'])],
    ], colWidths=[8.3*cm, 8.3*cm])
    sig3.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    E.append(sig3)

    doc.build(E, onFirstPage=make_footer(fn), onLaterPages=make_footer(fn))
    print(f'✅ Formulario de Compromisos generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# 7. PLAN DE CAPACITACIÓN ANUAL
# ════════════════════════════════════════════════════════════════════════════════
def generate_plan_capacitacion(output_path, styles):
    fn = 'Plan de Capacitación Anual'
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2*cm, bottomMargin=2.2*cm)
    E = []
    header, _ = build_header(
        doc_label='DOCUMENTO DE GESTIÓN — DESARROLLO DE PERSONAS',
        doc_title='Plan de Capacitación\nAnual 2025',
        doc_subtitle='Programa de formación obligatorio y de desarrollo para todos los colaboradores de QoriCash.',
        version='1.0',
        footer_name=fn,
        styles=styles,
    )
    E += header

    chapter('1', 'Objetivo', E, styles, [
        Paragraph(
            'Garantizar que todos los colaboradores de QoriCash cuenten con los conocimientos, '
            'habilidades y actualizaciones necesarias para desempeñar sus funciones con excelencia, '
            'cumplir la normativa vigente y alinear su desarrollo con los objetivos de la empresa.',
            styles['body']),
    ])

    chapter('2', 'Módulos de Capacitación Obligatoria', E, styles, [
        Paragraph(
            'Los siguientes módulos son obligatorios para todos los colaboradores, '
            'independientemente del rol. La asistencia y aprobación es condición de permanencia.',
            styles['body']),
        Spacer(1, 0.2*cm),
        std_table([
            [Paragraph('Módulo', styles['table_h']),
             Paragraph('Contenido principal', styles['table_h']),
             Paragraph('Frec.', styles['table_h']),
             Paragraph('Duración', styles['table_h']),
             Paragraph('Responsable', styles['table_h'])],
            [Paragraph('Inducción corporativa', styles['table_b']),
             Paragraph('Historia, misión, valores, estructura, documentos de incorporación.', styles['table_b']),
             Paragraph('1 vez al incorporarse', styles['table_b']),
             Paragraph('4 h', styles['table_b']),
             Paragraph('Gerencia', styles['table_b'])],
            [Paragraph('Sistema QoriCash', styles['table_b']),
             Paragraph('Registro de operaciones, clientes, reportes, módulos de compliance.', styles['table_b']),
             Paragraph('Al incorporarse + actualiz.', styles['table_b']),
             Paragraph('3 h', styles['table_b']),
             Paragraph('Middle Office', styles['table_b'])],
            [Paragraph('AML / KYC básico', styles['table_b']),
             Paragraph('Señales de alerta, debida diligencia, procedimiento de reporte de ROS.', styles['table_b']),
             Paragraph('Anual', styles['table_b']),
             Paragraph('2 h', styles['table_b']),
             Paragraph('Middle Office', styles['table_b'])],
            [Paragraph('Conducta y ética', styles['table_b']),
             Paragraph('Repaso de políticas internas, casos prácticos, actualizaciones normativas.', styles['table_b']),
             Paragraph('Semestral', styles['table_b']),
             Paragraph('1 h', styles['table_b']),
             Paragraph('Gerencia', styles['table_b'])],
            [Paragraph('Seguridad TI y phishing', styles['table_b']),
             Paragraph('Contraseñas, uso de sistemas, cómo identificar ataques de phishing.', styles['table_b']),
             Paragraph('Semestral', styles['table_b']),
             Paragraph('1 h', styles['table_b']),
             Paragraph('Gerencia / Soporte TI', styles['table_b'])],
            [Paragraph('Atención al cliente', styles['table_b']),
             Paragraph('Protocolo de servicio, manejo de quejas, comunicación efectiva.', styles['table_b']),
             Paragraph('Trimestral', styles['table_b']),
             Paragraph('1.5 h', styles['table_b']),
             Paragraph('Middle Office', styles['table_b'])],
            [Paragraph('Libro de Reclamaciones', styles['table_b']),
             Paragraph('Proceso legal, plazos, cómo registrar y escalar un reclamo.', styles['table_b']),
             Paragraph('Anual', styles['table_b']),
             Paragraph('1 h', styles['table_b']),
             Paragraph('Middle Office', styles['table_b'])],
        ], [4*cm, 5.8*cm, 2.8*cm, 1.7*cm, 2.3*cm], styles),
    ])

    chapter('3', 'Módulos de Capacitación por Rol', E, styles, [
        std_table([
            [Paragraph('Módulo', styles['table_h']),
             Paragraph('Dirigido a', styles['table_h']),
             Paragraph('Contenido', styles['table_h']),
             Paragraph('Frec.', styles['table_h']),
             Paragraph('Duración', styles['table_h'])],
            [Paragraph('Técnicas de negociación y captación', styles['table_b']),
             Paragraph('Trader', styles['table_b']),
             Paragraph('Cómo presentar tipos de cambio, manejar objeciones, fidelizar clientes.', styles['table_b']),
             Paragraph('Trimestral', styles['table_b']),
             Paragraph('2 h', styles['table_b'])],
            [Paragraph('Conciliación bancaria', styles['table_b']),
             Paragraph('Operador', styles['table_b']),
             Paragraph('Cierre de caja, cuadre de saldos, manejo de discrepancias.', styles['table_b']),
             Paragraph('Semestral', styles['table_b']),
             Paragraph('2 h', styles['table_b'])],
            [Paragraph('Banca digital avanzada', styles['table_b']),
             Paragraph('Operador', styles['table_b']),
             Paragraph('Plataformas BCP, Interbank, BBVA — transferencias, CCI, CCE, alertas.', styles['table_b']),
             Paragraph('Anual', styles['table_b']),
             Paragraph('2 h', styles['table_b'])],
            [Paragraph('Gestión de reclamos y mediación', styles['table_b']),
             Paragraph('Middle Office', styles['table_b']),
             Paragraph('Técnicas de resolución de conflictos, redacción de respuestas formales.', styles['table_b']),
             Paragraph('Semestral', styles['table_b']),
             Paragraph('2 h', styles['table_b'])],
            [Paragraph('Análisis de riesgo y compliance avanzado', styles['table_b']),
             Paragraph('Middle Office', styles['table_b']),
             Paragraph('Perfilamiento de clientes, listas restrictivas, reportes UIF.', styles['table_b']),
             Paragraph('Anual', styles['table_b']),
             Paragraph('3 h', styles['table_b'])],
            [Paragraph('Tipo de cambio y mercado FX', styles['table_b']),
             Paragraph('Todos', styles['table_b']),
             Paragraph('Factores que mueven el tipo de cambio, lectura del mercado, contexto macro.', styles['table_b']),
             Paragraph('Trimestral', styles['table_b']),
             Paragraph('1 h', styles['table_b'])],
        ], [4*cm, 2.5*cm, 5.5*cm, 2.5*cm, 2.1*cm], styles),
    ])

    chapter('4', 'Cronograma de Capacitaciones 2025', E, styles, [
        std_table([
            [Paragraph('Mes', styles['table_h']),
             Paragraph('Capacitación(es) programadas', styles['table_h']),
             Paragraph('Dirigido a', styles['table_h'])],
            [Paragraph('Enero', styles['table_b']),
             Paragraph('Inducción corporativa (nuevos ingresos) · Tipo de cambio y mercado FX', styles['table_b']),
             Paragraph('Nuevos · Todos', styles['table_b'])],
            [Paragraph('Febrero', styles['table_b']),
             Paragraph('Sistema QoriCash (actualización) · Técnicas de negociación', styles['table_b']),
             Paragraph('Todos · Traders', styles['table_b'])],
            [Paragraph('Marzo', styles['table_b']),
             Paragraph('Atención al cliente (trimestral) · Conciliación bancaria', styles['table_b']),
             Paragraph('Todos · Operadores', styles['table_b'])],
            [Paragraph('Abril', styles['table_b']),
             Paragraph('Tipo de cambio y mercado FX · Gestión de reclamos', styles['table_b']),
             Paragraph('Todos · Middle Office', styles['table_b'])],
            [Paragraph('Mayo', styles['table_b']),
             Paragraph('Seguridad TI y phishing (semestral) · Conducta y ética', styles['table_b']),
             Paragraph('Todos · Todos', styles['table_b'])],
            [Paragraph('Junio', styles['table_b']),
             Paragraph('Atención al cliente · Técnicas de negociación', styles['table_b']),
             Paragraph('Todos · Traders', styles['table_b'])],
            [Paragraph('Julio', styles['table_b']),
             Paragraph('AML / KYC básico (anual) · Tipo de cambio y mercado FX', styles['table_b']),
             Paragraph('Todos · Todos', styles['table_b'])],
            [Paragraph('Agosto', styles['table_b']),
             Paragraph('Banca digital avanzada · Análisis de riesgo y compliance', styles['table_b']),
             Paragraph('Operadores · Middle Office', styles['table_b'])],
            [Paragraph('Septiembre', styles['table_b']),
             Paragraph('Atención al cliente · Conciliación bancaria', styles['table_b']),
             Paragraph('Todos · Operadores', styles['table_b'])],
            [Paragraph('Octubre', styles['table_b']),
             Paragraph('Seguridad TI y phishing (semestral) · Conducta y ética', styles['table_b']),
             Paragraph('Todos · Todos', styles['table_b'])],
            [Paragraph('Noviembre', styles['table_b']),
             Paragraph('Tipo de cambio y mercado FX · Libro de Reclamaciones', styles['table_b']),
             Paragraph('Todos · Todos', styles['table_b'])],
            [Paragraph('Diciembre', styles['table_b']),
             Paragraph('Cierre anual: repaso de incidentes, lecciones aprendidas y metas 2026.', styles['table_b']),
             Paragraph('Todos', styles['table_b'])],
        ], [2.2*cm, 10*cm, 4.4*cm], styles),
    ])

    chapter('5', 'Evaluación y Seguimiento', E, styles, [
        Paragraph(
            'Cada capacitación obligatoria incluirá una evaluación de comprensión (cuestionario breve '
            'o caso práctico). Los resultados serán registrados en el legajo de cada colaborador.',
            styles['body']),
        b('Puntuación mínima de aprobación: <b>70% de respuestas correctas.</b>', styles),
        b('En caso de no aprobar, el colaborador deberá repetir el módulo en un plazo de 15 días.', styles),
        b('La Gerencia recibirá un reporte trimestral con el estado de avance del plan de capacitación.', styles),
        b('Las capacitaciones externas o de certificación deberán ser coordinadas con Gerencia con 30 días de anticipación.', styles),
        Spacer(1, 0.2*cm),
        Paragraph(
            'El incumplimiento reiterado de la asistencia a capacitaciones obligatorias será considerado '
            'una falta al Reglamento Interno de Trabajo y podrá derivar en medidas disciplinarias.',
            styles['body']),
    ])

    doc.build(E, onFirstPage=make_footer(fn), onLaterPages=make_footer(fn))
    print(f'✅ Plan de Capacitación generado: {output_path}')


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mof_docs'
    )
    os.makedirs(output_dir, exist_ok=True)
    styles = build_styles()

    generate_rit(os.path.join(output_dir, 'RIT_ReglamentoInterno_QoriCash.pdf'), styles)
    generate_bienvenida(os.path.join(output_dir, 'MANUAL_Bienvenida_QoriCash.pdf'), styles)
    generate_seguridad_ti(os.path.join(output_dir, 'POL_SeguridadTI_QoriCash.pdf'), styles)
    generate_protocolo_cliente(os.path.join(output_dir, 'PROT_AtencionCliente_QoriCash.pdf'), styles)
    generate_gestion_incidentes(os.path.join(output_dir, 'PROC_GestionIncidentes_QoriCash.pdf'), styles)
    generate_form_compromisos(os.path.join(output_dir, 'FORM_Compromisos_QoriCash.pdf'), styles)
    generate_plan_capacitacion(os.path.join(output_dir, 'PLAN_Capacitacion_QoriCash.pdf'), styles)

    print(f'\n📁 7 documentos generados en: {output_dir}')

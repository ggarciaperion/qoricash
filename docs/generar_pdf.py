"""
Genera la carta de presentación corporativa de QoriCash FX en PDF.
Usa reportlab con colores de marca exactos.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import Image as RLImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import os

# ── Colores de marca ─────────────────────────────────────────────────────────
GREEN       = HexColor('#22C55E')
GREEN_DARK  = HexColor('#16A34A')
GREEN_XL    = HexColor('#f0fdf4')
GREEN_100   = HexColor('#dcfce7')
NAVY        = HexColor('#0D1B2A')
NAVY2       = HexColor('#1F2937')
MID_GRAY    = HexColor('#6B7280')
LIGHT_GRAY  = HexColor('#F9FAFB')
DARK_GRAY   = HexColor('#1F2937')
YELLOW      = HexColor('#FBBF24')

LOGO = "/Users/gianpierre/Desktop/Qoricash/Sistema/qoricashweb/public/logo-principal.png"
OUT  = "/Users/gianpierre/Desktop/Qoricash/Sistema/qoricash/docs/QoriCash_Carta_Corporativa.pdf"

W, H = A4  # 595 x 842 pt

# ── Estilos ──────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def S(name, parent="Normal", **kw):
    return ParagraphStyle(name, parent=base[parent], **kw)

style_cover_title  = S("CoverTitle",  fontSize=38, leading=46, textColor=white,
                        fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=8)
style_cover_sub    = S("CoverSub",    fontSize=14, leading=20, textColor=GREEN,
                        fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=6)
style_cover_body   = S("CoverBody",   fontSize=11, leading=16, textColor=white,
                        fontName="Helvetica", alignment=TA_CENTER)
style_section_h    = S("SectionH",    fontSize=20, leading=26, textColor=NAVY,
                        fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=4)
style_section_sub  = S("SectionSub",  fontSize=11, leading=15, textColor=MID_GRAY,
                        fontName="Helvetica", spaceAfter=12)
style_h2           = S("H2",          fontSize=15, leading=20, textColor=NAVY,
                        fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4)
style_h3           = S("H3",          fontSize=13, leading=18, textColor=GREEN_DARK,
                        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=3)
style_body         = S("Body",        fontSize=10.5, leading=15, textColor=DARK_GRAY,
                        fontName="Helvetica", spaceAfter=6, alignment=TA_JUSTIFY)
style_body_c       = S("BodyC",       fontSize=10.5, leading=15, textColor=DARK_GRAY,
                        fontName="Helvetica", spaceAfter=6, alignment=TA_CENTER)
style_bullet       = S("Bullet",      fontSize=10.5, leading=15, textColor=DARK_GRAY,
                        fontName="Helvetica", leftIndent=14, spaceAfter=3)
style_caption      = S("Caption",     fontSize=8.5, leading=12, textColor=MID_GRAY,
                        fontName="Helvetica", alignment=TA_CENTER)
style_white_bold   = S("WB",          fontSize=11, leading=16, textColor=white,
                        fontName="Helvetica-Bold", alignment=TA_CENTER)
style_white        = S("W",           fontSize=10, leading=14, textColor=white,
                        fontName="Helvetica", alignment=TA_CENTER)
style_green_big    = S("GB",          fontSize=28, leading=34, textColor=GREEN,
                        fontName="Helvetica-Bold", alignment=TA_CENTER)
style_green_label  = S("GL",          fontSize=10, leading=14, textColor=white,
                        fontName="Helvetica", alignment=TA_CENTER)
style_footer       = S("Footer",      fontSize=8, leading=11, textColor=MID_GRAY,
                        fontName="Helvetica", alignment=TA_CENTER)


# ── Canvas callbacks para header/footer ─────────────────────────────────────

def page_bg(canvas, doc):
    canvas.saveState()
    # Franja verde lateral izquierda
    canvas.setFillColor(GREEN)
    canvas.rect(0, 0, 8*mm, H, fill=1, stroke=0)
    # Franja navy lateral derecha (fina)
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(W - 6*mm, 0, 6*mm, H, fill=1, stroke=0)
    canvas.restoreState()


def cover_bg(canvas, doc):
    canvas.saveState()
    # Fondo navy total
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    # Franja verde izquierda
    canvas.setFillColor(GREEN)
    canvas.rect(0, 0, 10*mm, H, fill=1, stroke=0)
    # Franja verde derecha
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(W - 10*mm, 0, 10*mm, H, fill=1, stroke=0)
    # Línea verde inferior
    canvas.setFillColor(GREEN)
    canvas.rect(10*mm, 12*mm, W - 20*mm, 3*mm, fill=1, stroke=0)
    # SBS badge bottom
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(10*mm, 16*mm, W - 20*mm, 14*mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawCentredString(W/2, 21*mm,
        "Registrada ante la SBS — Resolución N° 00313-2026  ·  RUC: 20615113698")
    canvas.restoreState()


def later_page(canvas, doc):
    page_bg(canvas, doc)
    canvas.saveState()
    # Footer
    canvas.setFillColor(NAVY)
    canvas.rect(8*mm, 0, W - 14*mm, 12*mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(W/2, 5*mm,
        "QORICASH S.A.C.  ·  RUC 20615113698  ·  SBS Res. 00313-2026  "
        "·  www.qoricash.pe  ·  info@qoricash.pe  ·  © 2026 QoriCash FX")
    # Número de página
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(GREEN)
    canvas.drawRightString(W - 14*mm, 5*mm, f"Pág. {doc.page}")
    canvas.restoreState()


# ── Flowables helpers ─────────────────────────────────────────────────────────

def divider(color=GREEN, thickness=2, space_before=6, space_after=10):
    return HRFlowable(width="100%", thickness=thickness,
                      color=color, spaceAfter=space_after,
                      spaceBefore=space_before, lineCap="round")


def stat_table(stats):
    """stats = [(valor, label), ...]"""
    data = [[Paragraph(v, style_green_big) for v, _ in stats],
            [Paragraph(l, style_green_label) for _, l in stats]]
    col_w = (W - 3*cm) / len(stats)
    t = Table(data, colWidths=[col_w] * len(stats), rowHeights=[38, 22])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [NAVY, NAVY2]),
        ('LINEAFTER', (0, 0), (-2, -1), 0.5, GREEN_DARK),
    ]))
    return t


def info_row(label, value, bg=LIGHT_GRAY):
    data = [[Paragraph(f"<b>{label}</b>", style_body),
             Paragraph(value, style_body)]]
    t = Table(data, colWidths=[5*cm, 10*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, HexColor('#E5E7EB')),
    ]))
    return t


def benefit_card(title, desc, accent=GREEN):
    data = [[Paragraph(f"<b>{title}</b>",
                       ParagraphStyle("bt", fontSize=11, textColor=white,
                                      fontName="Helvetica-Bold", leading=14)),
             Paragraph(desc,
                       ParagraphStyle("bd", fontSize=9.5, textColor=GREEN_100,
                                      fontName="Helvetica", leading=13))]]
    t = Table(data, colWidths=[4.2*cm, 10.3*cm], rowHeights=None)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
        ('BACKGROUND',    (0, 0), (0, 0),   GREEN_DARK),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [NAVY]),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.5, GREEN_DARK),
    ]))
    return t


def reason_row(num, title, desc):
    data = [[Paragraph(f"<font color='#22C55E'><b>{num}</b></font>",
                       ParagraphStyle("rn", fontSize=22, fontName="Helvetica-Bold",
                                      textColor=GREEN, alignment=TA_CENTER, leading=26)),
             Paragraph(f"<b>{title}</b>",
                       ParagraphStyle("rt", fontSize=12, fontName="Helvetica-Bold",
                                      textColor=NAVY, leading=15)),
             Paragraph(desc,
                       ParagraphStyle("rd", fontSize=10, fontName="Helvetica",
                                      textColor=MID_GRAY, leading=14))]]
    t = Table(data, colWidths=[1.5*cm, 6*cm, 8.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LIGHT_GRAY),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.5, HexColor('#E5E7EB')),
        ('LEFTPADDING',   (0, 0), (0, 0),   4),
        ('BACKGROUND',    (0, 0), (0, 0),   GREEN_100),
    ]))
    return t


# ── Construcción del documento ───────────────────────────────────────────────
story = []

LEFT_M  = 1.8*cm
RIGHT_M = 1.8*cm
TOP_M   = 1.5*cm
BOT_M   = 1.8*cm

doc = SimpleDocTemplate(
    OUT,
    pagesize=A4,
    leftMargin=LEFT_M + 0.8*cm,   # margen extra para la franja verde
    rightMargin=RIGHT_M + 0.6*cm,
    topMargin=TOP_M,
    bottomMargin=BOT_M + 0.8*cm,
    title="QoriCash FX — Presentación Corporativa",
    author="QoriCash S.A.C.",
    subject="Carta de Presentación Corporativa 2026",
)

# ── PORTADA ──────────────────────────────────────────────────────────────────
try:
    story.append(RLImage(LOGO, width=3.5*cm, height=3.5*cm))
except Exception:
    pass

story.append(Spacer(1, 0.8*cm))
story.append(Paragraph("QoriCash FX", style_cover_title))
story.append(Paragraph("QORICASH S.A.C.", style_cover_sub))
story.append(Spacer(1, 0.4*cm))
story.append(Paragraph(
    "Tu casa de cambio digital de confianza",
    ParagraphStyle("tagline", fontSize=16, leading=22, textColor=white,
                   fontName="Helvetica", alignment=TA_CENTER)))
story.append(Spacer(1, 0.6*cm))
story.append(Paragraph(
    "Presentación Corporativa · Abril 2026",
    style_cover_body))
story.append(Spacer(1, 2.0*cm))
story.append(Paragraph(
    "Seguridad · Rapidez · Transparencia · Confianza",
    ParagraphStyle("values", fontSize=12, leading=18, textColor=GREEN,
                   fontName="Helvetica-Bold", alignment=TA_CENTER)))
story.append(PageBreak())


# ── PÁGINA 1: INTRODUCCIÓN ───────────────────────────────────────────────────
story.append(Paragraph("Introducción Institucional", style_section_h))
story.append(divider())
story.append(Paragraph("Lima, abril de 2026", style_body))
story.append(Spacer(1, 6))
story.append(Paragraph("Estimado/a cliente:", style_body))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "En un mercado donde cada centavo cuenta, el tipo de cambio al que usted convierte sus divisas "
    "puede significar una diferencia real en su patrimonio. En <b>QoriCash FX</b> hemos construido "
    "una plataforma diseñada para que esa diferencia siempre juegue a su favor.",
    style_body))
story.append(Paragraph(
    "Somos una <b>casa de cambio 100% digital</b>, registrada y supervisada por la "
    "Superintendencia de Banca, Seguros y AFP del Perú (SBS, Resolución N° 00313-2026), "
    "con presencia en Lima y alcance nacional. Nuestra misión es simple: "
    "<b>democratizar el acceso a tipos de cambio justos</b>, eliminando la burocracia, "
    "los intermediarios innecesarios y las comisiones ocultas que históricamente han "
    "penalizado a las personas y empresas al momento de cambiar dólares.",
    style_body))
story.append(Paragraph(
    "Hoy, miles de clientes particulares y empresas confían en QoriCash para gestionar "
    "sus operaciones cambiarias de manera segura, rápida y completamente en línea.",
    style_body))
story.append(Spacer(1, 0.4*cm))

# Badge SBS
sbs_data = [[Paragraph(
    "<font color='white'><b>  Registrada ante la SBS — Resolución N° 00313-2026</b></font>",
    ParagraphStyle("sbs", fontSize=11, fontName="Helvetica-Bold",
                   textColor=white, alignment=TA_CENTER, leading=15))]]
sbs_t = Table(sbs_data, colWidths=[doc.width])
sbs_t.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, -1), GREEN_DARK),
    ('TOPPADDING',    (0, 0), (-1, -1), 10),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
]))
story.append(sbs_t)


# ── PÁGINA 2: QUIÉNES SOMOS ──────────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("Quiénes Somos", style_section_h))
story.append(divider())

story.append(Paragraph("Datos Corporativos", style_h2))
corp = [
    ("Razón Social",     "QORICASH S.A.C."),
    ("Nombre Comercial", "QORICASH FX"),
    ("RUC",              "20615113698"),
    ("Registro SBS",     "Resolución N° 00313-2026"),
    ("Dirección",        "Av. Brasil N° 2790, Int. 504 — Pueblo Libre, Lima, Perú"),
    ("Horario",          "Lunes a viernes: 9:00 a.m. – 6:00 p.m.  ·  Sábados: 9:00 a.m. – 1:00 p.m."),
    ("Teléfono/WhatsApp","926 011 920"),
    ("Correo",           "info@qoricash.pe"),
    ("Sitio Web",        "www.qoricash.pe"),
]
alt = True
for label, val in corp:
    story.append(info_row(label, val, LIGHT_GRAY if alt else white))
    alt = not alt

story.append(Spacer(1, 0.5*cm))
story.append(Paragraph("Misión", style_h2))
story.append(Paragraph(
    "Democratizar el acceso a tipos de cambio justos y competitivos, eliminando las barreras "
    "tradicionales del cambio de divisas mediante una plataforma digital segura, rápida y "
    "transparente. Ofrecemos nuestros servicios a personas naturales y jurídicas debidamente "
    "identificadas, desde cualquier parte del mundo, siempre que cuenten con una cuenta bancaria "
    "en el Perú.",
    style_body))

story.append(Paragraph("Visión", style_h2))
story.append(Paragraph(
    "Ser la casa de cambio digital líder del Perú, reconocida por nuestra innovación tecnológica, "
    "excelencia en el servicio y compromiso inquebrantable con la seguridad y satisfacción de "
    "nuestros clientes.",
    style_body))

story.append(Paragraph("Nuestros Valores", style_h2))
for v, d in [
    ("Seguridad",      "Cada operación protegida con cifrado de extremo a extremo."),
    ("Rapidez",        "Transferencias completadas en menos de 15 minutos."),
    ("Transparencia",  "El tipo de cambio que ve es exactamente el que obtiene. Sin costos ocultos."),
    ("Confianza",      "Construida operación a operación, cliente a cliente."),
]:
    story.append(Paragraph(
        f"<font color='#16A34A'>■</font>  <b>{v}:</b>  {d}",
        style_bullet))


# ── PÁGINA 3: CIFRAS ─────────────────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("Cifras que nos Respaldan", style_section_h))
story.append(divider())
story.append(Paragraph(
    "Resultados reales, construidos operación a operación.",
    style_section_sub))

stats_data = [
    ("8,500+",   "Usuarios\nregistrados"),
    ("S/ 18M+",  "Soles\ncambiados"),
    ("4,200+",   "Operaciones\ncompletadas"),
    ("4.8 ★",    "Satisfacción\ndel cliente"),
]
story.append(stat_table(stats_data))
story.append(Spacer(1, 0.6*cm))
story.append(Paragraph(
    "Más de 8,500 clientes ya eligieron el mejor tipo de cambio del Perú.",
    ParagraphStyle("highlight", fontSize=13, leading=18, textColor=GREEN_DARK,
                   fontName="Helvetica-Bold", alignment=TA_CENTER,
                   spaceBefore=8, spaceAfter=8)))


# ── PÁGINA 4: CÓMO FUNCIONA ──────────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("Cómo Funciona", style_section_h))
story.append(divider())
story.append(Paragraph("5 pasos simples para realizar su operación de cambio:", style_section_sub))

steps_data = [
    [
        Paragraph("<font color='#22C55E'><b>Paso</b></font>",
                  ParagraphStyle("sh", fontSize=10, fontName="Helvetica-Bold",
                                 textColor=GREEN, alignment=TA_CENTER, leading=13)),
        Paragraph("<font color='#22C55E'><b>Acción</b></font>",
                  ParagraphStyle("sh2", fontSize=10, fontName="Helvetica-Bold",
                                 textColor=GREEN, leading=13)),
        Paragraph("<font color='#22C55E'><b>Descripción</b></font>",
                  ParagraphStyle("sh3", fontSize=10, fontName="Helvetica-Bold",
                                 textColor=GREEN, leading=13)),
    ]
]
steps_body = [
    ("1", "Cotización en tiempo real",
     "Consulte el tipo de cambio vigente en www.qoricash.pe o nuestra app móvil. Las tasas se actualizan en tiempo real."),
    ("2", "Registro KYC gratuito",
     "Cree su cuenta con DNI, Carnet de Extranjería o RUC (empresas). Verificación 100% digital desde cualquier dispositivo."),
    ("3", "Solicite su operación",
     "Indique el monto a cambiar, seleccione sus cuentas bancarias de origen y destino, y confirme la operación."),
    ("4", "Realice la transferencia",
     "Transfiera a las cuentas de QoriCash y adjunte su comprobante. Un operador especializado procesará su operación."),
    ("5", "Reciba su dinero",
     "En menos de 15 minutos recibirá el monto en su cuenta y la factura/boleta electrónica oficial."),
]

for num, action, desc in steps_body:
    steps_data.append([
        Paragraph(f"<b>{num}</b>",
                  ParagraphStyle("sn", fontSize=18, fontName="Helvetica-Bold",
                                 textColor=white, alignment=TA_CENTER, leading=22)),
        Paragraph(f"<b>{action}</b>",
                  ParagraphStyle("sa", fontSize=11, fontName="Helvetica-Bold",
                                 textColor=NAVY, leading=15)),
        Paragraph(desc,
                  ParagraphStyle("sd", fontSize=10, fontName="Helvetica",
                                 textColor=MID_GRAY, leading=14)),
    ])

steps_t = Table(steps_data, colWidths=[1.4*cm, 5.0*cm, 9.6*cm])
row_styles = [
    ('BACKGROUND',    (0, 0), (-1, 0),   NAVY),
    ('BACKGROUND',    (0, 1), (0, -1),   GREEN),
    ('BACKGROUND',    (1, 1), (-1, -1),  LIGHT_GRAY),
    ('ROWBACKGROUNDS',(1, 1), (-1, -1),  [LIGHT_GRAY, white]),
    ('TOPPADDING',    (0, 0), (-1, -1),  8),
    ('BOTTOMPADDING', (0, 0), (-1, -1),  8),
    ('LEFTPADDING',   (0, 0), (-1, -1),  8),
    ('RIGHTPADDING',  (0, 0), (-1, -1),  8),
    ('VALIGN',        (0, 0), (-1, -1),  'MIDDLE'),
    ('LINEBELOW',     (0, 0), (-1, -1),  0.5, HexColor('#E5E7EB')),
    ('GRID',          (0, 0), (-1, -1),  0.3, HexColor('#D1D5DB')),
]
steps_t.setStyle(TableStyle(row_styles))
story.append(steps_t)


# ── PÁGINA 5: CANALES Y BANCOS ───────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("Canales de Acceso y Cobertura Bancaria", style_section_h))
story.append(divider())

story.append(Paragraph("Canales Disponibles", style_h2))
channels_data = [
    ["Canal", "Descripción"],
    ["Plataforma Web",    "www.qoricash.pe — disponible desde cualquier navegador"],
    ["App Móvil",         "Aplicación iOS y Android — opere desde su celular"],
    ["Dashboard",         "Historial completo, gestión de cuentas y seguimiento en tiempo real"],
    ["Atención WhatsApp", "+51 926 011 920 — soporte especializado por operadores humanos"],
]
ch_t = Table(
    [[Paragraph(f"<b>{r[0]}</b>" if i == 0 else r[0],
                ParagraphStyle("ch", fontSize=10, fontName="Helvetica-Bold" if i==0 else "Helvetica",
                               textColor=white if i==0 else NAVY, leading=14)),
      Paragraph(f"<b>{r[1]}</b>" if i == 0 else r[1],
                ParagraphStyle("cv", fontSize=10, fontName="Helvetica-Bold" if i==0 else "Helvetica",
                               textColor=white if i==0 else MID_GRAY, leading=14))]
     for i, r in enumerate(channels_data)],
    colWidths=[4.5*cm, 11.5*cm]
)
ch_t.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
    ('ROWBACKGROUNDS',(0, 1), (-1, -1), [LIGHT_GRAY, white]),
    ('TOPPADDING',    (0, 0), (-1, -1), 7),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ('LEFTPADDING',   (0, 0), (-1, -1), 10),
    ('GRID',          (0, 0), (-1, -1), 0.3, HexColor('#E5E7EB')),
    ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
]))
story.append(ch_t)
story.append(Spacer(1, 0.5*cm))

story.append(Paragraph("Entidades Bancarias Operativas", style_h2))
banks_data = [
    ["Entidad", "Cobertura", "Tiempo"],
    ["BCP",            "Todo el Perú",  "Inmediato"],
    ["Interbank",      "Todo el Perú",  "Inmediato"],
    ["BBVA",           "Lima",          "≥ 2 horas"],
    ["Scotiabank",     "Lima",          "≥ 2 horas"],
    ["BanBif",         "Lima",          "≥ 2 horas"],
    ["Banco Pichincha","Lima",          "≥ 2 horas"],
    ["Otros bancos",   "Lima",          "≥ 2 horas"],
]
bk_t = Table(
    [[Paragraph(f"<b>{c}</b>",
                ParagraphStyle("bkh", fontSize=10, fontName="Helvetica-Bold",
                               textColor=white if i==0 else (NAVY if j==0 else MID_GRAY),
                               leading=14, alignment=TA_CENTER if j > 0 else TA_LEFT))
      for j, c in enumerate(r)]
     for i, r in enumerate(banks_data)],
    colWidths=[5.0*cm, 5.0*cm, 6.0*cm]
)
bk_t.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
    ('BACKGROUND',    (2, 1), (2, 2),  GREEN_100),
    ('ROWBACKGROUNDS',(0, 1), (-1, -1), [LIGHT_GRAY, white]),
    ('TOPPADDING',    (0, 0), (-1, -1), 7),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ('LEFTPADDING',   (0, 0), (-1, -1), 10),
    ('GRID',          (0, 0), (-1, -1), 0.3, HexColor('#E5E7EB')),
    ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ('ALIGN',         (1, 0), (-1, -1), 'CENTER'),
]))
story.append(bk_t)


# ── PÁGINA 6: BENEFICIOS ─────────────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("Beneficios para el Cliente", style_section_h))
story.append(divider())

benefits = [
    ("Mejor Tipo de Cambio",
     "Tasas actualizadas en tiempo real, siempre por encima de los bancos del sistema financiero peruano."),
    ("Sin Comisiones Ocultas",
     "El tipo de cambio que ve es exactamente el que obtiene. S/ 0 en cargos adicionales."),
    ("Rapidez Garantizada",
     "BCP e Interbank: inmediato. Resto del sistema bancario: en menos de 15 minutos."),
    ("100% Digital",
     "Sin colas, sin desplazamientos, sin papeleos. Opere desde su celular o computadora."),
    ("Factura Electrónica SUNAT",
     "Boleta o factura electrónica emitida mediante Nubefact con validez tributaria plena."),
    ("Historial y Trazabilidad",
     "Dashboard personal con historial completo, comprobantes descargables y seguimiento en tiempo real."),
    ("Atención por WhatsApp",
     "Operadores humanos especializados disponibles para acompañarle en cada transacción."),
    ("Programa de Referidos",
     "Acumule pips por cada cliente referido y aplíquelos como mejora directa en su tipo de cambio."),
]

for title, desc in benefits:
    story.append(benefit_card(title, desc))

story.append(Spacer(1, 0.3*cm))


# ── PÁGINA 7: TIPO DE CAMBIO COMPARATIVO ────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("Tipo de Cambio Comparativo", style_section_h))
story.append(divider())
story.append(Paragraph(
    "Comparamos nuestras tasas vs. los principales bancos. Usted decide con información real, "
    "no con estimaciones.", style_body))
story.append(Spacer(1, 0.3*cm))

# Savings box
sav_data = [[Paragraph(
    "<font color='#22C55E'><b>Al cambiar $1,000 dólares — usted recibe hasta S/ 100 más que en un banco</b></font>",
    ParagraphStyle("sav", fontSize=12, fontName="Helvetica-Bold",
                   textColor=GREEN, alignment=TA_CENTER, leading=16))]]
sav_t = Table(sav_data, colWidths=[doc.width])
sav_t.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
    ('TOPPADDING',    (0, 0), (-1, -1), 12),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ('LEFTPADDING',   (0, 0), (-1, -1), 12),
]))
story.append(sav_t)
story.append(Spacer(1, 0.4*cm))

comp_data = [
    ["Entidad", "Compra (aprox.)", "Venta (aprox.)"],
    ["QoriCash FX  ⭐ MEJOR TASA", "MEJOR DEL MERCADO", "MEJOR DEL MERCADO"],
    ["BCP",         "S/ 3.340", "S/ 3.440"],
    ["Interbank",   "S/ 3.345", "S/ 3.435"],
    ["BBVA",        "S/ 3.330", "S/ 3.450"],
    ["Scotiabank",  "S/ 3.325", "S/ 3.455"],
]

def make_cell(txt, bold, tc, align):
    return Paragraph(f"<b>{txt}</b>" if bold else txt,
                     ParagraphStyle("cc", fontSize=10,
                                    fontName="Helvetica-Bold" if bold else "Helvetica",
                                    textColor=tc, alignment=align, leading=14))

comp_rows = []
for i, r in enumerate(comp_data):
    if i == 0:
        comp_rows.append([make_cell(c, True, white, TA_CENTER) for c in r])
    elif i == 1:
        comp_rows.append([
            make_cell(r[0], True, GREEN, TA_LEFT),
            make_cell(r[1], True, GREEN, TA_CENTER),
            make_cell(r[2], True, GREEN, TA_CENTER),
        ])
    else:
        comp_rows.append([
            make_cell(r[0], False, NAVY, TA_LEFT),
            make_cell(r[1], False, MID_GRAY, TA_CENTER),
            make_cell(r[2], False, MID_GRAY, TA_CENTER),
        ])

comp_t = Table(comp_rows, colWidths=[7.0*cm, 4.5*cm, 4.5*cm])
comp_t.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
    ('BACKGROUND',    (0, 1), (-1, 1),  HexColor('#052e16')),
    ('ROWBACKGROUNDS',(0, 2), (-1, -1), [LIGHT_GRAY, white]),
    ('TOPPADDING',    (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('LEFTPADDING',   (0, 0), (-1, -1), 10),
    ('GRID',          (0, 0), (-1, -1), 0.3, HexColor('#E5E7EB')),
    ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ('ALIGN',         (1, 0), (-1, -1), 'CENTER'),
]))
story.append(comp_t)
story.append(Spacer(1, 4))
story.append(Paragraph(
    "* Tasas bancarias son referenciales. Las de QoriCash se actualizan en tiempo real durante el horario de atención.",
    style_caption))


# ── PÁGINA 8: SEGURIDAD ──────────────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("Seguridad y Cumplimiento Regulatorio", style_section_h))
story.append(divider())
story.append(Paragraph(
    "La confianza no se declara — se construye con hechos y responsabilidad.",
    style_section_sub))

pillars = [
    ("Registro SBS — Res. N° 00313-2026",
     "QoriCash S.A.C. opera bajo supervisión de la Superintendencia de Banca, Seguros y AFP. "
     "Empresa constituida con RUC activo y plena responsabilidad legal y regulatoria ante el "
     "Estado peruano."),
    ("KYC — Conozca a su Cliente",
     "Todo cliente pasa por verificación digital de identidad (DNI, CE o RUC) antes de operar. "
     "Los documentos se almacenan de forma segura en entornos en la nube con acceso restringido."),
    ("PLAFT / AML — Prevención de Lavado de Activos",
     "Sistema propio de compliance con score de riesgo 0–100 por cliente, monitoreo continuo de "
     "operaciones, alertas automáticas por umbrales de monto (>$10k, >$50k, >$100k) y frecuencia, "
     "y screening contra listas internacionales de sanciones y PEPs (Personas Políticamente Expuestas)."),
    ("Cifrado y Protección de Datos",
     "Cifrado de extremo a extremo en todas las transacciones. Acceso restringido y trazabilidad "
     "completa de cada acción. Cumplimiento de la Ley de Protección de Datos Personales del Perú."),
    ("Libro de Reclamaciones",
     "Disponible en plataforma digital conforme a la normativa peruana. Cada reclamación recibe "
     "respuesta en los plazos establecidos por ley."),
]

for title, desc in pillars:
    story.append(KeepTogether([
        Paragraph(f"<font color='#16A34A'>▸</font>  <b>{title}</b>",
                  ParagraphStyle("pt", fontSize=12, fontName="Helvetica-Bold",
                                 textColor=NAVY, leading=16, spaceBefore=10)),
        Paragraph(desc, style_body),
    ]))
story.append(Spacer(1, 0.3*cm))


# ── PÁGINA 9: POR QUÉ ELEGIRNOS ─────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("8 Razones para Elegir QoriCash FX", style_section_h))
story.append(divider())

reasons = [
    ("01", "Supervisados por la SBS",
     "Registro oficial Res. 00313-2026. Operamos con plena transparencia regulatoria."),
    ("02", "Mejor tipo de cambio",
     "Tasas siempre por encima de los bancos, actualizadas en tiempo real."),
    ("03", "Tecnología de punta",
     "Plataforma web, app móvil y operadores humanos integrados en un solo sistema."),
    ("04", "Atención multicanal real",
     "WhatsApp + dashboard + plataforma web. Sin bots, con personas reales."),
    ("05", "Cobertura bancaria amplia",
     "7 entidades del sistema financiero peruano. BCP e Interbank: transferencia inmediata."),
    ("06", "Gestión empresarial completa",
     "Atendemos personas jurídicas con RUC, emisión de facturas y múltiples cuentas."),
    ("07", "Trazabilidad total",
     "Historial completo, comprobantes descargables y seguimiento en tiempo real."),
    ("08", "Programa de fidelización",
     "Cada referido le genera pips que mejoran directamente su tipo de cambio."),
]

for num, title, desc in reasons:
    story.append(reason_row(num, title, desc))
    story.append(Spacer(1, 3))


# ── PÁGINA 10: CIERRE ────────────────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph("Nuestra Promesa", style_section_h))
story.append(divider())
story.append(Paragraph(
    "Cambiar divisas no debería ser complicado, costoso ni inseguro. En QoriCash hemos trabajado "
    "para que cada operación sea simple, transparente y rentable para el cliente.",
    style_body))
story.append(Paragraph(
    "Somos conscientes de que al elegirnos usted nos confía algo más que dinero: nos confía su "
    "tiempo, su tranquilidad y la certeza de que la operación se realizará correctamente. "
    "Esa responsabilidad la tomamos con total seriedad.",
    style_body))
story.append(Spacer(1, 0.4*cm))

# CTA
cta_data = [[Paragraph(
    "<font color='white'><b>Créanos hoy. Compruébalo en su primera operación.</b></font>",
    ParagraphStyle("cta", fontSize=14, fontName="Helvetica-Bold",
                   textColor=white, alignment=TA_CENTER, leading=18))]]
cta_t = Table(cta_data, colWidths=[doc.width])
cta_t.setStyle(TableStyle([
    ('BACKGROUND',    (0, 0), (-1, -1), GREEN_DARK),
    ('TOPPADDING',    (0, 0), (-1, -1), 14),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
]))
story.append(cta_t)
story.append(Spacer(1, 0.6*cm))

story.append(Paragraph("Información de Contacto", style_h2))
contact_rows = [
    ("Sitio Web",        "www.qoricash.pe"),
    ("WhatsApp",         "+51 926 011 920"),
    ("Correo",           "info@qoricash.pe"),
    ("Dirección",        "Av. Brasil N° 2790, Int. 504 — Pueblo Libre, Lima, Perú"),
    ("Horario",          "Lun–Vie: 9:00 a.m. – 6:00 p.m.  ·  Sáb: 9:00 a.m. – 1:00 p.m."),
    ("Registro SBS",     "Res. N° 00313-2026"),
    ("RUC",              "20615113698"),
]
alt = True
for label, val in contact_rows:
    story.append(info_row(label, val, LIGHT_GRAY if alt else white))
    alt = not alt

story.append(Spacer(1, 0.5*cm))
story.append(Paragraph(
    "QORICASH S.A.C.  ·  RUC 20615113698  ·  Registrada ante la SBS, Res. N° 00313-2026",
    style_footer))
story.append(Paragraph("© 2026 QoriCash FX. Todos los derechos reservados.", style_footer))


# ── Generar PDF ───────────────────────────────────────────────────────────────
def _on_page(canvas, doc):
    if doc.page == 1:
        cover_bg(canvas, doc)
    else:
        later_page(canvas, doc)

doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
print(f"OK — PDF guardado en:\n{OUT}")

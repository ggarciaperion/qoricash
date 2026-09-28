"""
Genera el Informe Diario de Mercados de QoriCash en PDF.
Estilo idéntico al informe de referencia Informe_Mercados_QoriCash_YYYYMMDD.pdf

Uso:
    python3 docs/generar_informe_mercados.py [--output /ruta/archivo.pdf]

Requiere: DATABASE_URL, ANTHROPIC_API_KEY en .env
"""

import os, sys, json, argparse, logging
from datetime import datetime, timezone, timedelta

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, '.env'))
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

# ── DB standalone (PostgreSQL o SQLite) ───────────────────────────────────────
_DB_URL = os.environ.get('DATABASE_URL', '')
_USE_SQLITE = _DB_URL.startswith('sqlite://')

if _USE_SQLITE:
    import sqlite3
    _SQLITE_PATH = _DB_URL.replace('sqlite:///', '').replace('sqlite://', '')
    if not os.path.isabs(_SQLITE_PATH):
        for _p in [
            os.path.join(_ROOT, 'instance', _SQLITE_PATH),
            os.path.join(_ROOT, _SQLITE_PATH),
        ]:
            if os.path.exists(_p):
                _SQLITE_PATH = _p
                break

    def _conn():
        c = sqlite3.connect(_SQLITE_PATH)
        c.row_factory = sqlite3.Row
        return c

    def _query(sql, params=None):
        with _conn() as c:
            return [dict(r) for r in c.execute(sql.replace('%s','?'), params or ()).fetchall()]

    def _one(sql, params=None):
        rows = _query(sql, params)
        return rows[0] if rows else None

else:
    import psycopg2, psycopg2.extras
    _db_cs = _DB_URL
    for _s in ('postgresql+psycopg2://', 'postgresql+psycopg://', 'postgres://'):
        if _DB_URL.startswith(_s):
            _db_cs = 'postgresql://' + _DB_URL[len(_s):]
            break

    def _conn():
        return psycopg2.connect(_db_cs, cursor_factory=psycopg2.extras.RealDictCursor)

    def _query(sql, params=None):
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def _one(sql, params=None):
        rows = _query(sql, params)
        return rows[0] if rows else None

# ── Anthropic standalone ───────────────────────────────────────────────────────
import anthropic as _anthropic

def _ask_claude(prompt: str, max_tokens: int = 5000) -> dict:
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        raise RuntimeError('ANTHROPIC_API_KEY no configurada')
    client = _anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=max_tokens,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = msg.content[0].text.strip()
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0].strip()
    elif '```' in text:
        text = text.split('```')[1].split('```')[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Intentar reparar JSON truncado
        for end in ('}', ']}', '"]}}', '"]}'):
            try:
                return json.loads(text[:text.rfind(end)+len(end)] + '}')
            except Exception:
                pass
        raise

# ── Helpers ───────────────────────────────────────────────────────────────────
_LIMA = timezone(timedelta(hours=-5))

def _to_dt(val):
    if val is None: return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        val = val.rstrip('Z').replace('T', ' ')
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try: return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
            except ValueError: pass
    return None

def _fv(v, d=2):
    try: return f'{float(v):.{d}f}' if v is not None else '—'
    except: return '—'

def _pct(v, d=2):
    try:
        x = float(v)
        return f'{x:+.{d}f}%'
    except: return '—'

def _score_to_trend(net):
    ab = abs(net)
    if ab >= 8:   c = min(90 + (ab-8), 95)
    elif ab >= 5: c = 70 + (ab-5)*5
    elif ab >= 2: c = 45 + (ab-2)*8
    else:         c = 30 + ab*5
    t = 'alza' if net >= 3 else ('baja' if net <= -3 else 'estable')
    return t, c

# ── Reportlab ─────────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak, CondPageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import Image as RLImage

# Paleta exacta del PDF de referencia
C_NAVY     = HexColor('#0f172a')
C_SLATE    = HexColor('#334155')
C_GRAY_MD  = HexColor('#64748b')
C_GRAY_LT  = HexColor('#94a3b8')
C_RED      = HexColor('#dc2626')
C_GREEN    = HexColor('#16a34a')
C_AMBER    = HexColor('#d97706')
C_AMBER_DK = HexColor('#92400e')
C_GREEN_BG = HexColor('#effdf4')
C_AMBER_BG = HexColor('#fffbeb')
C_WHITE    = white

W, H = A4  # 595.3 × 841.9

LOGO = os.path.join(_ROOT, '..', 'qoricashweb', 'public', 'logo-principal.png')

_base = getSampleStyleSheet()
def _S(name, **kw):
    return ParagraphStyle(name, parent=_base['Normal'], **kw)

# Estilos exactos del PDF de referencia
st_header_brand  = _S('HB',  fontSize=8.5, fontName='Helvetica-Bold', textColor=C_WHITE, leading=11)
st_header_meta   = _S('HM',  fontSize=7.5, fontName='Helvetica',      textColor=C_GRAY_LT, leading=10)
st_header_date   = _S('HD',  fontSize=7.0, fontName='Helvetica',      textColor=C_GRAY_LT, leading=10)
st_title_page    = _S('TP',  fontSize=13,  fontName='Helvetica-Bold', textColor=C_NAVY, leading=17, spaceAfter=0)
st_date_green    = _S('DG',  fontSize=8.0, fontName='Helvetica-Bold', textColor=C_GREEN, leading=11, spaceAfter=0)
st_sub_meta      = _S('SM',  fontSize=8.0, fontName='Helvetica',      textColor=C_GRAY_MD, leading=11, spaceAfter=0)
st_footer_contact= _S('FC',  fontSize=6.5, fontName='Helvetica',      textColor=C_GRAY_MD, leading=9)
st_footer_page   = _S('FP',  fontSize=6.5, fontName='Helvetica',      textColor=C_GRAY_MD, leading=9)
st_disclaimer    = _S('DIS', fontSize=6.0, fontName='Helvetica',      textColor=C_GRAY_LT, leading=8)

st_ticker_label  = _S('TL',  fontSize=7.0, fontName='Helvetica-Bold', textColor=C_GRAY_MD, leading=9)
st_ticker_val_up = _S('TVU', fontSize=15,  fontName='Helvetica-Bold', textColor=C_RED,    leading=18)
st_ticker_val_dn = _S('TVD', fontSize=15,  fontName='Helvetica-Bold', textColor=C_GRAY_MD,leading=18)
st_ticker_chg    = _S('TC2', fontSize=7.0, fontName='Helvetica-Bold', textColor=C_GRAY_MD, leading=9)

st_sec_label     = _S('SL',  fontSize=8.0, fontName='Helvetica-Bold', textColor=C_WHITE, leading=10, alignment=TA_CENTER)
st_sec_title     = _S('ST',  fontSize=9.0, fontName='Helvetica-Bold', textColor=C_NAVY,  leading=12)
st_tbl_header    = _S('TH',  fontSize=7.5, fontName='Helvetica-Bold', textColor=C_GRAY_MD, leading=10)
st_tbl_name      = _S('TN',  fontSize=8.5, fontName='Helvetica-Bold', textColor=C_NAVY,  leading=11)
st_tbl_val       = _S('TV',  fontSize=9.0, fontName='Helvetica-Bold', textColor=C_NAVY,  leading=12)
st_tbl_chg_red   = _S('TR',  fontSize=8.0, fontName='Helvetica-Bold', textColor=C_RED,   leading=10)
st_tbl_chg_grn   = _S('TG',  fontSize=8.0, fontName='Helvetica-Bold', textColor=C_GREEN, leading=10)
st_tbl_chg_neu   = _S('TU',  fontSize=8.0, fontName='Helvetica-Bold', textColor=C_GRAY_MD, leading=10)
st_tbl_ctx       = _S('TX',  fontSize=8.5, fontName='Helvetica',      textColor=C_SLATE, leading=11)
st_tbl_ctx_bold  = _S('TXB', fontSize=8.5, fontName='Helvetica-Bold', textColor=C_SLATE, leading=11)
st_tbl_imp_red   = _S('IR',  fontSize=8.0, fontName='Helvetica-Bold', textColor=C_RED,   leading=10)
st_tbl_imp_grn   = _S('IG',  fontSize=8.0, fontName='Helvetica-Bold', textColor=C_GREEN, leading=10)
st_tbl_imp_neu   = _S('IN',  fontSize=8.0, fontName='Helvetica',      textColor=C_GRAY_MD, leading=10)

st_analysis_label= _S('AL',  fontSize=7.0, fontName='Helvetica-Bold', textColor=C_GREEN, leading=9)
st_analysis_body = _S('AB',  fontSize=8.5, fontName='Helvetica',      textColor=C_SLATE, leading=12, alignment=TA_JUSTIFY)
st_alert_title   = _S('AT',  fontSize=9.0, fontName='Helvetica-Bold', textColor=C_AMBER, leading=12)
st_alert_body    = _S('ABo', fontSize=8.5, fontName='Helvetica',      textColor=C_AMBER_DK, leading=12, alignment=TA_JUSTIFY)

st_dxy_val       = _S('DV',  fontSize=16,  fontName='Helvetica-Bold', textColor=C_RED,   leading=20)
st_sem_sig_alerta= _S('SSA', fontSize=8.0, fontName='Helvetica-Bold', textColor=C_AMBER, leading=10)
st_sem_sig_neu   = _S('SSN', fontSize=8.0, fontName='Helvetica-Bold', textColor=C_GRAY_MD,leading=10)
st_sem_sig_ok    = _S('SSO', fontSize=8.0, fontName='Helvetica-Bold', textColor=C_GREEN, leading=10)


# ── Canvas callbacks ──────────────────────────────────────────────────────────

def _make_on_page(total_pages, fecha_str, today_display):
    def on_page(canvas, doc):
        canvas.saveState()
        # Barra superior navy (exactamente como el PDF de referencia)
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, H - 28.3, W, 28.3, fill=1, stroke=0)
        # Logo area / brand
        canvas.setFillColor(C_WHITE)
        canvas.setFont('Helvetica-Bold', 8.5)
        canvas.drawString(45, H - 17, 'QORICASH')
        canvas.setFillColor(C_GRAY_LT)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(100, H - 17, '|  Informe de Mercados')
        canvas.setFont('Helvetica', 7.0)
        canvas.drawRightString(W - 45, H - 17, fecha_str)
        # Footer
        canvas.setFillColor(C_NAVY)
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawString(45, 48, 'Informe de Mercados')
        canvas.setFillColor(C_GREEN)
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(45, 36, today_display)
        canvas.setFillColor(C_GRAY_MD)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(45, 25, 'Tipo de cambio · Tasas · Commodities · Mercados globales · Análisis QoriCash')
        canvas.setFont('Helvetica', 6.5)
        canvas.drawString(45, 16, 'qoricash.pe  ·  +51 910 624 404  ·  Autorizado SBS')
        canvas.drawRightString(W - 45, 16, f'Página {doc.page} / {total_pages}')
        canvas.setFillColor(C_GRAY_LT)
        canvas.setFont('Helvetica', 6)
        canvas.drawString(45, 7, 'Informe de carácter informativo. Precios de mercado sujetos a variación. No constituye asesoría financiera.')
        canvas.restoreState()
    return on_page


# ── Flowable helpers ──────────────────────────────────────────────────────────

def _section_header(num: str, title: str) -> Table:
    """Badge verde con número + título de sección."""
    badge = Paragraph(f'<b>{num}</b>', st_sec_label)
    ttl   = Paragraph(title, st_sec_title)
    t = Table([[badge, ttl]], colWidths=[19.8, 450])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, 0), C_GREEN),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def _analysis_box(label: str, text: str, doc_width, bold_suffix: str = '') -> Table:
    """Caja verde clara con label ANÁLISIS QORICASH y texto."""
    content = [Paragraph(label, st_analysis_label)]
    # Texto con posible parte en negrita al final
    if bold_suffix and text.endswith(bold_suffix):
        normal_part = text[:-len(bold_suffix)]
        content.append(Paragraph(normal_part, st_analysis_body))
        content.append(Paragraph(bold_suffix, _S('ABS', fontSize=8.5, fontName='Helvetica-Bold',
                                                  textColor=C_SLATE, leading=12, alignment=TA_JUSTIFY)))
    else:
        content.append(Paragraph(text, st_analysis_body))
    data = [[content]]
    t = Table(data, colWidths=[doc_width])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_GREEN_BG),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
    ]))
    return t


def _alert_box(title: str, text: str, doc_width) -> Table:
    """Caja ámbar con alerta."""
    content = [
        Paragraph(f'⚠  {title}', st_alert_title),
        Paragraph(text, st_alert_body),
    ]
    data = [[content]]
    t = Table(data, colWidths=[doc_width])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_AMBER_BG),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
    ]))
    return t


def _chg_style(chg_str: str, up_ok: bool = True):
    """Estilo para variación según signo."""
    try:
        v = float(chg_str.replace('%','').replace('+',''))
        if v > 0:   return st_tbl_chg_red if not up_ok else st_tbl_chg_red
        elif v < 0: return st_tbl_chg_red
        return st_tbl_chg_neu
    except: return st_tbl_chg_neu


def _chg_para(chg_str: str) -> Paragraph:
    try:
        v = float(str(chg_str).replace('%','').replace('+',''))
        st = st_tbl_chg_red  # En el PDF de referencia siempre usa rojo para variaciones
    except:
        st = st_tbl_chg_neu
    return Paragraph(str(chg_str), st)


def _data_table(headers, rows, col_widths) -> Table:
    """Tabla de datos estilo referencia."""
    header_row = [Paragraph(h, st_tbl_header) for h in headers]
    table_rows = [header_row] + rows
    t = Table(table_rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.3, HexColor('#e2e8f0')),
    ]))
    return t


# ── Prompt Claude ─────────────────────────────────────────────────────────────

def _build_prompt(snap, fed_val, bcrp_val, net_score, trend, confidence, news_rows, events):
    g = snap.get if snap else lambda k, d=None: d

    def fv(k, d=2): return _fv(g(k), d)
    def pc(k, d=2): return _pct(g(k), d)

    fecha_hoy = datetime.now(_LIMA).strftime('%A %d de %B de %Y').capitalize()

    market_ctx = f"""
DATOS DE MERCADO ACTUALES — {fecha_hoy}

USD/PEN:      S/ {fv('usdpen',4)} ({pc('usdpen_chg_pct')})
DXY:          {fv('dxy',3)} ({pc('dxy_chg_pct')})
EUR/USD:      {fv('eurusd',4)} ({pc('eurusd_chg_pct')})
USD/JPY:      {fv('usdjpy',3)} ({pc('usdjpy_chg_pct')})
Treasury 10Y: {fv('treasury_10y',3)}% (chg: {fv('treasury_10y_chg',3)} pb)
Fed rate:     {f'{fed_val:.2f}%' if fed_val else 'N/D'}
BCRP rate:    {f'{bcrp_val:.2f}%' if bcrp_val else 'N/D'}
Petróleo WTI: US$ {fv('oil',2)} ({pc('oil_chg_pct')})
Oro (XAU):    US$ {fv('gold',2)} ({pc('gold_chg_pct')})
Cobre:        US$ {fv('copper',4)}/lb ({pc('copper_chg_pct')})
S&P 500:      {fv('sp500',2)} ({pc('sp500_chg_pct')})
Nasdaq:       {fv('nasdaq',2)} ({pc('nasdaq_chg_pct')})
VIX:          {fv('vix',2)} ({pc('vix_chg_pct')})
Bitcoin:      US$ {fv('btc',0)} ({pc('btc_chg_pct')})
EPU (Perú):   {fv('epu',2)} ({pc('epu_chg_pct')})
EEM (EM):     {fv('eem',2)} ({pc('eem_chg_pct')})

SEÑAL ENGINE: tendencia={trend} | confianza={confidence}% | net_score={net_score:+d}"""

    news_txt = ''
    for n in news_rows[:8]:
        arr = {'bullish_usd':'▲','bearish_usd':'▼'}.get(n.get('direction',''),'━')
        news_txt += f"  [{arr}][{n.get('impact_level','').upper()}] {n.get('title','')}\n"
    if not news_txt:
        news_txt = '  (sin noticias relevantes en ventana de 18h)'

    ev_txt = ''
    for ev in events[:5]:
        ev_txt += f"  {ev.get('flag','')} {ev.get('event_name','')} ({ev.get('country','')}) — {ev.get('impact','').upper()}\n"
    if not ev_txt:
        ev_txt = '  (sin eventos de alto impacto programados hoy)'

    return f"""Eres el analista senior de FX de QoriCash, casa de cambio digital en Lima Perú.
Genera el contenido completo para el Informe Diario de Mercados del {fecha_hoy}.
Escribe como trader FX experimentado en mercados emergentes. Sé específico, usa números reales.

{market_ctx}

NOTICIAS ÚLTIMAS 18H:
{news_txt}

EVENTOS HOY:
{ev_txt}

INSTRUCCIONES:
- Para cada activo de la tabla de tipo de cambio, genera un "contexto" de 1-2 líneas breves (máx 12 palabras por línea, 2 líneas)
- Para cada tabla, escribe texto analítico real y específico, no genérico
- El análisis QoriCash debe ser periodístico y preciso
- El campo "analisis_bold" es la oración o párrafo final en negrita (consejo operativo)
- Las señales del semáforo: "alerta" (preocupante), "neutro" (neutral), "ok" (positivo para el sol)
- Si un campo no tiene dato disponible, omítelo de la lista

Responde SOLO JSON válido con esta estructura exacta:
{{
  "tc_rows": [
    {{"par": "USD / PEN — Dólar · Sol peruano", "precio": "S/ X.XXX", "chg": "↑ +X.XX%", "contexto_l1": "...", "contexto_l2": "..."}},
    {{"par": "EUR / USD — Euro · Dólar",         "precio": "X.XXXX",   "chg": "↓ −X.XX%", "contexto_l1": "...", "contexto_l2": "..."}},
    {{"par": "USD / JPY — Dólar · Yen",          "precio": "XXX.XX",   "chg": "...",       "contexto_l1": "...", "contexto_l2": "..."}}
  ],
  "tc_analisis": "Párrafo de análisis del tipo de cambio (3-5 oraciones específicas con números).",
  "tc_analisis_bold": "Oración final en negrita con consejo operativo para importadores/exportadores.",

  "tasas_rows": [
    {{"entidad": "Fed — Reserva Federal EE.UU.", "tasa": "X.XX%", "estado": "...", "estado_color": "red|green|neutral", "notas_l1": "...", "notas_l2": "...", "notas_l3": "..."}},
    {{"entidad": "BCRP — Banco Central del Perú", "tasa": "X.XX%", "estado": "...", "estado_color": "...", "notas_l1": "...", "notas_l2": "...", "notas_l3": "..."}},
    {{"entidad": "Tesoro EE.UU. — T-Note 10 años", "tasa": "X.XX%", "estado": "...", "estado_color": "...", "notas_l1": "...", "notas_l2": "...", "notas_l3": "..."}}
  ],
  "tasas_analisis": "Análisis de tasas (3-4 oraciones).",
  "tasas_analisis_bold": "Implicación clave en negrita.",

  "commodities_rows": [
    {{"nombre": "Petróleo WTI",   "precio": "US$ XX.XX /bbl", "chg": "...", "contexto_l1": "...", "contexto_l2": "..."}},
    {{"nombre": "Oro — XAU/USD", "precio": "US$ X,XXX /oz",  "chg": "...", "contexto_l1": "...", "contexto_l2": "..."}},
    {{"nombre": "Cobre — COMEX", "precio": "US$ X.XX /lb",   "chg": "...", "contexto_l1": "...", "contexto_l2": "..."}}
  ],
  "commodities_analisis": "Análisis commodities (3-4 oraciones).",
  "commodities_analisis_bold": "Implicación para Perú en negrita.",

  "dxy_val": "XXX.XX",
  "dxy_chg": "↑ +X.XX%",
  "dxy_umbral": "...",
  "dxy_resistencia": "...",
  "dxy_tendencia": "...",
  "dxy_analisis": "Análisis DXY detallado (4-5 oraciones con niveles técnicos).",
  "dxy_analisis_bold": "Implicación directa en el sol en negrita.",

  "mercados_rows": [
    {{"activo": "S&P 500",        "nivel": "X,XXX.XX", "chg": "...", "contexto_l1": "...", "contexto_l2": "..."}},
    {{"activo": "Nasdaq Composite","nivel": "XX,XXX",   "chg": "...", "contexto_l1": "...", "contexto_l2": "..."}},
    {{"activo": "VIX — Volatilidad","nivel": "XX.XX",   "chg": "...", "contexto_l1": "...", "contexto_l2": "..."}},
    {{"activo": "Bitcoin (BTC/USD)","nivel": "US$ XX,XXX","chg": "...","contexto_l1": "...", "contexto_l2": "..."}}
  ],
  "mercados_analisis": "Análisis mercados bursátiles (3-4 oraciones).",
  "mercados_analisis_bold": "Señal clave para próximas sesiones en negrita.",

  "macro_rows": [
    {{"factor": "...", "situacion_l1": "...", "situacion_l2": "...", "impacto_l1": "...", "impacto_l2": "...", "impacto_color": "red|green|neutral"}},
    {{"factor": "...", "situacion_l1": "...", "situacion_l2": "...", "impacto_l1": "...", "impacto_l2": "...", "impacto_color": "..."}}
  ],
  "macro_analisis": "Análisis macro completo (4-6 oraciones, escenario base).",
  "macro_analisis_bold": "Escenario base y recomendación en negrita.",

  "alerta_titulo": "Alerta cambiaria — descripción breve del día",
  "alerta_texto": "Texto completo de alerta operativa (4-6 oraciones). Incluye escenarios y recomendación concreta con porcentaje de cobertura sugerido.",

  "semaforo": [
    {{"indicador": "USD/PEN",       "valor": "S/ X.XXX", "señal": "alerta|neutro|ok", "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "DXY",           "valor": "XXX.XX",   "señal": "...",              "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "T-Note 10Y",    "valor": "X.XX%",    "señal": "...",              "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "Petróleo WTI",  "valor": "US$ XX/bbl","señal": "...",             "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "VIX Volatilidad","valor": "XX.XX",   "señal": "...",              "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "Oro spot",      "valor": "US$ X,XXX/oz","señal": "...",           "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "Cobre COMEX",   "valor": "US$ X.XX/lb","señal": "...",            "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "S&P 500",       "valor": "X,XXX",    "señal": "...",              "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "Bitcoin",       "valor": "US$ XX,XXX","señal": "...",             "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "Fed funds rate","valor": "X.XX%",    "señal": "...",              "implicacion_l1": "...", "implicacion_l2": "..."}},
    {{"indicador": "BCRP tasa",     "valor": "X.XX%",    "señal": "...",              "implicacion_l1": "...", "implicacion_l2": "..."}}
  ]
}}"""


# ── Construir PDF ─────────────────────────────────────────────────────────────

def generar(output_path: str):
    now_lima  = datetime.now(_LIMA)
    today_str = now_lima.strftime('%d/%m/%Y')
    today_long= now_lima.strftime('%A, %d de %B de %Y').capitalize()
    hora_str  = now_lima.strftime('%H:%M')
    fecha_footer = today_long  # ej: "Jueves, 25 de septiembre de 2026"

    # ── Query datos ───────────────────────────────────────────────────────────
    snap = _one('SELECT * FROM market_snapshots ORDER BY captured_at DESC LIMIT 1')
    snap = dict(snap) if snap else {}

    snap_hora = '—'
    ts = _to_dt(snap.get('captured_at'))
    if ts:
        snap_hora = ts.astimezone(_LIMA).strftime('%H:%M')

    print(f'[DB] Snapshot USD/PEN={snap.get("usdpen","—")} @ {snap_hora}')

    desde = (now_lima - timedelta(hours=18)).astimezone(timezone.utc).replace(tzinfo=None)
    news_rows = _query(
        """SELECT title, direction, impact_level, source, fetched_at FROM market_news
           WHERE fetched_at >= %s AND direction != 'neutral'
           ORDER BY CASE impact_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    fetched_at DESC LIMIT 20""", (desde,))
    news_rows = [dict(r) for r in news_rows]

    hoy_s = now_lima.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    hoy_e = now_lima.replace(hour=23,minute=59,second=59).astimezone(timezone.utc).replace(tzinfo=None)
    events = _query(
        """SELECT event_date, flag, event_name, country, impact FROM economic_events
           WHERE event_date >= %s AND event_date <= %s
           ORDER BY CASE impact WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    event_date ASC""", (hoy_s, hoy_e))
    events = [dict(e) for e in events]

    fed_row  = _one("SELECT value FROM macro_indicators WHERE key='fed_rate' LIMIT 1")
    bcrp_row = _one("SELECT value FROM macro_indicators WHERE key='bcrp_rate' LIMIT 1")
    fed_val  = float(fed_row['value'])  if fed_row  and fed_row.get('value')  else None
    bcrp_val = float(bcrp_row['value']) if bcrp_row and bcrp_row.get('value') else None

    _w = {'high':3,'medium':2,'low':1}
    net_score = sum(_w.get(n.get('impact_level'),0) * (1 if n.get('direction')=='bullish_usd' else -1)
                    for n in news_rows)
    trend, confidence = _score_to_trend(net_score)
    print(f'[SCORE] net={net_score:+d} → {trend} {confidence}%')

    # ── Claude análisis ───────────────────────────────────────────────────────
    prompt = _build_prompt(snap, fed_val, bcrp_val, net_score, trend, confidence, news_rows, events)
    print('[AI] Llamando a Claude Sonnet...')
    ai = {}
    try:
        ai = _ask_claude(prompt, max_tokens=5000)
        print('[AI] OK')
    except Exception as e:
        print(f'[WARN] Claude: {e}')

    def _ag(key, default=''):
        return ai.get(key, default)

    # ── Documento ─────────────────────────────────────────────────────────────
    TOTAL_PAGES = 5
    on_page = _make_on_page(TOTAL_PAGES, fecha_footer, today_str)

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=45.4, rightMargin=45.4,
        topMargin=38,    bottomMargin=60,
        title=f'Informe de Mercados — QoriCash — {fecha_footer}',
        author='QoriCash',
    )
    DW = doc.width  # ~504.5 pt
    story = []

    # ─────────────────────────────────────────────────────────────────────────
    # PÁGINA 1: Ticker strip + TIPO DE CAMBIO
    # ─────────────────────────────────────────────────────────────────────────

    # Ticker strip (fondo verde claro #effdf4, exactamente como la referencia)
    g = snap.get if snap else (lambda k, d=None: d)

    def _ticker_cell(label, val, chg_str):
        arrow = '↑' if (chg_str or '').startswith('+') else ('↓' if '-' in (chg_str or '') else '')
        return [
            Paragraph(label, st_ticker_label),
            Paragraph(val, st_ticker_val_up),
            Paragraph(f'{arrow} {chg_str}', st_ticker_chg),
        ]

    usdpen_p   = f"S/ {_fv(g('usdpen'),4)}"
    usdpen_c   = _pct(g('usdpen_chg_pct'))
    dxy_p      = _fv(g('dxy'),3)
    dxy_c      = _pct(g('dxy_chg_pct'))
    gold_p     = f"US$ {_fv(g('gold'),0)}"
    gold_c     = _pct(g('gold_chg_pct'))
    oil_p      = f"US$ {_fv(g('oil'),2)}"
    oil_c      = _pct(g('oil_chg_pct'))

    ticker_data = [[
        _ticker_cell('USD / PEN', usdpen_p, usdpen_c),
        _ticker_cell('DXY — Índice USD', dxy_p, dxy_c),
        _ticker_cell('Oro spot (XAU)', gold_p, gold_c),
        _ticker_cell('Petróleo WTI', oil_p, oil_c),
    ]]
    ticker_t = Table(ticker_data, colWidths=[DW/4]*4)
    ticker_t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_GREEN_BG),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LINEAFTER',     (0, 0), (-2, -1), 0.5, HexColor('#bbf7d0')),
    ]))
    story.append(ticker_t)
    story.append(Spacer(1, 12))

    # SECCIÓN 01 — TIPO DE CAMBIO
    story.append(_section_header('01', 'TIPO DE CAMBIO'))
    story.append(Spacer(1, 6))

    tc_rows_data = _ag('tc_rows', [])
    if tc_rows_data:
        tbl_rows = []
        for r in tc_rows_data:
            ctx = r.get('contexto_l1','')
            if r.get('contexto_l2'):
                ctx += '\n' + r['contexto_l2']
            tbl_rows.append([
                Paragraph(r.get('par',''), st_tbl_name),
                Paragraph(r.get('precio',''), st_tbl_val),
                _chg_para(r.get('chg','')),
                Paragraph(ctx, st_tbl_ctx),
            ])
        story.append(_data_table(
            ['Par de divisas', 'Precio', 'Tendencia', 'Fuente'],
            tbl_rows,
            [180, 70, 65, DW-315]
        ))
    story.append(Spacer(1, 6))

    tc_analisis = _ag('tc_analisis','')
    tc_bold     = _ag('tc_analisis_bold','')
    if tc_analisis:
        full_text = tc_analisis + (' ' + tc_bold if tc_bold else '')
        story.append(_analysis_box('ANÁLISIS QORICASH', full_text, DW))
    story.append(Spacer(1, 14))

    # SECCIÓN 02 — TASAS DE INTERÉS (empieza en pág 1, puede fluir a pág 2)
    story.append(_section_header('02', 'TASAS DE INTERÉS'))
    story.append(Spacer(1, 6))

    tasas_rows_data = _ag('tasas_rows', [])
    _estado_color = {'red': st_tbl_chg_red, 'green': st_tbl_chg_grn, 'neutral': st_tbl_chg_neu}
    if tasas_rows_data:
        tbl_rows = []
        for r in tasas_rows_data:
            ec = r.get('estado_color','neutral')
            est_st = _estado_color.get(ec, st_tbl_chg_neu)
            notas = r.get('notas_l1','')
            if r.get('notas_l2'): notas += '\n' + r['notas_l2']
            if r.get('notas_l3'): notas += '\n' + r['notas_l3']
            tbl_rows.append([
                Paragraph(r.get('entidad',''), st_tbl_name),
                Paragraph(r.get('tasa',''), st_tbl_val),
                Paragraph(r.get('estado',''), est_st),
                Paragraph(notas, st_tbl_ctx),
            ])
        story.append(_data_table(
            ['Banco central / Instrumento', 'Tasa vigente', 'Estado', 'Notas'],
            tbl_rows,
            [175, 70, 90, DW-335]
        ))
    story.append(Spacer(1, 6))

    tasas_an = _ag('tasas_analisis','')
    tasas_bold = _ag('tasas_analisis_bold','')
    if tasas_an:
        story.append(_analysis_box('ANÁLISIS QORICASH', tasas_an + (' ' + tasas_bold if tasas_bold else ''), DW))

    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # PÁGINA 2 (cont.) → SECCIÓN 03 COMMODITIES
    # ─────────────────────────────────────────────────────────────────────────
    story.append(_section_header('03', 'COMMODITIES'))
    story.append(Spacer(1, 6))

    comm_rows_data = _ag('commodities_rows', [])
    if comm_rows_data:
        tbl_rows = []
        for r in comm_rows_data:
            ctx = r.get('contexto_l1','')
            if r.get('contexto_l2'): ctx += '\n' + r['contexto_l2']
            tbl_rows.append([
                Paragraph(r.get('nombre',''), st_tbl_name),
                Paragraph(r.get('precio',''), st_tbl_val),
                _chg_para(r.get('chg','')),
                Paragraph(ctx, st_tbl_ctx),
            ])
        story.append(_data_table(
            ['Commodity', 'Precio', 'Variación', 'Contexto'],
            tbl_rows,
            [150, 90, 65, DW-305]
        ))
    story.append(Spacer(1, 6))

    comm_an   = _ag('commodities_analisis','')
    comm_bold = _ag('commodities_analisis_bold','')
    if comm_an:
        story.append(_analysis_box('ANÁLISIS QORICASH', comm_an + (' ' + comm_bold if comm_bold else ''), DW))
    story.append(Spacer(1, 14))

    # SECCIÓN 04 — DXY
    story.append(_section_header('04', 'ÍNDICE DEL DÓLAR (DXY)'))
    story.append(Spacer(1, 6))

    dxy_row_data = [[
        Paragraph('DXY — Valor actual', st_tbl_header),
        Paragraph('Var. diaria', st_tbl_header),
        Paragraph('Umbral roto', st_tbl_header),
        Paragraph('Próxima resistencia', st_tbl_header),
        Paragraph('Tendencia', st_tbl_header),
    ], [
        Paragraph(_ag('dxy_val', _fv(g('dxy'),3)), st_dxy_val),
        _chg_para(_ag('dxy_chg', _pct(g('dxy_chg_pct')))),
        Paragraph(_ag('dxy_umbral','—'), st_tbl_ctx),
        Paragraph(_ag('dxy_resistencia','—'), st_tbl_ctx),
        Paragraph(_ag('dxy_tendencia','—'), _S('DTx', fontSize=8, fontName='Helvetica',
                                               textColor=C_GRAY_MD, leading=11)),
    ]]
    dxy_t = Table(dxy_row_data, colWidths=[80, 55, 100, 120, DW-355])
    dxy_t.setStyle(TableStyle([
        ('TOPPADDING',    (0,0),(-1,-1), 6),
        ('BOTTOMPADDING', (0,0),(-1,-1), 6),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
        ('LINEBELOW',     (0,0),(-1,-1), 0.3, HexColor('#e2e8f0')),
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
    ]))
    story.append(dxy_t)
    story.append(Spacer(1, 6))

    dxy_an   = _ag('dxy_analisis','')
    dxy_bold = _ag('dxy_analisis_bold','')
    if dxy_an:
        story.append(_analysis_box('ANÁLISIS QORICASH', dxy_an + (' ' + dxy_bold if dxy_bold else ''), DW))

    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # PÁGINA 3 → SECCIÓN 05 MERCADOS BURSÁTILES
    # ─────────────────────────────────────────────────────────────────────────
    story.append(_section_header('05', 'MERCADOS BURSÁTILES Y CRIPTOMONEDAS'))
    story.append(Spacer(1, 6))

    mkt_rows_data = _ag('mercados_rows', [])
    if mkt_rows_data:
        tbl_rows = []
        for r in mkt_rows_data:
            ctx = r.get('contexto_l1','')
            if r.get('contexto_l2'): ctx += '\n' + r['contexto_l2']
            tbl_rows.append([
                Paragraph(r.get('activo',''), st_tbl_name),
                Paragraph(r.get('nivel',''), st_tbl_val),
                _chg_para(r.get('chg','')),
                Paragraph(ctx, st_tbl_ctx),
            ])
        story.append(_data_table(
            ['Índice / Activo', 'Nivel', 'Variación', 'Contexto'],
            tbl_rows,
            [155, 85, 65, DW-305]
        ))
    story.append(Spacer(1, 6))

    mkt_an   = _ag('mercados_analisis','')
    mkt_bold = _ag('mercados_analisis_bold','')
    if mkt_an:
        story.append(_analysis_box('ANÁLISIS QORICASH', mkt_an + (' ' + mkt_bold if mkt_bold else ''), DW))
    story.append(Spacer(1, 14))

    # SECCIÓN 06 — CONTEXTO MACROECONÓMICO
    story.append(_section_header('06', 'CONTEXTO MACROECONÓMICO'))
    story.append(Spacer(1, 6))

    macro_rows_data = _ag('macro_rows', [])
    _imp_color = {'red': st_tbl_imp_red, 'green': st_tbl_imp_grn, 'neutral': st_tbl_imp_neu}
    if macro_rows_data:
        tbl_rows = []
        for r in macro_rows_data:
            ic = _imp_color.get(r.get('impacto_color','neutral'), st_tbl_imp_neu)
            sit = r.get('situacion_l1','')
            if r.get('situacion_l2'): sit += '\n' + r['situacion_l2']
            imp = r.get('impacto_l1','')
            if r.get('impacto_l2'): imp += '\n' + r['impacto_l2']
            tbl_rows.append([
                Paragraph(r.get('factor',''), st_tbl_name),
                Paragraph(sit, st_tbl_ctx),
                Paragraph(imp, ic),
            ])
        story.append(_data_table(
            ['Factor', 'Situación actual', 'Impacto en PEN/USD'],
            tbl_rows,
            [130, 195, DW-325]
        ))
    story.append(Spacer(1, 6))

    macro_an   = _ag('macro_analisis','')
    macro_bold = _ag('macro_analisis_bold','')
    if macro_an:
        story.append(_analysis_box('ANÁLISIS QORICASH', macro_an + (' ' + macro_bold if macro_bold else ''), DW))

    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # PÁGINA 4 → ALERTA + SECCIÓN 07 SEMÁFORO
    # ─────────────────────────────────────────────────────────────────────────

    alerta_titulo = _ag('alerta_titulo','')
    alerta_texto  = _ag('alerta_texto','')
    if alerta_titulo or alerta_texto:
        story.append(_alert_box(alerta_titulo, alerta_texto, DW))
        story.append(Spacer(1, 14))

    # SECCIÓN 07 — RESUMEN EJECUTIVO SEMÁFORO
    story.append(_section_header('07', 'RESUMEN EJECUTIVO — SEMÁFORO DE INDICADORES'))
    story.append(Spacer(1, 6))

    sem_rows_data = _ag('semaforo', [])
    _sig_style = {'alerta': st_sem_sig_alerta, 'neutro': st_sem_sig_neu, 'ok': st_sem_sig_ok}
    _sig_label = {'alerta': 'Alerta', 'neutro': 'Neutral', 'ok': 'OK'}

    if sem_rows_data:
        header_row = [
            Paragraph('Indicador', st_tbl_header),
            Paragraph('Valor', st_tbl_header),
            Paragraph('Señal', st_tbl_header),
            Paragraph('Implicación para operaciones de cambio', st_tbl_header),
        ]
        tbl_rows = [header_row]
        for r in sem_rows_data:
            sen = r.get('señal','neutro').lower()
            sig_st = _sig_style.get(sen, st_sem_sig_neu)
            sig_lb = _sig_label.get(sen, 'Neutral')
            impl = r.get('implicacion_l1','')
            if r.get('implicacion_l2'): impl += '\n' + r['implicacion_l2']
            row_bg = C_AMBER_BG if sen == 'alerta' else (C_GREEN_BG if sen == 'ok' else None)

            sem_row = [
                Paragraph(r.get('indicador',''), st_tbl_name),
                Paragraph(r.get('valor',''), st_tbl_val),
                Paragraph(f'● {sig_lb}', sig_st),
                Paragraph(impl, st_tbl_ctx),
            ]
            tbl_rows.append(sem_row)

        sem_t = Table(tbl_rows, colWidths=[110, 85, 65, DW-260], repeatRows=1)
        style = [
            ('TOPPADDING',    (0,0),(-1,-1), 5),
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING',   (0,0),(-1,-1), 6),
            ('RIGHTPADDING',  (0,0),(-1,-1), 6),
            ('VALIGN',        (0,0),(-1,-1), 'TOP'),
            ('LINEBELOW',     (0,0),(-1,-1), 0.3, HexColor('#e2e8f0')),
        ]
        for i, r in enumerate(sem_rows_data, start=1):
            sen = r.get('señal','neutro').lower()
            if sen == 'alerta':
                style.append(('BACKGROUND', (0,i),(-1,i), C_AMBER_BG))
            elif sen == 'ok':
                style.append(('BACKGROUND', (0,i),(-1,i), C_GREEN_BG))
        sem_t.setStyle(TableStyle(style))
        story.append(sem_t)

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f'[OK] PDF guardado en:\n     {output_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', '-o', default=None)
    args = parser.parse_args()

    if args.output:
        out = args.output
    else:
        fecha = datetime.now(timezone(timedelta(hours=-5))).strftime('%Y%m%d')
        out = os.path.join(_ROOT, 'docs', f'Informe_Mercados_QoriCash_{fecha}.pdf')

    os.makedirs(os.path.dirname(out), exist_ok=True)
    print('[QoriCash] Generando Informe de Mercados...')
    generar(out)

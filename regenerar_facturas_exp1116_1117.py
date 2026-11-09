"""
Diagnóstico y regeneración de facturas para EXP-1116 y EXP-1117.

Contexto:
  - Ambas operaciones están 'Completada' (9 de octubre de 2026)
  - Sus facturas (F001-387 y F001-388) quedaron en estado 'Error'
  - Las facturas en Error NUNCA llegaron a SUNAT (NubeFact las rechazó antes)
  - Se reusan los mismos números correlativos para no dejar huecos en la serie

Uso (en Render Shell):
    python3 regenerar_facturas_exp1116_1117.py            # diagnóstico + corrección
    python3 regenerar_facturas_exp1116_1117.py --solo-diagnostico  # solo ver errores

IMPORTANTE: Este script NO activa ni modifica ningún agente de prospección.
"""
import os, sys, json, requests
from datetime import datetime
import pytz

# ── Variables de entorno ─────────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: Define DATABASE_URL en el entorno")
    sys.exit(1)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

NUBEFACT_TOKEN   = os.environ.get('NUBEFACT_TOKEN', '')
NUBEFACT_API_URL = os.environ.get('NUBEFACT_API_URL', 'https://api.nubefact.com/api/v1')
COMPANY_RUC      = os.environ.get('COMPANY_RUC',      os.environ.get('NUBEFACT_RUC', '20615113698'))
COMPANY_NAME     = os.environ.get('COMPANY_NAME',     'QORICASH SAC')
COMPANY_ADDRESS  = os.environ.get('COMPANY_ADDRESS',  '')
COMPANY_DISTRICT = os.environ.get('COMPANY_DISTRICT', '')
COMPANY_PROVINCE = os.environ.get('COMPANY_PROVINCE', '')
COMPANY_DEPT     = os.environ.get('COMPANY_DEPARTMENT', '')

SOLO_DIAGNOSTICO = '--solo-diagnostico' in sys.argv

# Fecha valor de ambas operaciones (la de la operación real)
FECHA_EMISION = "09-10-2026"  # dd-mm-yyyy — formato NubeFact

OPERATIONS = ['EXP-1116', 'EXP-1117']

# ── Helpers ──────────────────────────────────────────────────────────────────
def now_peru():
    peru_tz = pytz.timezone('America/Lima')
    return datetime.now(pytz.utc).astimezone(peru_tz).replace(tzinfo=None)

def company_full_address():
    parts = [COMPANY_ADDRESS, COMPANY_DISTRICT, COMPANY_PROVINCE, COMPANY_DEPT]
    return ', '.join(p for p in parts if p)

def doc_type_code(doc_type):
    return {'DNI': '1', 'CE': '4', 'RUC': '6'}.get(doc_type, '1')

def generate_description(op_type, amount_usd, amount_pen, exchange_rate):
    if op_type == 'Venta':
        return (
            f"QORICASH VENDE {float(amount_usd):.2f} USD "
            f"CON TIPO DE CAMBIO {float(exchange_rate):.4f} - "
            f"CLIENTE ENVIA {float(amount_pen):.2f} PEN - "
            f"CLIENTE RECIBE {float(amount_usd):.2f} USD"
        )
    else:
        return (
            f"QORICASH COMPRA {float(amount_usd):.2f} USD "
            f"CON TIPO DE CAMBIO {float(exchange_rate):.4f} - "
            f"CLIENTE ENVIA {float(amount_usd):.2f} USD - "
            f"CLIENTE RECIBE {float(amount_pen):.2f} PEN"
        )

# ── Conexión a DB ─────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, text
engine = create_engine(DATABASE_URL)

print("=" * 70)
print("DIAGNÓSTICO — FACTURAS EXP-1116 / EXP-1117")
print("=" * 70)

rows_info = []

with engine.connect() as conn:
    for op_code in OPERATIONS:
        print(f"\n▶ {op_code}")

        # Operación
        op = conn.execute(text("""
            SELECT o.id, o.operation_id, o.status, o.operation_type,
                   o.amount_usd, o.amount_pen, o.exchange_rate, o.created_at,
                   c.id as client_id, c.full_name, c.document_type, c.dni,
                   c.email, c.full_address
            FROM operations o
            JOIN clients c ON c.id = o.client_id
            WHERE o.operation_id = :oid
        """), {'oid': op_code}).fetchone()

        if not op:
            print(f"  ERROR: operación {op_code} no encontrada en la DB")
            continue

        op = dict(op._mapping)
        print(f"  Estado: {op['status']}")
        print(f"  Tipo:   {op['operation_type']}")
        print(f"  Monto:  USD {float(op['amount_usd']):.2f} / PEN {float(op['amount_pen']):.2f}")
        print(f"  TC:     {float(op['exchange_rate']):.4f}")
        print(f"  Cliente: {op['full_name']} ({op['document_type']} {op['dni']})")
        print(f"  Creada: {op['created_at']}")

        # Facturas existentes
        invoices = conn.execute(text("""
            SELECT id, invoice_number, serie, numero, status, error_message,
                   nubefact_response, created_at
            FROM invoices
            WHERE operation_id = :oid
            ORDER BY id
        """), {'oid': op['id']}).fetchall()

        if not invoices:
            print("  Facturas: ninguna registrada")
        else:
            for inv in invoices:
                inv = dict(inv._mapping)
                print(f"  Factura: {inv['invoice_number']}  estado={inv['status']}")
                if inv['error_message']:
                    print(f"  ⚠  Error: {inv['error_message']}")
                if inv['nubefact_response']:
                    try:
                        resp = json.loads(inv['nubefact_response'].replace("'", '"'))
                        print(f"  Resp NubeFact: {resp}")
                    except Exception:
                        print(f"  Resp NubeFact (raw): {inv['nubefact_response'][:300]}")

        rows_info.append({'op': op, 'invoices': [dict(i._mapping) for i in invoices]})

# ── Salir si solo diagnóstico ─────────────────────────────────────────────────
if SOLO_DIAGNOSTICO:
    print("\n[--solo-diagnostico] No se realizaron cambios.")
    sys.exit(0)

# ── Validaciones antes de corregir ───────────────────────────────────────────
if not NUBEFACT_TOKEN:
    print("\nERROR: NUBEFACT_TOKEN no está configurado — no se puede enviar a NubeFact")
    sys.exit(1)

for item in rows_info:
    op = item['op']
    if op['status'] != 'Completada':
        print(f"\nERROR: {op['operation_id']} no está en estado Completada (estado={op['status']})")
        sys.exit(1)
    existing_ok = [i for i in item['invoices'] if i['status'] in ('Aceptado', 'Demo')]
    if existing_ok:
        print(f"\nAVISO: {op['operation_id']} ya tiene factura aceptada: {existing_ok[0]['invoice_number']}")
        print("No se regenerará esta operación.")
        rows_info = [r for r in rows_info if r['op']['operation_id'] != op['operation_id']]

if not rows_info:
    print("\nNada que regenerar — todas las operaciones ya tienen factura aceptada.")
    sys.exit(0)

print("\n" + "=" * 70)
print("REGENERACIÓN CON FECHA VALOR 09-10-2026")
print("=" * 70)

# ── Obtener correlativos a reusar ─────────────────────────────────────────────
# Las facturas en Error nunca llegaron a SUNAT → podemos reusar sus números.
# Si no tienen número asignado → calcular el siguiente libre.

def get_correlativo_a_usar(conn, op_id, serie, error_invoices):
    """
    Devuelve el número a usar.
    - Si hay una factura Error con número → reusamos ese número
    - Si no hay número → calculamos el siguiente disponible
    """
    for inv in error_invoices:
        if inv['serie'] == serie and inv['numero']:
            try:
                return int(inv['numero'])
            except (ValueError, TypeError):
                pass
    # Calcular siguiente libre
    result = conn.execute(text("""
        SELECT MAX(CAST(numero AS INTEGER))
        FROM invoices
        WHERE serie = :serie AND numero ~ '^[0-9]+$'
    """), {'serie': serie}).scalar()
    return (result or 0) + 1

results = []

with engine.begin() as conn:
    for item in rows_info:
        op         = item['op']
        op_code    = op['operation_id']
        error_invs = [i for i in item['invoices'] if i['status'] == 'Error']

        # Tipo de comprobante
        if op['document_type'] == 'RUC':
            invoice_type_name = 'Factura'
            invoice_type_code = '1'
            serie = 'F001'
        else:
            invoice_type_name = 'Boleta'
            invoice_type_code = '2'
            serie = 'B002'

        numero = get_correlativo_a_usar(conn, op['id'], serie, error_invs)
        invoice_number = f"{serie}-{numero}"

        print(f"\n▶ {op_code} → {invoice_number}  (fecha emision: {FECHA_EMISION})")

        # Descripción
        description = generate_description(
            op['operation_type'],
            op['amount_usd'],
            op['amount_pen'],
            op['exchange_rate']
        )
        total_amount = float(op['amount_pen'])

        # Payload NubeFact
        payload = {
            "operacion": "generar_comprobante",
            "tipo_de_comprobante": invoice_type_code,
            "serie": serie,
            "numero": numero,
            "sunat_transaction": 1,
            "cliente_tipo_de_documento": int(doc_type_code(op['document_type'])),
            "cliente_numero_de_documento": op['dni'],
            "cliente_denominacion": op['full_name'] or "CLIENTE",
            "cliente_direccion": op['full_address'] or "-",
            "cliente_email": op['email'].split(';')[0] if op['email'] else "",
            "cliente_email_1": "",
            "cliente_email_2": "",
            "fecha_de_emision": FECHA_EMISION,
            "fecha_de_vencimiento": "",
            "moneda": 1,
            "tipo_de_cambio": "",
            "porcentaje_de_igv": 18.00,
            "descuento_global": "",
            "total_descuento": "",
            "total_anticipo": "",
            "total_gravada": 0,
            "total_inafecta": total_amount,
            "total_exonerada": 0,
            "total_igv": 0,
            "total_gratuita": 0,
            "total_otros_cargos": 0,
            "total": total_amount,
            "percepcion_tipo": "",
            "percepcion_base_imponible": "",
            "total_percepcion": "",
            "total_incluido_percepcion": "",
            "detraccion": False,
            "observaciones": f"Operación #{op_code}",
            "documento_que_se_modifica_tipo": None,
            "documento_que_se_modifica_serie": None,
            "documento_que_se_modifica_numero": None,
            "tipo_de_nota_de_credito": None,
            "tipo_de_nota_de_debito": None,
            "enviar_automaticamente_a_la_sunat": True,
            "enviar_automaticamente_al_cliente": False,
            "codigo_unico": op_code,
            "condiciones_de_pago": "",
            "medio_de_pago": "",
            "placa_vehiculo": "",
            "orden_compra_servicio": "",
            "tabla_personalizada_codigo": "",
            "formato_de_pdf": "",
            "items": [{
                "unidad_de_medida": "ZZ",
                "codigo": "001",
                "descripcion": description,
                "cantidad": 1,
                "valor_unitario": total_amount,
                "precio_unitario": total_amount,
                "subtotal": total_amount,
                "tipo_de_igv": 9,
                "igv": 0,
                "total": total_amount,
                "anticipo_regularizacion": False
            }]
        }

        print(f"  Enviando a NubeFact... ({NUBEFACT_API_URL})")

        try:
            resp = requests.post(
                NUBEFACT_API_URL,
                json=payload,
                headers={
                    'Authorization': f'Token token="{NUBEFACT_TOKEN}"',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            resp_data = resp.json()
        except Exception as e:
            print(f"  ❌ Error de conexión con NubeFact: {e}")
            results.append({'op': op_code, 'ok': False, 'error': str(e)})
            continue

        print(f"  HTTP {resp.status_code} → {resp_data}")

        enlace_pdf = resp_data.get('enlace_del_pdf', '')
        enlace_xml = resp_data.get('enlace_del_xml', '')
        aceptada   = resp_data.get('aceptada_por_sunat', False)
        sunat_desc = resp_data.get('sunat_description', '')

        if resp.status_code in (200, 201) and enlace_pdf and enlace_xml:
            new_status = 'Aceptado' if aceptada else 'Demo'
            now = now_peru()

            # Eliminar registros Error anteriores para esta operación
            conn.execute(text("""
                DELETE FROM invoices
                WHERE operation_id = :oid AND status = 'Error'
            """), {'oid': op['id']})

            # Insertar nuevo registro de factura
            conn.execute(text("""
                INSERT INTO invoices (
                    operation_id, client_id, invoice_type, serie, numero, invoice_number,
                    emisor_ruc, emisor_razon_social, emisor_direccion,
                    cliente_tipo_documento, cliente_numero_documento, cliente_denominacion,
                    cliente_direccion, cliente_email,
                    descripcion, monto_total, moneda, exonerada, gravada, igv,
                    status, nubefact_response, nubefact_enlace_pdf, nubefact_enlace_xml,
                    nubefact_aceptada_por_sunat, nubefact_sunat_description,
                    sent_at, accepted_at, created_at, updated_at
                ) VALUES (
                    :op_id, :client_id, :inv_type, :serie, :numero, :inv_number,
                    :ruc, :razon_social, :address,
                    :cli_doc_type, :cli_doc_num, :cli_name,
                    :cli_address, :cli_email,
                    :desc, :total, 'PEN', :total, 0, 0,
                    :status, :nf_resp, :pdf, :xml,
                    :sunat_ok, :sunat_desc,
                    :now, :accepted_at, :now, :now
                )
            """), {
                'op_id':      op['id'],
                'client_id':  op['client_id'],
                'inv_type':   invoice_type_name,
                'serie':      serie,
                'numero':     str(numero),
                'inv_number': invoice_number,
                'ruc':        COMPANY_RUC,
                'razon_social': COMPANY_NAME,
                'address':    company_full_address(),
                'cli_doc_type': op['document_type'],
                'cli_doc_num':  op['dni'],
                'cli_name':     op['full_name'] or 'CLIENTE',
                'cli_address':  op['full_address'] or '',
                'cli_email':    op['email'] or '',
                'desc':       description,
                'total':      total_amount,
                'status':     new_status,
                'nf_resp':    str(resp_data),
                'pdf':        enlace_pdf,
                'xml':        enlace_xml,
                'sunat_ok':   aceptada,
                'sunat_desc': sunat_desc,
                'now':        now,
                'accepted_at': now if aceptada else None,
            })

            print(f"  ✅ {invoice_number} registrada como '{new_status}'")
            if enlace_pdf:
                print(f"  📄 PDF: {enlace_pdf}")
            results.append({'op': op_code, 'ok': True, 'invoice': invoice_number,
                            'pdf': enlace_pdf, 'status': new_status})
        else:
            error_msg = resp_data.get('errors', resp_data.get('sunat_description', 'Error desconocido'))
            print(f"  ❌ NubeFact rechazó el comprobante: {error_msg}")
            results.append({'op': op_code, 'ok': False, 'error': str(error_msg)})

# ── Resumen final ─────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("RESUMEN")
print("=" * 70)
for r in results:
    if r.get('ok'):
        print(f"  ✅ {r['op']} → {r['invoice']}  [{r['status']}]  PDF: {r.get('pdf', '')}")
    else:
        print(f"  ❌ {r['op']} → ERROR: {r.get('error')}")

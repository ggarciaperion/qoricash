"""
scripts/limpiar_pipeline.py — Auditoría y limpieza del Pipeline Comercial

Clasifica todas las oportunidades en oportunidades_comerciales y elimina
las que no representan oportunidades reales de negocio.

Categorías de clasificación:
  REAL             — oportunidad legítima (mantener)
  INTERNO_QORICASH — email @qoricash.pe (eliminar)
  TEST_DEMO        — asunto o empresa con [PRUEBA/TEST/DEMO] (eliminar)
  AUTO_REPLY       — respuesta automática mal clasificada (eliminar)
  PROMOCIONAL      — newsletter, marketing, delivery notification (eliminar)
  DUPLICADO        — mismo gmail_message_id repetido (eliminar el menor id)

Uso:
  cd /ruta/al/proyecto/qoricash
  python3 scripts/limpiar_pipeline.py              # modo auditoría (solo muestra)
  python3 scripts/limpiar_pipeline.py --borrar     # ejecuta la limpieza real
  python3 scripts/limpiar_pipeline.py --borrar --confirmar  # sin prompt interactivo
"""
import os
import sys
import re
from pathlib import Path

# Añadir el directorio raíz al path para poder importar la app Flask
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Reglas de clasificación ─────────────────────────────────────────────────

INTERNAL_DOMAINS = {'qoricash.pe', 'qoricash.com'}

TEST_PATTERNS = [
    r'\[prueba', r'\[test', r'\[demo',
    r'prueba\s+de\s+envio', r'correo\s+de\s+prueba',
    r'email\s+de\s+prueba', r'test\s+email',
    r'prueba\s+prospecci', r'\btest\b.*\bprecio', r'\bprueba\b.*\bprecio',
]
_TEST_RE = [re.compile(p, re.IGNORECASE) for p in TEST_PATTERNS]

AUTO_REPLY_PATTERNS = [
    'out of office', 'fuera de oficina', 'automatic reply',
    'respuesta automatica', 'autorespuesta', 'auto-reply',
    'de vacaciones', 'not available', 'on leave',
]

PROMO_PATTERNS = [
    'newsletter', 'boletin', 'boletín', 'oferta especial', 'descuento',
    'suscripcion', 'suscripción', 'delivery status notification',
    'undeliverable', 'mail delivery failed', 'returned to sender',
    'estado de cuenta', 'factura electronica', 'recibo de pago',
    'confirmacion de pago', 'codigo de verificacion',
    'mailer-daemon', 'postmaster',
]

PROMO_ACCOUNT_ORIGINS = {
    'westernunion.com', 'paypal.com', 'visa.com', 'mailchimp.com',
    'sendgrid.net', 'sendgrid.com', 'amazonses.com',
}

TIPOS_COMERCIALES = {
    'solicita_cotizacion', 'solicita_llamada', 'solicita_whatsapp',
    'interesado', 'solicita_informacion', 'consulta_tc',
    'respuesta_positiva', 'referido',
}

# Tipos nunca deben estar en el pipeline (fueron mal derivados)
TIPOS_NO_PIPELINE = {
    'bounce_hard', 'bounce_soft', 'bounce',
    'fuera_oficina', 'auto_reply', 'irrelevante',
    'no_interesado', 'no_contactar', 'persona_incorrecta',
}


def _norm(s: str) -> str:
    return (s.lower()
            .replace('ó', 'o').replace('é', 'e').replace('á', 'a')
            .replace('í', 'i').replace('ú', 'u').replace('ñ', 'n'))


def clasificar(op) -> str:
    """
    Retorna categoría de la oportunidad:
      REAL | INTERNO_QORICASH | TEST_DEMO | AUTO_REPLY | PROMOCIONAL | TIPO_INVALIDO
    """
    email        = (op.email or '').lower().strip()
    empresa      = _norm(op.empresa or '')
    necesidad    = _norm(op.necesidad or '')
    sujeto       = _norm(op.cuerpo_email or '')   # campo cuerpo_email guarda el asunto original
    tipo         = (op.tipo if hasattr(op, 'tipo') else None)
    cuenta       = (op.cuenta_origen or '').lower()

    # 1. Interno Qoricash
    if email:
        domain = email.split('@')[-1] if '@' in email else ''
        if domain in INTERNAL_DOMAINS:
            return 'INTERNO_QORICASH'

    # 2. Tipo claramente no comercial
    # (si el tipo fue guardado en necesidad o cuerpo_email)
    for tipo_invalido in TIPOS_NO_PIPELINE:
        if tipo_invalido in necesidad or tipo_invalido in sujeto:
            return 'TIPO_INVALIDO'

    # 3. Test / Demo
    texto_clasif = empresa + ' ' + necesidad + ' ' + sujeto
    for pat in _TEST_RE:
        if pat.search(texto_clasif):
            return 'TEST_DEMO'

    # 4. Auto-reply
    if any(k in sujeto for k in AUTO_REPLY_PATTERNS):
        return 'AUTO_REPLY'
    if any(k in necesidad for k in AUTO_REPLY_PATTERNS):
        return 'AUTO_REPLY'

    # 5. Promocional / no comercial
    if any(k in sujeto for k in PROMO_PATTERNS):
        return 'PROMOCIONAL'
    if any(k in necesidad for k in PROMO_PATTERNS):
        return 'PROMOCIONAL'
    if cuenta:
        cuenta_domain = cuenta.split('@')[-1] if '@' in cuenta else cuenta
        if cuenta_domain in PROMO_ACCOUNT_ORIGINS:
            return 'PROMOCIONAL'

    # 6. Email de sistema o notificación
    if email:
        local = email.split('@')[0]
        if re.match(r'^(noreply|no-reply|notifications?|alerts?|mailer|bounce|system)', local):
            return 'INTERNO_SISTEMA'

    return 'REAL'


def run_audit(borrar: bool = False, confirmar: bool = False):
    from app import create_app
    from app.extensions import db
    from app.models.inteligencia import Oportunidad

    app = create_app()
    with app.app_context():
        ops = Oportunidad.query.order_by(Oportunidad.id).all()
        total = len(ops)
        print(f"\n{'='*60}")
        print(f"AUDITORÍA PIPELINE COMERCIAL — {total} oportunidades")
        print(f"{'='*60}\n")

        por_categoria = {}
        ids_eliminar = []

        # Detectar duplicados por gmail_msg_id
        seen_msg_ids = {}
        duplicados_ids = set()
        for op in ops:
            mid = op.mensaje_id or ''
            if mid:
                if mid in seen_msg_ids:
                    # Mantener el de mayor id, marcar el menor como duplicado
                    older_id = min(seen_msg_ids[mid], op.id)
                    duplicados_ids.add(older_id)
                    seen_msg_ids[mid] = max(seen_msg_ids[mid], op.id)
                else:
                    seen_msg_ids[mid] = op.id

        for op in ops:
            if op.id in duplicados_ids:
                cat = 'DUPLICADO'
            else:
                cat = clasificar(op)
            por_categoria.setdefault(cat, []).append(op)
            if cat != 'REAL':
                ids_eliminar.append(op.id)

        # Mostrar resumen
        print(f"{'Categoría':<20} {'Count':>6}  {'Acción'}")
        print('-' * 45)
        for cat in ['REAL', 'INTERNO_QORICASH', 'TEST_DEMO', 'AUTO_REPLY',
                    'PROMOCIONAL', 'TIPO_INVALIDO', 'INTERNO_SISTEMA', 'DUPLICADO']:
            items = por_categoria.get(cat, [])
            accion = 'MANTENER' if cat == 'REAL' else 'ELIMINAR'
            print(f"  {cat:<18} {len(items):>6}  {accion}")

        print(f"\nTotal a mantener: {len(por_categoria.get('REAL', []))}")
        print(f"Total a eliminar: {len(ids_eliminar)}")

        # Detalle de no-REAL
        for cat in ['INTERNO_QORICASH', 'TEST_DEMO', 'AUTO_REPLY',
                    'PROMOCIONAL', 'TIPO_INVALIDO', 'INTERNO_SISTEMA', 'DUPLICADO']:
            items = por_categoria.get(cat, [])
            if not items:
                continue
            print(f"\n  [{cat}] — {len(items)} registros:")
            for op in items[:20]:
                print(f"    id={op.id:4d}  email={op.email or 'N/A':<35}  "
                      f"empresa={op.empresa or 'N/A':<30}  estado={op.estado}")
            if len(items) > 20:
                print(f"    ... y {len(items)-20} más")

        # Detalle de REAL
        reales = por_categoria.get('REAL', [])
        print(f"\n  [REAL] — {len(reales)} oportunidades legítimas:")
        if reales:
            for op in reales:
                print(f"    id={op.id:4d}  email={op.email or 'N/A':<35}  "
                      f"empresa={op.empresa or 'N/A':<30}  "
                      f"tipo={op.necesidad[:40] if op.necesidad else 'N/A'}  "
                      f"estado={op.estado}")
        else:
            print("    (ninguna oportunidad real encontrada — pipeline vacío después de limpieza)")

        if not borrar:
            print("\n[MODO AUDITORÍA] — Para ejecutar la limpieza: --borrar")
            return

        if not ids_eliminar:
            print("\nNada que eliminar.")
            return

        if not confirmar:
            resp = input(f"\n¿Confirmar eliminación de {len(ids_eliminar)} registros? [s/N] ")
            if resp.strip().lower() not in ('s', 'si', 'sí', 'y', 'yes'):
                print("Cancelado.")
                return

        # Ejecutar limpieza
        deleted = Oportunidad.query.filter(Oportunidad.id.in_(ids_eliminar)).delete(
            synchronize_session=False
        )
        db.session.commit()
        print(f"\n✓ {deleted} registros eliminados del pipeline.")
        print(f"✓ {len(reales)} oportunidades reales conservadas.")
        print(f"\nPipeline limpio. Si hay 0 oportunidades reales, el pipeline")
        print(f"mostrará 'Sin datos' en lugar de datos de prueba.")


if __name__ == '__main__':
    borrar    = '--borrar' in sys.argv
    confirmar = '--confirmar' in sys.argv
    run_audit(borrar=borrar, confirmar=confirmar)

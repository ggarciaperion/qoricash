"""
Agente 2: Email Intelligence Agent
Analiza todas las bandejas de correo cada 15 minutos.
Detecta respuestas, rebotes, oportunidades y actualiza el CRM.
"""
import logging
import os
import re
import base64
from datetime import timedelta, timezone, datetime
from .base import BaseAgent

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))

_BANDEJAS_ENV = {
    'ggarcia@qoricash.pe':  'GMAIL_REFRESH_TOKEN_GGARCIA',
    'gerencia@qoricash.pe': 'GMAIL_REFRESH_TOKEN_GERENCIA',
    'info@qoricash.pe':     'GMAIL_REFRESH_TOKEN_INFO',
}

_BOUNCE_SENDERS = re.compile(
    r'(mailer.daemon|postmaster|delivery.failure|bounce|noreply.*delivery'
    r'|no.reply.*bounce|mail.*delivery|mailerdaemon)',
    re.I
)
_BOUNCE_SUBJECTS = re.compile(
    r'(undeliverable|delivery.status.notification|mail.delivery.fail'
    r'|returned.mail|delivery.failure|bounce|smtp.error)',
    re.I
)

_POSITIVE_KEYWORDS = re.compile(
    r'(cotizaci[oó]n|precio|cu[aá]nto.cobran|inter[eé]s|cuándo.puedo|'
    r'información|cu[eé]ntame|hablemos|llamada|reuni[oó]n|whatsapp|'
    r'disponible|trabajemos|adelante|me.interesa|quiero.saber)',
    re.I
)
_NO_CONTACT_KEYWORDS = re.compile(
    r'(no.me.contacte|no.contactar|remover|dar.de.baja|unsubscribe|'
    r'eliminar.mi.correo|no.deseo.recibir)',
    re.I
)
_AUTORESPUESTA_RE = re.compile(
    r'(auto.?reply|auto.?response|fuera.de.oficina|out.of.office|'
    r'on.vacation|de.vacaciones|respuesta.autom[aá]tica|estoy.de.viaje|'
    r'currently.out|away.from.the.office|will.be.back|estaré.de.regreso)',
    re.I
)
_RESPUESTA_NEUTRAL = re.compile(
    r'(recib[ií]|gracias|muchas.gracias|thank.you|lo.revisar|en.breve|'
    r'a.la.brevedad|tendr[eé].en.cuenta|lo.considerar|lo.consultar[eé])',
    re.I
)


class EmailIntelligenceAgent(BaseAgent):
    agent_id     = 'email_intelligence'
    name         = 'Email Intelligence Agent'
    description  = 'Analiza bandejas cada 15 min: rebotes, respuestas, oportunidades'
    icon         = 'bi-envelope-open'
    color        = 'amber'
    run_interval = 900  # 15 min

    def _execute(self, app) -> dict:
        from app.models.inteligencia import EmailEvento, Oportunidad
        from app.models.prospecto import Prospecto
        from app.extensions import db

        with app.app_context():
            bounces        = 0
            opportunities  = 0
            no_contact     = 0
            autorespuestas = 0
            neutrales      = 0
            total_analyzed = 0

            for cuenta, env_key in _BANDEJAS_ENV.items():
                try:
                    service = self._get_gmail_service(env_key)
                    if not service:
                        continue
                    msgs = self._fetch_unread(service)
                    for msg_data in msgs[:50]:  # máx 50 por bandeja por ciclo
                        total_analyzed += 1
                        try:
                            result = self._process_message(msg_data, cuenta, service, db)
                            # Marcar como leído SOLO si el procesamiento fue exitoso
                            self._mark_read(service, msg_data['id'])
                            if result == 'bounce':
                                bounces += 1
                            elif result == 'oportunidad':
                                opportunities += 1
                            elif result == 'no_contactar':
                                no_contact += 1
                            elif result == 'autorespuesta':
                                autorespuestas += 1
                            elif result == 'neutral':
                                neutrales += 1
                        except Exception as e_msg:
                            _log.warning(f'[EmailIntelligence] Error procesando mensaje {msg_data.get("id")}: {e_msg}')
                            # NO marcar como leído — se reintentará en el próximo ciclo
                except Exception as e:
                    _log.warning(f'[EmailIntelligence] Error en {cuenta}: {e}')

            db.session.commit()
            msg = (f'Analizados {total_analyzed} emails — '
                   f'{bounces} rebotes · {opportunities} oportunidades · '
                   f'{no_contact} no contactar · {autorespuestas} auto-respuestas · '
                   f'{neutrales} respuestas neutras')
            return {
                'tasks':   total_analyzed,
                'message': msg,
                'metrics': {
                    'emails_analyzed':   total_analyzed,
                    'bounces_detected':  bounces,
                    'opportunities':     opportunities,
                    'autorespuestas':    autorespuestas,
                    'neutrales':         neutrales,
                },
            }

    def _extract_bounced_email(self, msg_data: dict, subject: str) -> str:
        """
        FIX 4: Extrae el email rebotado usando múltiples estrategias:
          1. Cabecera 'Final-Recipient' (estándar RFC 3464)
          2. Patrón to=<email> en el subject
          3. Cualquier email corporativo en el subject
          4. Cuerpo del mensaje en texto plano
        """
        # Estrategia 1: cabeceras de diagnóstico DSN
        headers = {h['name']: h['value'] for h in
                   msg_data.get('payload', {}).get('headers', [])}
        for hdr in ('Final-Recipient', 'Original-Rcpt-To', 'X-Failed-Recipients'):
            val = headers.get(hdr, '')
            m = re.search(r'[\w.+\-]+@[\w.\-]+\.\w+', val)
            if m:
                return m.group(0).lower()

        # Estrategia 2: to=<email> en subject
        m = re.search(r'to=<([^>]+)>', subject, re.I)
        if m:
            return m.group(1).lower()

        # Estrategia 3: email corporativo en subject (excluye dominios gratuitos)
        _FREE = {'gmail.com', 'hotmail.com', 'yahoo.com', 'outlook.com', 'live.com'}
        for candidate in re.findall(r'[\w.+\-]+@[\w.\-]+\.\w+', subject):
            if candidate.split('@')[-1].lower() not in _FREE:
                return candidate.lower()

        # Estrategia 4: buscar en partes del cuerpo (snippet o primeras partes)
        snippet = msg_data.get('snippet', '')
        for candidate in re.findall(r'[\w.+\-]+@[\w.\-]+\.\w+', snippet):
            if candidate.split('@')[-1].lower() not in _FREE:
                return candidate.lower()

        return ''

    def _get_gmail_service(self, env_key: str):
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            refresh_token = os.environ.get(env_key, '').strip()
            client_id     = os.environ.get('GMAIL_CLIENT_ID', '')
            client_secret = os.environ.get('GMAIL_CLIENT_SECRET', '')
            if not all([refresh_token, client_id, client_secret]):
                return None

            creds = Credentials(
                token=None, refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_id, client_secret=client_secret,
                scopes=['https://mail.google.com/'],
            )
            creds.refresh(Request())
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            _log.warning(f'[EmailIntelligence] No pudo conectar a Gmail: {e}')
            return None

    def _fetch_unread(self, service) -> list:
        """Descarga mensajes no leídos SIN marcarlos todavía. El marcado
        ocurre en _mark_read() tras el procesamiento exitoso."""
        try:
            response = service.users().messages().list(
                userId='me', q='is:unread', maxResults=50
            ).execute()
            msg_ids = [m['id'] for m in response.get('messages', [])]
            result = []
            for mid in msg_ids:
                try:
                    m = service.users().messages().get(
                        userId='me', id=mid, format='metadata',
                        metadataHeaders=['From', 'To', 'Subject', 'Message-ID']
                    ).execute()
                    result.append(m)
                except Exception:
                    pass
            return result
        except Exception:
            return []

    def _mark_read(self, service, msg_id: str):
        """Marca un mensaje como leído. Llamar solo tras procesamiento exitoso."""
        try:
            service.users().messages().modify(
                userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except Exception:
            pass

    def _process_message(self, msg_data: dict, cuenta: str, service, db) -> str:
        from app.models.inteligencia import EmailEvento, Oportunidad
        from app.models.prospecto import Prospecto, ActividadProspecto, SeguimientoProspecto
        from app.utils.formatters import now_peru

        now_dt = now_peru()
        headers = {h['name']: h['value'] for h in
                   msg_data.get('payload', {}).get('headers', [])}
        sender   = headers.get('From', '')
        subject  = headers.get('Subject', '')
        msg_id   = headers.get('Message-ID', msg_data.get('id', ''))

        # Evitar duplicados
        if EmailEvento.query.filter_by(mensaje_id=msg_id).first():
            return 'duplicate'

        tipo = 'irrelevante'
        sender_email = re.search(r'[\w.+\-]+@[\w.\-]+', sender)
        sender_email = sender_email.group(0).lower() if sender_email else ''

        bot_user = self._get_bot_user()

        # 1. Rebote: extraer email rebotado y actualizar CRM
        if _BOUNCE_SENDERS.search(sender) or _BOUNCE_SUBJECTS.search(subject):
            tipo = 'bounce'
            bounced_email = self._extract_bounced_email(msg_data, subject)
            if bounced_email:
                (Prospecto.query
                 .filter_by(email=bounced_email)
                 .update({'estado_email': 'REBOTE'}, synchronize_session=False))
                # Registrar actividad en el prospecto afectado
                if bot_user:
                    prospecto = Prospecto.query.filter_by(email=bounced_email).first()
                    if prospecto:
                        db.session.add(ActividadProspecto(
                            prospecto_id=prospecto.id,
                            user_id=bot_user.id,
                            tipo='sistema',
                            canal='email',
                            bandeja=cuenta,
                            descripcion=f'Email rebotado detectado: {subject[:120]}',
                            resultado='rebote',
                            nuevo_estado='REBOTE',
                        ))

            # Eliminar mensaje de rebote permanentemente
            try:
                service.users().messages().trash(userId='me', id=msg_data['id']).execute()
            except Exception:
                pass

        # 2. Auto-respuesta (fuera de oficina / vacaciones) — ignorar sin alterar CRM
        elif _AUTORESPUESTA_RE.search(subject) or _AUTORESPUESTA_RE.search(
                msg_data.get('snippet', '')):
            tipo = 'autorespuesta'
            # No modificar estado comercial; registrar solo como actividad
            if bot_user and sender_email:
                prospecto = Prospecto.query.filter_by(email=sender_email).first()
                if prospecto:
                    db.session.add(ActividadProspecto(
                        prospecto_id=prospecto.id,
                        user_id=bot_user.id,
                        tipo='sistema',
                        canal='email',
                        bandeja=cuenta,
                        descripcion=f'Auto-respuesta recibida: {subject[:120]}',
                        resultado='auto-respuesta',
                    ))

        # 3. No contactar
        elif _NO_CONTACT_KEYWORDS.search(subject) or _NO_CONTACT_KEYWORDS.search(
                msg_data.get('snippet', '')):
            tipo = 'no_contactar'
            if sender_email:
                (Prospecto.query
                 .filter_by(email=sender_email)
                 .update({'estado_comercial': 'NO CONTACTAR',
                          'estado_email': 'NO CONTACTAR'}, synchronize_session=False))
                if bot_user:
                    prospecto = Prospecto.query.filter_by(email=sender_email).first()
                    if prospecto:
                        db.session.add(ActividadProspecto(
                            prospecto_id=prospecto.id,
                            user_id=bot_user.id,
                            tipo='sistema',
                            canal='email',
                            bandeja=cuenta,
                            descripcion=f'Solicitud de no contacto recibida: {subject[:120]}',
                            resultado='no_contactar',
                            nuevo_estado='NO CONTACTAR',
                        ))

        # 4. Oportunidad / respuesta positiva
        elif _POSITIVE_KEYWORDS.search(subject) or _POSITIVE_KEYWORDS.search(
                msg_data.get('snippet', '')):
            tipo = 'oportunidad'
            prospecto = Prospecto.query.filter_by(email=sender_email).first()
            opp = Oportunidad(
                empresa=prospecto.razon_social if prospecto else sender,
                email=sender_email,
                sector=prospecto.rubro if prospecto else '',
                prioridad='alta',
                score=80,
                necesidad=f'Respuesta positiva al email de prospección: "{subject}"',
                recomendacion='Contactar de inmediato por WhatsApp o llamada',
                cuenta_origen=cuenta,
                mensaje_id=msg_id,
                prospecto_creado_id=prospecto.id if prospecto else None,
            )
            db.session.add(opp)
            if prospecto:
                prospecto.nivel_interes = 'alto'
                prospecto.estado_comercial = 'negociando'
                prospecto.fecha_ultimo_contacto = now_dt.strftime('%Y-%m-%d')
                if bot_user:
                    db.session.add(ActividadProspecto(
                        prospecto_id=prospecto.id,
                        user_id=bot_user.id,
                        tipo='respuesta',
                        canal='email',
                        bandeja=cuenta,
                        descripcion=f'Respuesta positiva recibida: {subject[:120]}',
                        resultado='oportunidad',
                        nuevo_estado='negociando',
                    ))

        # 5. Respuesta neutral (acuse de recibo, "lo revisaré", etc.)
        elif _RESPUESTA_NEUTRAL.search(subject) or _RESPUESTA_NEUTRAL.search(
                msg_data.get('snippet', '')):
            tipo = 'neutral'
            if sender_email and bot_user:
                prospecto = Prospecto.query.filter_by(email=sender_email).first()
                if prospecto:
                    # Crear seguimiento para revisión humana
                    tiene_seg = (SeguimientoProspecto.query
                                 .filter(
                                     SeguimientoProspecto.prospecto_id == prospecto.id,
                                     SeguimientoProspecto.completado == False,
                                 ).first())
                    if not tiene_seg:
                        from datetime import timedelta
                        db.session.add(SeguimientoProspecto(
                            prospecto_id=prospecto.id,
                            user_id=bot_user.id,
                            tipo='email',
                            descripcion=f'Respuesta neutral recibida: "{subject[:120]}". Hacer seguimiento.',
                            fecha_programada=now_dt + timedelta(days=2),
                            completado=False,
                        ))
                    db.session.add(ActividadProspecto(
                        prospecto_id=prospecto.id,
                        user_id=bot_user.id,
                        tipo='respuesta',
                        canal='email',
                        bandeja=cuenta,
                        descripcion=f'Respuesta neutral recibida: {subject[:120]}',
                        resultado='neutral',
                    ))

        # Registrar evento
        evento = EmailEvento(
            cuenta=cuenta,
            mensaje_id=msg_id,
            remitente=sender[:300],
            asunto=subject[:500],
            tipo=tipo,
            email_afectado=sender_email,
            crm_updated=(tipo in ('bounce', 'no_contactar', 'oportunidad', 'neutral')),
        )
        db.session.add(evento)
        return tipo

    def _get_bot_user(self):
        try:
            from app.models.user import User
            return User.query.filter_by(role='Master').first()
        except Exception:
            return None

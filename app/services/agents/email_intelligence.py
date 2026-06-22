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
            bounces = 0
            opportunities = 0
            no_contact = 0
            total_analyzed = 0

            for cuenta, env_key in _BANDEJAS_ENV.items():
                try:
                    service = self._get_gmail_service(env_key)
                    if not service:
                        continue
                    msgs = self._fetch_unread(service)
                    for msg_data in msgs[:50]:  # máx 50 por bandeja por ciclo
                        total_analyzed += 1
                        result = self._process_message(msg_data, cuenta, service, db)
                        if result == 'bounce':
                            bounces += 1
                        elif result == 'opportunity':
                            opportunities += 1
                        elif result == 'no_contact':
                            no_contact += 1
                except Exception as e:
                    _log.warning(f'[EmailIntelligence] Error en {cuenta}: {e}')

            db.session.commit()
            msg = (f'Analizados {total_analyzed} emails — '
                   f'{bounces} rebotes · {opportunities} oportunidades · {no_contact} no contactar')
            return {
                'tasks':   total_analyzed,
                'message': msg,
                'metrics': {
                    'emails_analyzed':   total_analyzed,
                    'bounces_detected':  bounces,
                    'opportunities':     opportunities,
                },
            }

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
                    # Marcar como leído
                    service.users().messages().modify(
                        userId='me', id=mid, body={'removeLabelIds': ['UNREAD']}
                    ).execute()
                except Exception:
                    pass
            return result
        except Exception:
            return []

    def _process_message(self, msg_data: dict, cuenta: str, service, db) -> str:
        from app.models.inteligencia import EmailEvento, Oportunidad
        from app.models.prospecto import Prospecto
        from app.utils.formatters import now_peru

        headers = {h['name']: h['value'] for h in
                   msg_data.get('payload', {}).get('headers', [])}
        sender   = headers.get('From', '')
        subject  = headers.get('Subject', '')
        msg_id   = headers.get('Message-ID', msg_data.get('id', ''))

        # Evitar duplicados
        if EmailEvento.query.filter_by(mensaje_id=msg_id).first():
            return 'duplicate'

        # Clasificar
        tipo = 'irrelevante'
        sender_email = re.search(r'[\w.+\-]+@[\w.\-]+', sender)
        sender_email = sender_email.group(0).lower() if sender_email else ''

        # 1. Rebote
        if _BOUNCE_SENDERS.search(sender) or _BOUNCE_SUBJECTS.search(subject):
            tipo = 'bounce'
            # Extraer email rebotado del asunto/cuerpo
            bounced = re.search(r'to=<([^>]+)>', subject) or re.search(r'[\w.+]+@[\w.]+\.\w+', subject)
            bounced_email = bounced.group(1) if bounced else ''
            if bounced_email:
                (Prospecto.query
                 .filter_by(email=bounced_email)
                 .update({'estado_email': 'REBOTE'}, synchronize_session=False))

            # Eliminar mensaje de rebote permanentemente
            try:
                service.users().messages().trash(userId='me', id=msg_data['id']).execute()
            except Exception:
                pass

        # 2. No contactar
        elif _NO_CONTACT_KEYWORDS.search(subject):
            tipo = 'no_contactar'
            if sender_email:
                (Prospecto.query
                 .filter_by(email=sender_email)
                 .update({'estado_comercial': 'NO CONTACTAR',
                          'estado_email': 'NO CONTACTAR'}, synchronize_session=False))

        # 3. Oportunidad / respuesta positiva
        elif _POSITIVE_KEYWORDS.search(subject):
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

        # Registrar evento
        evento = EmailEvento(
            cuenta=cuenta,
            mensaje_id=msg_id,
            remitente=sender[:300],
            asunto=subject[:500],
            tipo=tipo,
            email_afectado=sender_email,
            crm_updated=(tipo in ('bounce', 'no_contactar', 'oportunidad')),
        )
        db.session.add(evento)
        return tipo

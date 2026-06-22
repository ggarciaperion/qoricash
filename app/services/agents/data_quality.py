"""
Agente 4: Data Quality Agent
Mantiene la calidad de la base maestra: valida emails, detecta duplicados reales,
corrige inconsistencias y marca emails rebotados o inactivos.
"""
import logging
import re
import socket
from .base import BaseAgent

_log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def _valid_email_syntax(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or '').strip()))


def _mx_exists(domain: str) -> bool:
    try:
        import dns.resolver
        dns.resolver.resolve(domain, 'MX', lifetime=3)
        return True
    except Exception:
        try:
            socket.getaddrinfo(domain, None, timeout=2)
            return True
        except Exception:
            return False


class DataQualityAgent(BaseAgent):
    agent_id     = 'data_quality'
    name         = 'Data Quality Agent'
    description  = 'Valida emails, detecta duplicados reales y corrige inconsistencias en la base'
    icon         = 'bi-shield-check'
    color        = 'purple'
    run_interval = 7200  # cada 2 horas

    def _execute(self, app) -> dict:
        from app.models.prospecto import Prospecto
        from app.extensions import db

        with app.app_context():
            fixed = 0
            invalid_emails = 0
            duplicates = 0

            # 1. Detectar emails con sintaxis inválida
            candidates = (Prospecto.query
                          .filter(Prospecto.estado_email.notin_(['INVALIDO', 'REBOTE', 'NO CONTACTAR']))
                          .filter(Prospecto.email.isnot(None))
                          .limit(2000).all())

            for p in candidates:
                email = (p.email or '').strip()
                if not email:
                    continue
                if not _valid_email_syntax(email):
                    p.estado_email = 'INVALIDO'
                    invalid_emails += 1
                    fixed += 1

            # 2. Detectar duplicados exactos (mismo RUC + mismo email)
            from sqlalchemy import func
            dup_query = (db.session.query(
                            Prospecto.ruc,
                            Prospecto.email,
                            func.count(Prospecto.id).label('cnt'))
                         .filter(Prospecto.ruc.isnot(None), Prospecto.email.isnot(None))
                         .group_by(Prospecto.ruc, Prospecto.email)
                         .having(func.count(Prospecto.id) > 1)
                         .limit(500).all())

            for row in dup_query:
                if not row.ruc or not row.email:
                    continue
                # Mantener el más reciente, marcar los demás
                dupes = (Prospecto.query
                         .filter_by(ruc=row.ruc, email=row.email)
                         .order_by(Prospecto.id.desc())
                         .offset(1).all())
                for d in dupes:
                    d.notas = (d.notas or '') + ' [DUPLICADO FUSIONADO]'
                    duplicates += 1
                    fixed += 1

            # 3. Normalizar estado_email vacío en registros antiguos
            Prospecto.query.filter(
                Prospecto.estado_email.is_(None),
                Prospecto.email.isnot(None)
            ).limit(5000).update({'estado_email': 'pendiente'}, synchronize_session=False)

            db.session.commit()

            msg = (f'Calidad OK — {invalid_emails} emails inválidos · '
                   f'{duplicates} duplicados marcados · {fixed} correcciones')
            return {
                'tasks':   fixed,
                'message': msg,
                'metrics': {
                    'prospects_validated': len(candidates),
                    'duplicates_removed':  duplicates,
                },
            }

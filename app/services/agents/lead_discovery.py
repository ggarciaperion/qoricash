"""
Agente 3: Lead Discovery Agent
Descubre nuevos prospectos desde SUNAT, directorios y fuentes públicas.
Usa el LeadHunterAgent existente (run_hunt).
"""
import logging
from .base import BaseAgent

_log = logging.getLogger(__name__)


class LeadDiscoveryAgent(BaseAgent):
    agent_id     = 'lead_discovery'
    name         = 'Lead Discovery Agent'
    description  = 'Descubre nuevos prospectos desde SUNAT, directorios y fuentes públicas'
    icon         = 'bi-search'
    color        = 'blue'
    run_interval = 3600  # cada hora

    def _execute(self, app) -> dict:
        from app.services.ai.lead_hunter_agent import run_hunt

        with app.app_context():
            result = run_hunt(max_new_leads=50, min_score=30)
            found    = result.get('encontrados', 0)
            new_ones = result.get('nuevos', 0)
            inserted = result.get('insertados', 0)
            return {
                'tasks':   inserted,
                'message': f'Encontrados {found} leads · {new_ones} únicos · {inserted} insertados',
                'detail':  result.get('resumen', ''),
                'metrics': {
                    'prospects_found': inserted,
                },
            }

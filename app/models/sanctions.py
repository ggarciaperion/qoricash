"""
Modelo para almacenamiento local de listas de sanciones internacionales.
Fuentes: OFAC SDN (US Treasury), ONU Consolidated, UE, UK
"""
from app.extensions import db
from app.utils.formatters import now_peru


class SanctionsEntry(db.Model):
    """Entrada de una lista de sanciones internacional (cacheada localmente)"""

    __tablename__ = 'sanctions_entries'

    id              = db.Column(db.Integer, primary_key=True)
    source          = db.Column(db.String(20), nullable=False, index=True)   # OFAC, UN, EU, UK
    entity_type     = db.Column(db.String(20))   # Individual, Entity
    uid             = db.Column(db.String(100))  # ID original de la fuente
    name            = db.Column(db.String(400), nullable=False)
    name_normalized = db.Column(db.String(400), index=True)  # mayúsculas, sin acentos
    aliases_json    = db.Column(db.Text)         # JSON list de nombres alternativos normalizados
    nationality     = db.Column(db.String(100))
    program         = db.Column(db.String(300))  # programa de sanciones
    loaded_at       = db.Column(db.DateTime, default=now_peru)

    def __repr__(self):
        return f'<SanctionsEntry {self.source} {self.name}>'

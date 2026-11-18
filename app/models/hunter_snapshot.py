"""
hunter_snapshot.py — Snapshot del estado del worker Hunter recibido vía sync.

Una sola fila (snapshot_key='latest') actualizada por el POST /api/sync/hunter.
El worker Hunter empuja el snapshot cada 5 minutos desde scheduler_hunter.py.
"""
from datetime import datetime, timezone
from app.extensions import db


class HunterSnapshot(db.Model):
    __tablename__ = 'hunter_snapshots'

    id               = db.Column(db.Integer, primary_key=True)
    snapshot_key     = db.Column(db.String(64), unique=True, nullable=False, default='latest')
    payload          = db.Column(db.Text, nullable=False)   # JSON completo
    received_at      = db.Column(db.DateTime, nullable=False,
                                 default=lambda: datetime.now(timezone.utc))
    worker_hostname  = db.Column(db.String(128))
    schema_version   = db.Column(db.String(16), default='1.0')

    def __repr__(self):
        return f'<HunterSnapshot key={self.snapshot_key} at={self.received_at}>'

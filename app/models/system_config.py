"""
Configuración dinámica del sistema QoriCash.
Almacena parámetros fiscales y operativos que cambian periódicamente
(UIT, tasas IR, umbrales, etc.) sin necesidad de redeploy.
"""
from datetime import datetime
from app.extensions import db


class SystemConfig(db.Model):
    __tablename__ = 'system_config'

    key         = db.Column(db.String(50), primary_key=True)
    value       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(200))
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f'<SystemConfig {self.key}={self.value}>'

    @staticmethod
    def get(key: str, default: str = None) -> str:
        """Obtiene un valor de configuración; retorna default si no existe."""
        row = SystemConfig.query.get(key)
        return row.value if row else default

    @staticmethod
    def set(key: str, value: str, description: str = None, user_id: int = None):
        """Crea o actualiza un parámetro de configuración."""
        row = SystemConfig.query.get(key)
        if row:
            row.value      = str(value)
            row.updated_at = datetime.utcnow()
            row.updated_by = user_id
        else:
            row = SystemConfig(
                key=key,
                value=str(value),
                description=description,
                updated_by=user_id,
            )
            db.session.add(row)
        db.session.flush()
        return row

"""
Modelo de Auditoría para QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class AuditLog(db.Model):
    """Modelo de registro de auditoría"""
    
    __tablename__ = 'audit_logs'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Acción realizada
    action = db.Column(db.String(100), nullable=False)  # CREATE_USER, UPDATE_OPERATION, etc.
    
    # Entidad afectada
    entity = db.Column(db.String(50), nullable=False)  # User, Client, Operation
    entity_id = db.Column(db.Integer)
    
    # Detalles
    details = db.Column(db.Text)
    notes = db.Column(db.Text)
    
    # Información de la petición
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(200))
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False, index=True)
    
    def to_dict(self):
        """
        Convertir a diccionario
        
        Returns:
            dict: Representación del log
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.username if self.user else None,
            'action': self.action,
            'entity': self.entity,
            'entity_id': self.entity_id,
            'details': self.details,
            'notes': self.notes,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def log_action(user_id, action, entity, entity_id=None, details=None, notes=None, ip_address=None, user_agent=None):
        """
        Crear un registro de auditoría
        
        Args:
            user_id: ID del usuario que realiza la acción
            action: Acción realizada (CREATE_USER, UPDATE_OPERATION, etc.)
            entity: Entidad afectada (User, Client, Operation)
            entity_id: ID de la entidad afectada
            details: Detalles adicionales
            notes: Notas adicionales
            ip_address: IP del usuario
            user_agent: User agent del navegador
        
        Returns:
            AuditLog: Registro creado
        """
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details,
            notes=notes,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(log)
        db.session.commit()
        return log
    
    def __repr__(self):
        return f'<AuditLog {self.action} on {self.entity} by User {self.user_id}>'

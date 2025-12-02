"""
Modelo de Usuario para QoriCash Trading V2
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.utils.formatters import now_peru


class User(UserMixin, db.Model):
    """Modelo de Usuario del sistema"""
    
    __tablename__ = 'users'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Información básica
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    dni = db.Column(db.String(8), unique=True, nullable=False)
    
    # Rol y estado
    role = db.Column(
        db.String(20),
        nullable=False,
        default='Trader'
    )  # Master, Trader, Operador, Middle Office
    
    status = db.Column(
        db.String(20),
        nullable=False,
        default='Activo'
    )  # Activo, Inactivo
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    last_login = db.Column(db.DateTime)
    last_logout = db.Column(db.DateTime)
    
    # Relaciones
    # Operaciones creadas por este usuario
    operations = db.relationship(
        'Operation',
        foreign_keys='Operation.user_id',
        backref='user',
        lazy='dynamic'
    )

    # Operaciones asignadas a este operador
    assigned_operations = db.relationship(
        'Operation',
        foreign_keys='Operation.assigned_operator_id',
        backref='assigned_operator',
        lazy='dynamic'
    )

    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(
            role.in_(['Master', 'Trader', 'Operador', 'Middle Office']),
            name='check_user_role'
        ),
        db.CheckConstraint(
            status.in_(['Activo', 'Inactivo']),
            name='check_user_status'
        ),
    )
    
    def set_password(self, password):
        """
        Establecer contraseña hasheada
        
        Args:
            password: Contraseña en texto plano
        """
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """
        Verificar contraseña
        
        Args:
            password: Contraseña en texto plano
        
        Returns:
            bool: True si la contraseña es correcta
        """
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_relations=False):
        """
        Convertir a diccionario
        
        Args:
            include_relations: Si incluir operaciones relacionadas
        
        Returns:
            dict: Representación del usuario
        """
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'dni': self.dni,
            'role': self.role,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_logout': self.last_logout.isoformat() if self.last_logout else None
        }
        
        if include_relations:
            data['operations_count'] = self.operations.count()
        
        return data
    
    def is_master(self):
        """Verificar si es Master"""
        return self.role == 'Master'
    
    def is_trader(self):
        """Verificar si es Trader"""
        return self.role == 'Trader'
    
    def is_operador(self):
        """Verificar si es Operador"""
        return self.role == 'Operador'

    def is_middle_office(self):
        """Verificar si es Middle Office"""
        return self.role == 'Middle Office'

    def is_active_user(self):
        """Verificar si está activo"""
        return self.status == 'Activo'
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

"""
Modelo de Operación para QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db


class Operation(db.Model):
    """Modelo de Operación de cambio de divisas"""
    
    __tablename__ = 'operations'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # ID de operación (EXP-1001, EXP-1002, etc.)
    operation_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Foreign Keys
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Tipo de operación
    operation_type = db.Column(
        db.String(20),
        nullable=False
    )  # Compra, Venta
    
    # Montos
    amount_usd = db.Column(db.Numeric(15, 2), nullable=False)
    exchange_rate = db.Column(db.Numeric(10, 4), nullable=False)
    amount_pen = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Cuentas bancarias
    source_account = db.Column(db.String(100))
    destination_account = db.Column(db.String(100))
    
    # Comprobantes de pago (URLs de Cloudinary)
    payment_proof_url = db.Column(db.String(500))
    operator_proof_url = db.Column(db.String(500))
    
    # Estado
    status = db.Column(
        db.String(20),
        nullable=False,
        default='Pendiente',
        index=True
    )  # Pendiente, En proceso, Completada, Cancelado
    
    # Notas
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(
            operation_type.in_(['Compra', 'Venta']),
            name='check_operation_type'
        ),
        db.CheckConstraint(
            status.in_(['Pendiente', 'En proceso', 'Completada', 'Cancelado']),
            name='check_operation_status'
        ),
        db.CheckConstraint(
            'amount_usd > 0',
            name='check_amount_usd_positive'
        ),
        db.CheckConstraint(
            'exchange_rate > 0',
            name='check_exchange_rate_positive'
        ),
    )
    
    def to_dict(self, include_relations=False):
        """
        Convertir a diccionario
        
        Args:
            include_relations: Si incluir datos de cliente y usuario
        
        Returns:
            dict: Representación de la operación
        """
        data = {
            'id': self.id,
            'operation_id': self.operation_id,
            'client_id': self.client_id,
            'user_id': self.user_id,
            'operation_type': self.operation_type,
            'amount_usd': float(self.amount_usd),
            'exchange_rate': float(self.exchange_rate),
            'amount_pen': float(self.amount_pen),
            'source_account': self.source_account,
            'destination_account': self.destination_account,
            'payment_proof_url': self.payment_proof_url,
            'operator_proof_url': self.operator_proof_url,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
        
        if include_relations:
            # Obtener nombre del cliente según su tipo
            if self.client:
                if self.client.document_type == 'RUC':
                    data['client_name'] = self.client.razon_social
                else:
                    data['client_name'] = self.client.full_name
            else:
                data['client_name'] = None

            data['user_name'] = self.user.username if self.user else None
        
        return data
    
    def is_pending(self):
        """Verificar si está pendiente"""
        return self.status == 'Pendiente'
    
    def is_in_process(self):
        """Verificar si está en proceso"""
        return self.status == 'En proceso'
    
    def is_completed(self):
        """Verificar si está completada"""
        return self.status == 'Completada'
    
    def is_canceled(self):
        """Verificar si está cancelada"""
        return self.status == 'Cancelado'
    
    def can_be_processed(self):
        """Verificar si puede ser procesada"""
        return self.status in ['Pendiente', 'En proceso']
    
    def can_be_canceled(self):
        """Verificar si puede ser cancelada"""
        return self.status in ['Pendiente', 'En proceso']
    
    @staticmethod
    def generate_operation_id():
        """
        Generar ID de operación secuencial
        
        Returns:
            str: ID de operación (EXP-1001, EXP-1002, etc.)
        """
        last_operation = Operation.query.order_by(Operation.id.desc()).first()
        
        if last_operation and last_operation.operation_id:
            try:
                last_num = int(last_operation.operation_id.split('-')[1])
                new_num = last_num + 1
            except (IndexError, ValueError):
                new_num = 1001
        else:
            new_num = 1001
        
        return f'EXP-{new_num:04d}'
    
    def __repr__(self):
        return f'<Operation {self.operation_id} - {self.operation_type} ${self.amount_usd}>'

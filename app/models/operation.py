"""
Modelo de Operación para QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru
import json


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
    assigned_operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Operador asignado

    # Tipo de operación
    operation_type = db.Column(
        db.String(20),
        nullable=False
    )  # Compra, Venta

    # Origen de la operación
    origen = db.Column(
        db.String(20),
        nullable=False,
        default='sistema',
        index=True
    )  # plataforma, sistema

    # Montos
    amount_usd = db.Column(db.Numeric(15, 2), nullable=False)
    exchange_rate = db.Column(db.Numeric(10, 4), nullable=False)
    amount_pen = db.Column(db.Numeric(15, 2), nullable=False)

    # Cuentas bancarias (usadas al crear la operación)
    source_account = db.Column(db.String(100))
    destination_account = db.Column(db.String(100))

    # === NUEVOS CAMPOS ===

    # Abonos del cliente (JSON array)
    # [{importe, codigo_operacion, cuenta_cargo, comprobante_url}, ...]
    client_deposits_json = db.Column(db.Text, default='[]')

    # Pagos al cliente (JSON array, máx 4)
    # [{importe, cuenta_destino}, ...]
    client_payments_json = db.Column(db.Text, default='[]')

    # Comprobantes del operador (JSON array, máx 4)
    # [{comprobante_url, comentario}, ...]
    operator_proofs_json = db.Column(db.Text, default='[]')

    # Log de modificaciones (JSON array)
    # [{fecha, usuario, campo, valor_anterior, valor_nuevo}, ...]
    modification_logs_json = db.Column(db.Text, default='[]')

    # Comentarios del operador al finalizar
    operator_comments = db.Column(db.Text)

    # === FIN NUEVOS CAMPOS ===

    # Comprobantes legacy (mantener por compatibilidad)
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

    # IDs de usuarios que han leído las notas (JSON array de IDs)
    # Ej: [1, 3, 5] significa que los usuarios con ID 1, 3 y 5 ya vieron las notas
    notes_read_by_json = db.Column(db.Text, default='[]')

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    completed_at = db.Column(db.DateTime)
    in_process_since = db.Column(db.DateTime)  # Cuando pasó a "En proceso"

    # Marca si la operación está en observación (detiene alertas repetitivas)
    # NOTA: Comentado temporalmente hasta ejecutar migración en Render
    # en_observacion = db.Column(db.Boolean, default=False, nullable=False)

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
            origen.in_(['plataforma', 'sistema']),
            name='check_operation_origen'
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

    # === PROPIEDADES PARA ACCEDER A LOS JSON ===

    @property
    def client_deposits(self):
        """Obtener abonos del cliente como lista"""
        try:
            return json.loads(self.client_deposits_json or '[]')
        except:
            return []

    @client_deposits.setter
    def client_deposits(self, value):
        """Guardar abonos del cliente"""
        self.client_deposits_json = json.dumps(value or [])

    @property
    def client_payments(self):
        """Obtener pagos al cliente como lista"""
        try:
            return json.loads(self.client_payments_json or '[]')
        except:
            return []

    @client_payments.setter
    def client_payments(self, value):
        """Guardar pagos al cliente"""
        self.client_payments_json = json.dumps(value or [])

    @property
    def operator_proofs(self):
        """Obtener comprobantes del operador como lista"""
        try:
            return json.loads(self.operator_proofs_json or '[]')
        except:
            return []

    @operator_proofs.setter
    def operator_proofs(self, value):
        """Guardar comprobantes del operador"""
        self.operator_proofs_json = json.dumps(value or [])

    @property
    def modification_logs(self):
        """Obtener logs de modificación como lista"""
        try:
            return json.loads(self.modification_logs_json or '[]')
        except:
            return []

    @property
    def notes_read_by(self):
        """Obtener lista de IDs de usuarios que leyeron las notas"""
        try:
            return json.loads(self.notes_read_by_json or '[]')
        except:
            return []

    @notes_read_by.setter
    def notes_read_by(self, value):
        """Guardar lista de IDs de usuarios que leyeron las notas"""
        self.notes_read_by_json = json.dumps(value or [])

    @modification_logs.setter
    def modification_logs(self, value):
        """Guardar logs de modificación"""
        self.modification_logs_json = json.dumps(value or [])

    def add_modification_log(self, user, campo, valor_anterior, valor_nuevo):
        """Agregar un log de modificación"""
        logs = self.modification_logs
        logs.append({
            'fecha': now_peru().isoformat(),
            'usuario': user.username if user else 'Sistema',
            'usuario_id': user.id if user else None,
            'campo': campo,
            'valor_anterior': str(valor_anterior),
            'valor_nuevo': str(valor_nuevo)
        })
        self.modification_logs = logs

    def mark_notes_as_read(self, user_id):
        """Marcar las notas como leídas por un usuario"""
        read_by = self.notes_read_by
        if user_id not in read_by:
            read_by.append(user_id)
            self.notes_read_by = read_by

    def has_user_read_notes(self, user_id):
        """Verificar si un usuario ya leyó las notas"""
        return user_id in self.notes_read_by

    def has_unread_notes(self, user_id):
        """Verificar si hay notas sin leer para un usuario"""
        return bool(self.notes and self.notes.strip()) and not self.has_user_read_notes(user_id)

    def get_total_deposits(self):
        """Calcular suma total de abonos"""
        return sum(float(d.get('importe', 0)) for d in self.client_deposits)

    def get_total_payments(self):
        """Calcular suma total de pagos"""
        return sum(float(p.get('importe', 0)) for p in self.client_payments)

    def validate_deposits_sum(self):
        """
        Validar que la suma de abonos coincide con el total de la operación
        Compra → suma en USD
        Venta → suma en PEN
        """
        total_deposits = self.get_total_deposits()
        if self.operation_type == 'Compra':
            expected = float(self.amount_usd)
        else:
            expected = float(self.amount_pen)

        return abs(total_deposits - expected) < 0.01  # Tolerancia de centavos

    def validate_payments_sum(self):
        """
        Validar que la suma de pagos coincide con el total de la operación
        Venta → suma en USD
        Compra → suma en PEN
        """
        total_payments = self.get_total_payments()
        if self.operation_type == 'Venta':
            expected = float(self.amount_usd)
        else:
            expected = float(self.amount_pen)

        return abs(total_payments - expected) < 0.01  # Tolerancia de centavos

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
            'origen': self.origen,
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
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'in_process_since': self.in_process_since.isoformat() if self.in_process_since else None,
            'time_in_process_minutes': self.get_time_in_process_minutes(),
            # Nuevos campos
            'client_deposits': self.client_deposits,
            'client_payments': self.client_payments,
            'operator_proofs': self.operator_proofs,
            'modification_logs': self.modification_logs,
            'operator_comments': self.operator_comments,
            'total_deposits': self.get_total_deposits(),
            'total_payments': self.get_total_payments(),
            'notes_read_by': self.notes_read_by,
            'assigned_operator_id': self.assigned_operator_id,
            'en_observacion': getattr(self, 'en_observacion', False),  # Compatibilidad pre-migración
        }

        if include_relations:
            # Obtener nombre del cliente según su tipo
            if self.client:
                if self.client.document_type == 'RUC':
                    data['client_name'] = self.client.razon_social
                else:
                    data['client_name'] = self.client.full_name
                # Incluir cuentas bancarias del cliente
                data['client_bank_accounts'] = self.client.bank_accounts or []

                # Obtener nombres de bancos de origen y destino
                bank_accounts = self.client.bank_accounts or []
                source_bank = None
                destination_bank = None

                for account in bank_accounts:
                    if account.get('account_number') == self.source_account:
                        source_bank = account.get('bank_name', 'N/A')
                    if account.get('account_number') == self.destination_account:
                        destination_bank = account.get('bank_name', 'N/A')

                data['source_bank_name'] = source_bank or 'N/A'
                data['destination_bank_name'] = destination_bank or 'N/A'
            else:
                data['client_name'] = None
                data['client_bank_accounts'] = []
                data['source_bank_name'] = 'N/A'
                data['destination_bank_name'] = 'N/A'

            data['user_name'] = self.user.username if self.user else None

            # Obtener nombre del operador asignado
            if self.assigned_operator_id:
                from app.models.user import User
                assigned_operator = User.query.get(self.assigned_operator_id)
                data['assigned_operator_name'] = assigned_operator.username if assigned_operator else None
            else:
                data['assigned_operator_name'] = None

            # Agregar facturas electrónicas de la operación
            if self.invoices:
                data['invoices'] = [invoice.to_dict() for invoice in self.invoices]
            else:
                data['invoices'] = []

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
        """Verificar si puede ser cancelada (solo Pendiente)"""
        return self.status == 'Pendiente'

    def can_trader_edit(self):
        """Verificar si el trader puede editar"""
        return self.status == 'Pendiente'

    def can_operator_edit(self, operator_user_id=None):
        """
        Verificar si el operador puede editar/finalizar

        Args:
            operator_user_id: ID del usuario operador (opcional, para verificar asignación)

        Returns:
            bool: True si puede editar
        """
        if self.status != 'En proceso':
            return False

        # Si se proporciona operator_user_id, verificar que sea el operador asignado
        if operator_user_id is not None:
            # Solo el operador asignado puede editar (o Master que no tiene assigned_operator_id)
            return self.assigned_operator_id == operator_user_id

        return True

    def is_assigned_to_operator(self, operator_user_id):
        """
        Verificar si esta operación está asignada a un operador específico

        Args:
            operator_user_id: ID del usuario operador

        Returns:
            bool: True si está asignada a este operador
        """
        return self.assigned_operator_id == operator_user_id

    def get_time_in_process_minutes(self):
        """
        Calcular el tiempo que lleva en estado 'En proceso' en minutos

        Returns:
            int: Minutos en estado 'En proceso', o None si no aplica
        """
        if self.status != 'En proceso' or not self.in_process_since:
            return None

        delta = now_peru() - self.in_process_since
        return int(delta.total_seconds() / 60)

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

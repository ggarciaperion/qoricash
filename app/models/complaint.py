"""
Modelo de Reclamo para QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class Complaint(db.Model):
    """Modelo de Reclamo/Queja del Libro de Reclamaciones"""

    __tablename__ = 'complaints'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Número de reclamo (formato: REC-0001)
    complaint_number = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Tipo de documento
    document_type = db.Column(db.String(10), nullable=False)  # DNI, CE, RUC

    # Número de documento
    document_number = db.Column(db.String(20), nullable=False, index=True)

    # Información personal (para DNI y CE)
    full_name = db.Column(db.String(300))  # Nombre completo para DNI/CE

    # Información empresa (para RUC)
    company_name = db.Column(db.String(300))  # Razón social para RUC
    contact_person = db.Column(db.String(300))  # Persona de contacto para RUC

    # Contacto
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(500))  # Dirección completa

    # Tipo de solicitud
    complaint_type = db.Column(
        db.String(20),
        nullable=False,
        default='Reclamo'
    )  # Reclamo, Queja

    # Detalle del reclamo
    detail = db.Column(db.Text, nullable=False)

    # Estado
    status = db.Column(
        db.String(20),
        nullable=False,
        default='Pendiente'
    )  # Pendiente, En Revisión, Resuelto

    # Respuesta del equipo
    response = db.Column(db.Text)

    # Imágenes (Cloudinary URLs)
    evidence_image_url = db.Column(db.Text)  # URL de imagen de evidencia subida por el cliente
    resolution_image_url = db.Column(db.Text)  # URL de imagen de resolución subida por el equipo

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    resolved_at = db.Column(db.DateTime)  # Fecha de resolución

    # Usuario que resolvió (ForeignKey a User)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relación con User (quien resolvió)
    resolver = db.relationship(
        'User',
        backref='resolved_complaints',
        lazy='joined'
    )

    # Constraints
    __table_args__ = (
        db.CheckConstraint(
            document_type.in_(['DNI', 'CE', 'RUC']),
            name='check_complaint_document_type'
        ),
        db.CheckConstraint(
            complaint_type.in_(['Reclamo', 'Queja']),
            name='check_complaint_type'
        ),
        db.CheckConstraint(
            status.in_(['Pendiente', 'En Revisión', 'Resuelto']),
            name='check_complaint_status'
        ),
    )

    @property
    def display_name(self):
        """
        Retorna el nombre para mostrar según el tipo de documento

        Returns:
            str: Nombre completo o razón social según corresponda
        """
        if self.document_type == 'RUC':
            return self.company_name or '-'
        else:
            return self.full_name or '-'

    def to_dict(self, include_relations=False):
        """
        Convertir a diccionario

        Args:
            include_relations: Si incluir relaciones

        Returns:
            dict: Representación del reclamo
        """
        data = {
            'id': self.id,
            'complaint_number': self.complaint_number,
            'document_type': self.document_type,
            'document_number': self.document_number,
            'full_name': self.full_name,
            'company_name': self.company_name,
            'contact_person': self.contact_person,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'complaint_type': self.complaint_type,
            'detail': self.detail,
            'status': self.status,
            'response': self.response,
            'evidence_image_url': self.evidence_image_url,
            'resolution_image_url': self.resolution_image_url,
            'display_name': self.display_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by
        }

        if include_relations and self.resolver:
            data['resolver'] = {
                'id': self.resolver.id,
                'username': self.resolver.username,
                'email': self.resolver.email
            }

        return data

    @staticmethod
    def generate_complaint_number():
        """
        Generar número de reclamo único (REC-XXXX)

        Returns:
            str: Número de reclamo en formato REC-0001
        """
        # Obtener el último reclamo
        last_complaint = Complaint.query.order_by(Complaint.id.desc()).first()

        if last_complaint and last_complaint.complaint_number:
            # Extraer el número del formato REC-XXXX
            try:
                last_number = int(last_complaint.complaint_number.split('-')[1])
                new_number = last_number + 1
            except (IndexError, ValueError):
                new_number = 1
        else:
            new_number = 1

        # Formatear con padding de 4 dígitos
        return f"REC-{new_number:04d}"

    def __repr__(self):
        return f'<Complaint {self.complaint_number} - {self.complaint_type} ({self.status})>'

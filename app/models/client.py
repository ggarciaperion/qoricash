"""
Modelo de Cliente ACTUALIZADO para QoriCash Trading V2

- validate_bank_accounts ahora es @staticmethod para permitir validación desde servicios
- full_name devuelve None si no hay datos (la plantilla mostrará fallback '-')
- get/set para bank_accounts (JSON) y compatibilidad con campos legacy
- Autenticación con password para acceso a app móvil
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.utils.formatters import now_peru
import json


class Client(db.Model):
    """Modelo de Cliente"""

    __tablename__ = 'clients'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Tipo de documento
    document_type = db.Column(db.String(10), nullable=False)  # DNI, CE, RUC

    # Información personal (para DNI y CE)
    apellido_paterno = db.Column(db.String(100))
    apellido_materno = db.Column(db.String(100))
    nombres = db.Column(db.String(100))

    # Información empresa (para RUC)
    razon_social = db.Column(db.String(200))
    persona_contacto = db.Column(db.String(200))

    # Número de documento
    dni = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Contacto
    email = db.Column(db.String(120), nullable=False, index=True)  # Puede contener múltiples emails separados por ;
    phone = db.Column(db.String(100))  # Puede contener múltiples números separados por ;

    # Autenticación para app móvil
    password_hash = db.Column(db.String(200))  # Contraseña hasheada (NULL si cliente aún no tiene acceso a app)
    requires_password_change = db.Column(db.Boolean, default=True)  # True si debe cambiar contraseña en primer login

    # Documentos (URLs de Cloudinary)
    dni_front_url = db.Column(db.String(500))  # DNI/CE Anverso
    dni_back_url = db.Column(db.String(500))   # DNI/CE Reverso

    # Documentos adicionales para RUC
    dni_representante_front_url = db.Column(db.String(500))
    dni_representante_back_url = db.Column(db.String(500))
    ficha_ruc_url = db.Column(db.String(500))

    # Validación Oficial de Cumplimiento (OC)
    validation_oc_url = db.Column(db.String(500))  # Documento de validación OC

    # Dirección completa
    direccion = db.Column(db.String(300))
    distrito = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    departamento = db.Column(db.String(100))

    # Información bancaria - MÚLTIPLES CUENTAS en JSON
    # Formato: [{"origen": "Lima", "bank_name": "BCP", "account_type": "Ahorro",
    #            "currency": "S/", "account_number": "123456"}]
    bank_accounts_json = db.Column(db.Text)

    # Campos antiguos para compatibilidad (deprecated)
    bank_name = db.Column(db.String(100))
    account_type = db.Column(db.String(20))
    currency = db.Column(db.String(10))
    bank_account_number = db.Column(db.String(100))
    bank_account_pen = db.Column(db.String(100))
    bank_account_usd = db.Column(db.String(100))
    origen = db.Column(db.String(20))

    # Estado
    status = db.Column(
        db.String(20),
        nullable=False,
        default='Inactivo'
    )  # Activo, Inactivo

    # Control de operaciones sin documentos completos
    operations_without_docs_count = db.Column(db.Integer, default=0)
    operations_without_docs_limit = db.Column(db.Integer, nullable=True)
    max_amount_without_docs = db.Column(db.Numeric(15, 2), nullable=True)
    has_complete_documents = db.Column(db.Boolean, default=False)
    inactive_reason = db.Column(db.String(200), nullable=True)
    documents_pending_since = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relaciones
    operations = db.relationship('Operation', backref='client', lazy='dynamic')
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def full_name(self):
        """Obtener nombre completo según tipo de documento. Retorna None si no hay datos."""
        if self.document_type == 'RUC':
            return (self.razon_social.upper() if self.razon_social else None)
        else:
            parts = []
            if self.apellido_paterno:
                parts.append(self.apellido_paterno.upper())
            if self.apellido_materno:
                parts.append(self.apellido_materno.upper())
            if self.nombres:
                parts.append(self.nombres.upper())
            return ' '.join(parts) if parts else None

    @property
    def full_address(self):
        """Obtener dirección completa"""
        parts = []
        if self.direccion:
            parts.append(self.direccion)
        if self.distrito:
            parts.append(self.distrito)
        if self.provincia:
            parts.append(self.provincia)
        if self.departamento:
            parts.append(self.departamento)
        return ', '.join(parts) if parts else None

    @property
    def bank_accounts(self):
        """Obtener cuentas bancarias como lista de diccionarios"""
        if self.bank_accounts_json:
            try:
                # Si ya es un dict/list (JSONB de PostgreSQL), devolverlo directamente
                if isinstance(self.bank_accounts_json, (list, dict)):
                    return self.bank_accounts_json if isinstance(self.bank_accounts_json, list) else [self.bank_accounts_json]
                # Si es string, parsearlo
                return json.loads(self.bank_accounts_json)
            except Exception as e:
                print(f"Error parsing bank_accounts_json: {e}")
                return []
        return []

    def set_bank_accounts(self, accounts_list):
        """
        Establecer cuentas bancarias desde lista de diccionarios

        Args:
            accounts_list: Lista de diccionarios con información de cuentas
                [{"origen": "Lima", "bank_name": "BCP", "account_type": "Ahorro",
                  "currency": "S/", "account_number": "123456"}]
        """
        if not accounts_list:
            self.bank_accounts_json = None
            return

        # store complete normalized list
        normalized = []
        for acc in accounts_list:
            normalized.append({
                'origen': (acc.get('origen') or '').strip(),
                'bank_name': (acc.get('bank_name') or '').strip(),
                'account_type': (acc.get('account_type') or '').strip(),
                'currency': (acc.get('currency') or '').strip(),
                'account_number': (acc.get('account_number') or '').strip()
            })
        self.bank_accounts_json = json.dumps(normalized, ensure_ascii=False)

        # Mantener compatibilidad con campos antiguos (usar primera cuenta)
        if len(normalized) > 0:
            first = normalized[0]
            self.bank_name = first.get('bank_name') or None
            self.account_type = first.get('account_type') or None
            self.currency = first.get('currency') or None
            self.bank_account_number = first.get('account_number') or None
            self.origen = first.get('origen') or None

    @staticmethod
    def validate_bank_accounts(accounts_list):
        """
        Validar que existan al menos 2 cuentas: una en S/ y otra en $
        Máximo 6 cuentas permitidas

        ACTUALIZADO: Ahora permite múltiples cuentas con el mismo banco y moneda,
        pero rechaza duplicados exactos (mismo banco, tipo de cuenta, número y moneda)

        Returns:
            tuple: (is_valid: bool, message: str)
        """
        if not accounts_list or not isinstance(accounts_list, (list, tuple)):
            return False, 'bank_accounts debe ser una lista de cuentas'

        if len(accounts_list) < 2:
            return False, 'Debes registrar al menos 2 cuentas bancarias'

        if len(accounts_list) > 6:
            return False, 'Máximo 6 cuentas bancarias permitidas'

        # validar estructura de cada cuenta
        allowed_account_types = {'Ahorro', 'Corriente'}
        allowed_currencies = {'S/', '$'}

        currencies_present = []
        seen_accounts = set()  # Para detectar duplicados EXACTOS (banco + tipo + número + moneda)

        for idx, account in enumerate(accounts_list, start=1):
            if not isinstance(account, dict):
                return False, f'Cuenta #{idx} inválida'
            bank = (account.get('bank_name') or '').strip()
            acc_num = (account.get('account_number') or '').strip()
            acct_type = (account.get('account_type') or '').strip()
            currency = (account.get('currency') or '').strip()

            if not bank:
                return False, f'Cuenta #{idx}: bank_name es requerido'
            if not acc_num:
                return False, f'Cuenta #{idx}: account_number es requerido'
            if acct_type and acct_type not in allowed_account_types:
                return False, f'Cuenta #{idx}: account_type inválido (Ahorro|Corriente)'
            if currency and currency not in allowed_currencies:
                return False, f'Cuenta #{idx}: currency inválida (S/|$)'
            if currency:
                currencies_present.append(currency)

            # MEJORADO: Validar duplicados EXACTOS (toda la información debe ser idéntica)
            # Esto permite tener múltiples cuentas del mismo banco en la misma moneda
            # siempre que tengan números de cuenta diferentes
            account_key = f"{bank}_{acct_type}_{acc_num}_{currency}"
            if account_key in seen_accounts:
                return False, f'Cuenta duplicada detectada en Cuenta #{idx}: Ya existe una cuenta idéntica con {bank}, {acct_type}, {currency}, número {acc_num}'
            seen_accounts.add(account_key)

            # Validar CCI (20 dígitos) para bancos que requieren CCI
            if bank in ('BBVA', 'SCOTIABANK') and len(acc_num) != 20:
                return False, f'El CCI de {bank} (Cuenta #{idx}) debe tener exactamente 20 dígitos'

        if 'S/' not in currencies_present or '$' not in currencies_present:
            return False, 'Debes registrar al menos una cuenta en Soles (S/) y una en Dólares ($)'

        return True, 'Cuentas válidas'

    def set_password(self, password):
        """
        Establecer contraseña hasheada para acceso a app móvil

        Args:
            password: Contraseña en texto plano
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Verificar contraseña del cliente

        Args:
            password: Contraseña en texto plano

        Returns:
            bool: True si la contraseña es correcta
        """
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_stats=False):
        """
        Convertir a diccionario

        ACTUALIZADO: Ahora incluye información del usuario que creó el cliente
        """
        # NUEVO: Información del usuario que creó el cliente (con manejo de errores)
        created_by_username = None
        created_by_role = None
        if self.created_by:
            try:
                created_by_username = self.creator.username if self.creator else None
                created_by_role = self.creator.role if self.creator else None
            except Exception:
                # Si la relación creator no está cargada o hay un error, usar None
                pass

        data = {
            'id': self.id,
            'document_type': self.document_type,
            'dni': self.dni,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'bank_accounts': self.bank_accounts,
            'created_by_id': self.created_by,
            'created_by_username': created_by_username,
            'created_by_role': created_by_role,
            'has_complete_documents': self.has_complete_documents or False,
        }

        if self.document_type == 'RUC':
            data.update({
                'razon_social': self.razon_social,
                'persona_contacto': self.persona_contacto,
                'dni_representante_front_url': self.dni_representante_front_url,
                'dni_representante_back_url': self.dni_representante_back_url,
                'ficha_ruc_url': self.ficha_ruc_url,
            })
        else:
            data.update({
                'apellido_paterno': self.apellido_paterno,
                'apellido_materno': self.apellido_materno,
                'nombres': self.nombres,
                'dni_front_url': self.dni_front_url,
                'dni_back_url': self.dni_back_url,
            })

        # Dirección
        data.update({
            'direccion': self.direccion,
            'distrito': self.distrito,
            'provincia': self.provincia,
            'departamento': self.departamento,
            'full_address': self.full_address,
        })

        # Validación OC
        data['validation_oc_url'] = self.validation_oc_url

        # Compatibilidad con campos antiguos
        data.update({
            'bank_name': self.bank_name,
            'account_type': self.account_type,
            'currency': self.currency,
            'bank_account_number': self.bank_account_number,
            'origen': self.origen,
        })

        if include_stats:
            try:
                if hasattr(self, 'operations') and self.operations is not None:
                    # Usar count() si es una relación dynamic, o len() si es una lista
                    if hasattr(self.operations, 'count'):
                        data['total_operations'] = self.operations.count()
                        completed_operations = self.operations.filter_by(status='Completada').all()
                    else:
                        data['total_operations'] = len(self.operations) if self.operations else 0
                        completed_operations = [op for op in self.operations if op.status == 'Completada']

                    data['total_usd_traded'] = sum(float(op.amount_usd or 0) for op in completed_operations)
                else:
                    data['total_operations'] = 0
                    data['total_usd_traded'] = 0
            except Exception as e:
                data['total_operations'] = 0
                data['total_usd_traded'] = 0

        return data

    def is_active_client(self):
        """Verificar si está activo"""
        return self.status == 'Activo'

    def can_operate(self):
        """Verificar si puede realizar operaciones"""
        return self.status == 'Activo'

    def get_total_operations(self):
        """Obtener total de operaciones"""
        return self.operations.count() if hasattr(self, 'operations') else 0

    def get_completed_operations(self):
        """Obtener operaciones completadas"""
        return self.operations.filter_by(status='Completada').count() if hasattr(self, 'operations') else 0

    # Métodos para control de documentos parciales

    def check_complete_documents(self):
        """
        Verificar si el cliente tiene todos los documentos obligatorios completos

        Returns:
            bool: True si tiene documentos completos, False en caso contrario
        """
        if self.document_type in ('DNI', 'CE'):
            # Persona Natural: requiere DNI frente y reverso
            return bool(self.dni_front_url and self.dni_back_url)
        elif self.document_type == 'RUC':
            # Persona Jurídica: requiere DNI rep legal (frente y reverso) + Ficha RUC
            return bool(
                self.dni_representante_front_url and
                self.dni_representante_back_url and
                self.ficha_ruc_url
            )
        return False

    def initialize_partial_docs_limits(self):
        """
        Establecer límites iniciales basados en tipo de documento

        - DNI/CE: 1 operación, máximo USD 3,000
        - RUC: 1 operación, máximo USD 50,000
        """
        if self.document_type in ('DNI', 'CE'):
            self.operations_without_docs_limit = 1
            self.max_amount_without_docs = 3000.00
        elif self.document_type == 'RUC':
            self.operations_without_docs_limit = 1
            self.max_amount_without_docs = 50000.00

        # Inicializar contador en 0
        self.operations_without_docs_count = 0

        # Marcar fecha de inicio de documentos pendientes
        if not self.has_complete_documents:
            self.documents_pending_since = now_peru()

    def can_create_operation(self, amount_usd):
        """
        Verificar si el cliente puede crear una nueva operación

        Args:
            amount_usd: Monto de la operación en USD

        Returns:
            tuple: (bool, str) - (puede_operar, mensaje_error)
        """
        # Si tiene documentos completos, puede operar sin restricciones
        if self.has_complete_documents:
            return True, None

        # Verificar si tiene límites configurados
        if self.operations_without_docs_limit is None:
            return False, "Cliente sin límites configurados para operaciones sin documentos"

        # Verificar si ya excedió el número de operaciones permitidas
        if self.operations_without_docs_count >= self.operations_without_docs_limit:
            return False, f"Cliente ha alcanzado el límite de {self.operations_without_docs_limit} operación(es) sin documentos completos. Debe regularizar documentación."

        # Verificar si el monto excede el límite permitido
        if amount_usd > float(self.max_amount_without_docs):
            return False, f"Monto USD {amount_usd:,.2f} excede el límite permitido de USD {float(self.max_amount_without_docs):,.2f} para operaciones sin documentos completos"

        return True, None

    def increment_operations_without_docs(self):
        """
        Incrementar contador de operaciones sin documentos

        Returns:
            bool: True si alcanzó el límite, False si aún puede seguir operando
        """
        if not self.has_complete_documents:
            self.operations_without_docs_count += 1

            # Verificar si alcanzó el límite
            if self.operations_without_docs_count >= self.operations_without_docs_limit:
                return True  # Alcanzó límite

        return False  # Aún puede operar

    def disable_for_missing_documents(self):
        """
        Inhabilitar cliente por falta de documentos completos
        """
        self.status = 'Inactivo'
        self.inactive_reason = 'Inactivo por falta de documentos'

        # Si no tenía fecha de documentos pendientes, establecerla ahora
        if not self.documents_pending_since:
            self.documents_pending_since = now_peru()

    def complete_documents_and_reset(self):
        """
        Marcar documentos como completos y resetear contadores
        Llamar cuando Middle Office verifica y aprueba todos los documentos
        """
        self.has_complete_documents = True
        self.operations_without_docs_count = 0
        self.documents_pending_since = None

        # Si estaba inactivo por documentos, reactivar
        if self.inactive_reason == 'Inactivo por falta de documentos':
            self.status = 'Activo'
            self.inactive_reason = None

    def __repr__(self):
        return f'<Client {self.full_name or self.razon_social or self.dni} - {self.document_type}: {self.dni}>'
"""
Servicio de Archivos para QoriCash Trading V2

Maneja carga, validación y gestión de archivos en Cloudinary.
"""
import os
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
from app.utils.constants import MAX_FILE_SIZE, ALLOWED_EXTENSIONS


class FileService:
    """Servicio de gestión de archivos"""
    
    def __init__(self):
        """Inicializar configuración de Cloudinary"""
        self.configured = False
        self._configure_cloudinary()
    
    def _configure_cloudinary(self):
        """Configurar Cloudinary con variables de entorno"""
        try:
            cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
            api_key = os.environ.get('CLOUDINARY_API_KEY')
            api_secret = os.environ.get('CLOUDINARY_API_SECRET')

            # Verificar que las credenciales no sean valores de ejemplo
            if not cloud_name or cloud_name == 'your-cloud-name':
                print("ERROR: CLOUDINARY_CLOUD_NAME no está configurado correctamente en .env")
                self.configured = False
                return

            if not api_key or api_key == 'your-api-key':
                print("ERROR: CLOUDINARY_API_KEY no está configurado correctamente en .env")
                self.configured = False
                return

            if not api_secret or api_secret == 'your-api-secret':
                print("ERROR: CLOUDINARY_API_SECRET no está configurado correctamente en .env")
                self.configured = False
                return

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            self.configured = True
            print(f"[OK] Cloudinary configurado correctamente: {cloud_name}")
        except Exception as e:
            print(f"[ERROR] Error configurando Cloudinary: {e}")
            self.configured = False
    
    @staticmethod
    def allowed_file(filename):
        """
        Verificar si la extensión del archivo es permitida
        
        Args:
            filename: Nombre del archivo
        
        Returns:
            bool: True si es permitida
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
    @staticmethod
    def validate_file_size(file):
        """
        Validar tamaño del archivo
        
        Args:
            file: FileStorage object
        
        Returns:
            tuple: (is_valid: bool, message: str)
        """
        # Leer el archivo para obtener su tamaño
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)  # Volver al inicio
        
        if size > MAX_FILE_SIZE:
            size_mb = size / (1024 * 1024)
            max_mb = MAX_FILE_SIZE / (1024 * 1024)
            return False, f'Archivo muy grande ({size_mb:.1f}MB). Máximo permitido: {max_mb:.0f}MB'
        
        return True, 'Tamaño válido'
    
    def upload_file(self, file, folder, public_id_prefix=None):
        """
        Subir archivo a Cloudinary

        Args:
            file: FileStorage object
            folder: Carpeta en Cloudinary (e.g., 'dni', 'operations')
            public_id_prefix: Prefijo para el ID público (opcional)

        Returns:
            tuple: (success: bool, message: str, url: str|None)
        """
        if not self.configured:
            return False, 'Cloudinary no está configurado. Por favor configure las credenciales en el archivo .env', None
        
        # Validar que hay archivo
        if not file or file.filename == '':
            return False, 'No se seleccionó ningún archivo', None
        
        # Validar extensión
        if not self.allowed_file(file.filename):
            return False, f'Tipo de archivo no permitido. Permitidos: {", ".join(ALLOWED_EXTENSIONS)}', None
        
        # Validar tamaño
        is_valid, message = self.validate_file_size(file)
        if not is_valid:
            return False, message, None
        
        try:
            # Generar nombre seguro
            filename = secure_filename(file.filename)
            
            # Generar public_id
            if public_id_prefix:
                public_id = f"{folder}/{public_id_prefix}_{filename}"
            else:
                public_id = f"{folder}/{filename}"
            
            # Subir a Cloudinary
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                public_id=public_id,
                resource_type='auto'
            )
            
            # Obtener URL segura
            url = result.get('secure_url')
            
            return True, 'Archivo subido exitosamente', url
        
        except Exception as e:
            return False, f'Error al subir archivo: {str(e)}', None
    
    def upload_dni_front(self, file, client_dni):
        """
        Subir DNI frontal de cliente
        
        Args:
            file: FileStorage object
            client_dni: DNI del cliente
        
        Returns:
            tuple: (success: bool, message: str, url: str|None)
        """
        return self.upload_file(file, 'dni', f'{client_dni}_front')
    
    def upload_dni_back(self, file, client_dni):
        """
        Subir DNI reverso de cliente
        
        Args:
            file: FileStorage object
            client_dni: DNI del cliente
        
        Returns:
            tuple: (success: bool, message: str, url: str|None)
        """
        return self.upload_file(file, 'dni', f'{client_dni}_back')
    
    def upload_payment_proof(self, file, operation_id):
        """
        Subir comprobante de pago de operación
        
        Args:
            file: FileStorage object
            operation_id: ID de la operación (EXP-XXXX)
        
        Returns:
            tuple: (success: bool, message: str, url: str|None)
        """
        return self.upload_file(file, 'operations/payment_proofs', operation_id)
    
    def upload_operator_proof(self, file, operation_id):
        """
        Subir comprobante del operador
        
        Args:
            file: FileStorage object
            operation_id: ID de la operación (EXP-XXXX)
        
        Returns:
            tuple: (success: bool, message: str, url: str|None)
        """
        return self.upload_file(file, 'operations/operator_proofs', operation_id)
    
    @staticmethod
    def delete_file(url):
        """
        Eliminar archivo de Cloudinary (opcional)
        
        Args:
            url: URL del archivo en Cloudinary
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Extraer public_id de la URL
            # URL format: https://res.cloudinary.com/{cloud_name}/image/upload/v{version}/{public_id}.{format}
            parts = url.split('/')
            public_id_with_ext = '/'.join(parts[-2:])  # folder/filename.ext
            public_id = public_id_with_ext.rsplit('.', 1)[0]  # Remover extensión
            
            # Eliminar de Cloudinary
            result = cloudinary.uploader.destroy(public_id)
            
            if result.get('result') == 'ok':
                return True, 'Archivo eliminado exitosamente'
            else:
                return False, 'No se pudo eliminar el archivo'
        
        except Exception as e:
            return False, f'Error al eliminar archivo: {str(e)}'

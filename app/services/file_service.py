"""
Servicio de Archivos usando Cloudinary
"""
import os
import logging
import cloudinary
import cloudinary.uploader
from datetime import datetime
from werkzeug.utils import secure_filename
from app.utils.constants import MAX_FILE_SIZE, ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)


class FileService:
    """Servicio de gestión de archivos con Cloudinary"""

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

            if not all([cloud_name, api_key, api_secret]):
                print("[WARNING] Cloudinary no configurado completamente")
                self.configured = False
                return

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )

            self.configured = True
            print(f"[OK] Cloudinary configurado: {cloud_name}")

        except Exception as e:
            print(f"[ERROR] Error configurando Cloudinary: {e}")
            self.configured = False

    @staticmethod
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @staticmethod
    def validate_file_size(file):
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        return size <= MAX_FILE_SIZE

    def upload_file(self, file, folder, public_id_prefix=None):
        """Subir archivo a Cloudinary"""
        if not self.configured:
            return False, 'Cloudinary no configurado', None

        if not file or file.filename == '':
            return False, 'No se seleccionó ningún archivo', None

        filename = secure_filename(file.filename)

        if not self.allowed_file(filename):
            return False, f'Tipo de archivo no permitido: {filename}', None

        if not self.validate_file_size(file):
            return False, f'Archivo muy grande (max {MAX_FILE_SIZE/(1024*1024)}MB)', None

        try:
            # Generar public_id único
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if public_id_prefix:
                public_id = f"{folder}/{public_id_prefix}_{timestamp}"
            else:
                public_id = f"{folder}/{timestamp}_{filename.rsplit('.', 1)[0]}"

            # Subir a Cloudinary
            file.seek(0)
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                public_id=public_id,
                resource_type='auto',
                overwrite=True
            )

            url = result.get('secure_url')
            logger.info(f"Archivo subido a Cloudinary: {public_id}")
            print(f"[OK] Archivo subido: {url}")

            return True, 'Archivo subido exitosamente', url

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error al subir archivo: {error_msg}", exc_info=True)
            print(f"[ERROR] {error_msg}")
            return False, f'Error al subir archivo: {error_msg}', None

    def upload_dni_front(self, file, client_dni):
        return self.upload_file(file, 'dni', f'{client_dni}_front')

    def upload_dni_back(self, file, client_dni):
        return self.upload_file(file, 'dni', f'{client_dni}_back')

    def upload_payment_proof(self, file, operation_id):
        return self.upload_file(file, 'operations/payment_proofs', operation_id)

    def upload_operator_proof(self, file, operation_id):
        return self.upload_file(file, 'operations/operator_proofs', operation_id)

    def upload_validation_oc(self, file, client_dni):
        return self.upload_file(file, 'validation_oc', f'OC_{client_dni}')

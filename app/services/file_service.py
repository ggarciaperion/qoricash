"""
Servicio de Archivos para QoriCash Trading V2

Maneja carga, validación y gestión de archivos en Amazon S3.
"""
import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from app.utils.constants import MAX_FILE_SIZE, ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)


class FileService:
    """Servicio de gestión de archivos con Amazon S3"""

    def __init__(self):
        """Inicializar configuración de Amazon S3"""
        self.configured = False
        self.s3_client = None
        self.bucket_name = None
        self.region = None
        self._configure_s3()

    def _configure_s3(self):
        """Configurar Amazon S3 con variables de entorno"""
        try:
            import boto3
            from botocore.exceptions import ClientError

            # Obtener credenciales de variables de entorno
            access_key = os.environ.get('AWS_ACCESS_KEY_ID')
            secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            bucket_name = os.environ.get('AWS_S3_BUCKET_NAME')
            region = os.environ.get('AWS_S3_REGION', 'us-east-1')

            if not access_key:
                print("[WARNING] AWS_ACCESS_KEY_ID no configurado")
                self.configured = False
                return

            if not secret_key:
                print("[WARNING] AWS_SECRET_ACCESS_KEY no configurado")
                self.configured = False
                return

            if not bucket_name:
                print("[WARNING] AWS_S3_BUCKET_NAME no configurado")
                self.configured = False
                return

            # Crear cliente de S3
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )

            self.bucket_name = bucket_name
            self.region = region

            # Verificar que el bucket existe
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                self.configured = True
                print(f"[OK] Amazon S3 configurado correctamente: {bucket_name} (región: {region})")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    print(f"[ERROR] El bucket '{bucket_name}' no existe en S3")
                else:
                    print(f"[ERROR] Error al verificar bucket: {e}")
                self.configured = False

        except ImportError:
            print("[ERROR] boto3 no instalado. Ejecuta: pip install boto3")
            self.configured = False
        except Exception as e:
            print(f"[ERROR] Error configurando Amazon S3: {e}")
            logger.error(f"Error configurando S3: {e}", exc_info=True)
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
        Subir archivo a Amazon S3

        Args:
            file: FileStorage object
            folder: Carpeta en S3 (e.g., 'dni', 'operations')
            public_id_prefix: Prefijo para el nombre del archivo (opcional)

        Returns:
            tuple: (success: bool, message: str, url: str|None)
        """
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

        if not self.configured:
            return False, 'Amazon S3 no está configurado correctamente', None

        try:
            from botocore.exceptions import ClientError

            # Generar nombre seguro con timestamp
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            if public_id_prefix:
                s3_key = f"{folder}/{public_id_prefix}_{timestamp}_{filename}"
            else:
                s3_key = f"{folder}/{timestamp}_{filename}"

            # Detectar content type
            content_type = file.content_type or 'application/octet-stream'

            # Subir archivo a S3
            file.seek(0)  # Asegurar que estamos al inicio del archivo
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': content_type,
                    'ACL': 'public-read'  # Hacer archivo público
                }
            )

            # Generar URL pública
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"

            logger.info(f"Archivo subido a S3: {s3_key}")
            print(f"[OK] Archivo subido a Amazon S3: {url}")

            return True, 'Archivo subido exitosamente', url

        except ClientError as e:
            error_msg = str(e)
            logger.error(f"Error al subir archivo a S3: {error_msg}", exc_info=True)
            print(f"[ERROR] Error al subir archivo a S3: {error_msg}")
            return False, f'Error al subir archivo: {error_msg}', None
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error inesperado al subir archivo: {error_msg}", exc_info=True)
            print(f"[ERROR] Error inesperado: {error_msg}")
            return False, f'Error al subir archivo: {error_msg}', None

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

    def delete_file(self, url):
        """
        Eliminar archivo de Amazon S3

        Args:
            url: URL del archivo en S3

        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.configured:
            return False, 'Amazon S3 no está configurado'

        try:
            from botocore.exceptions import ClientError

            # Extraer key del archivo de la URL
            # URL format: https://{bucket}.s3.{region}.amazonaws.com/{key}
            if self.bucket_name in url:
                parts = url.split(f"{self.bucket_name}.s3.{self.region}.amazonaws.com/")
                if len(parts) < 2:
                    # Intentar formato alternativo
                    parts = url.split(f"s3.amazonaws.com/{self.bucket_name}/")
                    if len(parts) < 2:
                        return False, 'URL de archivo inválida'
                    s3_key = parts[1]
                else:
                    s3_key = parts[1]
            else:
                return False, 'URL no pertenece a este bucket'

            # Eliminar archivo
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )

            logger.info(f"Archivo eliminado de S3: {s3_key}")
            return True, 'Archivo eliminado exitosamente'

        except ClientError as e:
            error_msg = str(e)
            logger.error(f"Error al eliminar archivo de S3: {error_msg}", exc_info=True)
            return False, f'Error al eliminar archivo: {error_msg}'
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error inesperado al eliminar archivo: {error_msg}", exc_info=True)
            return False, f'Error al eliminar archivo: {error_msg}'

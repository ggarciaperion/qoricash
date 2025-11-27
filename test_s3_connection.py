"""
Script para probar la conexión a Amazon S3
Ejecutar DESPUÉS de configurar las variables de entorno
"""
import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()


def test_s3_configuration():
    """Probar configuración de Amazon S3"""
    print("\n" + "=" * 70)
    print("PRUEBA DE CONFIGURACIÓN DE AMAZON S3")
    print("=" * 70 + "\n")

    # 1. Verificar variables de entorno
    print("1. Verificando variables de entorno...")
    print("-" * 70)

    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    bucket_name = os.environ.get('AWS_S3_BUCKET_NAME')
    region = os.environ.get('AWS_S3_REGION', 'us-east-1')

    if not access_key:
        print("✗ AWS_ACCESS_KEY_ID: NO CONFIGURADO")
        return False
    else:
        # Mostrar solo primeros y últimos caracteres
        masked = access_key[:4] + "..." + access_key[-4:] if len(access_key) > 8 else "***"
        print(f"✓ AWS_ACCESS_KEY_ID: {masked}")

    if not secret_key:
        print("✗ AWS_SECRET_ACCESS_KEY: NO CONFIGURADO")
        return False
    else:
        print(f"✓ AWS_SECRET_ACCESS_KEY: {'*' * 20} (configurado)")

    if not bucket_name:
        print("✗ AWS_S3_BUCKET_NAME: NO CONFIGURADO")
        return False
    else:
        print(f"✓ AWS_S3_BUCKET_NAME: {bucket_name}")

    print(f"✓ AWS_S3_REGION: {region}")
    print()

    # 2. Probar importación de librería
    print("2. Verificando instalación de boto3...")
    print("-" * 70)

    try:
        import boto3
        from botocore.exceptions import ClientError
        print("✓ boto3 está instalado correctamente")
        print(f"  - Versión: {boto3.__version__}")
        print()
    except ImportError:
        print("✗ boto3 NO está instalado")
        print("  Ejecuta: pip install boto3")
        return False

    # 3. Probar conexión
    print("3. Probando conexión a Amazon S3...")
    print("-" * 70)

    try:
        # Crear cliente
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        print("✓ Cliente de Amazon S3 creado correctamente")

        # Verificar credenciales
        try:
            response = s3_client.list_buckets()
            print(f"✓ Credenciales válidas")
            print(f"  - Buckets disponibles: {len(response['Buckets'])}")
        except ClientError as e:
            print(f"✗ Error de autenticación: {e}")
            return False

        # Verificar bucket específico
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✓ Bucket '{bucket_name}' existe y es accesible")

            # Obtener información del bucket
            try:
                location = s3_client.get_bucket_location(Bucket=bucket_name)
                bucket_region = location['LocationConstraint'] or 'us-east-1'
                print(f"  - Región del bucket: {bucket_region}")
            except:
                pass

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"✗ Bucket '{bucket_name}' NO existe")
                print("  Verifica que creaste el bucket en AWS Console")
            elif error_code == '403':
                print(f"✗ No tienes permisos para acceder al bucket '{bucket_name}'")
                print("  Verifica que el usuario IAM tenga permisos S3")
            else:
                print(f"✗ Error al verificar bucket: {e}")
            return False

        print()

        # 4. Probar subida de archivo de prueba
        print("4. Probando subida de archivo de prueba...")
        print("-" * 70)

        test_content = f"Prueba de QoriCash Trading - {datetime.now().isoformat()}"
        test_key = f"test/prueba_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content.encode('utf-8'),
            ContentType='text/plain',
            ACL='public-read'
        )

        print(f"✓ Archivo de prueba subido exitosamente")
        print(f"  - Key: {test_key}")

        # Generar URL pública
        url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{test_key}"
        print(f"  - URL pública: {url}")
        print(f"  - Tamaño: {len(test_content)} bytes")

        print()

        # 5. Probar descarga
        print("5. Probando descarga del archivo...")
        print("-" * 70)

        response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
        downloaded_content = response['Body'].read().decode('utf-8')

        if downloaded_content == test_content:
            print("✓ Archivo descargado y verificado correctamente")
        else:
            print("✗ El contenido descargado no coincide")
            return False

        print()

        # 6. Limpiar archivo de prueba
        print("6. Limpiando archivo de prueba...")
        print("-" * 70)

        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        print("✓ Archivo de prueba eliminado\n")

        # RESUMEN FINAL
        print("=" * 70)
        print("✓✓✓ TODAS LAS PRUEBAS PASARON EXITOSAMENTE ✓✓✓")
        print("=" * 70)
        print("\nAmazon S3 está configurado correctamente.")
        print("Puedes proceder a aplicar los cambios en la aplicación.\n")

        return True

    except ClientError as e:
        print(f"\n✗ ERROR DE AWS: {str(e)}\n")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Ejecutar pruebas
    success = test_s3_configuration()

    if success:
        print("\n" + "=" * 70)
        print("SIGUIENTE PASO:")
        print("=" * 70)
        print("\n1. Reemplaza app/services/file_service.py con file_service_S3.py")
        print("2. Actualiza requirements.txt con requirements_S3.txt")
        print("3. Haz commit y push de los cambios")
        print("4. Deploy automático en Render\n")
    else:
        print("\n" + "=" * 70)
        print("SOLUCIÓN:")
        print("=" * 70)
        print("\n1. Revisa que las variables de entorno estén configuradas")
        print("2. Verifica que el bucket existe en AWS Console")
        print("3. Asegúrate de que las credenciales IAM tengan permisos S3")
        print("4. Vuelve a ejecutar este script\n")

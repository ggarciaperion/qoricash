import os
import boto3
from botocore.exceptions import ClientError

print("=== TEST S3 CONNECTIVITY ===")
print(f"AWS_ACCESS_KEY_ID: {os.environ.get('AWS_ACCESS_KEY_ID', 'NOT SET')[:10]}...")
print(f"AWS_S3_BUCKET_NAME: {os.environ.get('AWS_S3_BUCKET_NAME', 'NOT SET')}")
print(f"AWS_S3_REGION: {os.environ.get('AWS_S3_REGION', 'NOT SET')}")

try:
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_S3_REGION', 'us-east-1')
    )
    
    print("\nTesting connection...")
    response = s3.list_objects_v2(
        Bucket=os.environ.get('AWS_S3_BUCKET_NAME'),
        MaxKeys=1
    )
    print("✓ SUCCESS: Connected to S3!")
    print(f"Bucket exists and is accessible")
    
except ClientError as e:
    print(f"✗ ERROR: {e}")
except Exception as e:
    print(f"✗ UNEXPECTED ERROR: {e}")

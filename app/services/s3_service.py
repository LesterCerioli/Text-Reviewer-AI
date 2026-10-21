import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional, BinaryIO


def get_s3_client():
   
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "t-100"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "amadeus74367908"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )


def get_bucket_name() -> str:
    
    bucket_name = os.getenv("S3_BUCKET_NAME")
    if not bucket_name:
        # Default bucket for development/local testing
        bucket_name = "plagiarism-checker-dev"
    return bucket_name


def upload_fileobj(file_obj: BinaryIO, key: str, content_type: Optional[str] = None) -> str:
    
    s3 = get_s3_client()
    bucket = get_bucket_name()
    
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    
    try:
        s3.upload_fileobj(file_obj, bucket, key, ExtraArgs=extra_args)
        return f"s3://{bucket}/{key}"
    except ClientError as e:
        print(f"S3 upload error: {e}")
        raise


def download_file(key: str) -> bytes:
    
    s3 = get_s3_client()
    bucket = get_bucket_name()
    
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except ClientError as e:
        print(f"S3 download error: {e}")
        raise


def delete_file(key: str) -> bool:
    
    s3 = get_s3_client()
    bucket = get_bucket_name()
    
    try:
        s3.delete_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        print(f"S3 delete error: {e}")
        return False


def generate_user_key(user_id: str, filename: str) -> str:
    
    import uuid
    import datetime
    
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    
    if ext.lower() in ["docx", "doc", "pdf"]:
        return f"users/{user_id}/documents/{timestamp}_{unique_id}.{ext}"
    return f"users/{user_id}/documents/{timestamp}_{unique_id}.bin"
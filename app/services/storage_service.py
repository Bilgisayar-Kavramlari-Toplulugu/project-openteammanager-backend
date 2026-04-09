"""
Storage Service
MinIO (local) veya AWS S3 (prod) ile konuşur.
Hangi ortamda olduğunu .env'deki STORAGE_BACKEND belirler.
"""

import uuid
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from fastapi import HTTPException

from app.config import settings


def _get_client():
    """Env'e göre MinIO veya S3 client döner. Her ikisi de boto3 kullanır."""
    if settings.STORAGE_BACKEND == "minio":
        return boto3.client(
            "s3",
            endpoint_url=f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",  # MinIO için sabit, önemli değil
        )
    else:
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )


def _ensure_bucket_exists(client) -> None:
    """Bucket yoksa oluşturur. Özellikle local MinIO ilk kurulumda gerekli."""
    try:
        client.head_bucket(Bucket=settings.STORAGE_BUCKET)
    except ClientError:
        client.create_bucket(Bucket=settings.STORAGE_BUCKET)


def upload_file(
    file_content: bytes,
    storage_path: str,
    mime_type: str,
) -> None:
    """
    Dosyayı storage'a yükler.
    storage_path örn: "organizations/abc/projects/xyz/dosya.pdf"
    """
    client = _get_client()
    _ensure_bucket_exists(client)

    try:
        client.put_object(
            Bucket=settings.STORAGE_BUCKET,
            Key=storage_path,
            Body=file_content,
            ContentType=mime_type,
        )
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Dosya yüklenemedi: {str(e)}")


def delete_file(storage_path: str) -> None:
    """Dosyayı storage'dan siler."""
    client = _get_client()
    try:
        client.delete_object(
            Bucket=settings.STORAGE_BUCKET,
            Key=storage_path,
        )
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Dosya silinemedi: {str(e)}")


def generate_presigned_url(storage_path: str, expires_in: int = 900) -> str:
    """
    15 dakika (900 saniye) geçerli presigned download URL üretir.
    expires_in: saniye cinsinden geçerlilik süresi
    """
    client = _get_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.STORAGE_BUCKET,
                "Key": storage_path,
            },
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"URL üretilemedi: {str(e)}")


def build_storage_path(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    filename: str,
) -> str:
    """
    Storage'daki dosya yolunu oluşturur.
    Örn: "orgs/abc-123/projects/xyz-456/files/uuid-789_dosya.pdf"
    Dosya adını UUID ile önekliyoruz — aynı isimli dosyalar çakışmasın.
    """
    return f"orgs/{org_id}/projects/{project_id}/files/{file_id}_{filename}"
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentResponse
from app.services import storage_service
from app.services.helpers import require_project_member, is_project_manager, get_task_or_404, log_activity


# ── Dosya validasyon sabitleri ──

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

ALLOWED_MIME_TYPES = {
    # Resim
    "image/jpeg", "image/png", "image/gif", "image/webp",
    # Döküman
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # xlsx
    "text/plain", "text/markdown",
    # Arşiv
    "application/zip", "application/x-rar-compressed",
    # Diğer
    "text/csv", "application/json",
}

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp",
    "pdf", "docx", "xlsx", "txt", "md",
    "zip", "rar",
    "csv", "json",
}


async def upload_attachment(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID | None, file: UploadFile, user_id: uuid.UUID) -> AttachmentResponse:
    await require_project_member(db, project_id, user_id)

    # task_id verilmişse görev bu projeye ait mi kontrol et
    if task_id:
        await get_task_or_404(db, project_id, task_id)

    # Aynı isimli dosya var mı kontrol et
    existing = await db.execute(
        select(Attachment).where(
            Attachment.project_id == project_id,
            Attachment.task_id == task_id,  # None vs None da eşleşir
            Attachment.filename == file.filename,
            Attachment.deleted_at.is_(None),
        )
    )

    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"'{file.filename}' adında bir dosya zaten mevcut"
        )

    # Dosya validasyonu
    file_content = await file.read()
    _validate_file(file.filename, file.content_type, len(file_content))

    # Storage path oluştur ve yükle
    file_id = uuid.uuid4()
    storage_path = storage_service.build_storage_path(
        org_id, project_id, file_id, file.filename
    )
    storage_service.upload_file(file_content, storage_path, file.content_type)

    # Metadata DB'ye kaydet
    attachment = Attachment(
        id=file_id,
        project_id=project_id,
        task_id=task_id,
        uploaded_by=user_id,
        filename=file.filename,
        storage_path=storage_path,
        file_size=len(file_content),
        mime_type=file.content_type,
    )
    db.add(attachment)

    await log_activity(
        db,
        org_id=org_id,
        project_id=project_id,
        task_id=task_id,
        actor_id=user_id,
        action="attachment_uploaded",
        entity_type="attachment",
        entity_id=file_id
    )

    await db.commit()
    await db.refresh(attachment)
    return _serialize(attachment)


async def list_attachments(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID | None, user_id: uuid.UUID) -> list[AttachmentResponse]:
    await require_project_member(db, project_id, user_id)

    query = select(Attachment).where(
        Attachment.project_id == project_id,
        Attachment.deleted_at.is_(None),
    )
    if task_id:
        query = query.where(Attachment.task_id == task_id)

    result = await db.execute(query.order_by(Attachment.created_at.desc()))
    attachments = result.scalars().all()
    return [_serialize(a) for a in attachments]


async def list_task_attachments(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID, user_id: uuid.UUID) -> list[AttachmentResponse]:
    await require_project_member(db, project_id, user_id)
    await get_task_or_404(db, project_id, task_id)

    result = await db.execute(
        select(Attachment).where(
            Attachment.project_id == project_id,
            Attachment.task_id == task_id,
            Attachment.deleted_at.is_(None),
        ).order_by(Attachment.created_at.desc())
    )
    attachments = result.scalars().all()
    return [_serialize(a) for a in attachments]


async def delete_attachment(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, attachment_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await require_project_member(db, project_id, user_id)
    attachment = await _get_attachment_or_404(db, project_id, attachment_id)

    is_owner = attachment.uploaded_by == user_id
    is_manager = await is_project_manager(db, project_id, user_id)

    if not is_owner and not is_manager:
        raise HTTPException(status_code=403, detail="Bu dosyayı silme yetkiniz yok")

    # Önce storage'dan sil, sonra soft-delete
    storage_service.delete_file(attachment.storage_path)
    attachment.deleted_at = datetime.now(timezone.utc)

    await log_activity(
        db,
        org_id=org_id,
        project_id=project_id,
        task_id=attachment.task_id,
        actor_id=user_id,
        action="attachment_deleted",
        entity_type="attachment",
        entity_id=attachment_id
    )

    await db.commit()


# --- Yardımcı fonksiyonlar -----------------------------

def _validate_file(filename: str, mime_type: str, file_size: int) -> None:
    """Boyut, uzantı ve MIME type kontrolü."""
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya boyutu 50 MB sınırını aşıyor ({file_size / 1024 / 1024:.1f} MB)"
        )

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"'.{extension}' uzantısı desteklenmiyor"
        )

    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"'{mime_type}' MIME tipi desteklenmiyor"
        )


async def _get_attachment_or_404(
    db: AsyncSession, project_id: uuid.UUID, attachment_id: uuid.UUID
) -> Attachment:
    result = await db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.project_id == project_id,
            Attachment.deleted_at.is_(None),
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return attachment


def _serialize(attachment: Attachment) -> AttachmentResponse:
    """Presigned URL ekleyerek response oluşturur."""
    download_url = storage_service.generate_presigned_url(attachment.storage_path)
    return AttachmentResponse(
        id=attachment.id,
        project_id=attachment.project_id,
        task_id=attachment.task_id,
        uploaded_by=attachment.uploaded_by,
        filename=attachment.filename,
        file_size=attachment.file_size,
        mime_type=attachment.mime_type,
        download_url=download_url,
        created_at=attachment.created_at,
    )
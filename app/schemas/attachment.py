import uuid
from datetime import datetime
from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    uploaded_by: uuid.UUID
    filename: str
    file_size: int
    mime_type: str
    download_url: str        # presigned URL — storage_path dönmüyoruz, güvenlik
    created_at: datetime

    model_config = {"from_attributes": True}
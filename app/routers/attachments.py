import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.services import attachment_service

router = APIRouter(
    prefix="/api/v1/organizations/{org_id}/projects/{project_id}",
    tags=["attachments"],
)


@router.post("/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    task_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await attachment_service.upload_attachment(db, org_id, project_id, task_id, file, current_user.id)


@router.get("/attachments", response_model=list[AttachmentResponse])
async def list_attachments(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await attachment_service.list_attachments(db, project_id, task_id, current_user.id)


@router.get("/tasks/{task_id}/attachments", response_model=list[AttachmentResponse])
async def list_task_attachments(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await attachment_service.list_task_attachments(db, project_id, task_id, current_user.id)


@router.delete("/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    await attachment_service.delete_attachment(db, org_id, project_id, attachment_id, current_user.id)
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.task_comments import CommentCreate, CommentUpdate, CommentResponse, PaginatedComments
from app.services import task_comments_service

router = APIRouter(
    prefix="/api/v1/organizations/{org_id}/projects/{project_id}",
    tags=["comments"],
)


@router.post("/tasks/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await task_comments_service.create_comment(db, org_id, project_id, task_id, data, current_user.id)


@router.get("/tasks/{task_id}/comments", response_model=PaginatedComments)
async def list_comments(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await task_comments_service.list_comments(db, project_id, task_id, current_user.id, page, limit)


@router.patch("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    comment_id: uuid.UUID,
    data: CommentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await task_comments_service.update_comment(db, org_id, project_id, comment_id, data, current_user.id)


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    await task_comments_service.delete_comment(db, org_id, project_id, comment_id, current_user.id)
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate, TaskMoveRequest, TaskResponse
from app.services import task_service

router = APIRouter(prefix="/api/v1/organizations/{org_id}/projects/{project_id}/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    status: str | None = Query(default=None),
    assignee_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    label: str | None = Query(default=None)):
    return await task_service.get_tasks(db, project_id, current_user.id, status, assignee_id, label)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await task_service.create_task(db, org_id, project_id, data, current_user.id)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await task_service.get_task(db, project_id, task_id, current_user.id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await task_service.update_task(db, project_id, task_id, data, current_user.id)


@router.patch("/{task_id}/move", response_model=TaskResponse)
async def move_task(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: TaskMoveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await task_service.move_task(db, project_id, task_id, data, current_user.id)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    await task_service.delete_task(db, project_id, task_id, current_user.id)
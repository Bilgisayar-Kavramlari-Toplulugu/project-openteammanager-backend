import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectMemberInvite, ProjectMemberResponse
from app.services import project_service

router = APIRouter(prefix="/api/v1/organizations/{org_id}/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await project_service.get_projects(db, org_id, current_user)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    org_id: uuid.UUID,
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await project_service.create_project(db, org_id, data, current_user)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await project_service.get_project(db, org_id, project_id, current_user)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await project_service.update_project(db, org_id, project_id, data, current_user)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    await project_service.delete_project(db, org_id, project_id, current_user)


@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_project_members(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await project_service.get_project_members(db, org_id, project_id, current_user)


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=201)
async def add_project_member(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    data: ProjectMemberInvite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await project_service.add_project_member(db, org_id, project_id, data, current_user)
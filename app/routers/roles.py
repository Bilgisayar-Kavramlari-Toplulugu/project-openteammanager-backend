"""
Rol yönetimi router'ı.

main.py'ye şu şekilde ekle:
    from app.routers import roles
    app.include_router(roles.router)
"""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.role import (OrgRoleUpdate, ProjectRoleUpdate, OrgMemberRoleResponse, ProjectMemberRoleResponse)
from app.services import role_service

router = APIRouter(tags=["roles"])


@router.patch("/api/v1/organizations/{org_id}/members/{user_id}/role", response_model=OrgMemberRoleResponse)
async def update_org_member_role(org_id: uuid.UUID, user_id: uuid.UUID, data: OrgRoleUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Org üyesinin rolünü değiştir — yalnızca Owner."""
    return await role_service.update_org_member_role(
        db, org_id, user_id, data, current_user
    )


@router.patch("/api/v1/organizations/{org_id}/projects/{project_id}/members/{user_id}/role", response_model=ProjectMemberRoleResponse)
async def update_project_member_role(org_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID, data: ProjectRoleUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Proje üyesinin rolünü değiştir — Owner veya Manager."""
    return await role_service.update_project_member_role(
        db, org_id, project_id, user_id, data, current_user
    )
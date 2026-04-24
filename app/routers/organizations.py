import uuid
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationResponse, MemberInvite, MemberResponse, PaginatedMembers, MemberDetailResponse
from app.services import organization_service
from app.services import member_service

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])

@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await organization_service.get_organizations(db, current_user)


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await organization_service.create_organization(db, data, current_user)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await organization_service.get_organization(db, org_id, current_user)


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: uuid.UUID,
    data: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await organization_service.update_organization(db, org_id, data, current_user)


@router.delete("/{org_id}", status_code=204)
async def delete_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    await organization_service.delete_organization(db, org_id, current_user)


@router.get("/{org_id}/members", response_model=PaginatedMembers)
async def list_members(
    org_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await member_service.list_members(
        db, org_id, current_user.id, page, limit, search, role
    )


@router.get("/{org_id}/members/{user_id}", response_model=MemberDetailResponse)
async def get_member_detail(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await member_service.get_member_detail(
        db, org_id, user_id, current_user.id
    )

@router.post("/{org_id}/members", response_model=MemberResponse, status_code=201)
async def invite_member(
    org_id: uuid.UUID,
    data: MemberInvite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    return await organization_service.invite_member(db, org_id, data, current_user)


@router.delete("/{org_id}/members/{user_id}", status_code=204)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)):
    await organization_service.remove_member(db, org_id, user_id, current_user)
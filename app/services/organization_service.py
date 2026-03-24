from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.organization import Organization
from app.models.organization_members import OrganizationMember
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, MemberInvite
import uuid
from datetime import datetime, timezone


async def create_organization(db: AsyncSession, data: OrganizationCreate, owner: User) -> Organization:
    existing = await db.execute(select(Organization).where(Organization.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Bu slug zaten kullanımda")

    org = Organization(
        name=data.name,
        slug=data.slug,
        description=data.description,
        logo_url=data.logo_url,
        owner_id=owner.id,
    )
    db.add(org)
    await db.flush()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=owner.id,
        role="owner",
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.commit()
    await db.refresh(org)
    return org


async def get_organizations(db: AsyncSession, user: User) -> list[Organization]:
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == "active",
            Organization.deleted_at.is_(None),
        )
    )
    return result.scalars().all()


async def get_organization(db: AsyncSession, org_id: uuid.UUID, user: User) -> Organization:
    org = await _get_org_or_404(db, org_id)
    await _require_member(db, org_id, user.id)
    return org


async def update_organization(db: AsyncSession, org_id: uuid.UUID, data: OrganizationUpdate, user: User) -> Organization:
    org = await _get_org_or_404(db, org_id)
    await _require_role(db, org_id, user.id, ["owner", "admin"])

    if data.name is not None:
        org.name = data.name
    if data.description is not None:
        org.description = data.description
    if data.logo_url is not None:
        org.logo_url = data.logo_url

    await db.commit()
    await db.refresh(org)
    return org


async def delete_organization(db: AsyncSession, org_id: uuid.UUID, user: User):
    org = await _get_org_or_404(db, org_id)
    await _require_role(db, org_id, user.id, ["owner"])
    org.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def get_members(db: AsyncSession, org_id: uuid.UUID, user: User) -> list[OrganizationMember]:
    await _get_org_or_404(db, org_id)
    await _require_member(db, org_id, user.id)
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status != "removed",
        )
    )
    return result.scalars().all()


async def invite_member(db: AsyncSession, org_id: uuid.UUID, data: MemberInvite, user: User) -> OrganizationMember:
    await _get_org_or_404(db, org_id)
    await _require_role(db, org_id, user.id, ["owner", "admin"])

    user_exists = await db.execute(select(User).where(User.id == data.user_id))
    if not user_exists.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    existing = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Kullanıcı zaten üye")

    member = OrganizationMember(
        organization_id=org_id,
        user_id=data.user_id,
        role=data.role,
        status="active",
        invited_by=user.id,
        invited_at=datetime.now(timezone.utc),
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


# --- Yardımcı fonksiyonlar ---

async def _get_org_or_404(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organizasyon bulunamadı")
    return org


async def _require_member(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Bu organizasyona erişim yetkiniz yok")


async def _require_role(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, roles: list[str]):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
    )
    member = result.scalar_one_or_none()
    if not member or member.role not in roles:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
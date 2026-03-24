from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.organization_members import OrganizationMember
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectMemberInvite
import uuid
from datetime import datetime, timezone


async def create_project(db: AsyncSession, org_id: uuid.UUID, data: ProjectCreate, user: User) -> Project:
    await _require_org_member(db, org_id, user.id)

    project = Project(
        organization_id=org_id,
        name=data.name,
        description=data.description,
        key=data.key,
        status=data.status,
        visibility=data.visibility,
        category=data.category,
        color=data.color,
        icon=data.icon,
        start_date=data.start_date,
        end_date=data.end_date,
        created_by=user.id,
    )
    db.add(project)
    await db.flush()

    member = ProjectMember(
        project_id=project.id,
        user_id=user.id,
        role="manager",
        added_by=user.id,
    )
    db.add(member)
    await db.commit()
    await db.refresh(project)
    return project


async def get_projects(db: AsyncSession, org_id: uuid.UUID, user: User) -> list[Project]:
    await _require_org_member(db, org_id, user.id)
    result = await db.execute(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Project.organization_id == org_id,
            ProjectMember.user_id == user.id,
            Project.deleted_at.is_(None),
        )
    )
    return result.scalars().all()


async def get_project(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, user: User) -> Project:
    project = await _get_project_or_404(db, org_id, project_id)
    await _require_project_member(db, project_id, user.id)
    return project


async def update_project(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, data: ProjectUpdate, user: User) -> Project:
    project = await _get_project_or_404(db, org_id, project_id)
    await _require_project_role(db, project_id, user.id, ["manager"])

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, user: User):
    project = await _get_project_or_404(db, org_id, project_id)
    await _require_project_role(db, project_id, user.id, ["manager"])
    project.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def get_project_members(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, user: User) -> list[ProjectMember]:
    await _get_project_or_404(db, org_id, project_id)
    await _require_project_member(db, project_id, user.id)
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    return result.scalars().all()


async def add_project_member(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, data: ProjectMemberInvite, user: User) -> ProjectMember:
    await _get_project_or_404(db, org_id, project_id)
    await _require_project_role(db, project_id, user.id, ["manager"])
    await _require_org_member(db, org_id, data.user_id)

    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Kullanıcı zaten proje üyesi")

    member = ProjectMember(
        project_id=project_id,
        user_id=data.user_id,
        role=data.role,
        added_by=user.id,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


# --- Yardımcı fonksiyonlar ---

async def _get_project_or_404(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == org_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Proje bulunamadı")
    return project


async def _require_org_member(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Bu organizasyona erişim yetkiniz yok")


async def _require_project_member(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID):
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Bu projeye erişim yetkiniz yok")


async def _require_project_role(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, roles: list[str]):
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member or member.role not in roles:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
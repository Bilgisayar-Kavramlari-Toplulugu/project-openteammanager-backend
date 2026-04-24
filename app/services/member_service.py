import uuid
from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.organization_members import OrganizationMember
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.models.task import Task
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.schemas.organization import (
    PaginatedMembers,
    MemberListItem,
    MemberUserInfo,
    MemberDetailResponse,
    MemberStats,
    MemberProjectInfo,
    ActivityFeedItem,
)
from app.services.helpers import require_project_member
from app.services.organization_service import _require_member


async def list_members(
    db: AsyncSession,
    org_id: uuid.UUID,
    current_user_id: uuid.UUID,
    page: int,
    limit: int,
    search: str | None,
    role: str | None,
) -> PaginatedMembers:
    # Sadece org üyeleri erişebilir
    await _require_member(db, org_id, current_user_id)

    offset = (page - 1) * limit

    # Base query — User join ile
    base_query = (
        select(OrganizationMember)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == "active",
            User.deleted_at.is_(None),
        )
        .options(selectinload(OrganizationMember.user))
    )

    # Arama filtresi
    if search:
        base_query = base_query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
        )

    # Rol filtresi
    if role:
        if role not in ["owner", "member"]:
            raise HTTPException(status_code=422, detail="Geçerli roller: owner, member")
        base_query = base_query.where(OrganizationMember.role == role)

    # Toplam sayı
    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Sayfalı sonuç
    result = await db.execute(
        base_query.order_by(OrganizationMember.joined_at.asc()).offset(offset).limit(limit)
    )
    members = result.scalars().all()

    items = [
        MemberListItem(
            id=m.id,
            user_id=m.user_id,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
            user=MemberUserInfo(
                id=m.user.id,
                username=m.user.username,
                full_name=m.user.full_name,
                avatar_url=m.user.avatar_url,
                email=m.user.email,
            ),
        )
        for m in members
    ]

    return PaginatedMembers(
        items=items,
        total=total,
        page=page,
        limit=limit,
        has_next=(offset + len(items)) < total,
    )


async def get_member_detail(
    db: AsyncSession,
    org_id: uuid.UUID,
    target_user_id: uuid.UUID,
    current_user_id: uuid.UUID,
) -> MemberDetailResponse:
    # Sadece org üyeleri erişebilir
    await _require_member(db, org_id, current_user_id)

    # Hedef kullanıcının org üyeliğini bul
    result = await db.execute(
        select(OrganizationMember)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == target_user_id,
            OrganizationMember.status == "active",
            User.deleted_at.is_(None),
        )
        .options(selectinload(OrganizationMember.user))
    )
    org_member = result.scalar_one_or_none()
    if not org_member:
        raise HTTPException(status_code=404, detail="Üye bulunamadı")

    user = org_member.user

    # Katıldığı projeler (bu org'daki)
    proj_result = await db.execute(
        select(Project, ProjectMember)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Project.organization_id == org_id,
            ProjectMember.user_id == target_user_id,
            Project.deleted_at.is_(None),
        )
    )
    project_rows = proj_result.all()
    projects = [
        MemberProjectInfo(
            id=p.id,
            name=p.name,
            key=p.key,
            status=p.status,
            role=pm.role,
        )
        for p, pm in project_rows
    ]

    # İstatistikler
    total_projects = len(projects)

    total_tasks_result = await db.execute(
        select(func.count()).where(
            Task.assignee_id == target_user_id,
            Task.deleted_at.is_(None),
        )
    )
    total_tasks = total_tasks_result.scalar_one()

    completed_tasks_result = await db.execute(
        select(func.count()).where(
            Task.assignee_id == target_user_id,
            Task.status == "done",
            Task.deleted_at.is_(None),
        )
    )
    completed_tasks = completed_tasks_result.scalar_one()

    # Son aktivite (en son 10)
    activity_result = await db.execute(
        select(ActivityLog)
        .where(
            ActivityLog.actor_id == target_user_id,
            ActivityLog.organization_id == org_id,
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
    )
    activities = activity_result.scalars().all()
    recent_activity = [
        ActivityFeedItem(
            action=a.action,
            entity_type=a.entity_type,
            created_at=a.created_at,
        )
        for a in activities
    ]

    return MemberDetailResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        email=user.email,
        timezone=user.timezone,
        is_active=user.is_active,
        joined_at=org_member.joined_at,
        org_role=org_member.role,
        stats=MemberStats(
            total_projects=total_projects,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
        ),
        projects=projects,
        recent_activity=recent_activity,
    )
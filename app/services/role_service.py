import uuid
from datetime import datetime, UTC
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization_members import OrganizationMember
from app.models.project_member import ProjectMember
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.schemas.role import OrgRoleUpdate, ProjectRoleUpdate
from app.services import notification_service


# ── Org Rol Değişikliği

async def update_org_member_role(db: AsyncSession, org_id: uuid.UUID, target_user_id: uuid.UUID, data: OrgRoleUpdate, current_user: User) -> OrganizationMember:
    """
    Yetki kuralları:
    - Yalnızca Owner rol değiştirebilir
    - Owner başka birini owner yapabilir (birden fazla owner olabilir)
    - Member rol değiştiremez → 403
    """
    current_role = await _get_current_org_role(db, org_id, current_user.id)

    if current_role != "owner":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Rol değişikliği için organizasyon sahibi olmanız gerekiyor",
        )

    # Hedef üyeyi getir
    target_member = await _get_org_member_or_404(db, org_id, target_user_id)

    if target_member.role == data.role:
        return target_member  # zaten aynı rol, işlem yapma

    old_role = target_member.role
    target_member.role = data.role

    await _log_role_change(
        db,
        org_id=org_id,
        project_id=None,
        actor_id=current_user.id,
        entity_type="org_member",
        entity_id=target_member.id,
        old_role=old_role,
        new_role=data.role,
    )

    await notification_service.create_notification(
        db,
        user_id=target_user_id,
        notification_type="role_changed",
        title="Organizasyon rolünüz güncellendi",
        body=f"Rolünüz {old_role} → {data.role} olarak değiştirildi",
        link=f"/organizations/{org_id}",
    )

    await db.commit()
    await db.refresh(target_member)
    return target_member


# ── Proje Rol Değişikliği

async def update_project_member_role(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, target_user_id: uuid.UUID, data: ProjectRoleUpdate, current_user: User) -> ProjectMember:
    """
    Yetki kuralları:
    - Org owner her rolü değiştirebilir
    - Proje manager'ı contributor/reviewer/viewer rollerini değiştirebilir
    - Manager eklemek/çıkarmak: mevcut manager veya org owner yapabilir
    - Contributor/Reviewer/Viewer rol değiştiremez → 403
    """
    # Mevcut kullanıcının org rolünü kontrol et
    current_org_role = await _get_current_org_role(db, org_id, current_user.id)
    is_org_owner = current_org_role == "owner"

    # Org owner değilse proje rolüne bak
    if not is_org_owner:
        current_project_role = await _get_current_project_role(db, project_id, current_user.id)
        if current_project_role != "manager":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Rol değişikliği için proje yöneticisi veya organizasyon sahibi olmanız gerekiyor",
            )

    # Hedef üyeyi getir
    target_member = await _get_project_member_or_404(db, project_id, target_user_id)

    if target_member.role == data.role:
        return target_member

    old_role = target_member.role
    target_member.role = data.role

    await _log_role_change(
        db,
        org_id=org_id,
        project_id=project_id,
        actor_id=current_user.id,
        entity_type="project_member",
        entity_id=target_member.id,
        old_role=old_role,
        new_role=data.role,
    )

    await notification_service.create_notification(
        db,
        user_id=target_user_id,
        notification_type="role_changed",
        title="Proje rolünüz güncellendi",
        body=f"Rolünüz {old_role} → {data.role} olarak değiştirildi",
        link=f"/organizations/{org_id}/projects/{project_id}",
    )

    await db.commit()
    await db.refresh(target_member)
    return target_member


# ── Activity Log

async def _log_role_change(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None,
    actor_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    old_role: str,
    new_role: str,
) -> None:
    log = ActivityLog(
        organization_id=org_id,
        project_id=project_id,
        actor_id=actor_id,
        action="role_changed",
        entity_type=entity_type,
        entity_id=entity_id,
        changes={"old_role": old_role, "new_role": new_role},
    )
    db.add(log)


# ── Yardımcı Fonksiyonlar

async def _get_org_member_or_404(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> OrganizationMember:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Üye bulunamadı")
    return member


async def _get_project_member_or_404(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember:
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Proje üyesi bulunamadı")
    return member


async def _get_current_org_role(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> str:
    """Mevcut kullanıcının org'daki rolünü döndürür. Üye değilse 403."""
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Bu organizasyona erişim yetkiniz yok",
        )
    return member.role


async def _get_current_project_role(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    """Mevcut kullanıcının projedeki rolünü döndürür. Üye değilse None."""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    return member.role if member else None

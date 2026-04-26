import uuid
from datetime import datetime, UTC, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.invitation import Invitation, InviteLink, DomainAllowlist
from app.models.organization import Organization
from app.models.project import Project
from app.models.user import User
from app.schemas.invitation import (
    OrgInviteCreate,
    ProjectInviteCreate,
    InviteLinkCreate,
    InviteLinkResponse,
    DomainCreate)
from app.services import notification_service
from app.config import settings


# ── Org Daveti

async def send_org_invite(db: AsyncSession, org_id: uuid.UUID, data: OrgInviteCreate, current_user: User) -> Invitation:
    org = await _get_org_or_404(db, org_id)
    await _assert_org_owner(db, org_id, current_user.id)
    await _get_user_or_404(db, data.invited_user_id)
    await _check_not_already_member_org(db, org_id, data.invited_user_id)
    await _check_no_pending_invite(db, org_id, None, data.invited_user_id)

    invitation = Invitation(
        organization_id=org_id,
        project_id=None,
        invited_by=current_user.id,
        invited_user_id=data.invited_user_id,
        role=data.role,
        status="pending",
        invite_method=org.invite_method,
    )
    db.add(invitation)
    await db.flush()

    await notification_service.create_notification(
        db,
        user_id=data.invited_user_id,
        notification_type="org_invite",
        title=f"{current_user.full_name} sizi organizasyona davet etti",
        body=f"{org.name} organizasyonuna {data.role} rolüyle davet edildiniz",
        link=f"/invites/{invitation.id}",
    )

    await db.commit()

    # commit sonrası relationship'leri yükleyerek döndür
    result = await db.execute(_invitation_query().where(Invitation.id == invitation.id))
    return result.scalar_one()


async def list_org_invites(db: AsyncSession, org_id: uuid.UUID, current_user: User) -> list[Invitation]:
    await _get_org_or_404(db, org_id)
    await _assert_org_owner(db, org_id, current_user.id)

    result = await db.execute(
        _invitation_query().where(
            Invitation.organization_id == org_id,
            Invitation.project_id.is_(None),
        ).order_by(Invitation.created_at.desc())
    )
    return list(result.scalars().all())


# ── Proje Daveti

async def send_project_invite(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, data: ProjectInviteCreate, current_user: User) -> Invitation:
    org = await _get_org_or_404(db, org_id)
    await _get_project_or_404(db, org_id, project_id)
    await _assert_project_manager_or_owner(db, org_id, project_id, current_user.id)
    await _get_user_or_404(db, data.invited_user_id)
    await _check_not_already_member_project(db, project_id, data.invited_user_id)
    await _check_no_pending_invite(db, org_id, project_id, data.invited_user_id)

    invitation = Invitation(
        organization_id=org_id,
        project_id=project_id,
        invited_by=current_user.id,
        invited_user_id=data.invited_user_id,
        role=data.role,
        status="pending",
        invite_method=org.invite_method,
    )
    db.add(invitation)
    await db.flush()

    await notification_service.create_notification(
        db,
        user_id=data.invited_user_id,
        notification_type="project_invite",
        title=f"{current_user.full_name} sizi projeye davet etti",
        body=f"Projeye {data.role} rolüyle davet edildiniz",
        link=f"/invites/{invitation.id}",
    )

    await db.commit()
    result = await db.execute(_invitation_query().where(Invitation.id == invitation.id))
    return result.scalar_one()


async def list_project_invites(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, current_user: User) -> list[Invitation]:
    await _get_org_or_404(db, org_id)
    await _get_project_or_404(db, org_id, project_id)
    await _assert_project_manager_or_owner(db, org_id, project_id, current_user.id)

    result = await db.execute(
        _invitation_query().where(
            Invitation.organization_id == org_id,
            Invitation.project_id == project_id,
        ).order_by(Invitation.created_at.desc())
    )
    return list(result.scalars().all())


# ── Kullanıcının Gelen Davetleri

async def list_incoming_invites(db: AsyncSession, current_user: User) -> list[Invitation]:
    result = await db.execute(
        _invitation_query().where(
            Invitation.invited_user_id == current_user.id,
            Invitation.status == "pending",
        ).order_by(Invitation.created_at.desc())
    )
    return list(result.scalars().all())


# ── Kabul / Red / İptal

async def _get_pending_invite_for_recipient(db: AsyncSession, invite_id: uuid.UUID, current_user: User) -> Invitation:
    result = await db.execute(
        _invitation_query().where(
            Invitation.id == invite_id,
            Invitation.invited_user_id == current_user.id,
            Invitation.status == "pending",
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Davet bulunamadı veya bu işlem için yetkiniz yok",
        )
    return invitation


async def accept_invite(db: AsyncSession, invite_id: uuid.UUID, current_user: User) -> Invitation:
    invitation = await _get_pending_invite_for_recipient(db, invite_id, current_user)

    # Org veya projeye üye ekle
    if invitation.project_id is None:
        await _add_org_member(db, invitation)
    else:
        await _add_project_member(db, invitation)

    invitation.status = "accepted"
    invitation.responded_at = datetime.now(UTC)
    await db.flush()

    # Daveti gönderene bildirim
    await notification_service.create_notification(
        db,
        user_id=invitation.invited_by,
        notification_type="invite_accepted",
        title=f"{current_user.full_name} davetinizi kabul etti",
        link=f"/organizations/{invitation.organization_id}",
    )

    await db.commit()

    result = await db.execute(_invitation_query().where(Invitation.id == invitation.id))
    return result.scalar_one()


async def decline_invite(db: AsyncSession, invite_id: uuid.UUID, current_user: User) -> Invitation:
    invitation = await _get_pending_invite_for_recipient(db, invite_id, current_user)

    # Audit trail: silme değil, status güncelle
    invitation.status = "declined"
    invitation.responded_at = datetime.now(UTC)

    await notification_service.create_notification(
        db,
        user_id=invitation.invited_by,
        notification_type="invite_declined",
        title=f"{current_user.full_name} davetinizi reddetti",
        link=f"/organizations/{invitation.organization_id}",
    )

    await db.commit()
    result = await db.execute(_invitation_query().where(Invitation.id == invitation.id))
    return result.scalar_one()


async def cancel_invite(db: AsyncSession, invite_id: uuid.UUID, current_user: User) -> None:
    """Yalnızca daveti gönderen kişi iptal edebilir."""
    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invite_id,
            Invitation.invited_by == current_user.id,
            Invitation.status == "pending",
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Davet bulunamadı veya bu işlem için yetkiniz yok",
        )

    await db.delete(invitation)
    await db.commit()


# ── Üye Ekleme (accept sonrası)

async def _add_org_member(db: AsyncSession, invitation: Invitation) -> None:
    from app.models.organization_members import OrganizationMember  # noqa: circular-safe

    # Tekrar üye kontrolü (race condition için)
    existing = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == invitation.organization_id,
            OrganizationMember.user_id == invitation.invited_user_id,
        )
    )
    if existing.scalar_one_or_none():
        return

    member = OrganizationMember(
        organization_id=invitation.organization_id,
        user_id=invitation.invited_user_id,
        role=invitation.role,
    )
    db.add(member)
    await db.flush()


async def _add_project_member(db: AsyncSession, invitation: Invitation) -> None:
    from app.models.project_member import ProjectMember  # noqa: circular-safe

    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == invitation.project_id,
            ProjectMember.user_id == invitation.invited_user_id,
        )
    )
    if existing.scalar_one_or_none():
        return

    member = ProjectMember(
        project_id=invitation.project_id,
        organization_id=invitation.organization_id,
        user_id=invitation.invited_user_id,
        role=invitation.role,
    )
    db.add(member)
    await db.flush()


# ── Invite Link

async def create_invite_link(db: AsyncSession, org_id: uuid.UUID, data: InviteLinkCreate, current_user: User) -> InviteLinkResponse:
    await _get_org_or_404(db, org_id)
    await _assert_org_owner(db, org_id, current_user.id)

    link = InviteLink(
        organization_id=org_id,
        created_by=current_user.id,
        role=data.role,
        expires_at=datetime.now(UTC) + timedelta(hours=data.expires_in_hours),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _link_to_response(link)


async def list_invite_links(db: AsyncSession, org_id: uuid.UUID, current_user: User) -> list[InviteLinkResponse]:
    await _get_org_or_404(db, org_id)
    await _assert_org_owner(db, org_id, current_user.id)

    result = await db.execute(
        select(InviteLink).where(
            InviteLink.organization_id == org_id,
            InviteLink.is_active.is_(True),
        ).order_by(InviteLink.created_at.desc())
    )
    return [_link_to_response(link) for link in result.scalars().all()]


async def delete_invite_link(db: AsyncSession, org_id: uuid.UUID, link_id: uuid.UUID, current_user: User) -> None:
    await _get_org_or_404(db, org_id)
    await _assert_org_owner(db, org_id, current_user.id)

    result = await db.execute(
        select(InviteLink).where(
            InviteLink.id == link_id,
            InviteLink.organization_id == org_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Link bulunamadı")

    await db.delete(link)
    await db.commit()


async def join_via_token(db: AsyncSession, token: str, current_user: User) -> None:
    """Token ile org'a katılım. Süresi dolmuşsa 410, geçersizse 404."""
    result = await db.execute(
        select(InviteLink).where(
            InviteLink.token == token,
            InviteLink.is_active.is_(True),
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Token bulunamadı veya geçersiz")

    if link.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_410_GONE, detail="Bu token'ın süresi dolmuş")

    # Zaten üye mi?
    await _check_not_already_member_org(db, link.organization_id, current_user.id)

    from app.models.organization_members import OrganizationMember  # noqa: circular-safe

    member = OrganizationMember(
        organization_id=link.organization_id,
        user_id=current_user.id,
        role=link.role,
    )
    db.add(member)
    await db.commit()


# ── Domain Allowlist

async def add_domain(db: AsyncSession, org_id: uuid.UUID, data: DomainCreate, current_user: User) -> DomainAllowlist:
    await _get_org_or_404(db, org_id)
    await _assert_org_owner(db, org_id, current_user.id)

    # Duplicate domain kontrolü
    existing = await db.execute(
        select(DomainAllowlist).where(
            DomainAllowlist.organization_id == org_id,
            DomainAllowlist.domain == data.domain,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Bu domain zaten eklenmiş")

    domain_entry = DomainAllowlist(
        organization_id=org_id,
        domain=data.domain,
        auto_role=data.auto_role,
        created_by=current_user.id,
    )
    db.add(domain_entry)
    await db.commit()
    await db.refresh(domain_entry)
    return domain_entry


async def list_domains(db: AsyncSession, org_id: uuid.UUID, current_user: User) -> list[DomainAllowlist]:
    await _get_org_or_404(db, org_id)
    await _assert_org_owner(db, org_id, current_user.id)

    result = await db.execute(
        select(DomainAllowlist).where(
            DomainAllowlist.organization_id == org_id
        ).order_by(DomainAllowlist.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_domain(db: AsyncSession, org_id: uuid.UUID, domain_id: uuid.UUID, current_user: User) -> None:
    await _get_org_or_404(db, org_id)
    await _assert_org_owner(db, org_id, current_user.id)

    result = await db.execute(
        select(DomainAllowlist).where(
            DomainAllowlist.id == domain_id,
            DomainAllowlist.organization_id == org_id,
        )
    )
    domain_entry = result.scalar_one_or_none()
    if not domain_entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Domain bulunamadı")

    await db.delete(domain_entry)
    await db.commit()


async def check_domain_and_auto_join(db: AsyncSession, user: User) -> None:
    """
    Yeni kullanıcı kaydında çağrılır.
    Kullanıcının email domain'i herhangi bir org'un allowlist'indeyse otomatik üye yapar.
    """
    from app.models.organization_members import OrganizationMember  # noqa: circular-safe

    user_domain = user.email.split("@")[-1].lower()

    result = await db.execute(
        select(DomainAllowlist).where(DomainAllowlist.domain == user_domain)
    )
    matches = result.scalars().all()

    for entry in matches:
        # Zaten üye mi?
        existing = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == entry.organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        member = OrganizationMember(
            organization_id=entry.organization_id,
            user_id=user.id,
            role=entry.auto_role,
        )
        db.add(member)

    if matches:
        await db.commit()



# ── Yardımcı fonksiyonlar

def _invitation_query():
    """
    Invitation select'ine her zaman invited_user ve inviter'ı yükler.
    lazy="raise" olduğu için selectinload olmadan erişim hata fırlatır.
    """
    return select(Invitation).options(
        selectinload(Invitation.invited_user),
        selectinload(Invitation.inviter),
    )


def _link_to_response(link: InviteLink) -> InviteLinkResponse:
    return InviteLinkResponse(
        id=link.id,
        organization_id=link.organization_id,
        token=link.token,
        join_url=f"{settings.BASE_URL}/join?token={link.token}",
        role=link.role,
        expires_at=link.expires_at,
        is_active=link.is_active,
        created_at=link.created_at,
    )


async def _get_org_or_404(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Organizasyon bulunamadı")
    return org


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
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Proje bulunamadı")
    return project


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı platformda kayıtlı değil",
        )
    return user


async def _assert_org_owner(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Kullanıcının org owner'ı olup olmadığını kontrol eder."""
    from app.models.organization_members import OrganizationMember  # noqa: circular-safe
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.role == "owner",
            OrganizationMember.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için organizasyon sahibi olmanız gerekiyor",
        )


async def _assert_project_manager_or_owner(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Kullanıcının proje manager veya org owner olup olmadığını kontrol eder."""
    from app.models.project_member import ProjectMember  # noqa: circular-safe
    from app.models.organization_members import OrganizationMember  # noqa: circular-safe

    # Önce org owner mı?
    org_result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.role == "owner",
            OrganizationMember.deleted_at.is_(None),
        )
    )
    if org_result.scalar_one_or_none():
        return

    # Proje manager mı?
    proj_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role == "manager",
            ProjectMember.deleted_at.is_(None),
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için proje yöneticisi veya organizasyon sahibi olmanız gerekiyor",
        )


async def _check_no_pending_invite(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID | None, invited_user_id: uuid.UUID) -> None:
    """Zaten pending davet varsa 409 fırlatır."""
    result = await db.execute(
        select(Invitation).where(
            Invitation.organization_id == org_id,
            Invitation.project_id == project_id,
            Invitation.invited_user_id == invited_user_id,
            Invitation.status == "pending",
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Bu kullanıcıya zaten bekleyen bir davet gönderilmiş",
        )


async def _check_not_already_member_org(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from app.models.organization_members import OrganizationMember  # noqa: circular-safe

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Kullanıcı zaten bu organizasyonun üyesi",
        )


async def _check_not_already_member_project(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from app.models.project_member import ProjectMember  # noqa: circular-safe

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Kullanıcı zaten bu projenin üyesi",
        )
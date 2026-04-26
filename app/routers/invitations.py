import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.invitation import (
    OrgInviteCreate,
    ProjectInviteCreate,
    InvitationResponse,
    InviteLinkCreate,
    InviteLinkResponse,
    InviteLinkJoin,
    DomainCreate,
    DomainResponse,
)
from app.services import invitation_service

# ── /api/v1/invites — kullanıcı bazlı işlemler
router = APIRouter(prefix="/api/v1/invites", tags=["invitations"])


@router.get("/incoming", response_model=list[InvitationResponse])
async def get_incoming_invites(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Oturum açmış kullanıcının bekleyen davetlerini listeler."""
    return await invitation_service.list_incoming_invites(db, current_user)


@router.patch("/{invite_id}/accept", response_model=InvitationResponse)
async def accept_invite(invite_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Daveti kabul et; kullanıcı org/projeye belirlenen rol ile eklenir."""
    return await invitation_service.accept_invite(db, invite_id, current_user)


@router.patch("/{invite_id}/decline", response_model=InvitationResponse)
async def decline_invite(invite_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Daveti reddet; kayıt audit trail için tutulur."""
    return await invitation_service.decline_invite(db, invite_id, current_user)


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite(invite_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Daveti iptal et (yalnızca daveti gönderen kişi yapabilir)."""
    await invitation_service.cancel_invite(db, invite_id, current_user)


# ── /api/v1/invites/link — invite link ile katılım (public)
@router.post("/link/join", status_code=status.HTTP_200_OK)
async def join_via_token(data: InviteLinkJoin, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Token ile org'a katıl. Token geçersiz veya süresi dolmuşsa hata döner."""
    await invitation_service.join_via_token(db, data.token, current_user)
    return {"detail": "Organizasyona başarıyla katıldınız"}


# ── /api/v1/organizations/{org_id}/invites
org_invite_router = APIRouter(prefix="/api/v1/organizations/{org_id}", tags=["invitations"])

@org_invite_router.post("/invites", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def send_org_invite(org_id: uuid.UUID, data: OrgInviteCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Org'a üyelik daveti gönder. Yalnızca Owner."""
    return await invitation_service.send_org_invite(db, org_id, data, current_user)


@org_invite_router.get("/invites", response_model=list[InvitationResponse])
async def list_org_invites(org_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Org'un gönderdiği davetleri listele. Yalnızca Owner."""
    return await invitation_service.list_org_invites(db, org_id, current_user)


# ── Invite Link

@org_invite_router.post("/invites/link", response_model=InviteLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_invite_link(org_id: uuid.UUID, data: InviteLinkCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Yeni invite link üret. Yalnızca Owner."""
    return await invitation_service.create_invite_link(db, org_id, data, current_user)


@org_invite_router.get("/invites/link", response_model=list[InviteLinkResponse])
async def list_invite_links(org_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Aktif invite linkleri listele. Yalnızca Owner."""
    return await invitation_service.list_invite_links(db, org_id, current_user)


@org_invite_router.delete("/invites/link/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invite_link(org_id: uuid.UUID, link_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Invite linki sil/deaktif et. Yalnızca Owner."""
    await invitation_service.delete_invite_link(db, org_id, link_id, current_user)


# ── Domain Allowlist

@org_invite_router.post("/invites/domain", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def add_domain(org_id: uuid.UUID, data: DomainCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Domain allowlist'e domain ekle. Yalnızca Owner."""
    return await invitation_service.add_domain(db, org_id, data, current_user)


@org_invite_router.get("/invites/domain", response_model=list[DomainResponse])
async def list_domains(org_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Domain listesini getir. Yalnızca Owner."""
    return await invitation_service.list_domains(db, org_id, current_user)


@org_invite_router.delete("/invites/domain/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(org_id: uuid.UUID, domain_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Domain sil. Yalnızca Owner."""
    await invitation_service.delete_domain(db, org_id, domain_id, current_user)


# ── /api/v1/organizations/{org_id}/projects/{project_id}/invites
project_invite_router = APIRouter(prefix="/api/v1/organizations/{org_id}/projects/{project_id}", tags=["invitations"])

@project_invite_router.post("/invites", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def send_project_invite(org_id: uuid.UUID, project_id: uuid.UUID, data: ProjectInviteCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Projeye üyelik daveti gönder. Owner veya Manager."""
    return await invitation_service.send_project_invite(
        db, org_id, project_id, data, current_user
    )


@project_invite_router.get("/invites", response_model=list[InvitationResponse])
async def list_project_invites(org_id: uuid.UUID, project_id: uuid.UUID, current_user: User = Depends(get_current_user),db: AsyncSession = Depends(get_db)):
    """Projenin gönderdiği davetleri listele. Owner veya Manager."""
    return await invitation_service.list_project_invites(
        db, org_id, project_id, current_user
    )
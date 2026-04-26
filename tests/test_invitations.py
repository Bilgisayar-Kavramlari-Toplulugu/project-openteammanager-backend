"""
Üye Davet Sistemi — pytest test suite
"""

import uuid
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.models.invitation import Invitation, InviteLink, DomainAllowlist
from app.schemas.invitation import (
    OrgInviteCreate,
    ProjectInviteCreate,
    InviteLinkCreate,
    DomainCreate,
)
from app.services import invitation_service


# ── Mock yardımcıları ─────────────────────────────────────────────────────────
#
# SORUN: db.execute() bir AsyncMock olduğunda, döndürdüğü nesnenin
# tüm metodları da AsyncMock olur. Yani result.scalar_one_or_none() bir
# coroutine döndürür — ama service'de await edilmez, direkt kullanılır → hata.
#
# ÇÖZÜM: execute() sonucunu MagicMock ile oluştur, metodlarını da
# MagicMock olarak ayarla. Sadece db.execute'un kendisi AsyncMock olmalı.


def make_execute_result(scalar_value=None, scalars_list=None):
    """
    db.execute() → result nesnesi mock'u.
    scalar_one_or_none() ve scalar_one() → senkron MagicMock metodu (await edilmez)
    scalars().all()                       → senkron liste döner
    """
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_value
    result.scalar_one.return_value = scalar_value

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_list if scalars_list is not None else (
        [scalar_value] if scalar_value is not None else []
    )
    result.scalars.return_value = scalars_mock

    return result


def make_db(*execute_returns):
    """
    db mock'u. execute_returns sırayla döner.
    Her eleman make_execute_result(...) ile oluşturulmuş olmalı.
    """
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()

    if len(execute_returns) == 1:
        db.execute = AsyncMock(return_value=execute_returns[0])
    else:
        db.execute = AsyncMock(side_effect=list(execute_returns))

    return db


def make_user(tag: str = "user") -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.username = tag
    u.full_name = f"Test {tag.title()}"
    u.email = f"{tag}@example.com"
    u.avatar_url = None
    u.deleted_at = None
    return u


def make_org(invite_method: str = "email") -> MagicMock:
    o = MagicMock()
    o.id = uuid.uuid4()
    o.name = "Test Org"
    o.invite_method = invite_method
    o.deleted_at = None
    return o


def make_project(org_id: uuid.UUID) -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.organization_id = org_id
    p.deleted_at = None
    return p


def make_invitation(
    org_id: uuid.UUID,
    invited_by: uuid.UUID,
    invited_user_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    role: str = "member",
    status: str = "pending",
) -> MagicMock:
    inv = MagicMock(spec=Invitation)
    inv.id = uuid.uuid4()
    inv.organization_id = org_id
    inv.project_id = project_id
    inv.invited_by = invited_by
    inv.invited_user_id = invited_user_id
    inv.role = role
    inv.status = status
    inv.invite_method = "email"
    inv.created_at = datetime.now(UTC)
    inv.responded_at = None
    return inv


def make_invite_link(org_id: uuid.UUID, expired: bool = False) -> MagicMock:
    link = MagicMock(spec=InviteLink)
    link.id = uuid.uuid4()
    link.organization_id = org_id
    link.token = "test_token_abc123"
    link.role = "member"
    link.is_active = True
    link.expires_at = (
        datetime.now(UTC) - timedelta(hours=1)
        if expired
        else datetime.now(UTC) + timedelta(hours=72)
    )
    link.created_at = datetime.now(UTC)
    return link


# kısaltmalar
def r(val=None):
    """Tek scalar dönen execute sonucu."""
    return make_execute_result(scalar_value=val)


def rl(lst):
    """Liste dönen execute sonucu."""
    return make_execute_result(scalars_list=lst)


# ── Schema validasyon testleri ────────────────────────────────────────────────

class TestSchemaValidation:

    def test_org_invite_valid_roles(self):
        for role in ("owner", "member"):
            s = OrgInviteCreate(invited_user_id=uuid.uuid4(), role=role)
            assert s.role == role

    def test_org_invite_invalid_role_raises(self):
        with pytest.raises(Exception):
            OrgInviteCreate(invited_user_id=uuid.uuid4(), role="manager")

    def test_project_invite_valid_roles(self):
        for role in ("manager", "contributor", "reviewer", "viewer"):
            s = ProjectInviteCreate(invited_user_id=uuid.uuid4(), role=role)
            assert s.role == role

    def test_project_invite_invalid_role_raises(self):
        with pytest.raises(Exception):
            ProjectInviteCreate(invited_user_id=uuid.uuid4(), role="owner")

    def test_invite_link_valid_expiry(self):
        s = InviteLinkCreate(expires_in_hours=48)
        assert s.expires_in_hours == 48

    def test_invite_link_expiry_too_low_raises(self):
        with pytest.raises(Exception):
            InviteLinkCreate(expires_in_hours=0)

    def test_invite_link_expiry_too_high_raises(self):
        with pytest.raises(Exception):
            InviteLinkCreate(expires_in_hours=721)

    def test_domain_strips_and_lowercases(self):
        s = DomainCreate(domain="  Company.COM  ")
        assert s.domain == "company.com"

    def test_domain_without_dot_raises(self):
        with pytest.raises(Exception):
            DomainCreate(domain="nodot")

    def test_domain_with_at_raises(self):
        with pytest.raises(Exception):
            DomainCreate(domain="user@company.com")


# ── send_org_invite ───────────────────────────────────────────────────────────
#
# Gerçek çağrı sırası (her biri bir db.execute):
#   1. _get_org_or_404          → org
#   2. _assert_org_owner        → OrganizationMember (owner kaydı)
#   3. _get_user_or_404         → User
#   4. _check_not_org_member    → OrganizationMember (üyelik kontrolü)
#   5. _check_no_pending_invite → Invitation
#   6. commit sonrası _invitation_query → Invitation (response için)

class TestSendOrgInvite:

    @pytest.mark.asyncio
    async def test_success(self):
        owner = make_user("owner")
        invited = make_user("member")
        org = make_org()
        inv = make_invitation(org.id, owner.id, invited.id)

        db = make_db(
            r(org),          # 1. _get_org_or_404
            r(MagicMock()),  # 2. _assert_org_owner → owner var
            r(invited),      # 3. _get_user_or_404
            r(None),         # 4. _check_not_org_member → üye değil
            r(None),         # 5. _check_no_pending_invite → pending yok
            r(inv),          # 6. commit sonrası sorgu
        )

        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            result = await invitation_service.send_org_invite(
                db, org.id,
                OrgInviteCreate(invited_user_id=invited.id, role="member"),
                owner,
            )

        assert result.status == "pending"
        assert result.role == "member"
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_org_not_found_raises_404(self):
        db = make_db(r(None))  # org yok

        with pytest.raises(HTTPException) as exc:
            await invitation_service.send_org_invite(
                db, uuid.uuid4(),
                OrgInviteCreate(invited_user_id=uuid.uuid4()),
                make_user(),
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_non_owner_raises_403(self):
        org = make_org()
        db = make_db(
            r(org),   # 1. org bulundu
            r(None),  # 2. owner kaydı yok → 403
        )

        with pytest.raises(HTTPException) as exc:
            await invitation_service.send_org_invite(
                db, org.id,
                OrgInviteCreate(invited_user_id=uuid.uuid4()),
                make_user("member"),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_unregistered_user_raises_404(self):
        org = make_org()
        db = make_db(
            r(org),          # 1. org bulundu
            r(MagicMock()),  # 2. owner var
            r(None),         # 3. user bulunamadı → 404
        )

        with pytest.raises(HTTPException) as exc:
            await invitation_service.send_org_invite(
                db, org.id,
                OrgInviteCreate(invited_user_id=uuid.uuid4()),
                make_user(),
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_already_member_raises_409(self):
        org = make_org()
        invited = make_user("member")
        db = make_db(
            r(org),          # 1. org
            r(MagicMock()),  # 2. owner var
            r(invited),      # 3. user bulundu
            r(MagicMock()),  # 4. zaten üye → 409
        )

        with pytest.raises(HTTPException) as exc:
            await invitation_service.send_org_invite(
                db, org.id,
                OrgInviteCreate(invited_user_id=invited.id),
                make_user(),
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_pending_invite_exists_raises_409(self):
        org = make_org()
        invited = make_user("member")
        db = make_db(
            r(org),          # 1. org
            r(MagicMock()),  # 2. owner var
            r(invited),      # 3. user bulundu
            r(None),         # 4. üye değil
            r(MagicMock()),  # 5. pending davet var → 409
        )

        with pytest.raises(HTTPException) as exc:
            await invitation_service.send_org_invite(
                db, org.id,
                OrgInviteCreate(invited_user_id=invited.id),
                make_user(),
            )
        assert exc.value.status_code == 409


# ── accept_invite ─────────────────────────────────────────────────────────────
#
# Gerçek çağrı sırası:
#   1. _get_pending_invite_for_recipient → Invitation
#   2. _add_org_member: üyelik kontrolü  → None (üye değil)
#   3. commit sonrası _invitation_query  → Invitation

class TestAcceptInvite:

    @pytest.mark.asyncio
    async def test_accept_org_invite_adds_member(self):
        owner = make_user("owner")
        current = make_user("member")
        org = make_org()
        inv = make_invitation(org.id, owner.id, current.id)
        # project_id=None olduğunu açıkça belirt
        inv.project_id = None

        db = make_db(
            r(inv),   # 1. pending davet bulundu
            r(None),  # 2. _add_org_member → zaten üye değil
            r(inv),   # 3. commit sonrası sorgu
        )

        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            result = await invitation_service.accept_invite(db, inv.id, current)

        assert result.status == "accepted"
        assert result.responded_at is not None
        db.add.assert_called_once()  # OrganizationMember eklendi

    @pytest.mark.asyncio
    async def test_accept_nonexistent_invite_raises_404(self):
        db = make_db(r(None))  # davet yok

        with pytest.raises(HTTPException) as exc:
            await invitation_service.accept_invite(db, uuid.uuid4(), make_user())
        assert exc.value.status_code == 404


# ── decline_invite ────────────────────────────────────────────────────────────
#
# Gerçek çağrı sırası:
#   1. _get_pending_invite_for_recipient → Invitation
#   2. commit sonrası _invitation_query  → Invitation

class TestDeclineInvite:

    @pytest.mark.asyncio
    async def test_decline_keeps_record_and_sets_status(self):
        owner = make_user("owner")
        current = make_user("member")
        org = make_org()
        inv = make_invitation(org.id, owner.id, current.id)

        db = make_db(
            r(inv),  # 1. pending davet bulundu
            r(inv),  # 2. commit sonrası sorgu
        )

        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            result = await invitation_service.decline_invite(db, inv.id, current)

        assert result.status == "declined"
        assert result.responded_at is not None
        db.delete.assert_not_awaited()  # audit trail: silinmemeli

    @pytest.mark.asyncio
    async def test_decline_wrong_user_raises_404(self):
        db = make_db(r(None))  # davet yok

        with pytest.raises(HTTPException) as exc:
            await invitation_service.decline_invite(db, uuid.uuid4(), make_user())
        assert exc.value.status_code == 404


# ── cancel_invite ─────────────────────────────────────────────────────────────
#
# Gerçek çağrı sırası:
#   1. db.execute → Invitation (invited_by == current_user kontrolü)

class TestCancelInvite:

    @pytest.mark.asyncio
    async def test_cancel_by_sender_deletes(self):
        owner = make_user("owner")
        inv = make_invitation(uuid.uuid4(), owner.id, uuid.uuid4())

        db = make_db(r(inv))  # davet bulundu

        await invitation_service.cancel_invite(db, inv.id, owner)

        db.delete.assert_awaited_once_with(inv)
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancel_by_non_sender_raises_404(self):
        db = make_db(r(None))  # davet bulunamadı

        with pytest.raises(HTTPException) as exc:
            await invitation_service.cancel_invite(db, uuid.uuid4(), make_user())
        assert exc.value.status_code == 404


# ── join_via_token ────────────────────────────────────────────────────────────
#
# Gerçek çağrı sırası:
#   1. InviteLink sorgusu      → InviteLink
#   2. _check_not_org_member   → None (üye değil)

class TestJoinViaToken:

    @pytest.mark.asyncio
    async def test_valid_token_adds_member(self):
        org = make_org()
        link = make_invite_link(org.id)

        db = make_db(
            r(link),  # 1. token bulundu
            r(None),  # 2. zaten üye değil
        )

        await invitation_service.join_via_token(db, link.token, make_user())

        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_token_raises_404(self):
        db = make_db(r(None))  # token yok

        with pytest.raises(HTTPException) as exc:
            await invitation_service.join_via_token(db, "gecersiz_token", make_user())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_expired_token_raises_410(self):
        org = make_org()
        link = make_invite_link(org.id, expired=True)

        db = make_db(r(link))  # token bulundu ama süresi dolmuş

        with pytest.raises(HTTPException) as exc:
            await invitation_service.join_via_token(db, link.token, make_user())
        assert exc.value.status_code == 410

    @pytest.mark.asyncio
    async def test_already_member_raises_409(self):
        org = make_org()
        link = make_invite_link(org.id)

        db = make_db(
            r(link),         # 1. token bulundu
            r(MagicMock()),  # 2. zaten üye → 409
        )

        with pytest.raises(HTTPException) as exc:
            await invitation_service.join_via_token(db, link.token, make_user())
        assert exc.value.status_code == 409


# ── InviteLink CRUD ───────────────────────────────────────────────────────────
#
# create_invite_link çağrı sırası:
#   1. _get_org_or_404     → org
#   2. _assert_org_owner   → OrganizationMember
#
# delete_invite_link çağrı sırası:
#   1. _get_org_or_404     → org
#   2. _assert_org_owner   → OrganizationMember
#   3. InviteLink sorgusu  → InviteLink

class TestInviteLink:

    @pytest.mark.asyncio
    async def test_non_owner_cannot_create_link(self):
        org = make_org()
        db = make_db(
            r(org),   # 1. org bulundu
            r(None),  # 2. owner yok → 403
        )

        with pytest.raises(HTTPException) as exc:
            await invitation_service.create_invite_link(
                db, org.id, InviteLinkCreate(), make_user("member")
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_link_success(self):
        org = make_org()
        owner = make_user("owner")
        link = make_invite_link(org.id)

        db = make_db(
            r(org),          # 1. org bulundu
            r(MagicMock()),  # 2. owner var
        )

        # db.add ile eklenen nesneye token atıyoruz
        def fake_add(obj):
            obj.id = link.id
            obj.token = link.token
            obj.organization_id = org.id
            obj.role = "member"
            obj.expires_at = link.expires_at
            obj.is_active = True
            obj.created_at = link.created_at

        db.add = fake_add

        with patch("app.services.invitation_service.settings") as mock_settings:
            mock_settings.BASE_URL = "https://app.example.com"
            result = await invitation_service.create_invite_link(
                db, org.id, InviteLinkCreate(role="member", expires_in_hours=72), owner
            )

        assert result.token == link.token
        assert "https://app.example.com" in result.join_url
        assert link.token in result.join_url

    @pytest.mark.asyncio
    async def test_delete_nonexistent_link_raises_404(self):
        org = make_org()
        db = make_db(
            r(org),          # 1. org bulundu
            r(MagicMock()),  # 2. owner var
            r(None),         # 3. link yok → 404
        )

        with pytest.raises(HTTPException) as exc:
            await invitation_service.delete_invite_link(
                db, org.id, uuid.uuid4(), make_user()
            )
        assert exc.value.status_code == 404


# ── Domain Allowlist ──────────────────────────────────────────────────────────
#
# add_domain çağrı sırası:
#   1. _get_org_or_404     → org
#   2. _assert_org_owner   → OrganizationMember
#   3. duplicate kontrol   → None (yok)
#
# check_domain_and_auto_join çağrı sırası:
#   1. DomainAllowlist sorgusu     → [entry] veya []
#   2. (her eşleşme için) üyelik kontrolü → None

class TestDomainAllowlist:

    @pytest.mark.asyncio
    async def test_add_domain_success(self):
        org = make_org()
        owner = make_user("owner")

        db = make_db(
            r(org),          # 1. org bulundu
            r(MagicMock()),  # 2. owner var
            r(None),         # 3. domain yok
        )

        async def fake_refresh(obj):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(UTC)

        db.refresh = fake_refresh

        result = await invitation_service.add_domain(
            db, org.id, DomainCreate(domain="company.com"), owner
        )

        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_domain_raises_409(self):
        org = make_org()
        db = make_db(
            r(org),          # 1. org bulundu
            r(MagicMock()),  # 2. owner var
            r(MagicMock()),  # 3. domain zaten var → 409
        )

        with pytest.raises(HTTPException) as exc:
            await invitation_service.add_domain(
                db, org.id, DomainCreate(domain="company.com"), make_user()
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_check_domain_auto_join_adds_member(self):
        user = make_user()
        user.email = "ali@company.com"

        entry = MagicMock()
        entry.organization_id = uuid.uuid4()
        entry.auto_role = "member"

        db = make_db(
            rl([entry]),  # 1. domain eşleşti
            r(None),      # 2. zaten üye değil
        )

        await invitation_service.check_domain_and_auto_join(db, user)

        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_domain_no_match_does_nothing(self):
        user = make_user()
        user.email = "ali@unknown.com"

        db = make_db(rl([]))  # eşleşen domain yok

        await invitation_service.check_domain_and_auto_join(db, user)

        db.add.assert_not_called()
        db.commit.assert_not_awaited()
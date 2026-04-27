"""
BE-12 Rol Yönetimi — pytest test suite

Çalıştırmak için:
    pytest tests/test_role_service.py -v
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.schemas.role import OrgRoleUpdate, ProjectRoleUpdate
from app.services import role_service


# ── Mock yardımcıları

def make_execute_result(scalar_value=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_value
    result.scalar_one.return_value = scalar_value
    return result


def make_db(*execute_returns):
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    if len(execute_returns) == 1:
        db.execute = AsyncMock(return_value=execute_returns[0])
    else:
        db.execute = AsyncMock(side_effect=list(execute_returns))
    return db


def r(val=None):
    return make_execute_result(scalar_value=val)


def make_user(tag: str = "user") -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.full_name = f"Test {tag.title()}"
    u.email = f"{tag}@example.com"
    return u


def make_org_member(user_id: uuid.UUID, org_id: uuid.UUID, role: str) -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.user_id = user_id
    m.organization_id = org_id
    m.role = role
    m.deleted_at = None
    return m


def make_project_member(user_id: uuid.UUID, project_id: uuid.UUID, role: str) -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.user_id = user_id
    m.project_id = project_id
    m.role = role
    m.deleted_at = None
    return m


# ── Schema validasyon

class TestSchemaValidation:

    def test_org_role_valid(self):
        for role in ("owner", "member"):
            s = OrgRoleUpdate(role=role)
            assert s.role == role

    def test_org_role_invalid_raises(self):
        with pytest.raises(Exception):
            OrgRoleUpdate(role="manager")

    def test_project_role_valid(self):
        for role in ("manager", "contributor", "reviewer", "viewer"):
            s = ProjectRoleUpdate(role=role)
            assert s.role == role

    def test_project_role_invalid_raises(self):
        with pytest.raises(Exception):
            ProjectRoleUpdate(role="owner")


# ── update_org_member_role

# Gerçek çağrı sırası:
#   1. _get_current_org_role  → OrganizationMember (current_user)
#   2. _get_org_member_or_404 → OrganizationMember (target_user)

class TestUpdateOrgMemberRole:

    @pytest.mark.asyncio
    async def test_owner_can_change_member_to_owner(self):
        owner = make_user("owner")
        target = make_user("member")
        org_id = uuid.uuid4()

        current_member = make_org_member(owner.id, org_id, "owner")
        target_member = make_org_member(target.id, org_id, "member")

        db = make_db(
            r(current_member),  # 1. current_user'ın rolü → owner
            r(target_member),   # 2. target üye bulundu
        )

        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            result = await role_service.update_org_member_role(
                db, org_id, target.id, OrgRoleUpdate(role="owner"), owner
            )

        assert result.role == "owner"
        db.add.assert_called_once()   # activity log eklendi
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_owner_can_change_owner_to_member(self):
        owner = make_user("owner")
        target = make_user("owner2")
        org_id = uuid.uuid4()

        current_member = make_org_member(owner.id, org_id, "owner")
        target_member = make_org_member(target.id, org_id, "owner")

        db = make_db(
            r(current_member),
            r(target_member),
        )

        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            result = await role_service.update_org_member_role(
                db, org_id, target.id, OrgRoleUpdate(role="member"), owner
            )

        assert result.role == "member"

    @pytest.mark.asyncio
    async def test_member_cannot_change_role_raises_403(self):
        member = make_user("member")
        target = make_user("other")
        org_id = uuid.uuid4()

        current_member = make_org_member(member.id, org_id, "member")

        db = make_db(r(current_member))  # 1. current_user'ın rolü → member

        with pytest.raises(HTTPException) as exc:
            await role_service.update_org_member_role(
                db, org_id, target.id, OrgRoleUpdate(role="owner"), member
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_non_member_raises_403(self):
        user = make_user()
        org_id = uuid.uuid4()

        db = make_db(r(None))  # current_user org üyesi değil → 403

        with pytest.raises(HTTPException) as exc:
            await role_service.update_org_member_role(
                db, org_id, uuid.uuid4(), OrgRoleUpdate(role="member"), user
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_target_not_member_raises_404(self):
        owner = make_user("owner")
        org_id = uuid.uuid4()

        current_member = make_org_member(owner.id, org_id, "owner")

        db = make_db(
            r(current_member),  # 1. current_user → owner
            r(None),            # 2. target üye yok → 404
        )

        with pytest.raises(HTTPException) as exc:
            await role_service.update_org_member_role(
                db, org_id, uuid.uuid4(), OrgRoleUpdate(role="member"), owner
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_same_role_no_commit(self):
        """Aynı rol atanırsa commit yapılmamalı."""
        owner = make_user("owner")
        target = make_user("member")
        org_id = uuid.uuid4()

        current_member = make_org_member(owner.id, org_id, "owner")
        target_member = make_org_member(target.id, org_id, "member")

        db = make_db(
            r(current_member),
            r(target_member),
        )

        result = await role_service.update_org_member_role(
            db, org_id, target.id, OrgRoleUpdate(role="member"), owner
        )

        assert result.role == "member"
        db.commit.assert_not_awaited()  # aynı rol, commit yapılmamalı


# ── update_project_member_role

# Gerçek çağrı sırası:
#   1. _get_current_org_role     → OrganizationMember (current_user)
#   2. _get_current_project_role → ProjectMember (current_user) — org owner değilse
#   3. _get_project_member_or_404 → ProjectMember (target_user)

class TestUpdateProjectMemberRole:

    @pytest.mark.asyncio
    async def test_org_owner_can_change_any_role(self):
        owner = make_user("owner")
        target = make_user("contributor")
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()

        current_org_member = make_org_member(owner.id, org_id, "owner")
        target_member = make_project_member(target.id, project_id, "contributor")

        # Org owner olduğu için proje rolü sorgulanmaz
        db = make_db(
            r(current_org_member),  # 1. current_user org rolü → owner
            r(target_member),       # 2. target proje üyesi
        )

        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            result = await role_service.update_project_member_role(
                db, org_id, project_id, target.id, ProjectRoleUpdate(role="manager"), owner
            )

        assert result.role == "manager"
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_project_manager_can_change_contributor_role(self):
        manager = make_user("manager")
        target = make_user("contributor")
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()

        current_org_member = make_org_member(manager.id, org_id, "member")
        current_proj_member = make_project_member(manager.id, project_id, "manager")
        target_member = make_project_member(target.id, project_id, "contributor")

        db = make_db(
            r(current_org_member),   # 1. current_user org rolü → member (owner değil)
            r(current_proj_member),  # 2. current_user proje rolü → manager
            r(target_member),        # 3. target proje üyesi
        )

        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            result = await role_service.update_project_member_role(
                db, org_id, project_id, target.id, ProjectRoleUpdate(role="reviewer"), manager
            )

        assert result.role == "reviewer"

    @pytest.mark.asyncio
    async def test_project_manager_can_promote_to_manager(self):
        """Manager başka birini manager yapabilir."""
        manager = make_user("manager")
        target = make_user("contributor")
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()

        current_org_member = make_org_member(manager.id, org_id, "member")
        current_proj_member = make_project_member(manager.id, project_id, "manager")
        target_member = make_project_member(target.id, project_id, "contributor")

        db = make_db(
            r(current_org_member),
            r(current_proj_member),
            r(target_member),
        )

        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            result = await role_service.update_project_member_role(
                db, org_id, project_id, target.id, ProjectRoleUpdate(role="manager"), manager
            )

        assert result.role == "manager"

    @pytest.mark.asyncio
    async def test_contributor_cannot_change_role_raises_403(self):
        contributor = make_user("contributor")
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()

        current_org_member = make_org_member(contributor.id, org_id, "member")
        current_proj_member = make_project_member(contributor.id, project_id, "contributor")

        db = make_db(
            r(current_org_member),   # 1. org rolü → member
            r(current_proj_member),  # 2. proje rolü → contributor → 403
        )

        with pytest.raises(HTTPException) as exc:
            await role_service.update_project_member_role(
                db, org_id, project_id, uuid.uuid4(),
                ProjectRoleUpdate(role="viewer"), contributor
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_change_role_raises_403(self):
        viewer = make_user("viewer")
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()

        current_org_member = make_org_member(viewer.id, org_id, "member")
        current_proj_member = make_project_member(viewer.id, project_id, "viewer")

        db = make_db(
            r(current_org_member),
            r(current_proj_member),
        )

        with pytest.raises(HTTPException) as exc:
            await role_service.update_project_member_role(
                db, org_id, project_id, uuid.uuid4(),
                ProjectRoleUpdate(role="contributor"), viewer
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_non_org_member_raises_403(self):
        user = make_user()
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()

        db = make_db(r(None))  # org üyesi değil → 403

        with pytest.raises(HTTPException) as exc:
            await role_service.update_project_member_role(
                db, org_id, project_id, uuid.uuid4(),
                ProjectRoleUpdate(role="contributor"), user
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_target_not_project_member_raises_404(self):
        manager = make_user("manager")
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()

        current_org_member = make_org_member(manager.id, org_id, "member")
        current_proj_member = make_project_member(manager.id, project_id, "manager")

        db = make_db(
            r(current_org_member),
            r(current_proj_member),
            r(None),  # target proje üyesi yok → 404
        )

        with pytest.raises(HTTPException) as exc:
            await role_service.update_project_member_role(
                db, org_id, project_id, uuid.uuid4(),
                ProjectRoleUpdate(role="viewer"), manager
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_same_role_no_commit(self):
        """Aynı rol atanırsa commit yapılmamalı."""
        owner = make_user("owner")
        target = make_user("contributor")
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()

        current_org_member = make_org_member(owner.id, org_id, "owner")
        target_member = make_project_member(target.id, project_id, "contributor")

        db = make_db(
            r(current_org_member),
            r(target_member),
        )

        result = await role_service.update_project_member_role(
            db, org_id, project_id, target.id,
            ProjectRoleUpdate(role="contributor"), owner
        )

        assert result.role == "contributor"
        db.commit.assert_not_awaited()
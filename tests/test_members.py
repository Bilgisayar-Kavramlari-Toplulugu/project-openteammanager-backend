import pytest


MEMBERS_URL = "/api/v1/organizations/{org_id}/members"


# ── Üye Listeleme

@pytest.mark.asyncio
async def test_list_members_success(auth_client, org):
    """Org üyeleri listelenebilmeli."""
    response = await auth_client.get(MEMBERS_URL.format(org_id=org["id"]))
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(m["role"] == "owner" for m in data["items"])


@pytest.mark.asyncio
async def test_list_members_unauthenticated(client, completed_setup, org):
    """Giriş yapmamış kullanıcı erişemez."""
    response = await client.get(MEMBERS_URL.format(org_id=org["id"]),
                                headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_members_pagination(auth_client, org):
    """Sayfalama doğru çalışmalı."""
    response = await auth_client.get(
        MEMBERS_URL.format(org_id=org["id"]),
        params={"page": 1, "limit": 10}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 10
    assert "has_next" in data


@pytest.mark.asyncio
async def test_list_members_search(auth_client, org):
    """Arama çalışmalı."""
    response = await auth_client.get(
        MEMBERS_URL.format(org_id=org["id"]),
        params={"search": "owner"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_members_filter_by_role(auth_client, org):
    """Rol filtresi çalışmalı."""
    response = await auth_client.get(
        MEMBERS_URL.format(org_id=org["id"]),
        params={"role": "owner"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(m["role"] == "owner" for m in data["items"])


@pytest.mark.asyncio
async def test_list_members_invalid_role(auth_client, org):
    """Geçersiz rol filtresi 422 döndürmeli."""
    response = await auth_client.get(
        MEMBERS_URL.format(org_id=org["id"]),
        params={"role": "invalid_role"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_members_user_info_present(auth_client, org):
    """Her üyede kullanıcı bilgileri bulunmalı."""
    response = await auth_client.get(MEMBERS_URL.format(org_id=org["id"]))
    data = response.json()
    for member in data["items"]:
        assert "user" in member
        assert "username" in member["user"]
        assert "email" in member["user"]
        assert "full_name" in member["user"]
        assert "password_hash" not in member["user"]


# ── Üye Profil Detayı

@pytest.mark.asyncio
async def test_get_member_detail_success(auth_client, org):
    """Üye profil detayı dönmeli."""
    me = (await auth_client.get("/api/v1/auth/me")).json()
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/members/{me['id']}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == me["id"]
    assert data["username"] == me["username"]
    assert "org_role" in data
    assert "stats" in data
    assert "projects" in data
    assert "recent_activity" in data


@pytest.mark.asyncio
async def test_get_member_detail_stats(auth_client, org, project, task):
    """İstatistikler doğru dönmeli."""
    me = (await auth_client.get("/api/v1/auth/me")).json()
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/members/{me['id']}"
    )
    data = response.json()
    stats = data["stats"]
    assert "total_projects" in stats
    assert "total_tasks" in stats
    assert "completed_tasks" in stats
    assert stats["total_projects"] >= 1


@pytest.mark.asyncio
async def test_get_member_detail_not_found(auth_client, org):
    """Olmayan üye 404 döndürmeli."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/members/{fake_id}"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_member_detail_no_sensitive_data(auth_client, org):
    """Hassas veriler response'da bulunmamalı."""
    me = (await auth_client.get("/api/v1/auth/me")).json()
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/members/{me['id']}"
    )
    data = response.json()
    assert "password_hash" not in data
    assert "oauth_id" not in data


@pytest.mark.asyncio
async def test_get_member_detail_projects(auth_client, org, project):
    """Üyenin katıldığı projeler dönmeli."""
    me = (await auth_client.get("/api/v1/auth/me")).json()
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/members/{me['id']}"
    )
    data = response.json()
    assert len(data["projects"]) >= 1
    assert any(p["id"] == project["id"] for p in data["projects"])
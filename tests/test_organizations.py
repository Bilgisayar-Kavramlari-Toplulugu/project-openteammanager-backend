import pytest

# --- Organizasyon Oluşturma ---

@pytest.mark.asyncio
async def test_create_organization_success(auth_client):
    response = await auth_client.post("/api/v1/organizations", json={
        "name": "My Org",
        "slug": "my-org",
        "description": "Test org"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Org"
    assert data["slug"] == "my-org"
    assert "id" in data
    assert "owner_id" in data


@pytest.mark.asyncio
async def test_create_organization_duplicate_slug(auth_client):
    await auth_client.post("/api/v1/organizations", json={
        "name": "My Org",
        "slug": "my-org"
    })
    response = await auth_client.post("/api/v1/organizations", json={
        "name": "Another Org",
        "slug": "my-org"
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_organization_invalid_slug(auth_client):
    response = await auth_client.post("/api/v1/organizations", json={
        "name": "My Org",
        "slug": "My Invalid Slug!"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_organization_unauthenticated(client, completed_setup):
    response = await client.post("/api/v1/organizations", json={
        "name": "My Org",
        "slug": "my-org"
    })
    assert response.status_code == 401


# --- Organizasyon Listeleme ---

@pytest.mark.asyncio
async def test_list_organizations(auth_client, org):
    response = await auth_client.get("/api/v1/organizations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(o["id"] == org["id"] for o in data)


@pytest.mark.asyncio
async def test_list_organizations_only_own(auth_client, client, org):
    """Kullanıcı yalnızca üyesi olduğu organizasyonları görür.
    TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "other@example.com",
        "username": "other",
        "full_name": "Other User",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "other@example.com",
        "password": "Test1234!"
    })
    other_token = login.json()["access_token"]
    response = await client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert not any(o["id"] == org["id"] for o in data)


# --- Organizasyon Detay ---

@pytest.mark.asyncio
async def test_get_organization_success(auth_client, org):
    response = await auth_client.get(f"/api/v1/organizations/{org['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == org["id"]


@pytest.mark.asyncio
async def test_get_organization_not_found(auth_client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.get(f"/api/v1/organizations/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_organization_forbidden(client, org):
    """Üye olmayan kullanıcı organizasyon detayını göremez.
    TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "outsider@example.com",
        "username": "outsider",
        "full_name": "Outsider",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "outsider@example.com",
        "password": "Test1234!"
    })
    token = login.json()["access_token"]
    response = await client.get(
        f"/api/v1/organizations/{org['id']}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


# --- Organizasyon Güncelleme ---

@pytest.mark.asyncio
async def test_update_organization_success(auth_client, org):
    response = await auth_client.patch(f"/api/v1/organizations/{org['id']}", json={
        "name": "Updated Name"
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_organization_forbidden_for_member(auth_client, client, org):
    """Member rolündeki kullanıcı organizasyonu güncelleyemez.
    TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "member@example.com",
        "username": "member",
        "full_name": "Memeber User",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "member@example.com",
        "password": "Test1234!"
    })
    member_token = login.json()["access_token"]
    member_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {member_token}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": member_id,
        "role": "member"
    })

    response = await client.patch(
        f"/api/v1/organizations/{org['id']}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"name": "Hacked Name"}
    )
    assert response.status_code == 403


# --- Organizasyon Silme ---

@pytest.mark.asyncio
async def test_delete_organization_success(auth_client, org):
    response = await auth_client.delete(f"/api/v1/organizations/{org['id']}")
    assert response.status_code == 204

    get_response = await auth_client.get(f"/api/v1/organizations/{org['id']}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_organization_forbidden_for_member(auth_client, client, org):
    """Member rolündeki kullanıcı organizasyonu silemez, sadece owner silebilir.
    TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "member@example.com",
        "username": "memberuser",
        "full_name": "Member User",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "member@example.com",
        "password": "Test1234!"
    })
    member_token = login.json()["access_token"]
    member_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {member_token}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": member_id,
        "role": "member"
    })

    response = await client.delete(
        f"/api/v1/organizations/{org['id']}",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 403


# --- Üye Yönetimi ---

@pytest.mark.asyncio
async def test_invite_member_success(auth_client, client, org):
    """TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "newmember@example.com",
        "username": "newmember",
        "full_name": "New Member",
        "password": "Test1234!"
    })
    new_user = await client.post("/api/v1/auth/login", json={
        "email": "newmember@example.com",
        "password": "Test1234!"
    })
    new_user_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_user.json()['access_token']}"}
    )).json()["id"]

    response = await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": new_user_id,
        "role": "member"
    })
    assert response.status_code == 201
    assert response.json()["role"] == "member"


@pytest.mark.asyncio
async def test_invite_member_duplicate(auth_client, client, org):
    """Aynı kullanıcıyı iki kez davet etmek 400 döndürmeli.
    TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "username": "dupuser",
        "full_name": "Dup User",
        "password": "Test1234!"
    })
    dup_login = await client.post("/api/v1/auth/login", json={
        "email": "dup@example.com",
        "password": "Test1234!"
    })
    dup_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {dup_login.json()['access_token']}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": dup_id,
        "role": "member"
    })
    response = await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": dup_id,
        "role": "member"
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_invite_member_forbidden_for_member(auth_client, client, org):
    """Member üye davet edemez.
    TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "m2@example.com",
        "username": "member2",
        "full_name": "Member 2",
        "password": "Test1234!"
    })
    v2_login = await client.post("/api/v1/auth/login", json={
        "email": "m2@example.com",
        "password": "Test1234!"
    })
    v2_token = v2_login.json()["access_token"]
    v2_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {v2_token}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": v2_id,
        "role": "member"
    })

    await client.post("/api/v1/auth/register", json={
        "email": "target@example.com",
        "username": "target",
        "full_name": "Target",
        "password": "Test1234!"
    })
    target_login = await client.post("/api/v1/auth/login", json={
        "email": "target@example.com",
        "password": "Test1234!"
    })
    target_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {target_login.json()['access_token']}"}
    )).json()["id"]

    response = await client.post(
        f"/api/v1/organizations/{org['id']}/members",
        headers={"Authorization": f"Bearer {v2_token}"},
        json={"user_id": target_id, "role": "member"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_members_success(auth_client, org):
    response = await auth_client.get(f"/api/v1/organizations/{org['id']}/members")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1
    assert any(m["role"] == "owner" for m in data["items"])


@pytest.mark.asyncio
async def test_remove_member_success(auth_client, client, org):
    """Owner org üyesini silebilmeli.
    TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "tobe_removed@example.com",
        "username": "toberemoved",
        "full_name": "To Be Removed",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "tobe_removed@example.com",
        "password": "Test1234!"
    })
    user_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": user_id,
        "role": "member"
    })

    response = await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/members/{user_id}"
    )
    assert response.status_code == 204

    members = (await auth_client.get(
        f"/api/v1/organizations/{org['id']}/members"
    )).json()
    assert not any(m["user_id"] == user_id and m["status"] == "active" for m in members["items"])


@pytest.mark.asyncio
async def test_remove_owner_forbidden(auth_client, org):
    """Owner kendisini silemez."""
    me = (await auth_client.get("/api/v1/auth/me")).json()
    response = await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/members/{me['id']}"
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_remove_member_forbidden_for_member(auth_client, client, org):
    """Member üye silemez.
    TODO: BE-10 - davet sistemi tamamlandıktan sonra değişecek
    """
    await client.post("/api/v1/auth/register", json={
        "email": "member3@example.com",
        "username": "member3",
        "full_name": "Member 3",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "member3@example.com",
        "password": "Test1234!"
    })
    viewer_token = login.json()["access_token"]
    viewer_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": viewer_id,
        "role": "member"
    })

    me = (await auth_client.get("/api/v1/auth/me")).json()
    response = await client.delete(
        f"/api/v1/organizations/{org['id']}/members/{me['id']}",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert response.status_code == 403
import pytest


# --- Proje Oluşturma ---

@pytest.mark.asyncio
async def test_create_project_success(auth_client, org):
    response = await auth_client.post(f"/api/v1/organizations/{org['id']}/projects", json={
        "name": "My Project",
        "key": "MYP",
        "description": "Test projesi"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Project"
    assert data["key"] == "MYP"
    assert data["status"] == "active"
    assert data["visibility"] == "private"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_project_invalid_key(auth_client, org):
    """Key küçük harf içerirse 422 dönmeli."""
    response = await auth_client.post(f"/api/v1/organizations/{org['id']}/projects", json={
        "name": "My Project",
        "key": "myp"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_invalid_status(auth_client, org):
    response = await auth_client.post(f"/api/v1/organizations/{org['id']}/projects", json={
        "name": "My Project",
        "key": "MYP",
        "status": "invalid_status"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_non_org_member_forbidden(auth_client, client, org):
    """Organizasyon üyesi olmayan kullanıcı proje oluşturamaz."""
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
    response = await client.post(
        f"/api/v1/organizations/{org['id']}/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "My Project", "key": "MYP"}
    )
    assert response.status_code == 403


# --- Proje Listeleme ---

@pytest.mark.asyncio
async def test_list_projects(auth_client, org, project):
    response = await auth_client.get(f"/api/v1/organizations/{org['id']}/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(p["key"] == "TST" for p in data)


@pytest.mark.asyncio
async def test_list_projects_only_member(auth_client, client, org, project):
    """Kullanıcı yalnızca üyesi olduğu projeleri görür."""
    await client.post("/api/v1/auth/register", json={
        "email": "member@example.com",
        "username": "memberuser",
        "full_name": "Member",
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

    response = await client.get(
        f"/api/v1/organizations/{org['id']}/projects",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert not any(p["key"] == "TST" for p in response.json())


# --- Proje Detay ---

@pytest.mark.asyncio
async def test_get_project_success(auth_client, org, project):
    response = await auth_client.get(f"/api/v1/organizations/{org['id']}/projects/{project['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == project["id"]


@pytest.mark.asyncio
async def test_get_project_not_found(auth_client, org):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.get(f"/api/v1/organizations/{org['id']}/projects/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_project_forbidden(client, org, project):
    """Proje üyesi olmayan kullanıcı proje detayını göremez."""
    await client.post("/api/v1/auth/register", json={
        "email": "outsider2@example.com",
        "username": "outsider2",
        "full_name": "Outsider 2",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "outsider2@example.com",
        "password": "Test1234!"
    })
    token = login.json()["access_token"]
    response = await client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


# --- Proje Güncelleme ---

@pytest.mark.asyncio
async def test_update_project_success(auth_client, org, project):
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}",
        json={"name": "Updated Project", "status": "on_hold"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Project"
    assert data["status"] == "on_hold"


@pytest.mark.asyncio
async def test_update_project_forbidden_for_viewer(auth_client, client, org, project):
    """Viewer rolündeki kullanıcı projeyi güncelleyemez."""
    await client.post("/api/v1/auth/register", json={
        "email": "viewer@example.com",
        "username": "vieweruser",
        "full_name": "Viewer",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "viewer@example.com",
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
    await auth_client.post(f"/api/v1/organizations/{org['id']}/projects/{project['id']}/members", json={
        "user_id": viewer_id,
        "role": "viewer"
    })

    response = await client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"name": "Hacked"}
    )
    assert response.status_code == 403


# --- Proje Silme ---

@pytest.mark.asyncio
async def test_delete_project_success(auth_client, org, project):
    response = await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}"
    )
    assert response.status_code == 204

    get_response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}"
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_forbidden_for_contributor(auth_client, client, org, project):
    """Contributor rolündeki kullanıcı projeyi silemez."""
    await client.post("/api/v1/auth/register", json={
        "email": "contrib@example.com",
        "username": "contrib",
        "full_name": "Contributor",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "contrib@example.com",
        "password": "Test1234!"
    })
    contrib_token = login.json()["access_token"]
    contrib_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {contrib_token}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": contrib_id,
        "role": "member"
    })
    await auth_client.post(f"/api/v1/organizations/{org['id']}/projects/{project['id']}/members", json={
        "user_id": contrib_id,
        "role": "contributor"
    })

    response = await client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}",
        headers={"Authorization": f"Bearer {contrib_token}"}
    )
    assert response.status_code == 403


# --- Proje Üye Yönetimi ---

@pytest.mark.asyncio
async def test_add_project_member_success(auth_client, client, org, project):
    await client.post("/api/v1/auth/register", json={
        "email": "newmember@example.com",
        "username": "newmember",
        "full_name": "New Member",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "newmember@example.com",
        "password": "Test1234!"
    })
    new_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": new_id,
        "role": "member"
    })

    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/members",
        json={"user_id": new_id, "role": "contributor"}
    )
    assert response.status_code == 201
    assert response.json()["role"] == "contributor"


@pytest.mark.asyncio
async def test_add_project_member_duplicate(auth_client, client, org, project):
    """Aynı kullanıcıyı iki kez eklemek 400 döndürmeli."""
    await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "username": "dupuser",
        "full_name": "Dup",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "dup@example.com",
        "password": "Test1234!"
    })
    dup_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )).json()["id"]

    await auth_client.post(f"/api/v1/organizations/{org['id']}/members", json={
        "user_id": dup_id,
        "role": "member"
    })
    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/members",
        json={"user_id": dup_id, "role": "contributor"}
    )
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/members",
        json={"user_id": dup_id, "role": "contributor"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_add_project_member_not_org_member(auth_client, client, org, project):
    """Organizasyon üyesi olmayan kullanıcı projeye eklenemez."""
    await client.post("/api/v1/auth/register", json={
        "email": "nonorg@example.com",
        "username": "nonorg",
        "full_name": "Non Org",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "nonorg@example.com",
        "password": "Test1234!"
    })
    non_org_id = (await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )).json()["id"]

    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/members",
        json={"user_id": non_org_id, "role": "contributor"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_project_members(auth_client, org, project):
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/members"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(m["role"] == "manager" for m in data)
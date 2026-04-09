import pytest


# ── Yorum Oluşturma ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_comment_success(auth_client, org, project, task):
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        json={"content": "Harika bir görev!"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Harika bir görev!"
    assert data["task_id"] == task["id"]
    assert data["is_deleted"] is False
    assert data["is_edited"] is False
    assert data["parent_id"] is None
    assert "id" in data


@pytest.mark.asyncio
async def test_create_comment_empty_content(auth_client, org, project, task):
    """Boş yorum kabul edilmemeli."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        json={"content": "   "}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_comment_forbidden_non_member(client, org, project, task):
    """Proje üyesi olmayan kullanıcı yorum ekleyemez."""
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
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Izinsiz yorum"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_comment_task_not_found(auth_client, org, project):
    """Olmayan göreve yorum eklenemez."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{fake_id}/comments",
        json={"content": "Yorum"}
    )
    assert response.status_code == 404


# ── Reply (Thread) ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_reply_success(auth_client, org, project, task, comment):
    """parent_id ile reply oluşturulabilmeli."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        json={"content": "Bu bir yanıt.", "parent_id": comment["id"]}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["parent_id"] == comment["id"]


@pytest.mark.asyncio
async def test_create_reply_invalid_parent(auth_client, org, project, task):
    """Geçersiz parent_id 400 döndürmeli."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        json={"content": "Yanıt", "parent_id": fake_id}
    )
    assert response.status_code == 400


# ── Yorum Listeleme ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_comments_success(auth_client, org, project, task, comment):
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(c["id"] == comment["id"] for c in data["items"])


@pytest.mark.asyncio
async def test_list_comments_flat_list(auth_client, org, project, task, comment):
    """Reply dahil tüm yorumlar düz liste olarak dönmeli."""
    await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        json={"content": "Yanıt", "parent_id": comment["id"]}
    )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments"
    )
    assert response.status_code == 200
    items = response.json()["items"]
    # Düz liste — her item dict olmalı, nested items olmamalı
    assert all(isinstance(c, dict) for c in items)
    assert not any("replies" in c for c in items)


@pytest.mark.asyncio
async def test_list_comments_ordered_by_created_at(auth_client, org, project, task):
    """Yorumlar eskiden yeniye sıralanmalı."""
    for i in range(3):
        await auth_client.post(
            f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
            json={"content": f"Yorum {i}"}
        )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments"
    )
    items = response.json()["items"]
    dates = [c["created_at"] for c in items]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_list_comments_pagination(auth_client, org, project, task):
    """Pagination doğru çalışmalı."""
    for i in range(5):
        await auth_client.post(
            f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
            json={"content": f"Yorum {i}"}
        )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        params={"page": 1, "limit": 3}
    )
    data = response.json()
    assert len(data["items"]) == 3
    assert data["total"] == 5
    assert data["has_next"] is True
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_comments_pagination_last_page(auth_client, org, project, task):
    """Son sayfada has_next False olmalı."""
    for i in range(3):
        await auth_client.post(
            f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
            json={"content": f"Yorum {i}"}
        )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        params={"page": 2, "limit": 2}
    )
    data = response.json()
    assert len(data["items"]) == 1
    assert data["has_next"] is False


# ── Yorum Düzenleme ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_comment_success(auth_client, org, project, comment):
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{comment['id']}",
        json={"content": "Güncellenmiş yorum"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Güncellenmiş yorum"
    assert data["is_edited"] is True


@pytest.mark.asyncio
async def test_update_comment_empty_content(auth_client, org, project, comment):
    """Boş içerikle güncelleme yapılamamalı."""
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{comment['id']}",
        json={"content": ""}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_comment_forbidden_other_user(client, auth_client, org, project, task, comment):
    """Başkasının yorumunu düzenleyemez."""
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
    token = login.json()["access_token"]
    response = await client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{comment['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Hacklenmiş yorum"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_comment_not_found(auth_client, org, project):
    """Olmayan yorum güncellenemez."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.patch(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{fake_id}",
        json={"content": "Yorum"}
    )
    assert response.status_code == 404


# ── Yorum Silme ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_comment_success(auth_client, org, project, task, comment):
    """Yorum sahibi yorumunu silebilmeli."""
    response = await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{comment['id']}"
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_comment_soft_delete(auth_client, org, project, task, comment):
    """Silinen yorum listede görünmeli ama content=None, is_deleted=True olmalı."""
    await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{comment['id']}"
    )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments"
    )
    items = response.json()["items"]
    deleted = next((c for c in items if c["id"] == comment["id"]), None)
    assert deleted is not None
    assert deleted["is_deleted"] is True
    assert deleted["content"] is None


@pytest.mark.asyncio
async def test_delete_comment_replies_preserved(auth_client, org, project, task, comment):
    """Parent yorum silinse bile child yorumlar korunmalı."""
    reply = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        json={"content": "Bu bir yanıt.", "parent_id": comment["id"]}
    )
    await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{comment['id']}"
    )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments"
    )
    items = response.json()["items"]
    reply_still_exists = any(c["id"] == reply.json()["id"] for c in items)
    assert reply_still_exists


@pytest.mark.asyncio
async def test_delete_comment_forbidden_other_user(client, org, project, comment):
    """Başkasının yorumunu silemez."""
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
    token = login.json()["access_token"]
    response = await client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{comment['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_comment_not_found(auth_client, org, project):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/comments/{fake_id}"
    )
    assert response.status_code == 404
import io
import pytest
import pytest_asyncio


# ── Mock storage — gerçek MinIO olmadan test ─────────────────────────────────
# Testlerde storage_service fonksiyonlarını mock'luyoruz.
# Gerçek MinIO bağlantısı olmadan çalışır.

@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    """Tüm storage çağrılarını mock'lar."""
    monkeypatch.setattr("app.services.storage_service.upload_file", lambda *a, **kw: None)
    monkeypatch.setattr("app.services.storage_service.delete_file", lambda *a, **kw: None)
    monkeypatch.setattr(
        "app.services.storage_service.generate_presigned_url",
        lambda path, **kw: f"https://mock-storage/{path}?token=mock"
    )


def _make_file(filename="test.pdf", content=b"test content", content_type="application/pdf"):
    """Test için sahte UploadFile verisi döner."""
    return {
        "files": (filename, io.BytesIO(content), content_type)
    }


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def attachment(auth_client, org, project):
    """Test için hazır bir attachment döner (göreve bağlı değil)."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("test.pdf", io.BytesIO(b"test content"), "application/pdf")},
    )
    return response.json()


@pytest_asyncio.fixture
async def task_attachment(auth_client, org, project, task):
    """Test için göreve bağlı bir attachment döner."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("task_file.pdf", io.BytesIO(b"task content"), "application/pdf")},
        params={"task_id": task["id"]},
    )
    return response.json()


# ── Dosya Yükleme ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_attachment_success(auth_client, org, project):
    """Dosya yükleme başarılı, download_url response'da dönmeli."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("test.pdf", io.BytesIO(b"test content"), "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["project_id"] == project["id"]
    assert data["task_id"] is None
    assert "download_url" in data
    assert data["download_url"].startswith("https://")


@pytest.mark.asyncio
async def test_upload_attachment_with_task(auth_client, org, project, task):
    """task_id verilince dosya göreve bağlanmalı."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("task_file.png", io.BytesIO(b"img"), "image/png")},
        params={"task_id": task["id"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == task["id"]


@pytest.mark.asyncio
async def test_upload_attachment_invalid_task(auth_client, org, project):
    """Geçersiz task_id 404 döndürmeli."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
        params={"task_id": fake_id},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_upload_attachment_forbidden_non_member(client, org, project):
    """Proje üyesi olmayan kullanıcı dosya yükleyememeli."""
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
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_attachment_too_large(auth_client, org, project):
    """50 MB üzeri dosya reddedilmeli."""
    large_content = b"x" * (50 * 1024 * 1024 + 1)
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("big.pdf", io.BytesIO(large_content), "application/pdf")},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_attachment_invalid_extension(auth_client, org, project):
    """İzin verilmeyen uzantı reddedilmeli."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("script.exe", io.BytesIO(b"content"), "application/octet-stream")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_attachment_invalid_mime(auth_client, org, project):
    """Geçersiz MIME type reddedilmeli."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("test.pdf", io.BytesIO(b"content"), "application/x-msdownload")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_duplicate_filename(auth_client, org, project, attachment):
    """Aynı isimli dosya tekrar yüklenememeli."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        files={"file": ("test.pdf", io.BytesIO(b"different content"), "application/pdf")},
    )
    assert response.status_code == 409

# ── Dosya Listeleme ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_attachments_project(auth_client, org, project, attachment):
    """Proje dosyaları listelenebilmeli."""
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(a["id"] == attachment["id"] for a in data)


@pytest.mark.asyncio
async def test_list_attachments_filter_by_task(auth_client, org, project, attachment, task_attachment):
    """task_id filtresiyle sadece göreve ait dosyalar dönmeli."""
    task_id = task_attachment["task_id"]
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments",
        params={"task_id": task_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(a["task_id"] == task_id for a in data)
    assert not any(a["id"] == attachment["id"] for a in data)  # task'sız dosya görünmemeli


@pytest.mark.asyncio
async def test_list_task_attachments_endpoint(auth_client, org, project, task, task_attachment):
    """Dedicated task attachments endpoint çalışmalı."""
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/attachments"
    )
    assert response.status_code == 200
    data = response.json()
    assert any(a["id"] == task_attachment["id"] for a in data)


@pytest.mark.asyncio
async def test_list_attachments_download_url_present(auth_client, org, project, attachment):
    """Her dosyada download_url bulunmalı."""
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments"
    )
    data = response.json()
    assert all("download_url" in a for a in data)
    assert all(a["download_url"].startswith("https://") for a in data)


# ── Dosya Silme ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_attachment_success(auth_client, org, project, attachment):
    """Dosya sahibi silebilmeli."""
    response = await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments/{attachment['id']}"
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_attachment_removed_from_list(auth_client, org, project, attachment):
    """Silinen dosya listede görünmemeli (soft-delete)."""
    await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments/{attachment['id']}"
    )
    response = await auth_client.get(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments"
    )
    data = response.json()
    assert not any(a["id"] == attachment["id"] for a in data)


@pytest.mark.asyncio
async def test_delete_attachment_forbidden_other_user(client, org, project, attachment):
    """Başkasının dosyasını silemez."""
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
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments/{attachment['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_attachment_not_found(auth_client, org, project):
    """Olmayan dosya 404 döndürmeli."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await auth_client.delete(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/attachments/{fake_id}"
    )
    assert response.status_code == 404
import pytest


SETUP_URL = "/api/v1/setup"

VALID_SETUP_PAYLOAD = {
    "org_name": "Test Org",
    "org_display_name": "Test Organization",
    "org_type": "community",
    "owner": {
        "full_name": "Test Owner",
        "username": "test_user",
        "email": "owner@test.com",
        "password": "Test1234!"
    }
}


# ── GET /setup ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_setup_status_not_completed(client):
    """Setup tamamlanmamışsa setup_completed=False dönmeli."""
    response = await client.get(SETUP_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["setup_completed"] is False


@pytest.mark.asyncio
async def test_get_setup_status_completed(client):
    """Setup tamamlandıktan sonra GET /setup 403 dönmeli."""
    await client.post(SETUP_URL, json=VALID_SETUP_PAYLOAD)
    response = await client.get(SETUP_URL)
    assert response.status_code == 403


# ── POST /setup ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_setup_success(client):
    """Setup başarıyla tamamlanmalı, token dönmeli."""
    response = await client.post(SETUP_URL, json=VALID_SETUP_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["message"] == "Kurulum başarıyla tamamlandı."


@pytest.mark.asyncio
async def test_complete_setup_twice_forbidden(client):
    """Setup iki kez tamamlanamaz."""
    await client.post(SETUP_URL, json=VALID_SETUP_PAYLOAD)
    response = await client.post(SETUP_URL, json=VALID_SETUP_PAYLOAD)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_complete_setup_missing_org_type(client):
    """org_type zorunlu, eksikse 422 dönmeli."""
    payload = {**VALID_SETUP_PAYLOAD}
    del payload["org_type"]
    response = await client.post(SETUP_URL, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_complete_setup_invalid_org_type(client):
    """Geçersiz org_type 422 dönmeli."""
    payload = {**VALID_SETUP_PAYLOAD, "org_type": "invalid_type"}
    response = await client.post(SETUP_URL, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_complete_setup_weak_password(client):
    """8 karakterden kısa şifre 422 dönmeli."""
    payload = {
        **VALID_SETUP_PAYLOAD,
        "owner": {**VALID_SETUP_PAYLOAD["owner"], "password": "123"}
    }
    response = await client.post(SETUP_URL, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_complete_setup_duplicate_email(client):
    """Aynı email ile iki kez setup yapılamaz (ikincisi 403 döner)."""
    await client.post(SETUP_URL, json=VALID_SETUP_PAYLOAD)
    payload = {**VALID_SETUP_PAYLOAD, "org_name": "Other Org", "org_display_name": "Other"}
    response = await client.post(SETUP_URL, json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_complete_setup_slug_auto_generated(client):
    """slug verilmezse org_display_name'den otomatik üretilmeli."""
    payload = {**VALID_SETUP_PAYLOAD}
    payload.pop("slug", None)
    response = await client.post(SETUP_URL, json=payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_complete_setup_org_type_saved(client):
    """org_type DB'ye doğru kaydedilmeli"""
    response = await client.post(SETUP_URL, json=VALID_SETUP_PAYLOAD)
    assert response.status_code == 201
    token = response.json()["access_token"]

    orgs = await client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert orgs.status_code == 200
    org_list = orgs.json()
    assert len(org_list) == 1
    assert org_list[0]["org_type"] == "community"


# ── Middleware ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_guard_blocks_other_endpoints(client):
    """Setup tamamlanmadan diğer endpoint'lere erişim 503 dönmeli."""
    response = await client.get("/api/v1/organizations")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_setup_guard_allows_after_completion(client):
    """Setup tamamlandıktan sonra diğer endpoint'lere erişilebilmeli."""
    setup_resp = await client.post(SETUP_URL, json=VALID_SETUP_PAYLOAD)
    token = setup_resp.json()["access_token"]

    response = await client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
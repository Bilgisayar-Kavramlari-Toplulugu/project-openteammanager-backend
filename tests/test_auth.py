import pytest


@pytest.mark.asyncio
async def test_register_success(client, completed_setup):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "Test1234!"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client, completed_setup):
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "Test1234!"
    })
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "testuser2",
        "full_name": "Test User 2",
        "password": "Test1234!"
    })
    assert response.status_code == 400
    assert "e-posta" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client, completed_setup):
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "Test1234!"
    })
    response = await client.post("/api/v1/auth/register", json={
        "email": "test2@example.com",
        "username": "testuser",
        "full_name": "Test User 2",
        "password": "Test1234!"
    })
    assert response.status_code == 400
    assert "kullanıcı adı" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client, completed_setup):
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "Test1234!"
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "Test1234!"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, completed_setup):
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "Test1234!"
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword!"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client, completed_setup):
    response = await client.post("/api/v1/auth/login", json={
        "email": "yok@example.com",
        "password": "Test1234!"
    })
    assert response.status_code == 401
"""
Bu dosya; test altyapısıdır
"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from dotenv import load_dotenv
from app.main import app
from app.database import Base
from app.routers.auth import get_db

load_dotenv()

TEST_DATABASE_URL = os.getenv("DATABASE_URL").replace("/otm_db", "/otm_test")

SETUP_OWNER = {
    "email": "owner@example.com",
    "password": "Test1234!",
    "full_name": "Owner User",
    "username": "test_user"
}

SETUP_PAYLOAD = {
    "org_name": "Test Org",
    "org_display_name": "Test Organization",
    "org_type": "community",
    "owner": SETUP_OWNER,
}

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from app.middleware.rate_limiting import _instance
    if _instance is not None:
        _instance.storage._store.clear()
    yield


@pytest_asyncio.fixture(scope="function")
async def client():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def completed_setup(client: AsyncClient):
    """Setup wizard'ı tamamlar. auth_client bu fixture'a bağımlıdır."""
    response = await client.post("/api/v1/setup", json=SETUP_PAYLOAD)
    assert response.status_code == 201, f"Setup başarısız: {response.json()}"
    return response.json()

@pytest_asyncio.fixture(scope="function")
async def auth_client(client: AsyncClient, completed_setup: dict):
    """
    Setup tamamlandıktan sonra owner ile login yapar.
    Owner setup sırasında oluşuyor.
    """
    response = await client.post("/api/v1/auth/login", json={
        "email": SETUP_OWNER["email"],
        "password": SETUP_OWNER["password"]
    })
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest_asyncio.fixture(scope="function")
async def outsider_client(client: AsyncClient, completed_setup: dict):
    """
    Org üyesi ama test projesine üye olmayan kullanıcı.
    BE-10 davet sistemi tamamlandıktan sonra davet akışıyla güncellenecek.
    TODO: BE-10 - şu an register açık olduğu için direkt ekleniyor
    """
    await client.post("/api/v1/auth/register", json={
        "email": "outsider@example.com",
        "username": "outsider",
        "full_name": "Outsider User",
        "password": "Test1234!"
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "outsider@example.com",
        "password": "Test1234!"
    })
    token = login.json()["access_token"]

    from httpx import AsyncClient as HttpxClient, ASGITransport
    outsider = HttpxClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"}
    )
    async with outsider:
        yield outsider


@pytest_asyncio.fixture(scope="function")
async def org(auth_client: AsyncClient, completed_setup: dict):
    """
    Setup sırasında oluşturulan organizasyonu döner.
    """
    response = await auth_client.get("/api/v1/organizations")
    orgs = response.json()
    assert len(orgs) > 0, "Setup sonrası organizasyon bulunamadı"
    return orgs[0]


@pytest_asyncio.fixture(scope="function")
async def project(auth_client: AsyncClient, org: dict):
    """Test için hazır bir proje döner."""
    response = await auth_client.post(f"/api/v1/organizations/{org['id']}/projects", json={
        "name": "Test Project",
        "key": "TST",
        "description": "Test projesi",
        "visibility": "internal"
    })
    return response.json()


@pytest_asyncio.fixture(scope="function")
async def task(auth_client: AsyncClient, org: dict, project: dict):
    """Test için hazır bir görev döner."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks",
        json={
            "title": "Test Task",
            "description": "Test görevi",
            "status": "todo",
            "priority": "medium",
        }
    )
    return response.json()


@pytest_asyncio.fixture(scope="function")
async def comment(auth_client, org, project, task):
    """Test için hazır bir yorum döner."""
    response = await auth_client.post(
        f"/api/v1/organizations/{org['id']}/projects/{project['id']}/tasks/{task['id']}/comments",
        json={"content": "Test yorumu"}
    )
    return response.json()
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
async def auth_client(client: AsyncClient):
    """Kayıtlı ve giriş yapmış kullanıcı ile client döner."""
    await client.post("/api/v1/auth/register", json={
        "email": "owner@example.com",
        "username": "owner",
        "full_name": "Owner User",
        "password": "Test1234!"
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "owner@example.com",
        "password": "Test1234!"
    })
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest_asyncio.fixture(scope="function")
async def org(auth_client: AsyncClient):
    """Test için hazır bir organizasyon döner."""
    response = await auth_client.post("/api/v1/organizations", json={
        "name": "Test Org",
        "slug": "test-org",
        "description": "Test organizasyonu"
    })
    return response.json()
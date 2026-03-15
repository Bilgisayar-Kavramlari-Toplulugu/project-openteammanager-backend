"""
Rate Limiting Middleware Tests
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter before each test."""
    from app.middleware.rate_limiting import _instance
    if _instance is not None:
        _instance.storage._store.clear()
    yield


@pytest.mark.asyncio
async def test_auth_rate_limit_exceeded():
    """21. istekte /auth/* 429 dönmeli."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for i in range(20):
            r = await ac.post(
                "/api/v1/auth/login",
                headers={"X-Forwarded-For": "203.0.113.1"}
            )
            assert r.status_code != 429, f"Request {i + 1} should not be rate limited"

        r = await ac.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": "203.0.113.1"}
        )
        assert r.status_code == 429
        assert r.json()["error"] == "Too Many Requests"
        assert "retry_after_seconds" in r.json()


@pytest.mark.asyncio
async def test_api_rate_limit_exceeded():
    """101. istekte genel API 429 dönmeli."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for i in range(100):
            r = await ac.get(
                "/api/v1/users",
                headers={"X-Forwarded-For": "203.0.113.2"}
            )
            assert r.status_code != 429, f"Request {i + 1} should not be rate limited"

        r = await ac.get(
            "/api/v1/users",
            headers={"X-Forwarded-For": "203.0.113.2"}
        )
        assert r.status_code == 429


@pytest.mark.asyncio
async def test_health_endpoint_exempt():
    """/health endpoint rate limit'ten muaf olmalı."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(200):
            r = await ac.get("/health", headers={"X-Forwarded-For": "203.0.113.3"})
            assert r.status_code != 429


@pytest.mark.asyncio
async def test_retry_after_seconds_positive():
    """retry_after_seconds > 0 ve <= 60 olmalı."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(20):
            await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.4"})

        r = await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.4"})
        assert r.status_code == 429
        retry_after = r.json()["retry_after_seconds"]
        assert 0 < retry_after <= 60


@pytest.mark.asyncio
async def test_retry_after_header_present():
    """RFC 6585: 429 response'unda Retry-After header olmalı."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(20):
            await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.5"})

        r = await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.5"})
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert int(r.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_different_ips_independent_counters():
    """Farklı IP'lerin sayacı birbirini etkilememeli."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(20):
            await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "1.1.1.1"})

        r = await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "1.1.1.1"})
        assert r.status_code == 429

        r = await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "2.2.2.2"})
        assert r.status_code != 429


@pytest.mark.asyncio
async def test_independent_endpoint_patterns():
    """Auth ve API endpoint'leri bağımsız sayaçlara sahip olmalı."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(20):
            await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.6"})

        r = await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.6"})
        assert r.status_code == 429

        r = await ac.get("/api/v1/users", headers={"X-Forwarded-For": "203.0.113.6"})
        assert r.status_code != 429


@pytest.mark.asyncio
async def test_options_preflight_exempt():
    """OPTIONS preflight istekleri sayaca dahil olmamalı."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(150):
            r = await ac.options("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.7"})
            assert r.status_code != 429

        r = await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": "203.0.113.7"})
        assert r.status_code != 429


@pytest.mark.asyncio
async def test_window_reset_allows_new_requests():
    """Window süresi geçince sayaç sıfırlanmalı."""

    from app.middleware.rate_limiting import _instance
    test_ip = "203.0.113.99"
    past_time = datetime.now() - timedelta(seconds=61)
    _instance.storage._store[f"{test_ip}:auth"] = (past_time, 20)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/auth/login", headers={"X-Forwarded-For": test_ip})
        assert r.status_code != 429


@pytest.mark.asyncio
async def test_docs_endpoint_exempt():
    """/docs endpoint rate limit'ten muaf olmalı."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(200):
            r = await ac.get("/docs", headers={"X-Forwarded-For": "203.0.113.8"})
            assert r.status_code != 429
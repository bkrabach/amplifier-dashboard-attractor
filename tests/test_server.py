"""Tests for the FastAPI server skeleton."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.server import create_app


@pytest.mark.asyncio
async def test_health_endpoint():
    app = create_app(mock=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "mock" in body


@pytest.mark.asyncio
async def test_health_shows_mock_mode():
    app = create_app(mock=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.json()["mock"] is True


@pytest.mark.asyncio
async def test_cors_headers_present():
    app = create_app(mock=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers
"""Tests for the pipeline REST endpoints (mock mode)."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.server import create_app


@pytest.fixture
def app():
    return create_app(mock=True)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_pipelines_returns_list(client):
    resp = await client.get("/api/pipelines")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 2


@pytest.mark.asyncio
async def test_get_pipelines_item_has_required_fields(client):
    resp = await client.get("/api/pipelines")
    item = resp.json()[0]
    for field in ["context_id", "pipeline_id", "status", "nodes_completed", "nodes_total", "total_elapsed_ms"]:
        assert field in item, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_get_pipeline_detail(client):
    resp = await client.get("/api/pipelines/1001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pipeline_id"] == "research-summarize-001"
    assert "dot_source" in body
    assert "digraph" in body["dot_source"]
    assert "nodes" in body
    assert "node_runs" in body


@pytest.mark.asyncio
async def test_get_pipeline_detail_not_found(client):
    resp = await client.get("/api/pipelines/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_node_detail(client):
    resp = await client.get("/api/pipelines/1001/nodes/gather")
    assert resp.status_code == 200
    body = resp.json()
    assert body["node_id"] == "gather"
    assert "info" in body
    assert "runs" in body
    assert len(body["runs"]) >= 1


@pytest.mark.asyncio
async def test_get_node_detail_not_found(client):
    resp = await client.get("/api/pipelines/1001/nodes/nonexistent")
    assert resp.status_code == 404
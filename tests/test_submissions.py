"""Tests for pipeline submission endpoint (POST /api/pipelines)."""

import json
import os

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.server import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(pipeline_logs_dir=str(tmp_path))


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


SIMPLE_DOT = """
digraph {
    start [shape=Mdiamond]
    work [prompt="Do something"]
    exit [shape=Msquare]
    start -> work -> exit
}
"""


@pytest.mark.asyncio
async def test_submit_pipeline_returns_pipeline_id(client):
    """POST /api/pipelines returns 201 with pipeline_id and status."""
    resp = await client.post(
        "/api/pipelines",
        json={"dot_source": SIMPLE_DOT, "goal": "Test goal"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "pipeline_id" in body
    assert body["status"] == "running"


@pytest.mark.asyncio
async def test_submit_pipeline_invalid_dot(client):
    """POST /api/pipelines with invalid DOT returns 422."""
    resp = await client.post(
        "/api/pipelines",
        json={"dot_source": "not valid dot", "goal": "Test"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_pipeline_missing_dot_source(client):
    """POST /api/pipelines without dot_source returns 422."""
    resp = await client.post(
        "/api/pipelines",
        json={"goal": "Test"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_creates_logs_dir_with_graph_dot(client, tmp_path):
    """Submission creates logs directory containing graph.dot and manifest.json."""
    resp = await client.post(
        "/api/pipelines",
        json={"dot_source": SIMPLE_DOT, "goal": "Test goal"},
    )
    assert resp.status_code == 201
    body = resp.json()
    logs_root = body["logs_root"]

    # Verify the logs directory was created with expected files
    assert os.path.isdir(logs_root)
    assert os.path.isfile(os.path.join(logs_root, "graph.dot"))
    assert os.path.isfile(os.path.join(logs_root, "manifest.json"))
    manifest = json.loads(open(os.path.join(logs_root, "manifest.json")).read())
    assert manifest["goal"] == "Test goal"

"""Tests for pipeline cancellation."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.pipeline_executor import PipelineExecutor
from amplifier_dashboard_attractor.server import create_app


@pytest.mark.asyncio
async def test_cancel_sets_event_and_status():
    """cancel() sets the cancel event and changes status to 'cancelling'."""
    executor = PipelineExecutor()

    # Simulate a running pipeline (manual insert — no real engine needed)
    cancel_event = asyncio.Event()
    executor.active_pipelines["p1"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    executor.cancel_events["p1"] = cancel_event

    result = executor.cancel("p1")

    assert result is True
    assert cancel_event.is_set()
    assert executor.get_status("p1") == "cancelling"


@pytest.mark.asyncio
async def test_cancel_unknown_pipeline_returns_false():
    """cancel() returns False for unknown pipeline IDs."""
    executor = PipelineExecutor()
    assert executor.cancel("nonexistent") is False


@pytest.mark.asyncio
async def test_cancel_completed_pipeline_returns_false():
    """cancel() returns False if pipeline already completed."""
    executor = PipelineExecutor()
    executor.active_pipelines["p1"] = {
        "task": None,
        "status": "completed",
        "logs_root": "/tmp/test",
    }
    executor.cancel_events["p1"] = asyncio.Event()

    assert executor.cancel("p1") is False


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def cancel_app(tmp_path):
    app = create_app(pipeline_logs_dir=str(tmp_path))
    return app


@pytest.fixture
async def cancel_client(cancel_app):
    transport = ASGITransport(app=cancel_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_cancel_endpoint_not_found(cancel_client):
    """POST /api/pipelines/{id}/cancel returns 404 for unknown pipeline."""
    resp = await cancel_client.post("/api/pipelines/unknown-id/cancel")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_endpoint_success(cancel_app, cancel_client):
    """POST /api/pipelines/{id}/cancel returns 200 with cancelling status."""
    # Manually register a fake running pipeline on the executor
    executor = cancel_app.state.pipeline_executor
    executor.active_pipelines["test-pipe"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    executor.cancel_events["test-pipe"] = asyncio.Event()

    resp = await cancel_client.post("/api/pipelines/test-pipe/cancel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pipeline_id"] == "test-pipe"
    assert body["status"] == "cancelling"


@pytest.mark.asyncio
async def test_cancel_endpoint_conflict(cancel_app, cancel_client):
    """POST /api/pipelines/{id}/cancel returns 409 if already completed."""
    executor = cancel_app.state.pipeline_executor
    executor.active_pipelines["done-pipe"] = {
        "task": None,
        "status": "completed",
        "logs_root": "/tmp/test",
    }
    executor.cancel_events["done-pipe"] = asyncio.Event()

    resp = await cancel_client.post("/api/pipelines/done-pipe/cancel")
    assert resp.status_code == 409

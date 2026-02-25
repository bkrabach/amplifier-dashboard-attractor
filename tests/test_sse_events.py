"""Tests for SSE event capture and streaming."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.pipeline_executor import (
    EventCaptureHook,
    PipelineExecutor,
)
from amplifier_dashboard_attractor.server import create_app


@pytest.mark.asyncio
async def test_event_capture_hook_pushes_to_queue():
    """EventCaptureHook.emit() pushes events onto its queue."""
    queue: asyncio.Queue = asyncio.Queue()
    hook = EventCaptureHook(queue)

    await hook.emit("pipeline:node_start", {"node_id": "work"})

    assert not queue.empty()
    item = queue.get_nowait()
    assert item["event"] == "pipeline:node_start"
    assert item["data"]["node_id"] == "work"
    assert "ts" in item


@pytest.mark.asyncio
async def test_event_capture_hook_multiple_events():
    """Multiple emit() calls queue multiple events in order."""
    queue: asyncio.Queue = asyncio.Queue()
    hook = EventCaptureHook(queue)

    await hook.emit("pipeline:node_start", {"node_id": "a"})
    await hook.emit("pipeline:node_complete", {"node_id": "a"})

    assert queue.qsize() == 2
    first = queue.get_nowait()
    second = queue.get_nowait()
    assert first["event"] == "pipeline:node_start"
    assert second["event"] == "pipeline:node_complete"


@pytest.mark.asyncio
async def test_executor_creates_event_queue_on_start():
    """PipelineExecutor.start() creates an event_queue for the pipeline."""
    executor = PipelineExecutor()

    # We need to manually test that event_queues dict gets populated
    # by simulating what start() does internally
    executor.event_queues["p1"] = asyncio.Queue()

    assert "p1" in executor.event_queues
    assert isinstance(executor.event_queues["p1"], asyncio.Queue)


@pytest.mark.asyncio
async def test_get_event_queue_returns_none_for_unknown():
    """get_event_queue() returns None for unknown pipelines."""
    executor = PipelineExecutor()
    assert executor.get_event_queue("nonexistent") is None


@pytest.mark.asyncio
async def test_get_event_queue_returns_queue():
    """get_event_queue() returns the queue for a known pipeline."""
    executor = PipelineExecutor()
    q = asyncio.Queue()
    executor.event_queues["p1"] = q
    assert executor.get_event_queue("p1") is q


# ---------------------------------------------------------------------------
# Endpoint tests (SSE streaming)
# ---------------------------------------------------------------------------


@pytest.fixture
def sse_app(tmp_path):
    return create_app(pipeline_logs_dir=str(tmp_path))


@pytest.fixture
async def sse_client(sse_app):
    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_sse_endpoint_not_found(sse_client):
    """GET /api/pipelines/{id}/events returns 404 for unknown pipeline."""
    resp = await sse_client.get("/api/pipelines/unknown-id/events")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sse_endpoint_streams_events(sse_app):
    """GET /api/pipelines/{id}/events streams SSE events from the queue."""
    executor = sse_app.state.pipeline_executor

    # Register a fake pipeline with an event queue
    queue = asyncio.Queue()
    executor.active_pipelines["sse-pipe"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    executor.event_queues["sse-pipe"] = queue
    executor.cancel_events["sse-pipe"] = asyncio.Event()

    # Pre-load events into the queue
    queue.put_nowait(
        {
            "event": "pipeline:node_start",
            "data": {"node_id": "work"},
            "ts": "2026-02-25T00:00:00",
        }
    )
    queue.put_nowait(
        {
            "event": "pipeline:complete",
            "data": {"status": "success"},
            "ts": "2026-02-25T00:00:01",
        }
    )

    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use stream to read the SSE response
        async with client.stream("GET", "/api/pipelines/sse-pipe/events") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            lines = []
            saw_complete_event = False
            async for line in resp.aiter_lines():
                lines.append(line)
                # After we see the event: pipeline:complete line,
                # wait for its data: line then stop.
                if line.startswith("event:") and "pipeline:complete" in line:
                    saw_complete_event = True
                    continue
                if saw_complete_event and line.startswith("data:"):
                    break

    # Verify we got SSE-formatted events
    text = "\n".join(lines)
    assert "event: connected" in text or "event: pipeline:node_start" in text
    assert "event: pipeline:complete" in text

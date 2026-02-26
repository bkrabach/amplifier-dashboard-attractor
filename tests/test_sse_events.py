"""Tests for SSE event capture and streaming.

RED → GREEN TDD:
  - Tests in the first section target the new history+fan-out model.
  - Run `uv run pytest tests/test_sse_events.py -q` — they will be RED until the
    implementation is updated.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.pipeline_executor import (
    EventCaptureHook,
    PipelineExecutor,
)
from amplifier_dashboard_attractor.server import create_app


# ---------------------------------------------------------------------------
# Unit tests — EventCaptureHook (new history + subscribers model)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_capture_hook_appends_to_history():
    """emit() appends to history list AND pushes to all subscriber queues."""
    history: list[dict] = []
    q: asyncio.Queue = asyncio.Queue()
    hook = EventCaptureHook(history=history, subscribers=[q])

    await hook.emit("pipeline:node_start", {"node_id": "work"})

    # History updated
    assert len(history) == 1
    assert history[0]["event"] == "pipeline:node_start"
    assert history[0]["data"]["node_id"] == "work"
    assert "ts" in history[0]

    # Subscriber queue received the same item
    assert not q.empty()
    item = q.get_nowait()
    assert item["event"] == "pipeline:node_start"
    assert item["data"]["node_id"] == "work"
    assert "ts" in item


@pytest.mark.asyncio
async def test_event_capture_hook_multiple_events():
    """Multiple emit() calls append to history and queues in order."""
    history: list[dict] = []
    q: asyncio.Queue = asyncio.Queue()
    hook = EventCaptureHook(history=history, subscribers=[q])

    await hook.emit("pipeline:node_start", {"node_id": "a"})
    await hook.emit("pipeline:node_complete", {"node_id": "a"})

    assert len(history) == 2
    assert history[0]["event"] == "pipeline:node_start"
    assert history[1]["event"] == "pipeline:node_complete"

    assert q.qsize() == 2
    first = q.get_nowait()
    second = q.get_nowait()
    assert first["event"] == "pipeline:node_start"
    assert second["event"] == "pipeline:node_complete"


@pytest.mark.asyncio
async def test_event_capture_hook_no_subscribers():
    """emit() with no subscribers only appends to history (no error)."""
    history: list[dict] = []
    hook = EventCaptureHook(history=history, subscribers=[])

    await hook.emit("pipeline:complete", {"status": "success"})

    assert len(history) == 1
    assert history[0]["event"] == "pipeline:complete"


# ---------------------------------------------------------------------------
# Unit tests — PipelineExecutor subscribe / unsubscribe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_returns_history_snapshot_and_queue():
    """subscribe() returns a snapshot of history and a new live queue."""
    executor = PipelineExecutor()

    # Simulate what start() creates
    executor.event_history["p1"] = [
        {"event": "pipeline:node_start", "data": {"node_id": "a"}, "ts": "t1"}
    ]
    executor.event_subscribers["p1"] = []

    snapshot, queue = executor.subscribe("p1")

    # Snapshot is a copy of history at subscribe time
    assert len(snapshot) == 1
    assert snapshot[0]["event"] == "pipeline:node_start"

    # New queue is registered as a subscriber
    assert queue in executor.event_subscribers["p1"]


@pytest.mark.asyncio
async def test_subscribe_new_events_go_to_queue():
    """After subscribe(), newly emitted events appear in the subscriber queue."""
    executor = PipelineExecutor()
    executor.event_history["p1"] = []
    executor.event_subscribers["p1"] = []

    snapshot, queue = executor.subscribe("p1")
    assert len(snapshot) == 0  # nothing yet

    hook = EventCaptureHook(
        history=executor.event_history["p1"],
        subscribers=executor.event_subscribers["p1"],
    )
    await hook.emit("pipeline:node_complete", {"node_id": "work"})

    assert not queue.empty()
    item = queue.get_nowait()
    assert item["event"] == "pipeline:node_complete"


@pytest.mark.asyncio
async def test_multiple_subscribers_each_get_events():
    """Fan-out: two subscribers each receive every event."""
    executor = PipelineExecutor()
    executor.event_history["p1"] = []
    executor.event_subscribers["p1"] = []

    _, q1 = executor.subscribe("p1")
    _, q2 = executor.subscribe("p1")

    hook = EventCaptureHook(
        history=executor.event_history["p1"],
        subscribers=executor.event_subscribers["p1"],
    )
    await hook.emit("pipeline:complete", {"status": "success"})

    assert not q1.empty()
    assert not q2.empty()
    item1 = q1.get_nowait()
    item2 = q2.get_nowait()
    assert item1["event"] == "pipeline:complete"
    assert item2["event"] == "pipeline:complete"


@pytest.mark.asyncio
async def test_unsubscribe_removes_queue():
    """After unsubscribe(), new events no longer reach that queue."""
    executor = PipelineExecutor()
    executor.event_history["p1"] = []
    executor.event_subscribers["p1"] = []

    _, queue = executor.subscribe("p1")
    executor.unsubscribe("p1", queue)

    hook = EventCaptureHook(
        history=executor.event_history["p1"],
        subscribers=executor.event_subscribers["p1"],
    )
    await hook.emit("pipeline:complete", {"status": "success"})

    # Queue was removed before emit — should still be empty
    assert queue.empty()


@pytest.mark.asyncio
async def test_event_history_survives_pipeline_completion():
    """event_history is still accessible after the pipeline finishes."""
    executor = PipelineExecutor()
    executor.event_history["p1"] = [
        {"event": "pipeline:complete", "data": {}, "ts": "t1"}
    ]
    executor.event_subscribers["p1"] = []
    executor.active_pipelines["p1"] = {
        "task": None,
        "status": "completed",
        "logs_root": "/tmp",
    }
    executor.cancel_events["p1"] = asyncio.Event()

    # Simulate the _run_pipeline finally block: pop cancel + subscribers, NOT history
    executor.cancel_events.pop("p1", None)
    executor.event_subscribers.pop("p1", None)

    assert "p1" in executor.event_history
    assert len(executor.event_history["p1"]) == 1
    assert executor.event_history["p1"][0]["event"] == "pipeline:complete"


# ---------------------------------------------------------------------------
# SSE endpoint tests
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
async def test_sse_completed_pipeline_replays_full_history(sse_app):
    """For a completed pipeline the endpoint replays all history and closes."""
    executor = sse_app.state.pipeline_executor

    executor.active_pipelines["done-pipe"] = {
        "task": None,
        "status": "completed",
        "logs_root": "/tmp/test",
    }
    executor.event_history["done-pipe"] = [
        {
            "event": "pipeline:node_start",
            "data": {"node_id": "work"},
            "ts": "2026-02-25T00:00:00+00:00",
        },
        {
            "event": "pipeline:complete",
            "data": {"status": "success"},
            "ts": "2026-02-25T00:00:01+00:00",
        },
    ]

    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/pipelines/done-pipe/events") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            lines = []
            async for line in resp.aiter_lines():
                lines.append(line)

    text = "\n".join(lines)
    assert "pipeline:node_start" in text
    assert "pipeline:complete" in text


@pytest.mark.asyncio
async def test_sse_terminal_events_close_stream(sse_app):
    """pipeline:failed and pipeline:cancelled also close the stream."""
    executor = sse_app.state.pipeline_executor

    for terminal in ("pipeline:failed", "pipeline:cancelled"):
        pid = f"pipe-{terminal.replace(':', '-')}"
        executor.active_pipelines[pid] = {
            "task": None,
            "status": "failed" if terminal == "pipeline:failed" else "cancelled",
            "logs_root": "/tmp/test",
        }
        executor.event_history[pid] = [
            {
                "event": terminal,
                "data": {"reason": "test"},
                "ts": "2026-02-25T00:00:00+00:00",
            }
        ]

        transport = ASGITransport(app=sse_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", f"/api/pipelines/{pid}/events") as resp:
                assert resp.status_code == 200
                lines = []
                async for line in resp.aiter_lines():
                    lines.append(line)

        text = "\n".join(lines)
        assert terminal in text, f"Expected {terminal} in SSE output"


@pytest.mark.asyncio
async def test_sse_includes_id_field(sse_app):
    """SSE output includes an id: field with the event timestamp."""
    executor = sse_app.state.pipeline_executor
    ts = "2026-02-25T00:00:00+00:00"

    executor.active_pipelines["id-pipe"] = {
        "task": None,
        "status": "completed",
        "logs_root": "/tmp/test",
    }
    executor.event_history["id-pipe"] = [
        {
            "event": "pipeline:complete",
            "data": {"status": "success"},
            "ts": ts,
        }
    ]

    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/pipelines/id-pipe/events") as resp:
            assert resp.status_code == 200
            lines = []
            async for line in resp.aiter_lines():
                lines.append(line)

    text = "\n".join(lines)
    assert f"id: {ts}" in text


@pytest.mark.asyncio
async def test_sse_replays_history_on_connect(sse_app):
    """Running pipeline: history events appear in the stream before live events."""
    executor = sse_app.state.pipeline_executor

    executor.active_pipelines["hist-pipe"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    executor.event_history["hist-pipe"] = [
        {
            "event": "pipeline:node_start",
            "data": {"node_id": "work"},
            "ts": "2026-02-25T00:00:00+00:00",
        }
    ]
    executor.event_subscribers["hist-pipe"] = []
    executor.cancel_events["hist-pipe"] = asyncio.Event()

    # Inject terminal event shortly after the endpoint subscribes so the
    # stream can close in the test without timing out.
    async def inject_terminal():
        await asyncio.sleep(0.05)
        hook = EventCaptureHook(
            history=executor.event_history["hist-pipe"],
            subscribers=executor.event_subscribers["hist-pipe"],
        )
        await hook.emit("pipeline:complete", {"status": "success"})

    asyncio.create_task(inject_terminal())

    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/pipelines/hist-pipe/events") as resp:
            assert resp.status_code == 200
            lines = []
            async for line in resp.aiter_lines():
                lines.append(line)

    text = "\n".join(lines)
    # History event must appear
    assert "pipeline:node_start" in text
    # Live terminal event must also appear
    assert "pipeline:complete" in text


@pytest.mark.asyncio
async def test_sse_endpoint_streams_events(sse_app):
    """Running pipeline: GET /api/pipelines/{id}/events streams SSE events."""
    executor = sse_app.state.pipeline_executor

    executor.active_pipelines["sse-pipe"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    executor.event_history["sse-pipe"] = []
    executor.event_subscribers["sse-pipe"] = []
    executor.cancel_events["sse-pipe"] = asyncio.Event()

    # Populate history with two events before the client connects
    hook = EventCaptureHook(
        history=executor.event_history["sse-pipe"],
        subscribers=executor.event_subscribers["sse-pipe"],
    )
    await hook.emit("pipeline:node_start", {"node_id": "work"})
    await hook.emit("pipeline:complete", {"status": "success"})

    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/pipelines/sse-pipe/events") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            lines: list[str] = []
            saw_complete = False
            async for line in resp.aiter_lines():
                lines.append(line)
                if line.startswith("event:") and "pipeline:complete" in line:
                    saw_complete = True
                    continue
                if saw_complete and line.startswith("data:"):
                    break

    text = "\n".join(lines)
    assert "event: connected" in text or "event: pipeline:node_start" in text
    assert "event: pipeline:complete" in text


@pytest.mark.asyncio
async def test_sse_no_event_history_returns_404(sse_app):
    """If a pipeline has no event_history entry, /events returns 404."""
    executor = sse_app.state.pipeline_executor

    # Pipeline exists in active_pipelines but has no event_history
    executor.active_pipelines["ghost-pipe"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    # Deliberately do NOT set executor.event_history["ghost-pipe"]

    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/pipelines/ghost-pipe/events")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sse_data_is_valid_json(sse_app):
    """Every data: line in the SSE output must be valid JSON."""
    executor = sse_app.state.pipeline_executor

    executor.active_pipelines["json-pipe"] = {
        "task": None,
        "status": "completed",
        "logs_root": "/tmp/test",
    }
    executor.event_history["json-pipe"] = [
        {
            "event": "pipeline:node_start",
            "data": {"node_id": "a", "extra": [1, 2, 3]},
            "ts": "2026-02-25T00:00:00+00:00",
        },
        {
            "event": "pipeline:complete",
            "data": {"status": "success"},
            "ts": "2026-02-25T00:00:01+00:00",
        },
    ]

    transport = ASGITransport(app=sse_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/pipelines/json-pipe/events") as resp:
            assert resp.status_code == 200
            lines = []
            async for line in resp.aiter_lines():
                lines.append(line)

    data_lines = [ln for ln in lines if ln.startswith("data:")]
    assert len(data_lines) >= 2  # connected + at least 2 events
    for dl in data_lines:
        payload = dl[len("data:"):].strip()
        json.loads(payload)  # must not raise

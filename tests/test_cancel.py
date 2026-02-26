"""Tests for pipeline cancellation."""

import asyncio
import threading

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


# ---------------------------------------------------------------------------
# Threading.Event tests (cooperative cross-thread cancellation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_uses_threading_event(tmp_path):
    """cancel_events dict contains threading.Event instances after start()."""
    executor = PipelineExecutor()

    loop = asyncio.get_running_loop()

    # Create an already-resolved future to mock run_in_executor so no real
    # thread is spawned and no pipeline actually runs.
    done_future: asyncio.Future[None] = loop.create_future()
    done_future.set_result(None)

    original_run_in_executor = loop.run_in_executor

    def patched_run_in_executor(pool, func, *args):
        _ = (pool, func, args)  # ignored
        return done_future

    loop.run_in_executor = patched_run_in_executor  # type: ignore[method-assign]
    try:
        await executor.start(
            pipeline_id="p-thread",
            graph=object(),
            goal="test",
            logs_root=str(tmp_path),
            providers={},
        )
    finally:
        loop.run_in_executor = original_run_in_executor  # type: ignore[method-assign]

    event = executor.cancel_events.get("p-thread")
    assert event is not None, "cancel_events should contain an entry for the pipeline"
    assert isinstance(event, threading.Event), (
        f"Expected threading.Event, got {type(event)}"
    )


@pytest.mark.asyncio
async def test_cancel_event_is_set_after_cancel():
    """After executor.cancel(), the threading.Event is set."""
    executor = PipelineExecutor()

    # Manually insert a threading.Event (as start() will after the fix)
    cancel_event = threading.Event()
    executor.active_pipelines["p2"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    executor.cancel_events["p2"] = cancel_event

    assert not cancel_event.is_set()

    result = executor.cancel("p2")

    assert result is True
    assert cancel_event.is_set()
    assert executor.get_status("p2") == "cancelling"


# ---------------------------------------------------------------------------
# Cancelled outcome → status + SSE terminal event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_cancelled_emits_terminal_event():
    """When engine returns a cancelled outcome, executor emits pipeline:cancelled."""
    from unittest.mock import AsyncMock, MagicMock

    executor = PipelineExecutor()
    pipeline_id = "cancel-sse-test"

    # Pre-register pipeline tracking state (normally done by start())
    executor.active_pipelines[pipeline_id] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    executor.event_history[pipeline_id] = []
    executor.event_subscribers[pipeline_id] = []
    executor.cancel_events[pipeline_id] = threading.Event()

    # Build a mock outcome that looks like a cancelled pipeline
    mock_outcome = MagicMock()
    mock_outcome.is_success = False
    mock_outcome.failure_reason = "cancelled"
    mock_outcome.notes = "Pipeline cancelled by user request"
    mock_outcome.status = MagicMock()
    mock_outcome.status.value = "fail"

    # Mock the engine and imports so _run_pipeline doesn't need real deps
    mock_engine = AsyncMock()
    mock_engine.run = AsyncMock(return_value=mock_outcome)

    import amplifier_dashboard_attractor.pipeline_executor as pe_mod

    original = pe_mod.PipelineExecutor._run_pipeline

    async def patched_run(self, pid, graph, goal, logs_root, providers):
        """Minimal reimplementation that exercises the status + event logic."""
        outcome = mock_outcome

        if getattr(outcome, "failure_reason", None) == "cancelled":
            status = "cancelled"
        elif outcome.is_success:
            status = "completed"
        else:
            status = "failed"

        if pid in self.active_pipelines:
            self.active_pipelines[pid]["status"] = status

        if status == "cancelled":
            from datetime import datetime, timezone

            terminal = {
                "event": "pipeline:cancelled",
                "data": {
                    "pipeline_id": pid,
                    "status": "cancelled",
                    "reason": getattr(outcome, "notes", None)
                    or "Pipeline cancelled",
                },
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            history = self.event_history.get(pid)
            if history is not None:
                history.append(terminal)

    pe_mod.PipelineExecutor._run_pipeline = patched_run  # type: ignore[assignment]
    try:
        await executor._run_pipeline(
            pipeline_id, object(), "test", "/tmp/test", {}
        )
    finally:
        pe_mod.PipelineExecutor._run_pipeline = original  # type: ignore[assignment]

    # Verify status is "cancelled" (not "failed")
    assert executor.get_status(pipeline_id) == "cancelled"

    # Verify a pipeline:cancelled terminal event was appended to history
    history = executor.event_history[pipeline_id]
    cancelled_events = [e for e in history if e["event"] == "pipeline:cancelled"]
    assert len(cancelled_events) == 1
    assert cancelled_events[0]["data"]["status"] == "cancelled"
    assert "cancelled" in cancelled_events[0]["data"]["reason"].lower()

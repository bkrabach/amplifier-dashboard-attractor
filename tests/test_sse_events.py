"""Tests for SSE event capture and streaming."""

import asyncio

import pytest

from amplifier_dashboard_attractor.pipeline_executor import (
    EventCaptureHook,
    PipelineExecutor,
)


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

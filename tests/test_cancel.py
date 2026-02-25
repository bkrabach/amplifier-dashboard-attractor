"""Tests for pipeline cancellation."""

import asyncio

import pytest

from amplifier_dashboard_attractor.pipeline_executor import PipelineExecutor


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

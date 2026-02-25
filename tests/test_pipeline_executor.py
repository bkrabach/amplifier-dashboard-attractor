"""Tests for the pipeline background executor."""

import asyncio

import pytest

from amplifier_dashboard_attractor.pipeline_executor import PipelineExecutor


@pytest.mark.asyncio
async def test_executor_starts_and_tracks_pipeline(tmp_path):
    """Executor starts a pipeline and tracks it by ID."""
    executor = PipelineExecutor()

    dot_source = """
    digraph {
        start [shape=Mdiamond]
        work [prompt="Do something"]
        exit [shape=Msquare]
        start -> work -> exit
    }
    """
    logs_root = str(tmp_path / "test-pipeline")

    from amplifier_module_loop_pipeline.dot_parser import parse_dot

    graph = parse_dot(dot_source)

    await executor.start(
        pipeline_id="test-001",
        graph=graph,
        goal="Test goal",
        logs_root=logs_root,
        providers={},
    )

    assert "test-001" in executor.active_pipelines
    # Give the background task a moment to run
    await asyncio.sleep(0.5)

    status = executor.get_status("test-001")
    assert status in ("running", "completed", "failed")


@pytest.mark.asyncio
async def test_executor_unknown_pipeline():
    """Getting status of unknown pipeline returns None."""
    executor = PipelineExecutor()
    assert executor.get_status("nonexistent") is None


@pytest.mark.asyncio
async def test_executor_cleanup(tmp_path):
    """Completed pipelines can be cleaned up."""
    executor = PipelineExecutor()

    dot_source = """
    digraph {
        start [shape=Mdiamond]
        exit [shape=Msquare]
        start -> exit
    }
    """
    logs_root = str(tmp_path / "test-cleanup")

    from amplifier_module_loop_pipeline.dot_parser import parse_dot

    graph = parse_dot(dot_source)

    await executor.start(
        pipeline_id="cleanup-001",
        graph=graph,
        goal="Cleanup test",
        logs_root=logs_root,
        providers={},
    )

    # Wait for completion
    await asyncio.sleep(1.0)

    executor.cleanup_completed()
    # Completed pipeline should be removed from active tracking
    status = executor.get_status("cleanup-001")
    assert status is None


@pytest.mark.asyncio
async def test_run_pipeline_cleans_up_transient_resources(tmp_path):
    """_run_pipeline cleans up cancel_events and event_queues on completion."""
    executor = PipelineExecutor()

    dot_source = """
    digraph {
        start [shape=Mdiamond]
        exit [shape=Msquare]
        start -> exit
    }
    """
    logs_root = str(tmp_path / "test-auto-cleanup")

    from amplifier_module_loop_pipeline.dot_parser import parse_dot

    graph = parse_dot(dot_source)

    await executor.start(
        pipeline_id="auto-cleanup-001",
        graph=graph,
        goal="Auto cleanup test",
        logs_root=logs_root,
        providers={},
    )

    # Confirm transient resources were created
    assert "auto-cleanup-001" in executor.cancel_events
    assert "auto-cleanup-001" in executor.event_queues

    # Wait for pipeline to finish
    await asyncio.sleep(1.0)

    # cancel_events and event_queues should be cleaned up automatically
    assert "auto-cleanup-001" not in executor.cancel_events
    assert "auto-cleanup-001" not in executor.event_queues
    # questions are kept for a grace period
    # active_pipelines entry remains (tracks status)

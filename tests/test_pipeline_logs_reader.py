"""Tests for the pipeline_logs_reader module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from amplifier_dashboard_attractor.pipeline_logs_reader import (
    PipelineLogsReader,
    _build_pipeline_state,
    _derive_status,
    _path_to_id,
    _read_json,
    _read_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


SAMPLE_MANIFEST = {
    "graph_name": "test_pipeline",
    "goal": "Test the pipeline reader",
    "start_time": "2026-02-24T10:00:00+00:00",
    "node_count": 3,
    "edge_count": 2,
}

SAMPLE_CHECKPOINT = {
    "current_node": "done",
    "completed_nodes": {
        "start": "success",
        "plan": "success",
        "implement": "success",
    },
    "context": {
        "graph.goal": "Test the pipeline reader",
        "outcome": "success",
    },
    "node_outcomes": {
        "start": {"status": "success", "notes": "Start node"},
        "plan": {"status": "success", "notes": "Planning done"},
        "implement": {"status": "success", "notes": "Code written"},
    },
    "timestamp": "2026-02-24T10:05:00+00:00",
    "node_retries": {},
    "logs": [],
}

SAMPLE_NODE_STATUS = {
    "node_id": "plan",
    "outcome": "success",
    "status": "success",
    "preferred_next_label": None,
    "suggested_next_ids": None,
    "context_updates": None,
    "duration_ms": 5432.1,
    "notes": "Created implementation plan",
    "failure_reason": None,
}


@pytest.fixture()
def pipeline_dir(tmp_path: Path) -> Path:
    """Create a realistic pipeline log directory."""
    d = tmp_path / "pipeline-run"
    d.mkdir()

    _write_json(d / "manifest.json", SAMPLE_MANIFEST)
    _write_json(d / "checkpoint.json", SAMPLE_CHECKPOINT)

    # Per-node directories
    for node_id in ("start", "plan", "implement"):
        node_dir = d / node_id
        node_dir.mkdir()
        status = {
            "node_id": node_id,
            "outcome": "success",
            "status": "success",
            "duration_ms": 100.5 if node_id == "start" else 5432.1,
            "notes": f"Completed {node_id}",
            "failure_reason": None,
        }
        _write_json(node_dir / "status.json", status)
        _write_text(node_dir / "prompt.md", f"Prompt for {node_id}")

    # Only plan has a response.md
    _write_text(d / "plan" / "response.md", "Here is the plan...")

    return d


@pytest.fixture()
def multi_pipeline_dir(tmp_path: Path, pipeline_dir: Path) -> Path:
    """Create a parent directory containing multiple pipeline log dirs."""
    # pipeline_dir already exists under tmp_path as "pipeline-run"
    # Add a second pipeline
    d2 = tmp_path / "pipeline-run-2"
    d2.mkdir()
    _write_json(
        d2 / "manifest.json",
        {**SAMPLE_MANIFEST, "graph_name": "second_pipeline", "goal": "Another run"},
    )
    _write_json(
        d2 / "checkpoint.json",
        {
            "current_node": "plan",
            "completed_nodes": {"start": "success"},
            "context": {},
            "node_outcomes": {"start": {"status": "success"}},
        },
    )
    for node_id in ("start",):
        node_dir = d2 / node_id
        node_dir.mkdir()
        _write_json(
            node_dir / "status.json",
            {
                "node_id": node_id,
                "status": "success",
                "duration_ms": 50,
                "notes": "ok",
                "failure_reason": None,
            },
        )
    return tmp_path


# ---------------------------------------------------------------------------
# _read_json / _read_text
# ---------------------------------------------------------------------------


def test_read_json_valid(tmp_path: Path) -> None:
    p = tmp_path / "test.json"
    p.write_text('{"key": "value"}')
    assert _read_json(p) == {"key": "value"}


def test_read_json_missing(tmp_path: Path) -> None:
    assert _read_json(tmp_path / "nope.json") is None


def test_read_json_malformed(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert _read_json(p) is None


def test_read_text_valid(tmp_path: Path) -> None:
    p = tmp_path / "test.md"
    p.write_text("hello world")
    assert _read_text(p) == "hello world"


def test_read_text_missing(tmp_path: Path) -> None:
    assert _read_text(tmp_path / "nope.md") is None


# ---------------------------------------------------------------------------
# _path_to_id
# ---------------------------------------------------------------------------


def test_path_to_id_basic() -> None:
    pid = _path_to_id(Path("/tmp/attractor-pipeline"))
    assert pid.startswith("attractor-pipeline-")
    assert len(pid) == len("attractor-pipeline-") + 8  # 8 char hash


def test_path_to_id_deterministic() -> None:
    p = Path("/tmp/some/path")
    assert _path_to_id(p) == _path_to_id(p)


def test_path_to_id_unique() -> None:
    a = _path_to_id(Path("/tmp/run-1"))
    b = _path_to_id(Path("/tmp/run-2"))
    assert a != b


# ---------------------------------------------------------------------------
# _derive_status
# ---------------------------------------------------------------------------


def test_derive_status_complete() -> None:
    assert _derive_status({"current_node": "done", "context": {}}) == "complete"


def test_derive_status_success_outcome() -> None:
    # A pipeline is only "complete" when current_node is "done" —
    # outcome="success" alone just means the last node succeeded.
    assert (
        _derive_status({"context": {"outcome": "success"}, "current_node": "done"})
        == "complete"
    )


def test_derive_status_failed_outcome() -> None:
    assert _derive_status({"context": {"outcome": "fail"}}) == "failed"


def test_derive_status_failed_node() -> None:
    cp = {
        "context": {},
        "node_outcomes": {"plan": {"status": "fail"}},
        "completed_nodes": {"start": "success"},
    }
    assert _derive_status(cp) == "failed"


def test_derive_status_running() -> None:
    cp = {
        "context": {},
        "node_outcomes": {},
        "completed_nodes": {"start": "success"},
    }
    assert _derive_status(cp) == "running"


def test_derive_status_pending() -> None:
    assert _derive_status({"context": {}}) == "pending"


def test_derive_status_cancelled_context_outcome() -> None:
    """Cancelled via explicit context outcome."""
    assert _derive_status({"context": {"outcome": "cancelled"}}) == "cancelled"


def test_derive_status_cancelled_node_failure_reason() -> None:
    """Cancelled detected via node outcome failure_reason."""
    cp = {
        "context": {"outcome": "success"},  # last node succeeded
        "current_node": "NodeB",
        "node_outcomes": {
            "NodeA": {"status": "success", "failure_reason": "cancelled"},
        },
        "completed_nodes": {"NodeA": "success"},
    }
    assert _derive_status(cp) == "cancelled"


def test_derive_status_success_mid_run_is_running() -> None:
    """outcome='success' with current_node != 'done' means still running."""
    cp = {
        "context": {"outcome": "success"},
        "current_node": "NodeB",
        "completed_nodes": {"NodeA": "success"},
    }
    assert _derive_status(cp) == "running"


# ---------------------------------------------------------------------------
# _build_pipeline_state
# ---------------------------------------------------------------------------


def test_build_pipeline_state(pipeline_dir: Path) -> None:
    manifest = _read_json(pipeline_dir / "manifest.json")
    checkpoint = _read_json(pipeline_dir / "checkpoint.json")
    assert manifest is not None
    assert checkpoint is not None

    state = _build_pipeline_state(pipeline_dir, manifest, checkpoint)

    assert state["pipeline_id"] == "test_pipeline"
    assert state["goal"] == "Test the pipeline reader"
    assert state["status"] == "complete"
    assert state["nodes_completed"] == 3
    assert state["nodes_total"] == 3
    assert "start" in state["nodes"]
    assert "plan" in state["nodes"]
    assert "implement" in state["nodes"]
    assert len(state["node_runs"]["plan"]) == 1
    assert state["node_runs"]["plan"][0]["status"] == "success"
    assert state["node_runs"]["plan"][0]["duration_ms"] == 5432
    assert state["timing"]["plan"] == 5432
    assert state["errors"] == []


def test_build_pipeline_state_no_checkpoint(pipeline_dir: Path) -> None:
    manifest = _read_json(pipeline_dir / "manifest.json")
    assert manifest is not None
    state = _build_pipeline_state(pipeline_dir, manifest, {})
    # Without checkpoint, status should be pending and we still find nodes
    assert state["status"] == "pending"
    assert len(state["nodes"]) == 3  # node dirs still exist


def test_build_pipeline_state_with_failure(tmp_path: Path) -> None:
    d = tmp_path / "fail-run"
    d.mkdir()
    node_dir = d / "transform"
    node_dir.mkdir()
    _write_json(
        node_dir / "status.json",
        {
            "node_id": "transform",
            "status": "fail",
            "duration_ms": 1000,
            "notes": "Crashed",
            "failure_reason": "Rate limit exceeded",
        },
    )
    manifest = {"graph_name": "fail_test", "goal": "fail", "node_count": 1}
    checkpoint = {
        "context": {"outcome": "fail"},
        "completed_nodes": {},
        "node_outcomes": {"transform": {"status": "fail"}},
    }
    state = _build_pipeline_state(d, manifest, checkpoint)
    assert state["status"] == "failed"
    assert len(state["errors"]) == 1
    assert state["errors"][0]["message"] == "Rate limit exceeded"


# ---------------------------------------------------------------------------
# PipelineLogsReader
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_find_pipeline_sessions(pipeline_dir: Path) -> None:
    # Point reader at the parent of pipeline_dir so it scans subdirs
    reader = PipelineLogsReader([str(pipeline_dir.parent)])
    fleet = await reader.find_pipeline_sessions()
    assert len(fleet) >= 1
    item = fleet[0]
    assert item["pipeline_id"] == "test_pipeline"
    assert item["status"] == "complete"
    assert item["nodes_completed"] == 3
    assert item["goal"] == "Test the pipeline reader"
    # context_id should be a URL-safe string, not a raw path
    assert "/" not in item["context_id"]


@pytest.mark.asyncio()
async def test_find_pipeline_sessions_direct_dir(pipeline_dir: Path) -> None:
    # Point reader directly at the pipeline log dir
    reader = PipelineLogsReader([str(pipeline_dir)])
    fleet = await reader.find_pipeline_sessions()
    assert len(fleet) == 1
    assert fleet[0]["pipeline_id"] == "test_pipeline"


@pytest.mark.asyncio()
async def test_find_pipeline_sessions_multi(multi_pipeline_dir: Path) -> None:
    reader = PipelineLogsReader([str(multi_pipeline_dir)])
    fleet = await reader.find_pipeline_sessions()
    assert len(fleet) == 2
    names = {f["pipeline_id"] for f in fleet}
    assert "test_pipeline" in names
    assert "second_pipeline" in names


@pytest.mark.asyncio()
async def test_find_pipeline_sessions_empty(tmp_path: Path) -> None:
    reader = PipelineLogsReader([str(tmp_path)])
    fleet = await reader.find_pipeline_sessions()
    assert fleet == []


@pytest.mark.asyncio()
async def test_find_pipeline_sessions_nonexistent() -> None:
    reader = PipelineLogsReader(["/nonexistent/path"])
    fleet = await reader.find_pipeline_sessions()
    assert fleet == []


@pytest.mark.asyncio()
async def test_get_pipeline_state(pipeline_dir: Path) -> None:
    reader = PipelineLogsReader([str(pipeline_dir)])
    # Use the URL-safe ID from the fleet response
    fleet = await reader.find_pipeline_sessions()
    context_id = fleet[0]["context_id"]
    state = await reader.get_pipeline_state(context_id)
    assert state is not None
    assert state["pipeline_id"] == "test_pipeline"
    assert state["status"] == "complete"
    assert state["nodes_completed"] == 3


@pytest.mark.asyncio()
async def test_get_pipeline_state_not_found(pipeline_dir: Path) -> None:
    reader = PipelineLogsReader([str(pipeline_dir)])
    state = await reader.get_pipeline_state("nonexistent-id-00000000")
    assert state is None


@pytest.mark.asyncio()
async def test_get_node_events(pipeline_dir: Path) -> None:
    reader = PipelineLogsReader([str(pipeline_dir)])
    fleet = await reader.find_pipeline_sessions()
    context_id = fleet[0]["context_id"]
    result = await reader.get_node_events(context_id, "plan")
    assert result is not None
    assert result["node_id"] == "plan"
    assert result["info"]["id"] == "plan"
    assert len(result["runs"]) == 1
    assert result["prompt"] == "Prompt for plan"
    assert result["response"] == "Here is the plan..."


@pytest.mark.asyncio()
async def test_get_node_events_no_response(pipeline_dir: Path) -> None:
    reader = PipelineLogsReader([str(pipeline_dir)])
    fleet = await reader.find_pipeline_sessions()
    context_id = fleet[0]["context_id"]
    result = await reader.get_node_events(context_id, "start")
    assert result is not None
    assert result["prompt"] == "Prompt for start"
    assert result["response"] is None  # start has no response.md


@pytest.mark.asyncio()
async def test_get_node_events_not_found(pipeline_dir: Path) -> None:
    reader = PipelineLogsReader([str(pipeline_dir)])
    fleet = await reader.find_pipeline_sessions()
    context_id = fleet[0]["context_id"]
    result = await reader.get_node_events(context_id, "nonexistent")
    assert result is None


@pytest.mark.asyncio()
async def test_get_node_events_bad_pipeline(pipeline_dir: Path) -> None:
    reader = PipelineLogsReader([str(pipeline_dir)])
    result = await reader.get_node_events("bad-id-00000000", "plan")
    assert result is None

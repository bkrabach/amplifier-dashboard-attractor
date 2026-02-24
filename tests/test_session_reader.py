"""Tests for the events.jsonl session reader."""

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.session_reader import (
    SessionReader,
    reconstruct_pipeline_state,
)
from amplifier_dashboard_attractor.server import create_app


# ── Helpers ──────────────────────────────────────────────────────────


def _make_event(event: str, data: dict | None = None, ts: str = "2026-02-24T02:30:00+00:00", session_id: str = "test-session") -> str:
    """Build a single events.jsonl line."""
    obj = {
        "event": event,
        "ts": ts,
        "session_id": session_id,
        "lvl": "INFO",
        "schema": {"name": "amplifier.log", "ver": "1.0.0"},
        "data": data or {},
    }
    return json.dumps(obj)


def _write_pipeline_session(
    projects_dir: Path,
    session_id: str = "test-session-001",
    project: str = "test-project",
    *,
    extra_events: list[str] | None = None,
    include_metadata: bool = True,
    pipeline_id: str = "test-pipeline",
    goal: str = "Test the pipeline",
) -> Path:
    """Create a session directory with pipeline events and return its path."""
    session_dir = projects_dir / project / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    events = [
        _make_event("session:start", {"prompt": "run pipeline"}),
        _make_event("pipeline:start", {
            "graph_name": pipeline_id,
            "goal": goal,
            "node_count": 3,
            "dot_source": 'digraph { a -> b -> c; }',
            "graph_nodes": [
                {"id": "a", "label": "Step A", "shape": "box", "type": "llm"},
                {"id": "b", "label": "Step B", "shape": "box", "type": "tool"},
                {"id": "c", "label": "Step C", "shape": "box", "type": "llm"},
            ],
            "graph_edges": [
                {"from_node": "a", "to_node": "b", "label": "next"},
                {"from_node": "b", "to_node": "c", "label": "next"},
            ],
        }, ts="2026-02-24T02:30:01+00:00"),
        _make_event("pipeline:node_start", {
            "node_id": "a", "attempt": 1,
        }, ts="2026-02-24T02:30:02+00:00"),
        _make_event("pipeline:node_complete", {
            "node_id": "a", "status": "success", "duration_ms": 5000,
        }, ts="2026-02-24T02:30:07+00:00"),
        _make_event("pipeline:edge_selected", {
            "from_node": "a", "to_node": "b", "edge_label": "next",
        }, ts="2026-02-24T02:30:07+00:00"),
        _make_event("pipeline:node_start", {
            "node_id": "b", "attempt": 1,
        }, ts="2026-02-24T02:30:08+00:00"),
        # llm:response for token tracking
        _make_event("llm:response", {
            "provider": "anthropic", "model": "claude-sonnet-4-20250514",
            "usage": {"input": 1500, "output": 300},
        }, ts="2026-02-24T02:30:09+00:00"),
        _make_event("pipeline:node_complete", {
            "node_id": "b", "status": "success", "duration_ms": 3000,
        }, ts="2026-02-24T02:30:11+00:00"),
        _make_event("pipeline:edge_selected", {
            "from_node": "b", "to_node": "c", "edge_label": "next",
        }, ts="2026-02-24T02:30:11+00:00"),
        _make_event("pipeline:node_start", {
            "node_id": "c", "attempt": 1,
        }, ts="2026-02-24T02:30:12+00:00"),
        _make_event("pipeline:node_complete", {
            "node_id": "c", "status": "success", "duration_ms": 4000,
        }, ts="2026-02-24T02:30:16+00:00"),
        _make_event("pipeline:complete", {
            "status": "success", "duration_ms": 15000, "total_nodes_executed": 3,
        }, ts="2026-02-24T02:30:16+00:00"),
    ]

    if extra_events:
        events.extend(extra_events)

    (session_dir / "events.jsonl").write_text("\n".join(events) + "\n")

    if include_metadata:
        metadata = {
            "session_id": session_id,
            "created": "2026-02-24T02:30:00+00:00",
            "profile": "bundle:attractor",
            "model": "claude-sonnet-4-20250514",
            "turn_count": 5,
            "name": "Test Pipeline Session",
        }
        (session_dir / "metadata.json").write_text(json.dumps(metadata))

    return session_dir


# ── Unit tests: reconstruct_pipeline_state ───────────────────────────


@pytest.mark.asyncio
async def test_reconstruct_basic_pipeline(tmp_path):
    """A complete pipeline should reconstruct with correct status and counts."""
    session_dir = _write_pipeline_session(tmp_path)
    events_path = session_dir / "events.jsonl"
    state = reconstruct_pipeline_state(events_path)

    assert state is not None
    assert state["pipeline_id"] == "test-pipeline"
    assert state["goal"] == "Test the pipeline"
    assert state["status"] == "complete"
    assert state["nodes_total"] == 3
    assert state["nodes_completed"] == 3
    assert state["total_elapsed_ms"] == 15000


@pytest.mark.asyncio
async def test_reconstruct_has_node_runs(tmp_path):
    """Node runs should be populated with correct statuses and timing."""
    session_dir = _write_pipeline_session(tmp_path)
    state = reconstruct_pipeline_state(session_dir / "events.jsonl")

    assert "a" in state["node_runs"]
    assert "b" in state["node_runs"]
    assert "c" in state["node_runs"]
    assert state["node_runs"]["a"][0]["status"] == "success"
    assert state["node_runs"]["a"][0]["duration_ms"] == 5000
    assert state["node_runs"]["b"][0]["duration_ms"] == 3000


@pytest.mark.asyncio
async def test_reconstruct_has_graph_structure(tmp_path):
    """Nodes and edges should be populated from pipeline:start data."""
    session_dir = _write_pipeline_session(tmp_path)
    state = reconstruct_pipeline_state(session_dir / "events.jsonl")

    assert len(state["nodes"]) == 3
    assert state["nodes"]["a"]["label"] == "Step A"
    assert len(state["edges"]) == 2
    assert state["edges"][0]["from_node"] == "a"
    assert state["edges"][0]["to_node"] == "b"
    assert state["dot_source"] == "digraph { a -> b -> c; }"


@pytest.mark.asyncio
async def test_reconstruct_tracks_edge_decisions(tmp_path):
    """Edge selection events should populate edge_decisions."""
    session_dir = _write_pipeline_session(tmp_path)
    state = reconstruct_pipeline_state(session_dir / "events.jsonl")

    assert len(state["edge_decisions"]) == 2
    assert state["edge_decisions"][0]["from_node"] == "a"
    assert state["edge_decisions"][0]["selected_edge"]["to_node"] == "b"


@pytest.mark.asyncio
async def test_reconstruct_tracks_execution_path(tmp_path):
    """Execution path should list nodes in order of first execution."""
    session_dir = _write_pipeline_session(tmp_path)
    state = reconstruct_pipeline_state(session_dir / "events.jsonl")

    assert state["execution_path"] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_reconstruct_accumulates_tokens(tmp_path):
    """LLM response events should be summed into token totals."""
    session_dir = _write_pipeline_session(tmp_path)
    state = reconstruct_pipeline_state(session_dir / "events.jsonl")

    assert state["total_llm_calls"] == 1
    assert state["total_tokens_in"] == 1500
    assert state["total_tokens_out"] == 300


@pytest.mark.asyncio
async def test_reconstruct_returns_none_without_pipeline_events(tmp_path):
    """Sessions without pipeline:start should return None."""
    session_dir = tmp_path / "proj" / "sessions" / "no-pipeline"
    session_dir.mkdir(parents=True)
    events = [
        _make_event("session:start", {"prompt": "hello"}),
        _make_event("llm:response", {"usage": {"input": 100, "output": 50}}),
    ]
    (session_dir / "events.jsonl").write_text("\n".join(events) + "\n")

    state = reconstruct_pipeline_state(session_dir / "events.jsonl")
    assert state is None


@pytest.mark.asyncio
async def test_reconstruct_handles_malformed_lines(tmp_path):
    """Malformed JSON lines should be skipped without error."""
    session_dir = tmp_path / "proj" / "sessions" / "bad-lines"
    session_dir.mkdir(parents=True)
    lines = [
        "not valid json",
        '{"event": "pipeline:start", "ts": "2026-02-24T02:30:00+00:00", "session_id": "x", "data": {"graph_name": "p1", "goal": "g", "node_count": 1}, "lvl": "INFO", "schema": {}}',
        "another bad line {{{",
        "",
        '{"event": "pipeline:complete", "ts": "2026-02-24T02:30:05+00:00", "session_id": "x", "data": {"status": "success", "duration_ms": 5000}, "lvl": "INFO", "schema": {}}',
    ]
    (session_dir / "events.jsonl").write_text("\n".join(lines) + "\n")

    state = reconstruct_pipeline_state(session_dir / "events.jsonl")
    assert state is not None
    assert state["status"] == "complete"


@pytest.mark.asyncio
async def test_reconstruct_failed_pipeline(tmp_path):
    """Pipeline errors should set status to failed and populate errors."""
    session_dir = tmp_path / "proj" / "sessions" / "failed"
    session_dir.mkdir(parents=True)
    events = [
        _make_event("pipeline:start", {"graph_name": "fail-pipe", "goal": "try", "node_count": 2}),
        _make_event("pipeline:node_start", {"node_id": "step1", "attempt": 1}),
        _make_event("pipeline:node_complete", {"node_id": "step1", "status": "success", "duration_ms": 1000}),
        _make_event("pipeline:node_start", {"node_id": "step2", "attempt": 1}),
        _make_event("pipeline:error", {"node_id": "step2", "error_type": "timeout", "message": "Node timed out"}),
        _make_event("pipeline:complete", {"status": "fail", "duration_ms": 8000}),
    ]
    (session_dir / "events.jsonl").write_text("\n".join(events) + "\n")

    state = reconstruct_pipeline_state(session_dir / "events.jsonl")
    assert state["status"] == "failed"
    assert len(state["errors"]) == 1
    assert state["errors"][0]["message"] == "Node timed out"


@pytest.mark.asyncio
async def test_reconstruct_handles_missing_file(tmp_path):
    """Missing events.jsonl should return None."""
    state = reconstruct_pipeline_state(tmp_path / "nonexistent" / "events.jsonl")
    assert state is None


# ── Unit tests: SessionReader ────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_pipeline_sessions(tmp_path):
    """find_pipeline_sessions should return fleet items for pipeline sessions."""
    _write_pipeline_session(tmp_path, session_id="s1", project="proj1")
    _write_pipeline_session(
        tmp_path, session_id="s2", project="proj1",
        pipeline_id="other-pipe", goal="Another goal",
    )

    reader = SessionReader(projects_dir=str(tmp_path))
    fleet = await reader.find_pipeline_sessions()

    assert len(fleet) == 2
    ids = {item["context_id"] for item in fleet}
    assert "s1" in ids
    assert "s2" in ids

    for item in fleet:
        assert "pipeline_id" in item
        assert "status" in item
        assert "nodes_completed" in item
        assert "nodes_total" in item
        assert "total_elapsed_ms" in item
        assert "total_tokens_in" in item
        assert "total_tokens_out" in item
        assert "goal" in item
        assert "errors" in item


@pytest.mark.asyncio
async def test_find_pipeline_sessions_skips_non_pipeline(tmp_path):
    """Sessions without pipeline events should not appear in the fleet."""
    _write_pipeline_session(tmp_path, session_id="pipeline-session", project="proj")

    # Create a non-pipeline session
    non_pipe_dir = tmp_path / "proj" / "sessions" / "regular-session"
    non_pipe_dir.mkdir(parents=True)
    events = [
        _make_event("session:start", {"prompt": "hello"}),
        _make_event("llm:response", {"usage": {"input": 100, "output": 50}}),
    ]
    (non_pipe_dir / "events.jsonl").write_text("\n".join(events) + "\n")

    reader = SessionReader(projects_dir=str(tmp_path))
    fleet = await reader.find_pipeline_sessions()

    assert len(fleet) == 1
    assert fleet[0]["context_id"] == "pipeline-session"


@pytest.mark.asyncio
async def test_find_pipeline_sessions_empty_dir(tmp_path):
    """Empty projects directory should return empty list."""
    reader = SessionReader(projects_dir=str(tmp_path))
    fleet = await reader.find_pipeline_sessions()
    assert fleet == []


@pytest.mark.asyncio
async def test_find_pipeline_sessions_nonexistent_dir(tmp_path):
    """Non-existent projects directory should return empty list."""
    reader = SessionReader(projects_dir=str(tmp_path / "does-not-exist"))
    fleet = await reader.find_pipeline_sessions()
    assert fleet == []


@pytest.mark.asyncio
async def test_get_pipeline_state(tmp_path):
    """get_pipeline_state should return full state for a known session."""
    _write_pipeline_session(tmp_path, session_id="my-session", project="proj")

    reader = SessionReader(projects_dir=str(tmp_path))
    state = await reader.get_pipeline_state("my-session")

    assert state is not None
    assert state["pipeline_id"] == "test-pipeline"
    assert state["status"] == "complete"
    assert "node_runs" in state
    assert "nodes" in state


@pytest.mark.asyncio
async def test_get_pipeline_state_not_found(tmp_path):
    """get_pipeline_state should return None for unknown session."""
    reader = SessionReader(projects_dir=str(tmp_path))
    state = await reader.get_pipeline_state("nonexistent")
    assert state is None


@pytest.mark.asyncio
async def test_get_node_events(tmp_path):
    """get_node_events should return node detail matching mock shape."""
    _write_pipeline_session(tmp_path, session_id="s1", project="proj")

    reader = SessionReader(projects_dir=str(tmp_path))
    result = await reader.get_node_events("s1", "a")

    assert result is not None
    assert result["node_id"] == "a"
    assert "info" in result
    assert result["info"]["label"] == "Step A"
    assert "runs" in result
    assert len(result["runs"]) == 1
    assert result["runs"][0]["status"] == "success"
    assert "edge_decisions" in result


@pytest.mark.asyncio
async def test_get_node_events_not_found(tmp_path):
    """get_node_events should return None for unknown node."""
    _write_pipeline_session(tmp_path, session_id="s1", project="proj")

    reader = SessionReader(projects_dir=str(tmp_path))
    result = await reader.get_node_events("s1", "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_fleet_item_includes_metadata(tmp_path):
    """Fleet items should include metadata fields when available."""
    _write_pipeline_session(tmp_path, session_id="s1", project="proj")

    reader = SessionReader(projects_dir=str(tmp_path))
    fleet = await reader.find_pipeline_sessions()

    assert len(fleet) == 1
    item = fleet[0]
    assert item["model"] == "claude-sonnet-4-20250514"
    assert item["bundle"] == "bundle:attractor"
    assert item["session_name"] == "Test Pipeline Session"


# ── Integration tests: routes with SessionReader ─────────────────────


@pytest.fixture
def sessions_app(tmp_path):
    """Create an app using SessionReader with test data."""
    _write_pipeline_session(tmp_path, session_id="s1", project="proj", pipeline_id="pipe-1")
    return create_app(sessions_dir=str(tmp_path))


@pytest.fixture
async def sessions_client(sessions_app):
    transport = ASGITransport(app=sessions_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_route_list_pipelines_sessions_mode(sessions_client):
    """GET /api/pipelines should return data from SessionReader."""
    resp = await sessions_client.get("/api/pipelines")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["pipeline_id"] == "pipe-1"


@pytest.mark.asyncio
async def test_route_get_pipeline_sessions_mode(sessions_client):
    """GET /api/pipelines/{id} should return pipeline state from SessionReader."""
    resp = await sessions_client.get("/api/pipelines/s1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pipeline_id"] == "pipe-1"
    assert body["status"] == "complete"
    assert "node_runs" in body


@pytest.mark.asyncio
async def test_route_get_pipeline_not_found_sessions_mode(sessions_client):
    """GET /api/pipelines/{id} should 404 for unknown session."""
    resp = await sessions_client.get("/api/pipelines/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_route_get_node_sessions_mode(sessions_client):
    """GET /api/pipelines/{id}/nodes/{node} should return node detail."""
    resp = await sessions_client.get("/api/pipelines/s1/nodes/a")
    assert resp.status_code == 200
    body = resp.json()
    assert body["node_id"] == "a"
    assert body["info"]["label"] == "Step A"
    assert len(body["runs"]) >= 1


@pytest.mark.asyncio
async def test_route_get_node_not_found_sessions_mode(sessions_client):
    """GET /api/pipelines/{id}/nodes/{node} should 404 for unknown node."""
    resp = await sessions_client.get("/api/pipelines/s1/nodes/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_shows_sessions_source(sessions_client):
    """Health endpoint should report data_source as 'sessions'."""
    resp = await sessions_client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_source"] == "sessions"

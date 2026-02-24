"""Tests for mock pipeline data."""

from amplifier_dashboard_attractor.mock_data import MOCK_PIPELINES, get_mock_pipeline


def test_mock_pipelines_is_nonempty_list():
    assert isinstance(MOCK_PIPELINES, list)
    assert len(MOCK_PIPELINES) >= 2


def test_mock_pipeline_has_required_fields():
    p = MOCK_PIPELINES[0]
    assert "pipeline_id" in p
    assert "dot_source" in p
    assert "status" in p
    assert "nodes" in p
    assert "node_runs" in p
    assert "total_tokens_in" in p
    assert "nodes_completed" in p
    assert "nodes_total" in p


def test_mock_pipeline_dot_source_is_valid_dot():
    p = MOCK_PIPELINES[0]
    dot = p["dot_source"]
    assert "digraph" in dot
    assert "->" in dot


def test_mock_pipeline_has_multiple_node_states():
    """The mock should exercise multiple visual states for frontend development."""
    p = MOCK_PIPELINES[0]
    statuses = set()
    for runs in p["node_runs"].values():
        for run in runs:
            statuses.add(run["status"])
    assert len(statuses) >= 3, f"Expected >=3 distinct node statuses, got {statuses}"


def test_get_mock_pipeline_by_context_id():
    """Mock pipelines are keyed by a fake context_id (integer)."""
    result = get_mock_pipeline(1001)
    assert result is not None
    assert result["pipeline_id"] == MOCK_PIPELINES[0]["pipeline_id"]


def test_get_mock_pipeline_unknown_id_returns_none():
    assert get_mock_pipeline(9999) is None

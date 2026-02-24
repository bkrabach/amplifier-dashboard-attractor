"""Tests for the CXDB HTTP client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amplifier_dashboard_attractor.cxdb_client import CxdbClient


@pytest.fixture
def client():
    return CxdbClient(base_url="http://localhost:8080")


def _mock_response(data: dict) -> MagicMock:
    """Create a mock httpx.Response with synchronous .json() method."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = data
    return resp


@pytest.mark.asyncio
async def test_search_pipelines(client):
    """search_pipelines should query CXDB with a label CQL query."""
    mock_resp = _mock_response(
        {
            "contexts": [
                {
                    "context_id": "42",
                    "client_tag": "amplifier",
                    "title": "",
                    "head_turn_id": "100",
                    "head_depth": 5,
                    "is_live": True,
                    "created_at_unix_ms": 1708732200000,
                    "labels": ["pipeline_id:test-001", "pipeline_status:running"],
                },
            ],
            "total_count": 1,
        }
    )

    with patch.object(
        client._http, "get", AsyncMock(return_value=mock_resp)
    ) as mock_get:
        results = await client.search_pipelines()

    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert "pipeline_status" in call_args.kwargs.get("params", {}).get("q", "")
    assert len(results) == 1
    assert results[0]["context_id"] == "42"
    assert "pipeline_status:running" in results[0]["labels"]


@pytest.mark.asyncio
async def test_get_pipeline_state(client):
    """get_pipeline_state should find the latest pipeline_state_snapshot turn."""
    snapshot_content = json.dumps({"pipeline_id": "test-001", "status": "running"})
    mock_resp = _mock_response(
        {
            "turns": [
                {
                    "turn_id": 50,
                    "data": {
                        "item_type": "system",
                        "status": "complete",
                        "system": {
                            "kind": "info",
                            "title": "Pipeline started: test goal (4 nodes)",
                            "content": "test-001",
                        },
                    },
                },
                {
                    "turn_id": 55,
                    "data": {
                        "item_type": "system",
                        "status": "complete",
                        "system": {
                            "kind": "info",
                            "title": "pipeline_state_snapshot",
                            "content": snapshot_content,
                        },
                    },
                },
            ],
        }
    )

    with patch.object(client._http, "get", AsyncMock(return_value=mock_resp)):
        state = await client.get_pipeline_state(context_id=42)

    assert state is not None
    assert state["pipeline_id"] == "test-001"
    assert state["status"] == "running"


@pytest.mark.asyncio
async def test_get_pipeline_state_no_snapshot(client):
    """Returns None when no pipeline_state_snapshot turn exists."""
    mock_resp = _mock_response(
        {
            "turns": [
                {
                    "turn_id": 50,
                    "data": {
                        "item_type": "system",
                        "status": "complete",
                        "system": {
                            "kind": "info",
                            "title": "Some other turn",
                            "content": "",
                        },
                    },
                },
            ],
        }
    )

    with patch.object(client._http, "get", AsyncMock(return_value=mock_resp)):
        state = await client.get_pipeline_state(context_id=42)

    assert state is None


@pytest.mark.asyncio
async def test_get_node_events(client):
    """get_node_events should filter system turns for a specific node."""
    mock_resp = _mock_response(
        {
            "turns": [
                {
                    "turn_id": 60,
                    "data": {
                        "item_type": "system",
                        "status": "complete",
                        "system": {
                            "kind": "info",
                            "title": "Pipeline node started: gather",
                            "content": "gather",
                        },
                    },
                },
                {
                    "turn_id": 61,
                    "data": {
                        "item_type": "system",
                        "status": "complete",
                        "system": {
                            "kind": "info",
                            "title": "Pipeline node completed: gather",
                            "content": "gather",
                        },
                    },
                },
                {
                    "turn_id": 62,
                    "data": {
                        "item_type": "system",
                        "status": "complete",
                        "system": {
                            "kind": "info",
                            "title": "Pipeline node started: analyze",
                            "content": "analyze",
                        },
                    },
                },
            ],
        }
    )

    with patch.object(client._http, "get", AsyncMock(return_value=mock_resp)):
        events = await client.get_node_events(context_id=42, node_id="gather")

    assert len(events) == 2
    assert all("gather" in e["data"]["system"]["content"] for e in events)


@pytest.mark.asyncio
async def test_client_close():
    """Client should close its httpx client cleanly."""
    client = CxdbClient(base_url="http://localhost:8080")
    await client.close()
    assert client._http.is_closed

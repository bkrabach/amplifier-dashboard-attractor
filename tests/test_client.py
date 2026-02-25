"""Tests for the Dashboard API client.

Uses httpx.MockTransport to test all client methods without a running server.
"""

from __future__ import annotations

import json

import httpx
import pytest

from amplifier_dashboard_attractor.client import (
    AlreadyCompleted,
    DashboardClient,
    DashboardError,
    ExecutorNotConfigured,
    InvalidDOT,
    PipelineNotFound,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(handler) -> DashboardClient:
    """Build a DashboardClient backed by a mock transport."""
    transport = httpx.MockTransport(handler)
    mock_httpx = httpx.AsyncClient(transport=transport, base_url="http://test")
    return DashboardClient(_client=mock_httpx)


def _sse_body(*events: tuple[str, dict]) -> str:
    """Build an SSE-formatted response body from (event_type, data) pairs."""
    parts: list[str] = []
    for event_type, data in events:
        parts.append(f"event: {event_type}")
        parts.append(f"data: {json.dumps(data)}")
        parts.append("")  # empty line terminates the event
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pipelines():
    payload = [{"pipeline_id": "p1"}]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pipelines"
        assert request.method == "GET"
        return httpx.Response(200, json=payload)

    client = _make_client(handler)
    result = await client.list_pipelines()
    assert result == payload
    await client.close()


@pytest.mark.asyncio
async def test_get_pipeline():
    payload = {"pipeline_id": "p1", "status": "running", "nodes": []}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pipelines/p1"
        return httpx.Response(200, json=payload)

    client = _make_client(handler)
    result = await client.get_pipeline("p1")
    assert result == payload
    await client.close()


@pytest.mark.asyncio
async def test_get_node():
    payload = {"node_id": "gather", "status": "completed", "output": "..."}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pipelines/p1/nodes/gather"
        return httpx.Response(200, json=payload)

    client = _make_client(handler)
    result = await client.get_node("p1", "gather")
    assert result == payload
    await client.close()


@pytest.mark.asyncio
async def test_submit_pipeline():
    payload = {"pipeline_id": "p1", "status": "running"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pipelines"
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["dot_source"] == "digraph { A -> B }"
        assert body["goal"] == "test goal"
        assert body["providers"] == {"llm": "openai"}
        return httpx.Response(200, json=payload)

    client = _make_client(handler)
    result = await client.submit_pipeline(
        dot_source="digraph { A -> B }",
        goal="test goal",
        providers={"llm": "openai"},
    )
    assert result == payload
    await client.close()


@pytest.mark.asyncio
async def test_submit_pipeline_minimal():
    """submit_pipeline with only dot_source (no goal, no providers)."""
    payload = {"pipeline_id": "p2", "status": "running"}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["dot_source"] == "digraph { X }"
        assert body["goal"] == ""
        assert "providers" not in body
        return httpx.Response(200, json=payload)

    client = _make_client(handler)
    result = await client.submit_pipeline(dot_source="digraph { X }")
    assert result == payload
    await client.close()


@pytest.mark.asyncio
async def test_cancel_pipeline():
    payload = {"pipeline_id": "p1", "status": "cancelling"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pipelines/p1/cancel"
        assert request.method == "POST"
        return httpx.Response(200, json=payload)

    client = _make_client(handler)
    result = await client.cancel_pipeline("p1")
    assert result == payload
    await client.close()


@pytest.mark.asyncio
async def test_get_questions():
    payload = [
        {"question_id": "q1", "text": "Approve deploy?", "status": "pending"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pipelines/p1/questions"
        return httpx.Response(200, json=payload)

    client = _make_client(handler)
    result = await client.get_questions("p1")
    assert result == payload
    await client.close()


@pytest.mark.asyncio
async def test_answer_question():
    payload = {"status": "answered"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pipelines/p1/questions/q1/answer"
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["answer"] == "yes"
        return httpx.Response(200, json=payload)

    client = _make_client(handler)
    result = await client.answer_question("p1", "q1", "yes")
    assert result == payload
    await client.close()


# ---------------------------------------------------------------------------
# Error-handling tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Pipeline not found"})

    client = _make_client(handler)
    with pytest.raises(PipelineNotFound) as exc_info:
        await client.get_pipeline("missing")
    assert exc_info.value.status_code == 404
    assert "Pipeline not found" in str(exc_info.value)
    await client.close()


@pytest.mark.asyncio
async def test_already_completed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Pipeline already completed"})

    client = _make_client(handler)
    with pytest.raises(AlreadyCompleted) as exc_info:
        await client.cancel_pipeline("p1")
    assert exc_info.value.status_code == 409
    await client.close()


@pytest.mark.asyncio
async def test_invalid_dot():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "Invalid DOT syntax"})

    client = _make_client(handler)
    with pytest.raises(InvalidDOT) as exc_info:
        await client.submit_pipeline(dot_source="not valid dot")
    assert exc_info.value.status_code == 422
    await client.close()


@pytest.mark.asyncio
async def test_executor_not_configured():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "Executor not configured"})

    client = _make_client(handler)
    with pytest.raises(ExecutorNotConfigured) as exc_info:
        await client.submit_pipeline(dot_source="digraph { A }")
    assert exc_info.value.status_code == 503
    await client.close()


@pytest.mark.asyncio
async def test_generic_server_error():
    """Other 4xx/5xx should raise base DashboardError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "Internal server error"})

    client = _make_client(handler)
    with pytest.raises(DashboardError) as exc_info:
        await client.list_pipelines()
    assert exc_info.value.status_code == 500
    # Should NOT be one of the specific subclasses
    assert type(exc_info.value) is DashboardError
    await client.close()


# ---------------------------------------------------------------------------
# SSE streaming test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_events():
    sse_text = _sse_body(
        ("node_started", {"node_id": "gather", "status": "running"}),
        ("node_completed", {"node_id": "gather", "status": "completed"}),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pipelines/p1/events"
        return httpx.Response(
            200,
            content=sse_text,
            headers={"content-type": "text/event-stream"},
        )

    client = _make_client(handler)
    events: list[dict] = []
    async for event in client.stream_events("p1"):
        events.append(event)

    assert len(events) == 2
    assert events[0] == {
        "event": "node_started",
        "data": {"node_id": "gather", "status": "running"},
    }
    assert events[1] == {
        "event": "node_completed",
        "data": {"node_id": "gather", "status": "completed"},
    }
    await client.close()


@pytest.mark.asyncio
async def test_stream_events_skips_comments():
    """SSE comment lines (starting with ':') should be silently ignored."""
    lines = "\n".join(
        [
            ": this is a comment",
            "event: heartbeat",
            "data: {}",
            "",
            ": another comment",
            "event: node_started",
            'data: {"node_id": "A"}',
            "",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=lines,
            headers={"content-type": "text/event-stream"},
        )

    client = _make_client(handler)
    events = [e async for e in client.stream_events("p1")]
    assert len(events) == 2
    assert events[0] == {"event": "heartbeat", "data": {}}
    assert events[1] == {"event": "node_started", "data": {"node_id": "A"}}
    await client.close()


# ---------------------------------------------------------------------------
# Context manager test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager():
    """async with should work and close the underlying client."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    async with _make_client(handler) as client:
        result = await client.list_pipelines()
        assert result == []

    # After exiting the context manager, the httpx client should be closed
    assert client._client.is_closed

"""Tests for human gate question/answer lifecycle."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.pipeline_executor import (
    PendingQuestion,
    PipelineExecutor,
)
from amplifier_dashboard_attractor.server import create_app


@pytest.mark.asyncio
async def test_pending_question_creation():
    """PendingQuestion is created with correct fields."""
    q = PendingQuestion(
        question_id="q1",
        pipeline_id="p1",
        node_id="review",
        prompt="Approve changes?",
        options=["approve", "revise"],
        created_at="2026-02-25T00:00:00",
    )
    assert q.question_id == "q1"
    assert q.answer is None
    assert isinstance(q.answer_event, asyncio.Event)
    assert not q.answer_event.is_set()


@pytest.mark.asyncio
async def test_register_question():
    """register_question() stores the question and it's retrievable."""
    executor = PipelineExecutor()
    executor.active_pipelines["p1"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }

    q = PendingQuestion(
        question_id="q1",
        pipeline_id="p1",
        node_id="review",
        prompt="Approve?",
        options=["yes", "no"],
        created_at="2026-02-25T00:00:00",
    )
    executor.register_question("p1", q)

    questions = executor.get_questions("p1")
    assert len(questions) == 1
    assert questions[0].question_id == "q1"


@pytest.mark.asyncio
async def test_answer_question_sets_answer_and_signals():
    """answer_question() sets the answer and signals the event."""
    executor = PipelineExecutor()
    executor.active_pipelines["p1"] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }

    q = PendingQuestion(
        question_id="q1",
        pipeline_id="p1",
        node_id="review",
        prompt="Approve?",
        options=["yes", "no"],
        created_at="2026-02-25T00:00:00",
    )
    executor.register_question("p1", q)

    result = executor.answer_question("p1", "q1", "yes")
    assert result is True
    assert q.answer == "yes"
    assert q.answer_event.is_set()


@pytest.mark.asyncio
async def test_answer_question_unknown_pipeline():
    """answer_question() returns False for unknown pipeline."""
    executor = PipelineExecutor()
    assert executor.answer_question("nonexistent", "q1", "yes") is False


@pytest.mark.asyncio
async def test_answer_question_unknown_question():
    """answer_question() returns False for unknown question ID."""
    executor = PipelineExecutor()
    executor.questions["p1"] = {}
    assert executor.answer_question("p1", "nonexistent", "yes") is False


@pytest.mark.asyncio
async def test_answer_question_already_answered():
    """answer_question() returns False if already answered."""
    executor = PipelineExecutor()

    q = PendingQuestion(
        question_id="q1",
        pipeline_id="p1",
        node_id="review",
        prompt="Approve?",
        options=["yes", "no"],
        created_at="2026-02-25T00:00:00",
    )
    q.answer = "yes"  # already answered
    q.answer_event.set()
    executor.questions["p1"] = {"q1": q}

    assert executor.answer_question("p1", "q1", "no") is False


@pytest.mark.asyncio
async def test_get_questions_unknown_pipeline():
    """get_questions() returns empty list for unknown pipeline."""
    executor = PipelineExecutor()
    assert executor.get_questions("nonexistent") == []


@pytest.mark.asyncio
async def test_question_status_pipeline_not_found():
    """question_status() returns 'pipeline_not_found' for unknown pipeline."""
    executor = PipelineExecutor()
    assert executor.question_status("nonexistent", "q1") == "pipeline_not_found"


@pytest.mark.asyncio
async def test_question_status_not_found():
    """question_status() returns 'not_found' for unknown question ID."""
    executor = PipelineExecutor()
    executor.questions["p1"] = {}
    assert executor.question_status("p1", "q99") == "not_found"


@pytest.mark.asyncio
async def test_question_status_pending():
    """question_status() returns 'pending' for unanswered question."""
    executor = PipelineExecutor()
    q = PendingQuestion(
        question_id="q1",
        pipeline_id="p1",
        node_id="review",
        prompt="Approve?",
        options=["yes", "no"],
        created_at="2026-02-25T00:00:00",
    )
    executor.questions["p1"] = {"q1": q}
    assert executor.question_status("p1", "q1") == "pending"


@pytest.mark.asyncio
async def test_question_status_answered():
    """question_status() returns 'answered' for already-answered question."""
    executor = PipelineExecutor()
    q = PendingQuestion(
        question_id="q1",
        pipeline_id="p1",
        node_id="review",
        prompt="Approve?",
        options=["yes", "no"],
        created_at="2026-02-25T00:00:00",
    )
    q.answer = "yes"
    executor.questions["p1"] = {"q1": q}
    assert executor.question_status("p1", "q1") == "answered"


# ---------------------------------------------------------------------------
# Endpoint tests (Task 6)
# ---------------------------------------------------------------------------


@pytest.fixture
def gate_app(tmp_path):
    return create_app(pipeline_logs_dir=str(tmp_path))


@pytest.fixture
async def gate_client(gate_app):
    transport = ASGITransport(app=gate_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _register_fake_pipeline_with_question(
    app, pipeline_id="gate-pipe", question_id="q1"
):
    """Helper: register a fake running pipeline with a pending question."""
    executor = app.state.pipeline_executor
    executor.active_pipelines[pipeline_id] = {
        "task": None,
        "status": "running",
        "logs_root": "/tmp/test",
    }
    executor.cancel_events[pipeline_id] = asyncio.Event()
    executor.event_history[pipeline_id] = []
    executor.event_subscribers[pipeline_id] = []

    q = PendingQuestion(
        question_id=question_id,
        pipeline_id=pipeline_id,
        node_id="human_review",
        prompt="Approve changes?",
        options=["approve", "revise"],
        created_at="2026-02-25T00:00:00",
    )
    executor.register_question(pipeline_id, q)
    return q


@pytest.mark.asyncio
async def test_get_questions_endpoint_not_found(gate_client):
    """GET /api/pipelines/{id}/questions returns 404 for unknown pipeline."""
    resp = await gate_client.get("/api/pipelines/unknown-id/questions")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_questions_endpoint_returns_pending(gate_app, gate_client):
    """GET /api/pipelines/{id}/questions returns pending questions."""
    _register_fake_pipeline_with_question(gate_app)

    resp = await gate_client.get("/api/pipelines/gate-pipe/questions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["question_id"] == "q1"
    assert body[0]["prompt"] == "Approve changes?"
    assert body[0]["options"] == ["approve", "revise"]
    assert "answer_event" not in body[0]  # internal field not serialized


@pytest.mark.asyncio
async def test_answer_question_endpoint_success(gate_app, gate_client):
    """POST /api/pipelines/{id}/questions/{qid}/answer answers the question."""
    q = _register_fake_pipeline_with_question(gate_app)

    resp = await gate_client.post(
        "/api/pipelines/gate-pipe/questions/q1/answer",
        json={"answer": "approve"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "answered"

    # Verify the question object was updated
    assert q.answer == "approve"
    assert q.answer_event.is_set()


@pytest.mark.asyncio
async def test_answer_question_endpoint_not_found(gate_client):
    """POST answer for unknown pipeline returns 404."""
    resp = await gate_client.post(
        "/api/pipelines/unknown/questions/q1/answer",
        json={"answer": "yes"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_answer_question_endpoint_conflict(gate_app, gate_client):
    """POST answer for already-answered question returns 409."""
    q = _register_fake_pipeline_with_question(gate_app)
    q.answer = "approve"
    q.answer_event.set()

    resp = await gate_client.post(
        "/api/pipelines/gate-pipe/questions/q1/answer",
        json={"answer": "revise"},
    )
    assert resp.status_code == 409

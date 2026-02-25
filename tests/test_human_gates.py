"""Tests for human gate question/answer lifecycle."""

import asyncio

import pytest

from amplifier_dashboard_attractor.pipeline_executor import (
    PendingQuestion,
    PipelineExecutor,
)


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

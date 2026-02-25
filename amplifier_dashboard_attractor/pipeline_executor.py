"""Background pipeline execution manager.

Manages asyncio tasks for running pipelines submitted via the HTTP API.
Each pipeline runs in its own background task, writing results to disk
where the pipeline_logs_reader picks them up.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class EventCaptureHook:
    """Captures pipeline events and pushes them to an asyncio.Queue.

    Used by the SSE endpoint to stream events to connected clients.
    """

    def __init__(self, queue: asyncio.Queue) -> None:
        self._queue = queue

    async def emit(self, event: str, data: dict) -> None:
        """Push an event onto the queue."""
        self._queue.put_nowait(
            {
                "event": event,
                "data": data,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )


@dataclass
class PendingQuestion:
    """A human gate question awaiting an answer.

    The answer_event is signaled when an answer is provided,
    allowing the blocked pipeline handler to resume.
    """

    question_id: str
    pipeline_id: str
    node_id: str
    prompt: str
    options: list[str]
    created_at: str
    answer: str | None = None
    answer_event: asyncio.Event = field(default_factory=asyncio.Event)


class PipelineExecutor:
    """Manages background pipeline execution tasks.

    Each submitted pipeline gets its own asyncio task. The executor
    tracks active tasks by pipeline_id and provides status queries.
    """

    def __init__(self) -> None:
        self.active_pipelines: dict[str, dict[str, Any]] = {}
        self.cancel_events: dict[str, asyncio.Event] = {}
        self.event_queues: dict[str, asyncio.Queue] = {}
        self.questions: dict[str, dict[str, PendingQuestion]] = {}

    async def start(
        self,
        *,
        pipeline_id: str,
        graph: Any,
        goal: str,
        logs_root: str,
        providers: dict[str, Any],
    ) -> None:
        """Start a pipeline in a background asyncio task."""
        # Run pipeline in a thread pool to avoid blocking the FastAPI event loop.
        # The engine's LLM calls are blocking — running them in the main event loop
        # would freeze all HTTP endpoints during execution.
        loop = asyncio.get_running_loop()
        task = loop.run_in_executor(
            None,  # default ThreadPoolExecutor
            self._run_pipeline_sync,
            pipeline_id,
            graph,
            goal,
            logs_root,
            providers,
        )
        # Wrap in a Task so we can track it
        task = asyncio.ensure_future(task)
        self.active_pipelines[pipeline_id] = {
            "task": task,
            "status": "running",
            "logs_root": logs_root,
        }
        self.cancel_events[pipeline_id] = asyncio.Event()
        self.event_queues[pipeline_id] = asyncio.Queue()

    def _run_pipeline_sync(
        self,
        pipeline_id: str,
        graph: Any,
        goal: str,
        logs_root: str,
        providers: dict[str, Any],
    ) -> None:
        """Synchronous wrapper that runs the async pipeline in its own event loop.

        Called from a thread pool via run_in_executor() so the main FastAPI
        event loop stays responsive during long-running LLM calls.
        """
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self._run_pipeline(pipeline_id, graph, goal, logs_root, providers)
            )
        finally:
            loop.close()

    async def _run_pipeline(
        self,
        pipeline_id: str,
        graph: Any,
        goal: str,
        logs_root: str,
        providers: dict[str, Any],
    ) -> None:
        """Execute a pipeline engine in the background."""
        try:
            from amplifier_module_loop_pipeline.context import PipelineContext
            from amplifier_module_loop_pipeline.engine import PipelineEngine
            from amplifier_module_loop_pipeline.handlers import HandlerRegistry

            context = PipelineContext()

            # Build backend from providers config (if available)
            backend = self._build_backend(providers)

            registry = HandlerRegistry(backend=backend)

            engine = PipelineEngine(
                graph=graph,
                context=context,
                handler_registry=registry,
                logs_root=logs_root,
            )

            outcome = await engine.run(goal=goal)

            status = "completed" if outcome.is_success else "failed"
            if pipeline_id in self.active_pipelines:
                self.active_pipelines[pipeline_id]["status"] = status

            logger.info(
                "Pipeline %s finished: %s",
                pipeline_id,
                outcome.status.value,
            )

        except Exception as exc:
            logger.error("Pipeline %s failed with exception: %s", pipeline_id, exc)
            if pipeline_id in self.active_pipelines:
                self.active_pipelines[pipeline_id]["status"] = "failed"
                self.active_pipelines[pipeline_id]["error"] = str(exc)
        finally:
            # Clean up transient per-pipeline resources.
            # Keep questions for a grace period (don't clean up immediately).
            self.cancel_events.pop(pipeline_id, None)
            self.event_queues.pop(pipeline_id, None)

    def _build_backend(self, providers: dict[str, Any]) -> Any | None:
        """Build a backend from provider configuration.

        Attempts to create a DirectProviderBackend with a real unified_llm
        Client.  Falls back to None (simulation mode) if the required
        packages are not installed or no API keys are available.
        """
        try:
            from amplifier_module_loop_pipeline import DirectProviderBackend

            # DirectProviderBackend with provider=None auto-creates a
            # unified_llm.Client from environment variables (ANTHROPIC_API_KEY,
            # OPENAI_API_KEY, etc.)
            return DirectProviderBackend(provider=None, tools={}, hooks=None)
        except Exception as exc:
            logger.warning("Could not create real backend, using simulation: %s", exc)
            return None

    def get_status(self, pipeline_id: str) -> str | None:
        """Get the current status of a pipeline."""
        info = self.active_pipelines.get(pipeline_id)
        if info is None:
            return None
        return info["status"]

    def cancel(self, pipeline_id: str) -> bool:
        """Request cancellation of a running pipeline.

        Returns True if cancellation was requested, False if pipeline
        not found or not in a cancellable state.
        """
        info = self.active_pipelines.get(pipeline_id)
        if info is None:
            return False
        if info["status"] != "running":
            return False
        info["status"] = "cancelling"
        cancel_event = self.cancel_events.get(pipeline_id)
        if cancel_event:
            cancel_event.set()
        return True

    def get_event_queue(self, pipeline_id: str) -> asyncio.Queue | None:
        """Get the event queue for a pipeline, or None if not found."""
        return self.event_queues.get(pipeline_id)

    def register_question(self, pipeline_id: str, question: PendingQuestion) -> None:
        """Register a pending question for a pipeline."""
        if pipeline_id not in self.questions:
            self.questions[pipeline_id] = {}
        self.questions[pipeline_id][question.question_id] = question

    def get_questions(self, pipeline_id: str) -> list[PendingQuestion]:
        """Get all pending (unanswered) questions for a pipeline."""
        pipeline_questions = self.questions.get(pipeline_id, {})
        return [q for q in pipeline_questions.values() if q.answer is None]

    def question_status(self, pipeline_id: str, question_id: str) -> str:
        """Return the status of a question.

        Returns 'pending', 'answered', 'not_found', or 'pipeline_not_found'.
        """
        pipeline_questions = self.questions.get(pipeline_id)
        if pipeline_questions is None:
            return "pipeline_not_found"
        question = pipeline_questions.get(question_id)
        if question is None:
            return "not_found"
        if question.answer is not None:
            return "answered"
        return "pending"

    def answer_question(self, pipeline_id: str, question_id: str, answer: str) -> bool:
        """Answer a pending question.

        Returns True if the answer was accepted, False if the question
        was not found or already answered.
        """
        pipeline_questions = self.questions.get(pipeline_id)
        if pipeline_questions is None:
            return False
        question = pipeline_questions.get(question_id)
        if question is None:
            return False
        if question.answer is not None:
            return False
        question.answer = answer
        question.answer_event.set()
        return True

    def cleanup_completed(self) -> int:
        """Remove completed/failed pipelines from tracking.

        Returns the number of pipelines cleaned up.
        """
        to_remove = [
            pid
            for pid, info in self.active_pipelines.items()
            if info["status"] in ("completed", "failed", "cancelled")
        ]
        for pid in to_remove:
            self.cancel_events.pop(pid, None)
            self.event_queues.pop(pid, None)
            self.questions.pop(pid, None)
            del self.active_pipelines[pid]
        return len(to_remove)

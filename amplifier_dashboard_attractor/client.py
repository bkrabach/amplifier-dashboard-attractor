"""Async Python client for the Amplifier Dashboard API.

Wraps all dashboard REST endpoints and SSE streaming.
Uses httpx directly — no dependency on amplifier-core.

Usage:
    async with DashboardClient("http://localhost:8050") as client:
        pipelines = await client.list_pipelines()
        async for event in client.stream_events(pipeline_id):
            print(event)
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DashboardError(Exception):
    """Base exception for dashboard client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class PipelineNotFound(DashboardError):
    """Raised when a pipeline is not found (404)."""


class AlreadyCompleted(DashboardError):
    """Raised when an action targets an already-completed pipeline (409)."""


class InvalidDOT(DashboardError):
    """Raised when submitted DOT source is invalid (422)."""


class ExecutorNotConfigured(DashboardError):
    """Raised when the pipeline executor is not configured (503)."""


# ---------------------------------------------------------------------------
# Status code → exception mapping
# ---------------------------------------------------------------------------

_STATUS_EXCEPTIONS: dict[int, type[DashboardError]] = {
    404: PipelineNotFound,
    409: AlreadyCompleted,
    422: InvalidDOT,
    503: ExecutorNotConfigured,
}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class DashboardClient:
    """Async client for the Amplifier Dashboard HTTP API.

    Args:
        base_url: Root URL of the dashboard server.
        _client: Optional pre-built ``httpx.AsyncClient`` (used by tests).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8050",
        *,
        _client: httpx.AsyncClient | None = None,
    ):
        self._client = _client or httpx.AsyncClient(base_url=base_url)

    # -- context manager -----------------------------------------------------

    async def __aenter__(self) -> DashboardClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # -- internal helpers ----------------------------------------------------

    def _handle_response(self, response: httpx.Response) -> None:
        """Raise a typed exception for non-2xx responses."""
        if response.is_success:
            return

        status = response.status_code
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text

        exc_cls = _STATUS_EXCEPTIONS.get(status, DashboardError)
        raise exc_cls(str(detail), status_code=status)

    # -- pipeline CRUD -------------------------------------------------------

    async def list_pipelines(self) -> list[dict]:
        """List all pipelines.  ``GET /api/pipelines``"""
        resp = await self._client.get("/api/pipelines")
        self._handle_response(resp)
        return resp.json()

    async def get_pipeline(self, pipeline_id: str) -> dict:
        """Get a single pipeline.  ``GET /api/pipelines/{id}``"""
        resp = await self._client.get(f"/api/pipelines/{pipeline_id}")
        self._handle_response(resp)
        return resp.json()

    async def get_node(self, pipeline_id: str, node_id: str) -> dict:
        """Get a node within a pipeline.  ``GET /api/pipelines/{id}/nodes/{nodeId}``"""
        resp = await self._client.get(f"/api/pipelines/{pipeline_id}/nodes/{node_id}")
        self._handle_response(resp)
        return resp.json()

    async def submit_pipeline(
        self,
        dot_source: str,
        goal: str = "",
        providers: dict | None = None,
    ) -> dict:
        """Submit a new pipeline.  ``POST /api/pipelines``"""
        body: dict = {"dot_source": dot_source, "goal": goal}
        if providers is not None:
            body["providers"] = providers
        resp = await self._client.post("/api/pipelines", json=body)
        self._handle_response(resp)
        return resp.json()

    async def cancel_pipeline(self, pipeline_id: str) -> dict:
        """Cancel a running pipeline.  ``POST /api/pipelines/{id}/cancel``"""
        resp = await self._client.post(f"/api/pipelines/{pipeline_id}/cancel")
        self._handle_response(resp)
        return resp.json()

    # -- human-in-the-loop questions -----------------------------------------

    async def get_questions(self, pipeline_id: str) -> list[dict]:
        """Get pending questions.  ``GET /api/pipelines/{id}/questions``"""
        resp = await self._client.get(f"/api/pipelines/{pipeline_id}/questions")
        self._handle_response(resp)
        return resp.json()

    async def answer_question(
        self, pipeline_id: str, question_id: str, answer: str
    ) -> dict:
        """Answer a question.  ``POST /api/pipelines/{id}/questions/{qid}/answer``"""
        resp = await self._client.post(
            f"/api/pipelines/{pipeline_id}/questions/{question_id}/answer",
            json={"answer": answer},
        )
        self._handle_response(resp)
        return resp.json()

    # -- SSE event streaming -------------------------------------------------

    async def stream_events(self, pipeline_id: str) -> AsyncIterator[dict]:
        """Stream pipeline events via SSE.

        ``GET /api/pipelines/{id}/events``

        Yields dicts of the form ``{"event": "<type>", "data": <parsed-json>}``.
        """
        url = f"/api/pipelines/{pipeline_id}/events"
        async with self._client.stream("GET", url) as response:
            self._handle_response(response)

            event_type: str | None = None
            data_buf: list[str] = []

            async for line in response.aiter_lines():
                # Skip SSE comments
                if line.startswith(":"):
                    continue

                if line.startswith("event:"):
                    event_type = line[len("event:") :].strip()

                elif line.startswith("data:"):
                    data_buf.append(line[len("data:") :].strip())

                elif line == "":
                    # Empty line = end of event
                    if data_buf:
                        raw = "\n".join(data_buf)
                        try:
                            parsed = json.loads(raw)
                        except json.JSONDecodeError:
                            parsed = raw
                        yield {
                            "event": event_type or "message",
                            "data": parsed,
                        }
                    event_type = None
                    data_buf = []

            # Flush any remaining buffered event (stream closed without
            # a trailing blank line).
            if data_buf:
                raw = "\n".join(data_buf)
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = raw
                yield {
                    "event": event_type or "message",
                    "data": parsed,
                }

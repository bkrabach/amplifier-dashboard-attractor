"""Pipeline control endpoints — cancel, SSE events, human gates.

POST /api/pipelines/{pipeline_id}/cancel
GET  /api/pipelines/{pipeline_id}/events        (added in Task 4)
GET  /api/pipelines/{pipeline_id}/questions      (added in Task 6)
POST /api/pipelines/{pipeline_id}/questions/{question_id}/answer  (added in Task 6)
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse

router = APIRouter(prefix="/api/pipelines", tags=["control"])


def _get_executor(request: Request):
    """Get the pipeline executor from app state, or raise 503."""
    executor = getattr(request.app.state, "pipeline_executor", None)
    if executor is None:
        raise HTTPException(status_code=503, detail="Pipeline executor not available")
    return executor


@router.post("/{pipeline_id}/cancel")
async def cancel_pipeline(request: Request, pipeline_id: str):
    """Cancel a running pipeline.

    Returns 404 if pipeline not found.
    Returns 409 if pipeline already completed/failed (not cancellable).
    Returns 200 with cancelling status on success.
    """
    executor = _get_executor(request)

    status = executor.get_status(pipeline_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found")

    cancelled = executor.cancel(pipeline_id)
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline {pipeline_id} is {status}, cannot cancel",
        )

    return {"pipeline_id": pipeline_id, "status": "cancelling"}


@router.get("/{pipeline_id}/events")
async def pipeline_events(request: Request, pipeline_id: str):
    """Stream pipeline events as Server-Sent Events.

    Returns 404 if pipeline not found.
    Streams SSE-formatted events from the pipeline's event queue.
    Closes when pipeline completes, fails, or is cancelled.
    """
    executor = _get_executor(request)

    status = executor.get_status(pipeline_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found")

    queue = executor.get_event_queue(pipeline_id)
    if queue is None:
        raise HTTPException(
            status_code=404, detail=f"No event stream for {pipeline_id}"
        )

    async def event_generator():
        """Yield SSE-formatted strings from the event queue."""
        # Send initial connected event
        yield f"event: connected\ndata: {json.dumps({'pipeline_id': pipeline_id})}\nretry: 2000\n\n"

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive comment
                yield ": keepalive\n\n"
                continue

            event_type = item["event"]
            data = json.dumps(item["data"])
            yield f"event: {event_type}\ndata: {data}\n\n"

            # Close stream on terminal events
            if event_type == "pipeline:complete":
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

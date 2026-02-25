"""Pipeline control endpoints — cancel, SSE events, human gates.

POST /api/pipelines/{pipeline_id}/cancel
GET  /api/pipelines/{pipeline_id}/events        (added in Task 4)
GET  /api/pipelines/{pipeline_id}/questions      (added in Task 6)
POST /api/pipelines/{pipeline_id}/questions/{question_id}/answer  (added in Task 6)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

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

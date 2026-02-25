"""Pipeline submission endpoints.

POST /api/pipelines  — Submit DOT source + goal, start async execution.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["submissions"])


class PipelineSubmission(BaseModel):
    """Request body for pipeline submission."""

    dot_source: str = Field(..., description="DOT digraph source")
    goal: str = Field("", description="Pipeline goal")
    providers: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider configs: {provider_name: {api_key, default_model}}",
    )


@router.post("/api/pipelines", status_code=201)
async def submit_pipeline(request: Request, submission: PipelineSubmission):
    """Submit a pipeline for execution.

    1. Parse and validate the DOT source
    2. Create a logs_root directory
    3. Write graph.dot to the directory
    4. Start background execution (if executor available)
    5. Return pipeline_id + status immediately
    """
    # Lazy import to avoid hard dependency on the pipeline module
    try:
        from amplifier_module_loop_pipeline.dot_parser import parse_dot
        from amplifier_module_loop_pipeline.validation import (
            ValidationError,
            validate_or_raise,
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Pipeline engine module (amplifier-module-loop-pipeline) not installed",
        )

    # 1. Parse DOT
    try:
        graph = parse_dot(submission.dot_source)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid DOT source: {exc}")

    # 2. Validate
    try:
        validate_or_raise(graph)
    except ValidationError as exc:
        messages = [d.message for d in exc.diagnostics if d.severity == "ERROR"]
        raise HTTPException(
            status_code=422,
            detail=f"DOT validation failed: {'; '.join(messages)}",
        )

    # 3. Create logs directory
    pipeline_id = f"{graph.name}-{uuid.uuid4().hex[:8]}"
    logs_base = _get_logs_base(request)
    logs_root = os.path.join(logs_base, pipeline_id)
    os.makedirs(logs_root, exist_ok=True)

    # Write graph.dot
    with open(os.path.join(logs_root, "graph.dot"), "w") as f:
        f.write(submission.dot_source)

    # Write manifest.json
    manifest = {
        "graph_name": graph.name,
        "goal": submission.goal,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
    }
    with open(os.path.join(logs_root, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    # 4. Start background execution (Task 8 adds this)
    executor = getattr(request.app.state, "pipeline_executor", None)
    if executor is not None:
        await executor.start(
            pipeline_id=pipeline_id,
            graph=graph,
            goal=submission.goal,
            logs_root=logs_root,
            providers=submission.providers,
        )

    # 5. Return immediately
    return {
        "pipeline_id": pipeline_id,
        "status": "running",
        "logs_root": logs_root,
    }


def _get_logs_base(request: Request) -> str:
    """Resolve the base directory for pipeline logs."""
    reader = getattr(request.app.state, "pipeline_logs_reader", None)
    if reader and reader.logs_dirs:
        return str(reader.logs_dirs[0])
    return "/tmp/attractor-pipelines"

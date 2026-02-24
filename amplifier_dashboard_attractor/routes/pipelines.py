"""Pipeline REST endpoints.

GET /api/pipelines                           — fleet summary
GET /api/pipelines/{context_id}              — full pipeline state
GET /api/pipelines/{context_id}/nodes/{node_id} — node detail
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from amplifier_dashboard_attractor.mock_data import get_mock_fleet, get_mock_pipeline

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


@router.get("")
async def list_pipelines(request: Request):
    """Fleet view: list all pipeline instances with summary data."""
    if request.app.state.mock:
        return get_mock_fleet()

    # Live CXDB path (implemented when CXDB integration is ready)
    cxdb = request.app.state.cxdb_client
    contexts = await cxdb.search_pipelines()
    # TODO: enrich each context with metrics from state snapshots
    return contexts


@router.get("/{context_id}")
async def get_pipeline(request: Request, context_id: int):
    """Pipeline detail: full PipelineRunState including DOT source."""
    if request.app.state.mock:
        state = get_mock_pipeline(context_id)
        if state is None:
            raise HTTPException(
                status_code=404, detail=f"Pipeline {context_id} not found"
            )
        return state

    cxdb = request.app.state.cxdb_client
    state = await cxdb.get_pipeline_state(context_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Pipeline {context_id} not found")
    return state


@router.get("/{context_id}/nodes/{node_id}")
async def get_node(request: Request, context_id: int, node_id: str):
    """Node detail: node info + all run attempts."""
    if request.app.state.mock:
        pipeline = get_mock_pipeline(context_id)
        if pipeline is None:
            raise HTTPException(
                status_code=404, detail=f"Pipeline {context_id} not found"
            )
        node_info = pipeline.get("nodes", {}).get(node_id)
        if node_info is None:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
        runs = pipeline.get("node_runs", {}).get(node_id, [])
        return {
            "node_id": node_id,
            "info": node_info,
            "runs": runs,
            "edge_decisions": [
                d
                for d in pipeline.get("edge_decisions", [])
                if d["from_node"] == node_id
            ],
        }

    cxdb = request.app.state.cxdb_client
    events = await cxdb.get_node_events(context_id, node_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return {"node_id": node_id, "events": events}

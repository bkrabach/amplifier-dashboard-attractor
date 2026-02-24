"""WebSocket endpoint for real-time pipeline state updates.

Clients connect to ``/ws/pipelines/{context_id}`` and receive JSON
state snapshots whenever the underlying data changes.  The server
polls the active data source every 2 seconds and pushes diffs.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


def _state_fingerprint(state: dict) -> str:
    """Quick fingerprint to detect meaningful state changes.

    Compares status, completed count, current node, and error count —
    enough to avoid sending identical frames without deep-diffing the
    full state dict.
    """
    return (
        f"{state.get('status')}:"
        f"{state.get('nodes_completed')}:"
        f"{state.get('current_node')}:"
        f"{len(state.get('errors', []))}"
    )


@router.websocket("/ws/pipelines/{context_id}")
async def pipeline_ws(websocket: WebSocket, context_id: str) -> None:
    """Stream pipeline state updates to the client."""
    await websocket.accept()
    last_fingerprint: str | None = None

    try:
        while True:
            state: dict | None = None
            app = websocket.app

            # Resolve state from the active data source
            if hasattr(app.state, "pipeline_logs_reader"):
                state = await app.state.pipeline_logs_reader.get_pipeline_state(
                    context_id
                )
            elif hasattr(app.state, "session_reader"):
                state = await app.state.session_reader.get_pipeline_state(context_id)
            elif getattr(app.state, "mock", False):
                from amplifier_dashboard_attractor.mock_data import get_mock_pipeline

                state = get_mock_pipeline(_to_int(context_id))

            if state is not None:
                fp = _state_fingerprint(state)
                if fp != last_fingerprint:
                    await websocket.send_text(json.dumps(state))
                    last_fingerprint = fp

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected for context %s", context_id)
    except Exception:
        logger.exception("WebSocket error for context %s", context_id)


def _to_int(value: str) -> int:
    """Convert context_id to int for mock paths."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return -1

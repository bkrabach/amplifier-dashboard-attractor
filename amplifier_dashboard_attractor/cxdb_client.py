"""Thin async CXDB HTTP client for the dashboard.

Wraps the three CXDB HTTP API endpoints the dashboard needs.
No dependency on amplifier-core — uses httpx directly.

CXDB HTTP API reference:
  GET /v1/contexts/search?q={CQL}&limit={N}  — CQL context search
  GET /v1/contexts/{id}/turns?limit={N}       — turns with decoded payloads
"""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)


class CxdbClient:
    """Async HTTP client for querying CXDB.

    Usage:
        client = CxdbClient(base_url="http://localhost:8080")
        results = await client.search_pipelines()
        await client.close()
    """

    def __init__(
        self, base_url: str = "http://localhost:8080", *, timeout: float = 30.0
    ):
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def close(self):
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def search_pipelines(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Search CXDB for pipeline contexts.

        Uses CQL label search: `label = "pipeline_status:*"` for all pipelines,
        or `label = "pipeline_status:{status}"` for a specific status.

        Returns a list of context summary dicts.
        """
        if status:
            cql = f'label = "pipeline_status:{status}"'
        else:
            # Match any context with a pipeline_status label
            cql = 'label = "pipeline_status"'

        resp = await self._http.get(
            "/v1/contexts/search", params={"q": cql, "limit": limit}
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("contexts", [])

    async def get_pipeline_state(self, context_id: int) -> dict | None:
        """Get the latest PipelineRunState snapshot for a pipeline context.

        Fetches system turns and finds the most recent one with
        title="pipeline_state_snapshot". The content field contains the
        JSON-serialized PipelineRunState dict.

        Returns the parsed state dict, or None if no snapshot exists.
        """
        resp = await self._http.get(
            f"/v1/contexts/{context_id}/turns",
            params={"limit": 200, "include_unknown": 1, "bytes_render": "hex"},
        )
        resp.raise_for_status()
        turns = resp.json().get("turns", [])

        # Walk turns in reverse to find the latest snapshot
        snapshot_turn = None
        for turn in reversed(turns):
            data = turn.get("data", {})
            if data.get("item_type") != "system":
                continue
            system = data.get("system", {})
            if system.get("title") == "pipeline_state_snapshot":
                snapshot_turn = turn
                break

        if snapshot_turn is None:
            return None

        content = snapshot_turn["data"]["system"]["content"]
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Failed to parse pipeline_state_snapshot content for context %s",
                context_id,
            )
            return None

    async def get_node_events(self, context_id: int, node_id: str) -> list[dict]:
        """Get system turns related to a specific node.

        Filters turns where the system content field contains the node_id.
        Returns matching turn dicts.
        """
        resp = await self._http.get(
            f"/v1/contexts/{context_id}/turns",
            params={"limit": 200, "include_unknown": 1, "bytes_render": "hex"},
        )
        resp.raise_for_status()
        turns = resp.json().get("turns", [])

        return [
            turn
            for turn in turns
            if turn.get("data", {}).get("item_type") == "system"
            and node_id in turn.get("data", {}).get("system", {}).get("content", "")
        ]

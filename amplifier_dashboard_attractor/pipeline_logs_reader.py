"""Read pipeline state from the engine's own log directories.

The pipeline engine writes structured log files to a ``logs_root`` directory
(default: ``/tmp/attractor-pipeline/``) containing:

  manifest.json   — pipeline identity (graph_name, goal, start_time, …)
  checkpoint.json — full state (current_node, completed_nodes, node_outcomes, …)
  <node>/status.json  — per-node outcome (status, duration_ms, notes, …)
  <node>/prompt.md    — prompt sent to the LLM
  <node>/response.md  — LLM response (when available)

This reader is simpler and more reliable than parsing events.jsonl because
the data is written directly by the engine — no dependency on hook subscriptions
or mount ordering.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _path_to_id(path: Path) -> str:
    """Create a URL-safe identifier from a filesystem path.

    Uses the directory name plus a short hash suffix for uniqueness:
    ``/tmp/attractor-pipeline`` → ``attractor-pipeline-a1b2c3d4``
    """
    name = path.name or "pipeline"
    short_hash = hashlib.sha256(str(path).encode()).hexdigest()[:8]
    return f"{name}-{short_hash}"


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read and parse a JSON file, returning None on any error."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _read_text(path: Path) -> str | None:
    """Read a text file, returning None if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _derive_status(checkpoint: dict[str, Any]) -> str:
    """Derive pipeline status from checkpoint data.

    Returns "complete", "failed", "cancelled", "running", or "pending".
    """
    current = checkpoint.get("current_node", "")
    outcomes = checkpoint.get("node_outcomes", {})
    ctx = checkpoint.get("context", {})
    outcome = ctx.get("outcome", "")

    # Cancelled takes highest priority — check context and node outcomes
    if outcome == "cancelled":
        return "cancelled"
    for info in outcomes.values():
        if isinstance(info, dict) and info.get("failure_reason") == "cancelled":
            return "cancelled"

    # Pipeline reached terminal node → complete
    if current == "done":
        return "complete"

    # Explicit failure outcome in context
    if outcome in ("fail", "failed", "error"):
        return "failed"

    # Check if any node failed
    for info in outcomes.values():
        if isinstance(info, dict) and info.get("status") in ("fail", "failed", "error"):
            return "failed"

    # If we have completed nodes but current_node isn't "done", still running
    if checkpoint.get("completed_nodes"):
        return "running"

    return "pending"


def _build_pipeline_state(
    logs_dir: Path,
    manifest: dict[str, Any],
    checkpoint: dict[str, Any],
) -> dict[str, Any]:
    """Build a PipelineRunState-compatible dict from log files."""
    completed_nodes = checkpoint.get("completed_nodes", {})
    status = _derive_status(checkpoint)

    # Discover node directories (any subdir with a status.json)
    node_dirs: list[str] = []
    for entry in sorted(logs_dir.iterdir()):
        if entry.is_dir() and (entry / "status.json").is_file():
            node_dirs.append(entry.name)

    # Build nodes dict and node_runs from per-node status.json
    nodes: dict[str, Any] = {}
    node_runs: dict[str, list[dict[str, Any]]] = {}
    timing: dict[str, int] = {}
    total_duration_ms = 0
    execution_path: list[str] = []
    errors: list[dict[str, Any]] = []

    for node_id in node_dirs:
        node_status = _read_json(logs_dir / node_id / "status.json")
        if node_status is None:
            continue

        # Build node info
        nodes[node_id] = {
            "id": node_id,
            "label": node_id,
            "shape": "ellipse" if node_id == "start" else "box",
            "type": "",
            "prompt": "",
        }

        # Build node run entry
        duration_ms = int(node_status.get("duration_ms", 0))
        node_stat = node_status.get("status", node_status.get("outcome", "unknown"))
        run = {
            "status": "success" if node_stat == "success" else node_stat,
            "attempt": 1,
            "started_at": None,
            "completed_at": None,
            "duration_ms": duration_ms,
            "outcome_notes": node_status.get("notes", ""),
            "llm_calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "tokens_cached": 0,
        }
        node_runs[node_id] = [run]
        timing[node_id] = duration_ms
        total_duration_ms += duration_ms

        if node_id in completed_nodes:
            execution_path.append(node_id)

        # Capture failures as errors
        failure = node_status.get("failure_reason")
        if failure:
            errors.append(
                {
                    "node": node_id,
                    "message": failure,
                    "timestamp": "",
                }
            )

    # Use execution_path from completed_nodes order (preserves insertion order)
    if not execution_path:
        execution_path = list(completed_nodes.keys())

    nodes_completed = len([s for s in completed_nodes.values() if s == "success"])
    # node_count from manifest may be stale if the graph was extended at runtime
    nodes_total = max(manifest.get("node_count", len(nodes)), len(nodes))

    current_node = checkpoint.get("current_node")
    if current_node == "done":
        current_node = None

    return {
        "pipeline_id": manifest.get("graph_name", logs_dir.name),
        "dot_source": _read_text(logs_dir / "graph.dot") or "",
        "goal": manifest.get(
            "goal", checkpoint.get("context", {}).get("graph.goal", "")
        ),
        "nodes": nodes,
        "edges": [],  # Edge info not in logs
        "status": status,
        "current_node": current_node,
        "execution_path": execution_path,
        "branches_taken": [],
        "node_runs": node_runs,
        "edge_decisions": [],
        "loop_iterations": {},
        "goal_gate_checks": [],
        "parallel_branches": {},
        "subgraph_runs": {},
        "human_interactions": [],
        "supervisor_cycles": {},
        "total_elapsed_ms": total_duration_ms,
        "total_llm_calls": 0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "total_tokens_cached": 0,
        "total_tokens_reasoning": 0,
        "nodes_completed": nodes_completed,
        "nodes_total": nodes_total,
        "timing": timing,
        "errors": errors,
        "start_time": manifest.get("start_time", ""),
    }


class PipelineLogsReader:
    """Read pipeline state from the engine's log directories.

    Each directory in *logs_dirs* is checked for ``manifest.json`` —
    its presence indicates a pipeline log directory.
    """

    def __init__(self, logs_dirs: list[str]) -> None:
        self.logs_dirs = [Path(d).expanduser() for d in logs_dirs]
        # Mapping from URL-safe context_id → full Path (rebuilt on each scan)
        self._id_to_path: dict[str, Path] = {}

    def _find_log_dirs(self) -> list[Path]:
        """Return all directories that contain a manifest.json.

        Also rebuilds the ``_id_to_path`` mapping.
        """
        results: list[Path] = []
        self._id_to_path = {}
        for base in self.logs_dirs:
            if not base.is_dir():
                continue
            # Check if base itself is a pipeline log dir
            if (base / "manifest.json").is_file():
                results.append(base)
                self._id_to_path[_path_to_id(base)] = base
            # Also check immediate subdirectories (for multi-run layouts)
            for child in base.iterdir():
                if child.is_dir() and (child / "manifest.json").is_file():
                    results.append(child)
                    self._id_to_path[_path_to_id(child)] = child
        return results

    async def find_pipeline_sessions(self) -> list[dict[str, Any]]:
        """Scan logs_dirs for pipeline log directories.

        Returns fleet items matching the mock data format.
        """
        fleet: list[dict[str, Any]] = []
        for logs_dir in self._find_log_dirs():
            manifest = _read_json(logs_dir / "manifest.json")
            checkpoint = _read_json(logs_dir / "checkpoint.json")
            if manifest is None:
                continue
            if checkpoint is None:
                checkpoint = {}

            state = _build_pipeline_state(logs_dir, manifest, checkpoint)
            pipeline_id = state["pipeline_id"] or logs_dir.name

            fleet.append(
                {
                    "context_id": _path_to_id(logs_dir),
                    "pipeline_id": pipeline_id,
                    "status": state["status"],
                    "nodes_completed": state["nodes_completed"],
                    "nodes_total": state["nodes_total"],
                    "total_elapsed_ms": state["total_elapsed_ms"],
                    "total_tokens_in": state["total_tokens_in"],
                    "total_tokens_out": state["total_tokens_out"],
                    "goal": state["goal"],
                    "errors": state["errors"],
                    "start_time": state.get("start_time", ""),
                }
            )
        return fleet

    def _resolve_id(self, context_id: str) -> Path | None:
        """Resolve a URL-safe context_id to a filesystem Path.

        Triggers a directory scan if the mapping is empty.
        """
        if not self._id_to_path:
            self._find_log_dirs()
        return self._id_to_path.get(context_id)

    async def get_pipeline_state(self, context_id: str) -> dict[str, Any] | None:
        """Read full pipeline state from a log directory."""
        logs_dir = self._resolve_id(context_id)
        if logs_dir is None:
            return None
        manifest = _read_json(logs_dir / "manifest.json")
        checkpoint = _read_json(logs_dir / "checkpoint.json") or {}
        if manifest is None:
            return None
        return _build_pipeline_state(logs_dir, manifest, checkpoint)

    async def get_node_events(
        self, context_id: str, node_id: str
    ) -> dict[str, Any] | None:
        """Read a specific node's detail: status, prompt, response."""
        logs_dir = self._resolve_id(context_id)
        if logs_dir is None:
            return None

        state = await self.get_pipeline_state(context_id)
        if state is None:
            return None

        node_info = state.get("nodes", {}).get(node_id)
        if node_info is None:
            return None

        runs = state.get("node_runs", {}).get(node_id, [])
        edge_decisions = [
            d for d in state.get("edge_decisions", []) if d.get("from_node") == node_id
        ]

        # Read prompt and response from disk
        prompt = _read_text(logs_dir / node_id / "prompt.md")
        response = _read_text(logs_dir / node_id / "response.md")

        return {
            "node_id": node_id,
            "info": node_info,
            "runs": runs,
            "edge_decisions": edge_decisions,
            "prompt": prompt,
            "response": response,
        }

"""Read pipeline state from events.jsonl session files on disk.

Scans ~/.amplifier/projects/ for session directories and reconstructs
PipelineRunState dicts from the event stream. This bypasses CXDB entirely,
reading directly from the same event logs that the session-analyst uses.

Design constraints:
  - events.jsonl can be 100K+ lines — stream line by line, never load fully
  - Skip non-pipeline lines early (substring check before JSON parse)
  - Return dicts matching PipelineRunState.to_dict() shape from mock_data.py
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

# How many bytes to read when checking if a file has pipeline events.
# pipeline:start always appears near the top of events.jsonl.
_PEEK_BYTES = 8192

# Default cache TTL for find_pipeline_sessions results (seconds).
_CACHE_TTL_SECONDS = 30

# Default maximum age for session files to scan (hours).
_DEFAULT_MAX_AGE_HOURS = 24

# Event prefixes we care about — used for fast substring filtering
_PIPELINE_PREFIX = '"pipeline:'
_LLM_RESPONSE = '"llm:response"'
_SESSION_START = '"session:start"'
_SESSION_END = '"session:end"'

# All pipeline event names the aggregator handles
_PIPELINE_EVENTS = frozenset(
    {
        "pipeline:start",
        "pipeline:complete",
        "pipeline:node_start",
        "pipeline:node_complete",
        "pipeline:edge_selected",
        "pipeline:checkpoint",
        "pipeline:goal_gate_check",
        "pipeline:error",
        "pipeline:parallel_started",
        "pipeline:parallel_branch_started",
        "pipeline:parallel_branch_completed",
        "pipeline:parallel_complete",
    }
)


def _is_relevant_line(line: str) -> bool:
    """Fast check: does this line contain an event we care about?"""
    return (
        _PIPELINE_PREFIX in line
        or _LLM_RESPONSE in line
        or _SESSION_START in line
        or _SESSION_END in line
    )


def _iter_relevant_events(path: Path) -> Generator[dict[str, Any], None, None]:
    """Yield parsed JSON objects for relevant events only.

    Streams the file line-by-line, skipping irrelevant lines before parsing.
    Silently skips malformed lines.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or not _is_relevant_line(line):
                    continue
                try:
                    yield json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        return


def _has_pipeline_events(path: Path) -> bool:
    """Quick scan: does this events.jsonl contain any pipeline: events?

    Only reads the first ``_PEEK_BYTES`` of the file.  pipeline:start is
    always emitted near the top, so reading the whole file is unnecessary.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            head = fh.read(_PEEK_BYTES)
            return _PIPELINE_PREFIX in head
    except OSError:
        return False


def _empty_state() -> dict[str, Any]:
    """Return an empty PipelineRunState dict with all required fields."""
    return {
        "pipeline_id": "",
        "dot_source": "",
        "goal": "",
        "nodes": {},
        "edges": [],
        "status": "pending",
        "current_node": None,
        "execution_path": [],
        "branches_taken": [],
        "node_runs": {},
        "edge_decisions": [],
        "loop_iterations": {},
        "goal_gate_checks": [],
        "parallel_branches": {},
        "subgraph_runs": {},
        "human_interactions": [],
        "supervisor_cycles": {},
        "total_elapsed_ms": 0,
        "total_llm_calls": 0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "total_tokens_cached": 0,
        "total_tokens_reasoning": 0,
        "nodes_completed": 0,
        "nodes_total": 0,
        "timing": {},
        "errors": [],
    }


def reconstruct_pipeline_state(events_path: Path) -> dict[str, Any] | None:
    """Replay pipeline events from an events.jsonl to build PipelineRunState.

    Returns None if no pipeline:start event is found.
    """
    state = _empty_state()
    found_pipeline = False

    for event in _iter_relevant_events(events_path):
        ev_name = event.get("event", "")
        data = event.get("data", {})
        ts = event.get("ts", "")

        if ev_name == "pipeline:start":
            found_pipeline = True
            state["pipeline_id"] = data.get(
                "graph_name", data.get("pipeline_id", "unknown")
            )
            state["goal"] = data.get("goal", "")
            state["status"] = "running"
            state["nodes_total"] = data.get("node_count", 0)
            state["dot_source"] = data.get("dot_source", "")
            # Populate nodes from graph_nodes if provided
            for node in data.get("graph_nodes", []):
                nid = node.get("id", "")
                if nid:
                    state["nodes"][nid] = {
                        "id": nid,
                        "label": node.get("label", nid),
                        "shape": node.get("shape", "box"),
                        "type": node.get("type", ""),
                        "prompt": node.get("prompt", ""),
                    }
            # Populate edges from graph_edges if provided
            for edge in data.get("graph_edges", []):
                state["edges"].append(
                    {
                        "from_node": edge.get("from_node", ""),
                        "to_node": edge.get("to_node", ""),
                        "label": edge.get("label", ""),
                        "condition": edge.get("condition", ""),
                        "weight": edge.get("weight", 0),
                    }
                )

        elif ev_name == "pipeline:complete":
            status = data.get("status", "success")
            state["status"] = "failed" if status == "fail" else "complete"
            state["total_elapsed_ms"] = int(data.get("duration_ms", 0))
            if "total_nodes_executed" in data:
                state["nodes_completed"] = data["total_nodes_executed"]

        elif ev_name == "pipeline:node_start":
            node_id = data.get("node_id", "")
            state["current_node"] = node_id
            attempt = data.get("attempt", 1)
            run = {
                "status": "running",
                "attempt": attempt,
                "started_at": ts,
                "completed_at": None,
                "duration_ms": 0,
                "outcome_notes": None,
                "llm_calls": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "tokens_cached": 0,
            }
            state["node_runs"].setdefault(node_id, []).append(run)
            if node_id not in state["execution_path"]:
                state["execution_path"].append(node_id)

        elif ev_name == "pipeline:node_complete":
            node_id = data.get("node_id", "")
            status = data.get("status", "success")
            duration_ms = int(data.get("duration_ms", 0))
            runs = state["node_runs"].get(node_id, [])
            if runs:
                runs[-1]["status"] = status
                runs[-1]["completed_at"] = ts
                runs[-1]["duration_ms"] = duration_ms
            state["nodes_completed"] += 1
            state["timing"][node_id] = state["timing"].get(node_id, 0) + duration_ms
            state["current_node"] = None

        elif ev_name == "pipeline:edge_selected":
            edge = {
                "from_node": data.get("from_node", ""),
                "to_node": data.get("to_node", ""),
                "label": data.get("edge_label", ""),
                "condition": "",
                "weight": 0,
            }
            state["branches_taken"].append(edge)
            state["edge_decisions"].append(
                {
                    "from_node": data.get("from_node", ""),
                    "evaluated_edges": [],
                    "selected_edge": edge,
                    "reason": data.get("edge_label", "default"),
                }
            )

        elif ev_name == "pipeline:goal_gate_check":
            satisfied = data.get("satisfied", [])
            unsatisfied = data.get("unsatisfied", [])
            action = "complete" if not unsatisfied else "retry"
            state["goal_gate_checks"].append(
                {
                    "timestamp": ts,
                    "satisfied": satisfied,
                    "unsatisfied": unsatisfied,
                    "action": action,
                }
            )

        elif ev_name == "pipeline:error":
            state["status"] = "failed"
            state["errors"].append(
                {
                    "node_id": data.get("node_id", ""),
                    "error_type": data.get("error_type", ""),
                    "message": data.get("message", ""),
                }
            )

        elif ev_name == "llm:response":
            usage = data.get("usage", {})
            state["total_llm_calls"] += 1
            state["total_tokens_in"] += usage.get("input", 0)
            state["total_tokens_out"] += usage.get("output", 0)
            state["total_tokens_cached"] += usage.get("cache_read_input_tokens", 0)
            state["total_tokens_reasoning"] += usage.get("reasoning", 0)

    if not found_pipeline:
        return None

    return state


class SessionReader:
    """Scan session directories and reconstruct pipeline state from events.jsonl.

    Operates purely on the filesystem — no CXDB or network dependencies.
    """

    def __init__(self, projects_dir: str = "~/.amplifier/projects") -> None:
        self.projects_dir = Path(projects_dir).expanduser()
        # In-memory cache: (timestamp, results)
        self._fleet_cache: tuple[float, list[dict[str, Any]]] | None = None

    def _iter_session_dirs(
        self, *, max_age_hours: float | None = None
    ) -> Generator[Path, None, None]:
        """Yield session directories that contain events.jsonl.

        When *max_age_hours* is set, only directories whose ``events.jsonl``
        was modified within that window are yielded.  ``os.path.getmtime`` is
        a single stat call — much cheaper than opening the file.
        """
        if not self.projects_dir.is_dir():
            return

        cutoff: float | None = None
        if max_age_hours is not None:
            cutoff = time.time() - max_age_hours * 3600

        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            sessions_dir = project_dir / "sessions"
            if not sessions_dir.is_dir():
                continue
            for session_dir in sessions_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                events_file = session_dir / "events.jsonl"
                if not events_file.is_file():
                    continue
                if cutoff is not None:
                    try:
                        if os.path.getmtime(events_file) < cutoff:
                            continue
                    except OSError:
                        continue
                yield session_dir

    def _read_metadata(self, session_dir: Path) -> dict[str, Any]:
        """Read metadata.json from a session directory, returning {} on failure."""
        meta_path = session_dir / "metadata.json"
        try:
            with open(meta_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def _session_id_from_dir(self, session_dir: Path) -> str:
        """Extract a usable session identifier from the directory name."""
        return session_dir.name

    async def find_pipeline_sessions(
        self,
        *,
        max_age_hours: float = _DEFAULT_MAX_AGE_HOURS,
        cache_ttl: float = _CACHE_TTL_SECONDS,
    ) -> list[dict[str, Any]]:
        """Scan recent sessions, return those with pipeline events as fleet items.

        Returns list of dicts matching the PipelineFleetItem shape used by
        get_mock_fleet() — context_id, pipeline_id, status, nodes_*, tokens, etc.

        Performance controls:
          *max_age_hours* – only scan sessions whose ``events.jsonl`` was
              modified within this window (default 24h).  Set to ``0`` to
              disable the age filter and scan everything.
          *cache_ttl* – reuse a cached result if it is younger than this
              many seconds (default 30s).  Set to ``0`` to bypass the cache.
        """
        # --- cache check ---
        if cache_ttl > 0 and self._fleet_cache is not None:
            cached_at, cached_results = self._fleet_cache
            if time.time() - cached_at < cache_ttl:
                return cached_results

        # --- scan ---
        age = max_age_hours if max_age_hours > 0 else None
        fleet: list[dict[str, Any]] = []

        for session_dir in self._iter_session_dirs(max_age_hours=age):
            events_path = session_dir / "events.jsonl"
            if not _has_pipeline_events(events_path):
                continue

            state = reconstruct_pipeline_state(events_path)
            if state is None:
                continue

            metadata = self._read_metadata(session_dir)
            session_id = self._session_id_from_dir(session_dir)

            fleet.append(
                {
                    "context_id": session_id,
                    "pipeline_id": state["pipeline_id"],
                    "status": state["status"],
                    "nodes_completed": state["nodes_completed"],
                    "nodes_total": state["nodes_total"],
                    "total_elapsed_ms": state["total_elapsed_ms"],
                    "total_tokens_in": state["total_tokens_in"],
                    "total_tokens_out": state["total_tokens_out"],
                    "goal": state["goal"],
                    "errors": state["errors"],
                    # Extra metadata when available
                    "model": metadata.get("model", ""),
                    "bundle": metadata.get("profile", ""),
                    "created": metadata.get("created", ""),
                    "session_name": metadata.get("name", ""),
                }
            )

        # --- update cache ---
        self._fleet_cache = (time.time(), fleet)

        return fleet

    async def get_pipeline_state(self, session_id: str) -> dict[str, Any] | None:
        """Reconstruct full PipelineRunState from a session's events.jsonl.

        The session_id is the directory name under sessions/.
        """
        for session_dir in self._iter_session_dirs():
            if self._session_id_from_dir(session_dir) == session_id:
                events_path = session_dir / "events.jsonl"
                return reconstruct_pipeline_state(events_path)
        return None

    async def get_node_events(
        self, session_id: str, node_id: str
    ) -> dict[str, Any] | None:
        """Get node detail from a session's pipeline state.

        Returns dict with node_id, info, runs, edge_decisions — matching
        the mock mode response shape.
        """
        state = await self.get_pipeline_state(session_id)
        if state is None:
            return None

        node_info = state.get("nodes", {}).get(node_id)
        if node_info is None:
            # Node might exist in runs but not in static graph info
            if node_id not in state.get("node_runs", {}):
                return None
            node_info = {
                "id": node_id,
                "label": node_id,
                "shape": "box",
                "type": "",
                "prompt": "",
            }

        runs = state.get("node_runs", {}).get(node_id, [])
        edge_decisions = [
            d for d in state.get("edge_decisions", []) if d["from_node"] == node_id
        ]

        return {
            "node_id": node_id,
            "info": node_info,
            "runs": runs,
            "edge_decisions": edge_decisions,
        }

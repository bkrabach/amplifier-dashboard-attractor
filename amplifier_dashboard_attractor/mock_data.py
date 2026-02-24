"""Mock PipelineRunState data for --mock mode.

Provides realistic pipeline state dicts matching PipelineRunState.to_dict() output.
This enables full frontend development without a live CXDB instance.

Data model reference:
  amplifier-bundle-attractor/modules/hooks-pipeline-observability/
  amplifier_module_hooks_pipeline_observability/models.py
"""

from __future__ import annotations

# Each mock pipeline is keyed by a fake context_id for URL routing.
# context_id -> pipeline state dict
_MOCK_CONTEXT_IDS: list[int] = [1001, 1002, 1003]

MOCK_PIPELINES: list[dict] = [
    # Pipeline 1: "Research and Summarize" — mixed states (the main dev pipeline)
    {
        "pipeline_id": "research-summarize-001",
        "dot_source": (
            'digraph "Research and Summarize" {\n'
            "  rankdir=LR;\n"
            '  start [label="Start" shape=ellipse];\n'
            '  gather [label="Gather Sources" shape=box];\n'
            '  analyze [label="Analyze Content" shape=box];\n'
            '  synthesize [label="Synthesize" shape=box];\n'
            '  review [label="Review Quality" shape=diamond];\n'
            '  publish [label="Publish" shape=box];\n'
            "  start -> gather;\n"
            "  gather -> analyze;\n"
            "  analyze -> synthesize;\n"
            "  synthesize -> review;\n"
            '  review -> publish [label="pass"];\n'
            '  review -> synthesize [label="retry"];\n'
            "}\n"
        ),
        "goal": "Research the topic and produce a comprehensive summary",
        "nodes": {
            "start": {
                "id": "start",
                "label": "Start",
                "shape": "ellipse",
                "type": "",
                "prompt": "",
            },
            "gather": {
                "id": "gather",
                "label": "Gather Sources",
                "shape": "box",
                "type": "llm",
                "prompt": "Find and collect relevant sources on the given topic.",
            },
            "analyze": {
                "id": "analyze",
                "label": "Analyze Content",
                "shape": "box",
                "type": "llm",
                "prompt": "Analyze the collected sources for key themes.",
            },
            "synthesize": {
                "id": "synthesize",
                "label": "Synthesize",
                "shape": "box",
                "type": "llm",
                "prompt": "Combine analysis into a coherent summary.",
            },
            "review": {
                "id": "review",
                "label": "Review Quality",
                "shape": "diamond",
                "type": "llm",
                "prompt": "Evaluate whether the summary meets quality standards.",
            },
            "publish": {
                "id": "publish",
                "label": "Publish",
                "shape": "box",
                "type": "tool",
                "prompt": "",
            },
        },
        "edges": [
            {
                "from_node": "start",
                "to_node": "gather",
                "label": "",
                "condition": "",
                "weight": 0,
            },
            {
                "from_node": "gather",
                "to_node": "analyze",
                "label": "",
                "condition": "",
                "weight": 0,
            },
            {
                "from_node": "analyze",
                "to_node": "synthesize",
                "label": "",
                "condition": "",
                "weight": 0,
            },
            {
                "from_node": "synthesize",
                "to_node": "review",
                "label": "",
                "condition": "",
                "weight": 0,
            },
            {
                "from_node": "review",
                "to_node": "publish",
                "label": "pass",
                "condition": "quality >= 0.8",
                "weight": 1,
            },
            {
                "from_node": "review",
                "to_node": "synthesize",
                "label": "retry",
                "condition": "quality < 0.8",
                "weight": 0,
            },
        ],
        "status": "running",
        "current_node": "synthesize",
        "execution_path": ["start", "gather", "analyze", "synthesize"],
        "branches_taken": [],
        "node_runs": {
            "start": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T02:30:00",
                    "completed_at": "2026-02-24T02:30:00",
                    "duration_ms": 50,
                    "outcome_notes": "Pipeline initialized",
                    "llm_calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tokens_cached": 0,
                },
            ],
            "gather": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T02:30:01",
                    "completed_at": "2026-02-24T02:30:12",
                    "duration_ms": 11200,
                    "outcome_notes": "Found 8 relevant sources",
                    "llm_calls": 3,
                    "tokens_in": 4200,
                    "tokens_out": 1800,
                    "tokens_cached": 500,
                },
            ],
            "analyze": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T02:30:13",
                    "completed_at": "2026-02-24T02:30:28",
                    "duration_ms": 15400,
                    "outcome_notes": "Identified 5 key themes across sources",
                    "llm_calls": 2,
                    "tokens_in": 6100,
                    "tokens_out": 2400,
                    "tokens_cached": 1200,
                },
            ],
            "synthesize": [
                {
                    "status": "fail",
                    "attempt": 1,
                    "started_at": "2026-02-24T02:30:29",
                    "completed_at": "2026-02-24T02:30:45",
                    "duration_ms": 16000,
                    "outcome_notes": "Context window exceeded, retrying with summarized input",
                    "llm_calls": 1,
                    "tokens_in": 3200,
                    "tokens_out": 0,
                    "tokens_cached": 0,
                },
                {
                    "status": "running",
                    "attempt": 2,
                    "started_at": "2026-02-24T02:30:47",
                    "completed_at": None,
                    "duration_ms": 0,
                    "outcome_notes": None,
                    "llm_calls": 1,
                    "tokens_in": 2800,
                    "tokens_out": 0,
                    "tokens_cached": 0,
                },
            ],
        },
        "edge_decisions": [
            {
                "from_node": "gather",
                "evaluated_edges": [],
                "selected_edge": {
                    "from_node": "gather",
                    "to_node": "analyze",
                    "label": "",
                    "condition": "",
                    "weight": 0,
                },
                "reason": "default",
            },
        ],
        "loop_iterations": {},
        "goal_gate_checks": [],
        "parallel_branches": {},
        "subgraph_runs": {},
        "human_interactions": [],
        "supervisor_cycles": {},
        "total_elapsed_ms": 29500,
        "total_llm_calls": 6,
        "total_tokens_in": 13500,
        "total_tokens_out": 4200,
        "total_tokens_cached": 1700,
        "total_tokens_reasoning": 0,
        "nodes_completed": 3,
        "nodes_total": 6,
        "timing": {"start": 50, "gather": 11200, "analyze": 15400},
        "errors": [],
    },
    # Pipeline 2: "Code Review" — completed successfully
    {
        "pipeline_id": "code-review-042",
        "dot_source": (
            'digraph "Code Review" {\n'
            "  rankdir=LR;\n"
            '  fetch [label="Fetch PR"];\n'
            '  lint [label="Lint Check"];\n'
            '  review [label="AI Review"];\n'
            '  report [label="Write Report"];\n'
            "  fetch -> lint;\n"
            "  lint -> review;\n"
            "  review -> report;\n"
            "}\n"
        ),
        "goal": "Review pull request #187 for code quality issues",
        "nodes": {
            "fetch": {
                "id": "fetch",
                "label": "Fetch PR",
                "shape": "box",
                "type": "tool",
                "prompt": "",
            },
            "lint": {
                "id": "lint",
                "label": "Lint Check",
                "shape": "box",
                "type": "tool",
                "prompt": "",
            },
            "review": {
                "id": "review",
                "label": "AI Review",
                "shape": "box",
                "type": "llm",
                "prompt": "Review code for quality.",
            },
            "report": {
                "id": "report",
                "label": "Write Report",
                "shape": "box",
                "type": "llm",
                "prompt": "Summarize findings.",
            },
        },
        "edges": [
            {
                "from_node": "fetch",
                "to_node": "lint",
                "label": "",
                "condition": "",
                "weight": 0,
            },
            {
                "from_node": "lint",
                "to_node": "review",
                "label": "",
                "condition": "",
                "weight": 0,
            },
            {
                "from_node": "review",
                "to_node": "report",
                "label": "",
                "condition": "",
                "weight": 0,
            },
        ],
        "status": "complete",
        "current_node": None,
        "execution_path": ["fetch", "lint", "review", "report"],
        "branches_taken": [],
        "node_runs": {
            "fetch": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T02:00:00",
                    "completed_at": "2026-02-24T02:00:02",
                    "duration_ms": 2100,
                    "outcome_notes": "Fetched 12 files",
                    "llm_calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tokens_cached": 0,
                }
            ],
            "lint": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T02:00:03",
                    "completed_at": "2026-02-24T02:00:05",
                    "duration_ms": 1800,
                    "outcome_notes": "3 warnings, 0 errors",
                    "llm_calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tokens_cached": 0,
                }
            ],
            "review": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T02:00:06",
                    "completed_at": "2026-02-24T02:00:22",
                    "duration_ms": 16200,
                    "outcome_notes": "Found 2 issues",
                    "llm_calls": 4,
                    "tokens_in": 8500,
                    "tokens_out": 3200,
                    "tokens_cached": 2000,
                }
            ],
            "report": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T02:00:23",
                    "completed_at": "2026-02-24T02:00:31",
                    "duration_ms": 7800,
                    "outcome_notes": "Report generated",
                    "llm_calls": 1,
                    "tokens_in": 4200,
                    "tokens_out": 1800,
                    "tokens_cached": 0,
                }
            ],
        },
        "edge_decisions": [],
        "loop_iterations": {},
        "goal_gate_checks": [],
        "parallel_branches": {},
        "subgraph_runs": {},
        "human_interactions": [],
        "supervisor_cycles": {},
        "total_elapsed_ms": 27900,
        "total_llm_calls": 5,
        "total_tokens_in": 12700,
        "total_tokens_out": 5000,
        "total_tokens_cached": 2000,
        "total_tokens_reasoning": 0,
        "nodes_completed": 4,
        "nodes_total": 4,
        "timing": {"fetch": 2100, "lint": 1800, "review": 16200, "report": 7800},
        "errors": [],
    },
    # Pipeline 3: "Data Pipeline" — failed at node 3
    {
        "pipeline_id": "data-pipeline-007",
        "dot_source": (
            'digraph "Data Pipeline" {\n'
            "  rankdir=LR;\n"
            '  ingest [label="Ingest Data"];\n'
            '  validate [label="Validate Schema"];\n'
            '  transform [label="Transform"];\n'
            '  load [label="Load to DB"];\n'
            "  ingest -> validate;\n"
            "  validate -> transform;\n"
            "  transform -> load;\n"
            "}\n"
        ),
        "goal": "Process and load the Q4 dataset",
        "nodes": {
            "ingest": {
                "id": "ingest",
                "label": "Ingest Data",
                "shape": "box",
                "type": "tool",
                "prompt": "",
            },
            "validate": {
                "id": "validate",
                "label": "Validate Schema",
                "shape": "box",
                "type": "tool",
                "prompt": "",
            },
            "transform": {
                "id": "transform",
                "label": "Transform",
                "shape": "box",
                "type": "llm",
                "prompt": "Transform data.",
            },
            "load": {
                "id": "load",
                "label": "Load to DB",
                "shape": "box",
                "type": "tool",
                "prompt": "",
            },
        },
        "edges": [
            {
                "from_node": "ingest",
                "to_node": "validate",
                "label": "",
                "condition": "",
                "weight": 0,
            },
            {
                "from_node": "validate",
                "to_node": "transform",
                "label": "",
                "condition": "",
                "weight": 0,
            },
            {
                "from_node": "transform",
                "to_node": "load",
                "label": "",
                "condition": "",
                "weight": 0,
            },
        ],
        "status": "failed",
        "current_node": "transform",
        "execution_path": ["ingest", "validate", "transform"],
        "branches_taken": [],
        "node_runs": {
            "ingest": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T01:45:00",
                    "completed_at": "2026-02-24T01:45:05",
                    "duration_ms": 4800,
                    "outcome_notes": "Ingested 2.4GB",
                    "llm_calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tokens_cached": 0,
                }
            ],
            "validate": [
                {
                    "status": "success",
                    "attempt": 1,
                    "started_at": "2026-02-24T01:45:06",
                    "completed_at": "2026-02-24T01:45:08",
                    "duration_ms": 2100,
                    "outcome_notes": "Schema valid",
                    "llm_calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tokens_cached": 0,
                }
            ],
            "transform": [
                {
                    "status": "fail",
                    "attempt": 1,
                    "started_at": "2026-02-24T01:45:09",
                    "completed_at": "2026-02-24T01:45:30",
                    "duration_ms": 21000,
                    "outcome_notes": "Rate limit exceeded on OpenAI API",
                    "llm_calls": 2,
                    "tokens_in": 15000,
                    "tokens_out": 800,
                    "tokens_cached": 0,
                },
                {
                    "status": "fail",
                    "attempt": 2,
                    "started_at": "2026-02-24T01:45:45",
                    "completed_at": "2026-02-24T01:46:02",
                    "duration_ms": 17000,
                    "outcome_notes": "Rate limit still active",
                    "llm_calls": 1,
                    "tokens_in": 15000,
                    "tokens_out": 0,
                    "tokens_cached": 0,
                },
            ],
        },
        "edge_decisions": [],
        "loop_iterations": {},
        "goal_gate_checks": [],
        "parallel_branches": {},
        "subgraph_runs": {},
        "human_interactions": [],
        "supervisor_cycles": {},
        "total_elapsed_ms": 62000,
        "total_llm_calls": 3,
        "total_tokens_in": 30000,
        "total_tokens_out": 800,
        "total_tokens_cached": 0,
        "total_tokens_reasoning": 0,
        "nodes_completed": 2,
        "nodes_total": 4,
        "timing": {"ingest": 4800, "validate": 2100, "transform": 38000},
        "errors": [
            {
                "node": "transform",
                "message": "Rate limit exceeded after 2 retries",
                "timestamp": "2026-02-24T01:46:02",
            },
        ],
    },
]


def get_mock_pipeline(context_id: int) -> dict | None:
    """Get a mock pipeline state by its fake context_id."""
    try:
        idx = _MOCK_CONTEXT_IDS.index(context_id)
        return MOCK_PIPELINES[idx]
    except (ValueError, IndexError):
        return None


def get_mock_fleet() -> list[dict]:
    """Return fleet summary for all mock pipelines.

    Each item contains the fields needed by the fleet view table.
    """
    fleet = []
    for i, p in enumerate(MOCK_PIPELINES):
        fleet.append(
            {
                "context_id": _MOCK_CONTEXT_IDS[i],
                "pipeline_id": p["pipeline_id"],
                "status": p["status"],
                "nodes_completed": p["nodes_completed"],
                "nodes_total": p["nodes_total"],
                "total_elapsed_ms": p["total_elapsed_ms"],
                "total_tokens_in": p["total_tokens_in"],
                "total_tokens_out": p["total_tokens_out"],
                "goal": p["goal"],
                "errors": p["errors"],
            }
        )
    return fleet

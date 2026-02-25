# Consumer Readiness Design

## Goal

Make the Attractor Pipeline Dashboard server ready for consumption by the Amplifier Resolve team and other teams. Currently, the dashboard has a 17-line README, no client library, no agent tool, and no migration guidance — a consuming team can't discover or use the API without reading FastAPI source code.

## Background

The Attractor Pipeline Dashboard provides a FastAPI backend + React frontend for real-time pipeline monitoring and management. It exposes 10 HTTP endpoints for pipeline lifecycle operations including submission, status queries, SSE event streaming, cancellation, and human gate interactions.

The Resolve team is mid-transition from recipe-based pipeline execution (v1, container stdout parsing) to DOT-graph execution (v2). They currently poll container stdout with fragile string-matching (`__RECIPE_START__`, `__RESOLVE_WORKER_COMPLETE__`). The dashboard API replaces all of that with structured endpoints — but no one can discover or use those endpoints without reading the source.

## Key Design Decisions

1. **Dashboard README only** — NOT updating APP-INTEGRATION-GUIDE.md yet. The dashboard API path hasn't been production-tested by a real team. When a team uses it and we learn what works, then we prescribe best practices. For now, make the README self-contained and excellent.

2. **Client library inside the dashboard package** — not a separate pip package. Ship `amplifier_dashboard_attractor/client.py` alongside the server. One install gives you both server and client.

3. **Agent tool in the attractor bundle** — a `tool-dashboard-query` module that wraps the client, composable into any Amplifier session.

4. **Migration guide delivered separately** — written to the working directory for personal delivery to the Resolve team, not embedded in the dashboard repo.

## Scope Boundaries

- Dashboard README: comprehensive rewrite in the dashboard repo
- Python client: new file in the dashboard package
- Agent tool: new module in the attractor bundle
- Migration guide: standalone file in working directory (not committed to any repo)
- NO changes to APP-INTEGRATION-GUIDE.md or other attractor bundle docs

---

## Section 1: Dashboard README

Rewrite `amplifier-dashboard-attractor/README.md` as a comprehensive, self-contained document. This is the primary entry point for any consuming team.

### Project Overview

- What the dashboard does (real-time pipeline monitoring + management)
- Architecture: FastAPI backend + React frontend + React Flow graphs

### Quick Start

- Prerequisites (Python 3.11+, Node.js 18+, uv)
- Installation: clone repo, `uv pip install -e .`, `cd frontend && npm install`
- Running: 4 data source modes with their env vars:
  1. `DASHBOARD_MOCK=true` — mock data for development
  2. `PIPELINE_LOGS_DIR=/tmp/attractor-pipeline` — reads engine log dirs from disk + enables pipeline executor
  3. `SESSIONS_DIR=~/.amplifier/projects` — reads events.jsonl from Amplifier sessions
  4. Default — connects to CXDB at http://localhost:8080
- Frontend: `cd frontend && npm run dev` (dev) or `npm run build` (production, served by FastAPI)
- Generate sample data: `python scripts/generate_sample_data.py`

### API Reference

Complete table of all 10 endpoints with method, path, description, request body, and response shape. Include v1.0 and v1.1 endpoints.

### Curl Examples

One curl example per endpoint:

```bash
# Health check
curl http://localhost:8050/api/health

# List pipelines
curl http://localhost:8050/api/pipelines

# Get pipeline detail
curl http://localhost:8050/api/pipelines/{id}

# Get node detail
curl http://localhost:8050/api/pipelines/{id}/nodes/{nodeId}

# Submit pipeline
curl -X POST http://localhost:8050/api/pipelines \
  -H "Content-Type: application/json" \
  -d '{"dot_source": "digraph { start [shape=Mdiamond]; done [shape=Msquare]; start -> done }", "goal": "Test"}'

# Cancel pipeline
curl -X POST http://localhost:8050/api/pipelines/{id}/cancel

# Stream events (SSE)
curl -N http://localhost:8050/api/pipelines/{id}/events

# List pending questions
curl http://localhost:8050/api/pipelines/{id}/questions

# Answer question
curl -X POST http://localhost:8050/api/pipelines/{id}/questions/{qid}/answer \
  -H "Content-Type: application/json" \
  -d '{"answer": "approve"}'
```

### Python Client

Show `DashboardClient` usage:

```python
from amplifier_dashboard_attractor.client import DashboardClient

client = DashboardClient("http://localhost:8050")
pipelines = await client.list_pipelines()
result = await client.submit_pipeline(dot_source, goal="Build feature")
async for event in client.stream_events(result["pipeline_id"]):
    print(f"{event['event']}: {event['data']}")
```

### PIPELINE_LOGS_DIR Requirement

Clearly document that `POST /api/pipelines`, cancel, SSE events, and human gate endpoints require `PIPELINE_LOGS_DIR` to be set. Without it, these endpoints return `503 Service Unavailable`. This was previously undocumented and would confuse consuming teams.

### Data Source Modes

Explain each mode, when to use it, and what endpoints are available in each.

---

## Section 2: Python Client Library

Create `amplifier_dashboard_attractor/client.py` — an async Python client shipped inside the dashboard package itself.

### Interface

```python
class DashboardClient:
    def __init__(self, base_url: str = "http://localhost:8050"):
        self._base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url)

    # Read operations
    async def list_pipelines(self) -> list[dict]:
        """List all pipeline instances."""

    async def get_pipeline(self, pipeline_id: str) -> dict:
        """Get full pipeline state including DOT source."""

    async def get_node(self, pipeline_id: str, node_id: str) -> dict:
        """Get node detail with run history."""

    # Write operations
    async def submit_pipeline(self, dot_source: str, goal: str = "", providers: dict | None = None) -> dict:
        """Submit a DOT pipeline for execution. Returns {pipeline_id, status, logs_root}."""

    async def cancel_pipeline(self, pipeline_id: str) -> dict:
        """Cancel a running pipeline."""

    # Human gates
    async def get_questions(self, pipeline_id: str) -> list[dict]:
        """Get pending human gate questions."""

    async def answer_question(self, pipeline_id: str, question_id: str, answer: str) -> dict:
        """Answer a human gate question."""

    # Streaming
    async def stream_events(self, pipeline_id: str) -> AsyncIterator[dict]:
        """Stream pipeline events via SSE. Yields {"event": "...", "data": {...}}."""

    # Lifecycle
    async def close(self):
        """Close the underlying HTTP client."""

    async def __aenter__(self): return self
    async def __aexit__(self, *args): await self.close()
```

### Dependencies

- `httpx` for HTTP calls
- `httpx_sse` (or manual SSE line parsing) for the event stream

### Error Handling

Raises specific exceptions for known error codes:

| HTTP Status | Exception | Meaning |
|-------------|-----------|---------|
| 404 | `PipelineNotFound` | Pipeline ID does not exist |
| 409 | `AlreadyCompleted` | Pipeline already finished or cancelled |
| 422 | `InvalidDOT` | DOT source failed validation |
| 503 | `ExecutorNotConfigured` | PIPELINE_LOGS_DIR not set on server |

### Testing

Tests in `tests/test_client.py` using httpx mock transport or respx. No running dashboard server required.

---

## Section 3: Agent Tool for Pipeline Queries

Create `tool-dashboard-query` module in the attractor bundle at `modules/tool-dashboard-query/`.

### Purpose

Give Amplifier agents running inside a session the ability to check pipeline status, list running pipelines, submit new pipelines, and interact with human gates. Without this, agents are blind to pipeline progress.

### Tool Design

The module exposes a single `dashboard_query` tool with an `operation` parameter:

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `list_pipelines` | — | Returns fleet summary |
| `get_pipeline` | `pipeline_id` | Returns full pipeline state |
| `get_node` | `pipeline_id`, `node_id` | Returns node detail |
| `submit_pipeline` | `dot_source`, `goal` | Submits a new pipeline |
| `cancel_pipeline` | `pipeline_id` | Cancels a running pipeline |
| `get_questions` | `pipeline_id` | Lists pending human gate questions |
| `answer_question` | `pipeline_id`, `question_id`, `answer` | Answers a gate |

### Configuration

- `config.dashboard_url` — default `http://localhost:8050`

### Implementation

The tool uses `DashboardClient` from Section 2 internally. The mount function creates the client and registers the tool. This means the agent tool is a thin wrapper around the client library — no duplicated HTTP logic.

### Example Agent Interaction

An agent using this tool could say: "Let me check the pipeline status" then call `dashboard_query(operation="get_pipeline", pipeline_id="abc")`, get the full state back, and report to the user.

### Testing

Tests mock the HTTP calls (don't require a running dashboard server).

---

## Section 4: Resolve Team Migration Guide

Write `RESOLVE-MIGRATION-GUIDE.md` directly in the working directory (`/home/bkrabach/dev/attractor-next/`) for personal delivery to the team. NOT in the dashboard repo, NOT committed to any repo.

### Content

1. **What's available now:** The dashboard server with 10 API endpoints for pipeline lifecycle management.

2. **Before vs After:**
   - Before: `amplifier tool invoke recipes operation=execute recipe_path=...` then parse stdout for `__RECIPE_START__` / `__RESOLVE_WORKER_COMPLETE__` markers, then poll container for status
   - After: `POST /api/pipelines` with DOT source, `GET /api/pipelines/{id}` for status, `GET /api/pipelines/{id}/events` for real-time SSE stream

3. **How to use it:** Python client examples for their common operations (submit pipeline, poll status, stream events).

4. **What they gain:** Structured JSON status instead of stdout parsing, SSE event stream instead of text polling, human gate support via HTTP, cancellation, and the visual dashboard for free.

5. **The Python client:** How to install and use `DashboardClient`.

6. **Data source configuration:** How to set `PIPELINE_LOGS_DIR` to point at their pipeline logs.

### Tone

Informational ("here's what's available") not prescriptive ("you must do it this way"). This is a targeted migration note for one team we know is mid-transition, not a best-practice guide.

---

## Testing Strategy

| Item | Test Approach |
|------|---------------|
| Python client | Unit tests with mocked HTTP transport (httpx/respx) |
| Agent tool | Unit tests with mocked DashboardClient |
| README | Manual review (documentation) |
| Migration guide | Manual review (documentation) |

## Open Questions

- SSE parsing: use `httpx_sse` library or manual line parsing? Depends on whether we want the extra dependency.
- Should the Python client expose synchronous wrappers in addition to async, for simpler scripting use cases?
- Exact response shapes for the API reference table will be confirmed by reading the FastAPI route handlers during implementation.

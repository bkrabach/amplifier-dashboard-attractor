# Attractor Pipeline Dashboard

Real-time pipeline monitoring and management dashboard for the Attractor pipeline orchestration system. Provides an HTTP API for consuming pipeline execution data and a browser-based UI that visualizes directed pipeline graphs with live execution state overlaid.

Designed for teams that need to monitor, submit, and manage pipeline executions programmatically or through a visual interface.

**Architecture:** FastAPI backend serving a REST API and static SPA. React frontend using React Flow for interactive DAG visualization and ELK.js for automatic graph layout. Data sources are pluggable (mock, pipeline logs, session files, CXDB). The pipeline executor runs submitted pipelines as background asyncio tasks.

## Quick Start

**Prerequisites:** Python 3.11+, Node.js 18+ (for frontend development), [uv](https://docs.astral.sh/uv/).

```bash
cd amplifier-dashboard-attractor
uv sync
uv run dashboard --mock
```

Open http://localhost:8050 in your browser.

## Data Source Modes

The dashboard supports four data source modes. Configure with environment variables or CLI flags.

### 1. Mock Data

```bash
DASHBOARD_MOCK=true uv run dashboard
# or
uv run dashboard --mock
```

Generates synthetic pipeline data. Use for development and demos.

### 2. Pipeline Logs Directory

```bash
PIPELINE_LOGS_DIR=/path/to/logs uv run dashboard
```

Reads engine log directories from disk. Enables the pipeline executor, which provides pipeline submission, cancellation, SSE event streaming, and human gate interactions. This is the only mode that supports write operations.

### 3. Amplifier Session Files

```bash
SESSIONS_DIR=~/.amplifier/projects uv run dashboard
```

Reads `events.jsonl` files from Amplifier session directories. Provides read-only access to pipeline data captured in sessions.

### 4. CXDB (Default)

```bash
uv run dashboard
# or
CXDB_URL=http://localhost:8080 uv run dashboard
# or
uv run dashboard --cxdb-url http://custom-host:8080
```

Connects to a CXDB instance at http://localhost:8080 by default. Configure the URL with `CXDB_URL` or `--cxdb-url`.

## Pipeline Executor Requirement (PIPELINE_LOGS_DIR)

The following endpoints require `PIPELINE_LOGS_DIR` to be set. Without it, they return **503 Service Unavailable**:

- `POST /api/pipelines` -- submit a pipeline for execution
- `POST /api/pipelines/{id}/cancel` -- cancel a running pipeline
- `GET /api/pipelines/{id}/events` -- SSE event stream
- `GET /api/pipelines/{id}/questions` -- list pending human gate questions
- `POST /api/pipelines/{id}/questions/{qid}/answer` -- answer a question

The read-only endpoints (health, list pipelines, get pipeline, get node, WebSocket) work in all data source modes.

## API Reference

| Method | Path | Description | Requires Executor |
|--------|------|-------------|-------------------|
| GET | `/api/health` | Health check and data source info | No |
| GET | `/api/pipelines` | List all pipeline instances | No |
| GET | `/api/pipelines/{id}` | Get full pipeline state | No |
| GET | `/api/pipelines/{id}/nodes/{nodeId}` | Get node detail and run history | No |
| POST | `/api/pipelines` | Submit DOT pipeline for execution | Yes |
| POST | `/api/pipelines/{id}/cancel` | Cancel a running pipeline | Yes |
| GET | `/api/pipelines/{id}/events` | SSE event stream | Yes |
| GET | `/api/pipelines/{id}/questions` | List pending human gate questions | Yes |
| POST | `/api/pipelines/{id}/questions/{qid}/answer` | Answer a question | Yes |
| WS | `/ws/pipelines/{id}` | WebSocket real-time state updates | No |

### POST /api/pipelines

Request body:

```json
{
  "dot_source": "digraph { start [shape=Mdiamond]; done [shape=Msquare]; start -> done }",
  "goal": "Build feature X",
  "providers": {}
}
```

Response:

```json
{
  "pipeline_id": "...",
  "status": "running",
  "logs_root": "..."
}
```

### POST /api/pipelines/{id}/questions/{qid}/answer

Request body:

```json
{
  "answer": "approve"
}
```

## Curl Examples

```bash
# Health check
curl http://localhost:8050/api/health

# List pipelines
curl http://localhost:8050/api/pipelines

# Get pipeline detail
curl http://localhost:8050/api/pipelines/my-pipeline-abc123

# Get node detail
curl http://localhost:8050/api/pipelines/my-pipeline-abc123/nodes/build

# Submit pipeline
curl -X POST http://localhost:8050/api/pipelines \
  -H "Content-Type: application/json" \
  -d '{"dot_source": "digraph { start [shape=Mdiamond]; done [shape=Msquare]; start -> done }", "goal": "Test pipeline"}'

# Cancel pipeline
curl -X POST http://localhost:8050/api/pipelines/my-pipeline-abc123/cancel

# Stream events (SSE)
curl -N http://localhost:8050/api/pipelines/my-pipeline-abc123/events

# List pending questions
curl http://localhost:8050/api/pipelines/my-pipeline-abc123/questions

# Answer question
curl -X POST http://localhost:8050/api/pipelines/my-pipeline-abc123/questions/q1/answer \
  -H "Content-Type: application/json" \
  -d '{"answer": "approve"}'
```

## Python Client

The `DashboardClient` class provides async access to all dashboard endpoints.

```python
from amplifier_dashboard_attractor.client import DashboardClient

async with DashboardClient("http://localhost:8050") as client:
    # List pipelines
    pipelines = await client.list_pipelines()

    # Submit and monitor
    result = await client.submit_pipeline(
        dot_source='digraph { start -> done }',
        goal="Build feature X"
    )
    async for event in client.stream_events(result["pipeline_id"]):
        print(f"{event['event']}: {event['data']}")
```

## Frontend Development

For frontend development with hot reload:

```bash
cd frontend
npm install
npm run dev
```

This starts Vite on http://localhost:5173, proxying API requests to the backend.

To build for production (output is served by FastAPI at `/`):

```bash
cd frontend
npm run build
```

To generate sample data for development:

```bash
python scripts/generate_sample_data.py
```

## Architecture

The system has two main components:

- **Backend:** A FastAPI server that exposes the REST API, serves the static SPA, and manages WebSocket connections. Data source adapters are pluggable -- the backend loads mock data, reads pipeline log directories, parses Amplifier session files, or queries CXDB depending on configuration. When `PIPELINE_LOGS_DIR` is set, a pipeline executor manages submitted pipelines as background asyncio tasks.

- **Frontend:** A React application using React Flow for interactive, zoomable DAG visualization. ELK.js computes automatic hierarchical graph layouts. The frontend connects to the backend via REST for initial state and WebSocket for real-time updates.

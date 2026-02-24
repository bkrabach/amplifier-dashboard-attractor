# Attractor Pipeline Dashboard

Real-time pipeline monitoring dashboard for the Attractor pipeline orchestration system.
Visualizes directed pipeline graphs with execution state overlaid.

## Quick Start

Backend:
    cd amplifier-dashboard-attractor
    uv sync
    uv run dashboard --mock

## Architecture

- **Backend:** FastAPI server querying CXDB HTTP API, serving REST + static SPA
- **Frontend:** React + React Flow + ELK.js for DAG visualization
- **Data source:** CXDB (single source of truth) — no amplifier-core dependency
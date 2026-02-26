"""FastAPI server for the Attractor Pipeline Dashboard.

Thin stateless server that queries CXDB and serves JSON + static SPA files.

Data source resolution (first match wins):
  1. DASHBOARD_MOCK=true       → mock data (no external deps)
  2. PIPELINE_LOGS_DIR=<path>  → read pipeline engine log dirs from disk
  3. SESSIONS_DIR=<path>       → read events.jsonl from disk (no CXDB needed)
  4. Otherwise                 → live CXDB client
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from amplifier_dashboard_attractor.routes.pipelines import router as pipelines_router
from amplifier_dashboard_attractor.routes.submissions import (
    router as submissions_router,
)
from amplifier_dashboard_attractor.routes.ws import router as ws_router
from amplifier_dashboard_attractor.routes.control import router as control_router


def create_app(
    *,
    mock: bool = False,
    cxdb_url: str = "http://localhost:8080",
    pipeline_logs_dir: str | None = None,
    sessions_dir: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        mock: Use hardcoded mock data.
        cxdb_url: CXDB HTTP API base URL (used when not mock and no sessions_dir).
        pipeline_logs_dir: Path(s) to pipeline engine log dirs (comma-separated).
        sessions_dir: Path to ~/.amplifier/projects/ for reading events.jsonl files.
    """
    app = FastAPI(title="Attractor Pipeline Dashboard", version="0.1.0")

    # Store config in app state so routes can access it
    app.state.mock = mock
    app.state.sessions_dir = sessions_dir

    # CORS — allow Vite dev server during development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health():
        if mock:
            source = "mock"
        elif pipeline_logs_dir:
            source = "pipeline_logs"
        elif sessions_dir:
            source = "sessions"
        else:
            source = "cxdb"
        return {"status": "ok", "mock": app.state.mock, "data_source": source}

    # Register route modules
    app.include_router(pipelines_router)
    app.include_router(submissions_router)
    app.include_router(ws_router)
    app.include_router(control_router)

    # Initialize data source
    if pipeline_logs_dir:
        from amplifier_dashboard_attractor.pipeline_logs_reader import (
            PipelineLogsReader,
        )

        dirs = [d.strip() for d in pipeline_logs_dir.split(",") if d.strip()]
        app.state.pipeline_logs_reader = PipelineLogsReader(logs_dirs=dirs)

        # Initialize pipeline executor for background execution
        from amplifier_dashboard_attractor.pipeline_executor import PipelineExecutor

        app.state.pipeline_executor = PipelineExecutor()
    elif sessions_dir:
        from amplifier_dashboard_attractor.session_reader import SessionReader

        app.state.session_reader = SessionReader(projects_dir=sessions_dir)
    elif not mock:
        from amplifier_dashboard_attractor.cxdb_client import CxdbClient

        cxdb = CxdbClient(base_url=cxdb_url)
        app.state.cxdb_client = cxdb

        @app.on_event("shutdown")
        async def shutdown_cxdb():
            await cxdb.close()

    # Serve frontend static files if the dist/ directory exists
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        # SPA catch-all: serve index.html for any client-side route that doesn't
        # match an API route or a static asset request (file extension check).
        # Must be registered BEFORE the StaticFiles mount so FastAPI checks the
        # already-registered API routes first, then falls back here.
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            # Requests for static assets have a file extension — let StaticFiles
            # (mounted below) handle them; raise 404 if not found there.
            if "." in full_path.split("/")[-1]:
                raise HTTPException(status_code=404)
            return FileResponse(str(frontend_dist / "index.html"))

        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="spa")

    return app


def main():
    """CLI entry point: `dashboard [--mock] [--port PORT]`."""
    parser = argparse.ArgumentParser(description="Attractor Pipeline Dashboard")
    parser.add_argument(
        "--mock", action="store_true", help="Use mock data instead of CXDB"
    )
    parser.add_argument(
        "--port", type=int, default=8050, help="Server port (default: 8050)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--cxdb-url",
        default="http://localhost:8080",
        help="CXDB HTTP API base URL",
    )
    parser.add_argument(
        "--pipeline-logs-dir",
        default=None,
        help="Pipeline engine log directory (comma-separated for multiple)",
    )
    parser.add_argument(
        "--sessions-dir",
        default=None,
        help="Path to ~/.amplifier/projects/ for reading events.jsonl files",
    )
    args = parser.parse_args()

    # CLI flags take precedence; environment variables are fallbacks
    mock = args.mock or os.environ.get("DASHBOARD_MOCK", "").lower() in (
        "true",
        "1",
        "yes",
    )
    cxdb_url = args.cxdb_url
    if cxdb_url == "http://localhost:8080":  # still at default — check env
        cxdb_url = os.environ.get("CXDB_URL", cxdb_url)

    pipeline_logs_dir = (
        args.pipeline_logs_dir or os.environ.get("PIPELINE_LOGS_DIR") or None
    )
    sessions_dir = args.sessions_dir or os.environ.get("SESSIONS_DIR") or None

    app = create_app(
        mock=mock,
        cxdb_url=cxdb_url,
        pipeline_logs_dir=pipeline_logs_dir,
        sessions_dir=sessions_dir,
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

"""FastAPI server for the Attractor Pipeline Dashboard.

Thin stateless server that queries CXDB and serves JSON + static SPA files.
Supports a --mock flag for development without a live CXDB instance.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


def create_app(*, mock: bool = False) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Attractor Pipeline Dashboard", version="0.1.0")

    # Store mock flag in app state so routes can access it
    app.state.mock = mock

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
        return {"status": "ok", "mock": app.state.mock}

    # Serve frontend static files if the dist/ directory exists
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
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
    args = parser.parse_args()

    app = create_app(mock=args.mock)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

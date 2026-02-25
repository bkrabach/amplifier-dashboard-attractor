"""Background pipeline execution manager.

Manages asyncio tasks for running pipelines submitted via the HTTP API.
Each pipeline runs in its own background task, writing results to disk
where the pipeline_logs_reader picks them up.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """Manages background pipeline execution tasks.

    Each submitted pipeline gets its own asyncio task. The executor
    tracks active tasks by pipeline_id and provides status queries.
    """

    def __init__(self) -> None:
        self.active_pipelines: dict[str, dict[str, Any]] = {}

    async def start(
        self,
        *,
        pipeline_id: str,
        graph: Any,
        goal: str,
        logs_root: str,
        providers: dict[str, Any],
    ) -> None:
        """Start a pipeline in a background asyncio task."""
        task = asyncio.create_task(
            self._run_pipeline(pipeline_id, graph, goal, logs_root, providers),
            name=f"pipeline-{pipeline_id}",
        )
        self.active_pipelines[pipeline_id] = {
            "task": task,
            "status": "running",
            "logs_root": logs_root,
        }

    async def _run_pipeline(
        self,
        pipeline_id: str,
        graph: Any,
        goal: str,
        logs_root: str,
        providers: dict[str, Any],
    ) -> None:
        """Execute a pipeline engine in the background."""
        try:
            from amplifier_module_loop_pipeline.context import PipelineContext
            from amplifier_module_loop_pipeline.engine import PipelineEngine
            from amplifier_module_loop_pipeline.handlers import HandlerRegistry

            context = PipelineContext()

            # Build backend from providers config (if available)
            backend = self._build_backend(providers)

            registry = HandlerRegistry(backend=backend)

            engine = PipelineEngine(
                graph=graph,
                context=context,
                handler_registry=registry,
                logs_root=logs_root,
            )

            outcome = await engine.run(goal=goal)

            status = "completed" if outcome.is_success else "failed"
            if pipeline_id in self.active_pipelines:
                self.active_pipelines[pipeline_id]["status"] = status

            logger.info(
                "Pipeline %s finished: %s",
                pipeline_id,
                outcome.status.value,
            )

        except Exception as exc:
            logger.error("Pipeline %s failed with exception: %s", pipeline_id, exc)
            if pipeline_id in self.active_pipelines:
                self.active_pipelines[pipeline_id]["status"] = "failed"
                self.active_pipelines[pipeline_id]["error"] = str(exc)

    def _build_backend(self, providers: dict[str, Any]) -> Any | None:
        """Build a backend from provider configuration.

        Returns None if no providers are configured (simulation mode).
        """
        if not providers:
            return None
        # Future: build AmplifierBackend from provider configs
        return None

    def get_status(self, pipeline_id: str) -> str | None:
        """Get the current status of a pipeline."""
        info = self.active_pipelines.get(pipeline_id)
        if info is None:
            return None
        return info["status"]

    def cleanup_completed(self) -> int:
        """Remove completed/failed pipelines from tracking.

        Returns the number of pipelines cleaned up.
        """
        to_remove = [
            pid
            for pid, info in self.active_pipelines.items()
            if info["status"] in ("completed", "failed")
        ]
        for pid in to_remove:
            del self.active_pipelines[pid]
        return len(to_remove)

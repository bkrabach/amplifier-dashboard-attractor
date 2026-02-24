/**
 * REST API client for the dashboard backend.
 *
 * During development, Vite proxies /api/* to the FastAPI backend.
 * In production, the FastAPI server serves the SPA and the API is same-origin.
 */

import type { PipelineFleetItem, PipelineRunState, NodeDetail } from "./types";

const API_BASE = "/api";

async function fetchJSON<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${resp.statusText}`);
  }
  return resp.json();
}

export async function getPipelines(): Promise<PipelineFleetItem[]> {
  return fetchJSON<PipelineFleetItem[]>("/pipelines");
}

export async function getPipeline(
  contextId: string
): Promise<PipelineRunState> {
  return fetchJSON<PipelineRunState>(`/pipelines/${contextId}`);
}

export async function getNode(
  contextId: string,
  nodeId: string
): Promise<NodeDetail> {
  return fetchJSON<NodeDetail>(`/pipelines/${contextId}/nodes/${nodeId}`);
}

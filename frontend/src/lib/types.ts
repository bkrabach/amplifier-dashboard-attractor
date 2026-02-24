/**
 * TypeScript types matching PipelineRunState.to_dict() output.
 *
 * Data model reference:
 *   amplifier-bundle-attractor/modules/hooks-pipeline-observability/
 *   amplifier_module_hooks_pipeline_observability/models.py
 */

export interface NodeInfo {
  id: string;
  label: string;
  shape: string;
  type: string;
  prompt: string;
}

export interface EdgeInfo {
  from_node: string;
  to_node: string;
  label: string;
  condition: string;
  weight: number;
}

export interface NodeRun {
  status: "running" | "success" | "fail" | "timeout" | "partial_success";
  attempt: number;
  started_at: string;
  completed_at: string | null;
  duration_ms: number;
  outcome_notes: string | null;
  llm_calls: number;
  tokens_in: number;
  tokens_out: number;
  tokens_cached: number;
}

export interface EdgeDecision {
  from_node: string;
  evaluated_edges: unknown[];
  selected_edge: EdgeInfo;
  reason: string;
}

export interface PipelineRunState {
  pipeline_id: string;
  dot_source: string;
  goal: string;
  nodes: Record<string, NodeInfo>;
  edges: EdgeInfo[];
  status: "pending" | "running" | "complete" | "failed";
  current_node: string | null;
  execution_path: string[];
  branches_taken: EdgeInfo[];
  node_runs: Record<string, NodeRun[]>;
  edge_decisions: EdgeDecision[];
  loop_iterations: Record<string, number>;
  goal_gate_checks: unknown[];
  parallel_branches: Record<string, unknown[]>;
  subgraph_runs: Record<string, unknown>;
  human_interactions: unknown[];
  supervisor_cycles: Record<string, unknown[]>;
  total_elapsed_ms: number;
  total_llm_calls: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_tokens_cached: number;
  total_tokens_reasoning: number;
  nodes_completed: number;
  nodes_total: number;
  timing: Record<string, number>;
  errors: Array<{ node: string; message: string; timestamp: string }>;
}

export interface PipelineFleetItem {
  context_id: string;
  pipeline_id: string;
  status: string;
  nodes_completed: number;
  nodes_total: number;
  total_elapsed_ms: number;
  total_tokens_in: number;
  total_tokens_out: number;
  goal: string;
  errors: Array<{ node: string; message: string; timestamp: string }>;
}

export interface NodeDetail {
  node_id: string;
  info: NodeInfo;
  runs: NodeRun[];
  edge_decisions: EdgeDecision[];
}

/**
 * Resolve the effective state for a node based on its runs.
 * Used by the graph renderer to determine CSS class.
 */
export type NodeState =
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "retrying"
  | "skipped";

export function getNodeState(
  nodeId: string,
  state: PipelineRunState
): NodeState {
  const runs = state.node_runs[nodeId];
  if (!runs || runs.length === 0) return "pending";
  const lastRun = runs[runs.length - 1];
  if (lastRun.status === "running") return "running";
  if (lastRun.status === "success") return "success";
  if (lastRun.status === "fail" || lastRun.status === "timeout") {
    return "failed";
  }
  return "pending";
}

/**
 * DOT -> ELK -> React Flow layout pipeline.
 *
 * 1. Parse DOT source with ts-graphviz to extract topology (nodes, edges)
 * 2. Layout with ELK.js using the "layered" algorithm (designed for DAGs)
 * 3. Convert ELK positions to React Flow node/edge definitions
 *
 * The graph is laid out ONCE. Subsequent state changes only mutate CSS classes
 * on existing nodes -- no layout recalculation during execution.
 */

import ELK, { type ElkNode, type ElkExtendedEdge } from "elkjs/lib/elk.bundled.js";
import { fromDot } from "ts-graphviz";
import { MarkerType, type Node, type Edge } from "@xyflow/react";
import type { NodeInfo, PipelineRunState } from "./types";
import { getNodeState, type NodeState } from "./types";

const elk = new ELK();

/** Node dimensions (from design doc: 160px min-width) */
const NODE_WIDTH = 180;
const NODE_HEIGHT = 64;

export interface LayoutResult {
  nodes: Node<PipelineNodeData>[];
  edges: Edge[];
}

export interface PipelineNodeData {
  label: string;
  nodeId: string;
  nodeInfo: NodeInfo;
  state: NodeState;
  durationMs: number;
  tokensIn: number;
  tokensOut: number;
  loopCount: number;
  [key: string]: unknown;
}

/**
 * Extract node ID from a ts-graphviz edge target.
 * Targets can be NodeRef objects with an .id property or NodeRefGroup arrays.
 */
function extractNodeId(target: unknown): string {
  if (typeof target === "string") return target;
  if (target && typeof target === "object" && "id" in target) {
    return String((target as { id: unknown }).id);
  }
  return String(target);
}

/**
 * Parse DOT source and lay out with ELK, returning React Flow nodes and edges.
 */
export async function layoutPipeline(
  pipelineState: PipelineRunState
): Promise<LayoutResult> {
  // Step 1: Parse DOT source
  let dotNodes: string[] = [];
  let dotEdges: Array<{ source: string; target: string; label: string }> = [];

  try {
    const dotGraph = fromDot(pipelineState.dot_source);

    for (const node of dotGraph.nodes) {
      dotNodes.push(node.id);
    }

    for (const edge of dotGraph.edges) {
      const targets = edge.targets;
      // ts-graphviz chain edges like "a -> b -> c" have targets [a, b, c].
      // Iterate consecutive pairs to extract all edges in the chain.
      for (let i = 0; i < targets.length - 1; i++) {
        const fromId = extractNodeId(targets[i]);
        const toId = extractNodeId(targets[i + 1]);
        dotEdges.push({
          source: fromId,
          target: toId,
          label: (edge.attributes.get("label") as string) ?? "",
        });
      }
    }
  } catch {
    // Fallback: extract topology from PipelineRunState directly
    // (in case ts-graphviz can't parse this particular DOT format)
    dotNodes = Object.keys(pipelineState.nodes);
    dotEdges = pipelineState.edges.map((e) => ({
      source: e.from_node,
      target: e.to_node,
      label: e.label,
    }));
  }

  // Step 2: Build ELK graph
  const elkGraph: ElkNode = {
    id: "root",
    layoutOptions: {
      // Layered (Sugiyama) algorithm — best for DAGs
      "elk.algorithm": "layered",
      // Vertical top-to-bottom flow (pipeline reads naturally downward)
      "elk.direction": "DOWN",
      // Spacing between nodes in the same layer
      "elk.spacing.nodeNode": "50",
      // Spacing between layers (vertical distance between pipeline stages)
      "elk.layered.spacing.nodeNodeBetweenLayers": "80",
      // Edge routing: ORTHOGONAL routes edges around nodes with right-angle bends
      // (avoids edges going behind nodes on branches and loops)
      "elk.edgeRouting": "ORTHOGONAL",
      // Give edges more room to route around nodes
      "elk.spacing.edgeNode": "30",
      "elk.spacing.edgeEdge": "20",
      // Better handling of back-edges (loops/retries) — route them wider
      "elk.layered.feedbackEdges": "true",
      // Padding around the entire graph
      "elk.padding": "[top=30,left=30,bottom=30,right=30]",
    },
    children: dotNodes.map((id) => ({
      id,
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    })),
    edges: dotEdges.map((e, i) => ({
      id: `e${i}-${e.source}-${e.target}`,
      sources: [e.source],
      targets: [e.target],
    })) as ElkExtendedEdge[],
  };

  const layout = await elk.layout(elkGraph);

  // Step 3: Convert to React Flow format
  const nodes: Node<PipelineNodeData>[] = (layout.children ?? []).map(
    (elkNode) => {
      const nodeId = elkNode.id;
      const nodeInfo = pipelineState.nodes[nodeId] ?? {
        id: nodeId,
        label: nodeId,
        shape: "box",
        type: "",
        prompt: "",
      };
      const state = getNodeState(nodeId, pipelineState);
      const runs = pipelineState.node_runs[nodeId] ?? [];
      const lastRun = runs.length > 0 ? runs[runs.length - 1] : null;

      return {
        id: nodeId,
        type: "pipelineNode",
        position: { x: elkNode.x ?? 0, y: elkNode.y ?? 0 },
        data: {
          label: nodeInfo.label || nodeId,
          nodeId,
          nodeInfo,
          state,
          durationMs: lastRun?.duration_ms ?? 0,
          tokensIn: lastRun?.tokens_in ?? 0,
          tokensOut: lastRun?.tokens_out ?? 0,
          loopCount: pipelineState.loop_iterations[nodeId] ?? 0,
        },
      };
    }
  );

  // Build a lookup from edge ID to ELK's computed edge geometry.
  // ELK populates edge.sections with startPoint, bendPoints, and endPoint
  // after layout — this is the proper routed path that avoids node overlaps.
  const elkEdgeMap = new Map<string, (typeof layout.edges extends (infer E)[] | undefined ? E : never)>();
  for (const elkEdge of layout.edges ?? []) {
    elkEdgeMap.set(elkEdge.id, elkEdge);
  }

  const edges: Edge[] = dotEdges.map((e, i) => {
    // Determine edge visual state based on execution path
    const sourceIdx = pipelineState.execution_path.indexOf(e.source);
    const targetIdx = pipelineState.execution_path.indexOf(e.target);
    const isTraversed = sourceIdx >= 0 && targetIdx >= 0 && targetIdx > sourceIdx;

    const edgeId = `e${i}-${e.source}-${e.target}`;
    const elkEdge = elkEdgeMap.get(edgeId);
    const elkSections = elkEdge?.sections ?? [];

    return {
      id: edgeId,
      source: e.source,
      target: e.target,
      type: "pipelineEdge",
      label: e.label || undefined,
      data: {
        traversed: isTraversed,
        elkSections,
        sourceLabel: pipelineState.nodes[e.source]?.label || e.source,
        targetLabel: pipelineState.nodes[e.target]?.label || e.target,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: isTraversed ? "var(--text-secondary)" : "var(--text-tertiary)",
      },
    };
  });

  return { nodes, edges };
}

/**
 * Update node data in-place from a new PipelineRunState without re-computing
 * the ELK layout.  Only state, timing, and token fields change — positions
 * stay fixed so React Flow animates CSS transitions smoothly.
 */
export function updateNodeData(
  existingNodes: Node<PipelineNodeData>[],
  newState: PipelineRunState
): Node<PipelineNodeData>[] {
  return existingNodes.map((node) => {
    const nodeId = node.id;
    const state = getNodeState(nodeId, newState);
    const runs = newState.node_runs[nodeId] ?? [];
    const lastRun = runs.length > 0 ? runs[runs.length - 1] : null;
    const nodeInfo = newState.nodes[nodeId] ?? node.data.nodeInfo;

    return {
      ...node,
      data: {
        ...node.data,
        nodeInfo,
        state,
        durationMs: lastRun?.duration_ms ?? 0,
        tokensIn: lastRun?.tokens_in ?? 0,
        tokensOut: lastRun?.tokens_out ?? 0,
        loopCount: newState.loop_iterations[nodeId] ?? 0,
      },
    };
  });
}

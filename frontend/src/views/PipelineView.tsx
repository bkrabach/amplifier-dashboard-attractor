/**
 * Pipeline Detail View -- Level 2: graph + detail panel.
 *
 * Layout: CSS Grid
 *   Top: MetricsBar (48px)
 *   Main: Graph (flexible) + DetailPanel (360px)
 *
 * Fetches pipeline state via REST, then subscribes to WebSocket for live
 * updates.  Layout is computed once (DOT topology is stable); subsequent
 * WebSocket frames only update node data (state, timing) for CSS transitions.
 */

import { useParams, Link } from "react-router-dom";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { getPipeline, getNode } from "../lib/api";
import { layoutPipeline, updateNodeData } from "../lib/dotLayout";
import type { PipelineNodeData } from "../lib/dotLayout";
import type { PipelineRunState, NodeInfo, NodeRun, NodeDetail } from "../lib/types";
import { useWebSocket } from "../hooks/useWebSocket";
import PipelineNode from "../components/PipelineNode";
import PipelineEdge from "../components/PipelineEdge";
import MetricsBar from "../components/MetricsBar";
import DetailPanel from "../components/DetailPanel";

const nodeTypes: NodeTypes = { pipelineNode: PipelineNode };
const edgeTypes: EdgeTypes = { pipelineEdge: PipelineEdge };

export default function PipelineView() {
  const { contextId } = useParams<{ contextId: string }>();
  const [state, setState] = useState<PipelineRunState | null>(null);
  const [nodes, setNodes] = useState<Node<PipelineNodeData>[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const layoutDone = useRef(false);

  // Selected node for detail panel
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // WebSocket for live updates
  const { state: wsState, connected: wsConnected } = useWebSocket(contextId);

  // Initial REST fetch and layout
  useEffect(() => {
    if (!contextId) return;

    async function load() {
      try {
        const pipelineState = await getPipeline(contextId!);
        setState(pipelineState);

        const layout = await layoutPipeline(pipelineState);
        setNodes(layout.nodes);
        setEdges(layout.edges);
        layoutDone.current = true;
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load pipeline");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [contextId]);

  // Apply WebSocket state updates without re-computing layout
  useEffect(() => {
    if (!wsState || !layoutDone.current) return;
    setState(wsState);

    // Update node data in-place (state, timing, tokens) — no layout recalc
    setNodes((prev) => updateNodeData(prev, wsState));
  }, [wsState]);

  // Handle node click
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
    },
    []
  );

  // Derive selected node info
  const selectedNodeInfo: NodeInfo | null = useMemo(() => {
    if (!selectedNodeId || !state) return null;
    return state.nodes[selectedNodeId] ?? null;
  }, [selectedNodeId, state]);

  const selectedNodeRuns: NodeRun[] = useMemo(() => {
    if (!selectedNodeId || !state) return [];
    return state.node_runs[selectedNodeId] ?? [];
  }, [selectedNodeId, state]);

  // Lazy-fetch full node detail (prompt/response) on node click
  useEffect(() => {
    if (!selectedNodeId || !contextId) {
      setNodeDetail(null);
      return;
    }
    setDetailLoading(true);
    getNode(contextId, selectedNodeId)
      .then(setNodeDetail)
      .catch(() => setNodeDetail(null))
      .finally(() => setDetailLoading(false));
  }, [selectedNodeId, contextId]);

  if (loading) {
    return (
      <div style={{ padding: "var(--space-lg)", color: "var(--text-secondary)" }}>
        Loading pipeline...
      </div>
    );
  }

  if (error || !state) {
    return (
      <div style={{ padding: "var(--space-lg)", color: "var(--state-failed)" }}>
        {error ?? "Pipeline not found"}
      </div>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "auto 1fr",
        height: "calc(100vh - 41px)", /* Subtract header height */
      }}
    >
      {/* Breadcrumb + MetricsBar */}
      <div>
        <div
          style={{
            padding: "var(--space-xs) var(--space-lg)",
            fontSize: "0.8rem",
            color: "var(--text-tertiary)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-sm)",
          }}
        >
          <Link
            to="/pipelines"
            style={{ color: "var(--text-secondary)", textDecoration: "none" }}
          >
            Fleet
          </Link>
          {" / "}
          <span style={{ fontFamily: "var(--font-mono)" }}>
            {state.pipeline_id}
          </span>

          {/* Live indicator */}
          <span
            style={{
              marginLeft: "auto",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              fontSize: "0.75rem",
              color: wsConnected ? "var(--state-running)" : "var(--text-tertiary)",
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: wsConnected ? "var(--state-running)" : "var(--text-tertiary)",
                display: "inline-block",
                animation: wsConnected ? "breathe var(--pulse-duration) ease-in-out infinite" : "none",
              }}
            />
            {wsConnected ? "Live" : "Offline"}
          </span>
        </div>
        <MetricsBar state={state} />
      </div>

      {/* Graph + Detail Panel */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr var(--detail-panel-width)" }}>
        <div style={{ position: "relative" }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodeClick={onNodeClick}
            nodesDraggable={false}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
            style={{ background: "var(--surface-base)" }}
          >
            <Background variant={BackgroundVariant.Dots} color="var(--border-default)" gap={20} />
          </ReactFlow>
        </div>

        <DetailPanel
          nodeId={selectedNodeId}
          nodeInfo={selectedNodeInfo}
          runs={selectedNodeRuns}
          contextId={contextId ?? ""}
          prompt={nodeDetail?.prompt ?? null}
          response={nodeDetail?.response ?? null}
          edgeDecisions={nodeDetail?.edge_decisions ?? []}
          detailLoading={detailLoading}
          timing={state?.timing}
          loopIterations={state?.loop_iterations}
        />
      </div>
    </div>
  );
}

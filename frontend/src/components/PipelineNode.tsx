/**
 * Custom React Flow node for pipeline graph visualization.
 *
 * Displays: node label, duration, and state via CSS class.
 * State colors, borders, and animations are driven by CSS variables
 * and CSS classes defined in theme.css.
 *
 * Design reference (from design doc):
 *   +----------------------+
 *   |  [icon] Node Name    |  <- Inter 13px/500
 *   |  model-name . 2.3s   |  <- JetBrains Mono 11px/400
 *   +----------------------+
 */

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { PipelineNodeData } from "../lib/dotLayout";
import type { NodeState } from "../lib/types";

/** Static style properties per state (colors and border style). */
const STATE_STYLES: Record<
  NodeState,
  { border: string; borderStyle: string }
> = {
  pending: {
    border: "var(--state-pending)",
    borderStyle: "dashed",
  },
  running: {
    border: "var(--state-running)",
    borderStyle: "solid",
  },
  success: {
    border: "var(--state-success)",
    borderStyle: "solid",
  },
  failed: {
    border: "var(--state-failed)",
    borderStyle: "solid",
  },
  retrying: {
    border: "var(--state-retrying)",
    borderStyle: "dashed",
  },
  skipped: {
    border: "var(--state-skipped)",
    borderStyle: "dotted",
  },
};

/** Map node state to CSS animation class from theme.css. */
const STATE_CSS_CLASS: Partial<Record<NodeState, string>> = {
  running: "node--running",
  failed: "node--failed",
  success: "node--success",
};

function formatDuration(ms: number): string {
  if (ms === 0) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function PipelineNode({ data }: NodeProps) {
  const nodeData = data as unknown as PipelineNodeData;
  const style = STATE_STYLES[nodeData.state] ?? STATE_STYLES.pending;
  const animClass = STATE_CSS_CLASS[nodeData.state] ?? "";

  return (
    <>
      <Handle type="target" position={Position.Left} style={{ visibility: "hidden" }} />
      <div
        className={`nopan nodrag ${animClass}`}
        style={{
          minWidth: "var(--node-min-width)",
          background: "var(--surface-raised)",
          border: `2px ${style.borderStyle} ${style.border}`,
          borderRadius: "var(--node-border-radius)",
          padding: "var(--space-sm) var(--space-md)",
          cursor: "pointer",
          transition: "border-color var(--transition-normal), background var(--transition-normal)",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-ui)",
            fontSize: "13px",
            fontWeight: 500,
            color: "var(--text-primary)",
            marginBottom: "2px",
          }}
        >
          {nodeData.label}
        </div>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            fontWeight: 400,
            color: "var(--text-secondary)",
            display: "flex",
            gap: "var(--space-sm)",
          }}
        >
          {nodeData.nodeInfo.type && <span>{nodeData.nodeInfo.type}</span>}
          {nodeData.durationMs > 0 && (
            <>
              <span style={{ color: "var(--text-tertiary)" }}>&middot;</span>
              <span>{formatDuration(nodeData.durationMs)}</span>
            </>
          )}
          {nodeData.state === "running" && (
            <span style={{ color: "var(--state-running)" }}>running...</span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Right} style={{ visibility: "hidden" }} />
    </>
  );
}

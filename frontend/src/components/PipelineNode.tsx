/**
 * Custom React Flow node for pipeline graph visualization.
 *
 * Displays: node label, duration, and state via CSS class.
 * State colors, borders, and animations are driven by CSS variables.
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

const STATE_STYLES: Record<
  NodeState,
  { bg: string; border: string; borderStyle: string; animation?: string }
> = {
  pending: {
    bg: "var(--surface-raised)",
    border: "var(--state-pending)",
    borderStyle: "dashed",
  },
  running: {
    bg: "var(--surface-raised)",
    border: "var(--state-running)",
    borderStyle: "solid",
    animation: "breathe var(--pulse-duration) ease-in-out infinite",
  },
  success: {
    bg: "var(--surface-raised)",
    border: "var(--state-success)",
    borderStyle: "solid",
  },
  failed: {
    bg: "var(--surface-raised)",
    border: "var(--state-failed)",
    borderStyle: "solid",
  },
  retrying: {
    bg: "var(--surface-raised)",
    border: "var(--state-retrying)",
    borderStyle: "dashed",
  },
  skipped: {
    bg: "var(--surface-raised)",
    border: "var(--state-skipped)",
    borderStyle: "dotted",
  },
};

function formatDuration(ms: number): string {
  if (ms === 0) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function PipelineNode({ data }: NodeProps) {
  const nodeData = data as unknown as PipelineNodeData;
  const style = STATE_STYLES[nodeData.state] ?? STATE_STYLES.pending;

  return (
    <>
      <Handle type="target" position={Position.Left} style={{ visibility: "hidden" }} />
      <div
        className="nopan nodrag"
        style={{
          minWidth: "var(--node-min-width)",
          background: style.bg,
          border: `2px ${style.borderStyle} ${style.border}`,
          borderRadius: "var(--node-border-radius)",
          padding: "var(--space-sm) var(--space-md)",
          animation: style.animation,
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

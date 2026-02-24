/**
 * Detail panel -- right sidebar (360px) showing selected node info and run history.
 * Becomes an overlay drawer below 1280px viewport (deferred to v1.1).
 */

import { Link } from "react-router-dom";
import type { NodeInfo, NodeRun } from "../lib/types";

interface DetailPanelProps {
  nodeId: string | null;
  nodeInfo: NodeInfo | null;
  runs: NodeRun[];
  contextId?: string;
}

function formatDuration(ms: number): string {
  if (ms === 0) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function DetailPanel({ nodeId, nodeInfo, runs, contextId }: DetailPanelProps) {
  if (!nodeId || !nodeInfo) {
    return (
      <div
        style={{
          width: "var(--detail-panel-width)",
          borderLeft: "1px solid var(--border-default)",
          padding: "var(--space-lg)",
          color: "var(--text-tertiary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        Click a node to view details
      </div>
    );
  }

  return (
    <div
      style={{
        width: "var(--detail-panel-width)",
        borderLeft: "1px solid var(--border-default)",
        padding: "var(--space-lg)",
        overflow: "auto",
      }}
    >
      {/* Node identity */}
      <h2
        style={{
          fontSize: "1rem",
          fontWeight: 600,
          marginBottom: "var(--space-xs)",
        }}
      >
        {nodeInfo.label || nodeId}
      </h2>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.8rem",
          color: "var(--text-secondary)",
          marginBottom: "var(--space-lg)",
          display: "flex",
          gap: "var(--space-sm)",
        }}
      >
        <span>{nodeId}</span>
        {nodeInfo.type && (
          <>
            <span style={{ color: "var(--text-tertiary)" }}>&middot;</span>
            <span>{nodeInfo.type}</span>
          </>
        )}
        {nodeInfo.shape && (
          <>
            <span style={{ color: "var(--text-tertiary)" }}>&middot;</span>
            <span>{nodeInfo.shape}</span>
          </>
        )}
      </div>

      {/* Link to full node view */}
      {contextId && (
        <Link
          to={`/pipelines/${contextId}/nodes/${nodeId}`}
          style={{
            display: "inline-block",
            marginBottom: "var(--space-lg)",
            fontSize: "0.8rem",
            color: "var(--state-running)",
            textDecoration: "none",
          }}
        >
          View full details &rarr;
        </Link>
      )}

      {/* Run history */}
      <h3
        style={{
          fontSize: "0.85rem",
          fontWeight: 600,
          color: "var(--text-secondary)",
          marginBottom: "var(--space-sm)",
        }}
      >
        Run History ({runs.length} attempt{runs.length !== 1 ? "s" : ""})
      </h3>

      {runs.map((run, i) => (
        <div
          key={i}
          style={{
            background: "var(--surface-overlay)",
            borderRadius: 6,
            padding: "var(--space-sm) var(--space-md)",
            marginBottom: "var(--space-sm)",
            fontSize: "0.8rem",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginBottom: "var(--space-xs)",
            }}
          >
            <span style={{ fontWeight: 500 }}>Attempt {run.attempt}</span>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                color:
                  run.status === "success"
                    ? "var(--state-success)"
                    : run.status === "running"
                      ? "var(--state-running)"
                      : "var(--state-failed)",
              }}
            >
              {run.status}
            </span>
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              color: "var(--text-secondary)",
              display: "flex",
              gap: "var(--space-md)",
              flexWrap: "wrap",
            }}
          >
            <span>{formatDuration(run.duration_ms)}</span>
            {run.llm_calls > 0 && <span>{run.llm_calls} calls</span>}
            {run.tokens_in > 0 && <span>{run.tokens_in} in</span>}
            {run.tokens_out > 0 && <span>{run.tokens_out} out</span>}
          </div>
          {run.outcome_notes && (
            <div style={{ color: "var(--text-tertiary)", marginTop: "var(--space-xs)" }}>
              {run.outcome_notes}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

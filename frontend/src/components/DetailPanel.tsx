/**
 * Detail panel -- right sidebar (360px) showing selected node info and run history.
 * Becomes an overlay drawer below 1280px viewport (deferred to v1.1).
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import type { NodeInfo, NodeRun, EdgeDecision } from "../lib/types";

interface DetailPanelProps {
  nodeId: string | null;
  nodeInfo: NodeInfo | null;
  runs: NodeRun[];
  contextId?: string;
  prompt?: string | null;
  response?: string | null;
  edgeDecisions?: EdgeDecision[];
  detailLoading?: boolean;
  timing?: Record<string, number>;
  loopIterations?: Record<string, number>;
}

function CollapsibleBlock({ title, content }: { title: string; content: string }) {
  const [expanded, setExpanded] = useState(content.length <= 500);
  const displayContent = expanded ? content : content.slice(0, 500) + "…";
  return (
    <div style={{ marginTop: "var(--space-md)" }}>
      <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "var(--space-xs)" }}>
        {title}
      </h3>
      <pre style={{
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        fontSize: "0.8rem",
        fontFamily: "var(--font-mono)",
        background: "var(--bg-tertiary)",
        padding: "var(--space-sm)",
        borderRadius: "var(--radius-sm)",
        maxHeight: expanded ? "none" : "200px",
        overflow: "hidden",
      }}>
        {displayContent}
      </pre>
      {content.length > 500 && (
        <button onClick={() => setExpanded(!expanded)}
          style={{ fontSize: "0.75rem", color: "var(--text-link, #60a5fa)", background: "none", border: "none", cursor: "pointer", padding: "var(--space-xs, 4px) 0" }}>
          {expanded ? "Show less" : "Show full"}
        </button>
      )}
    </div>
  );
}

function formatDuration(ms: number): string {
  if (ms === 0) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function DetailPanel({
  nodeId,
  nodeInfo,
  runs,
  contextId,
  prompt,
  response,
  edgeDecisions,
  detailLoading,
  timing: _timing,
  loopIterations: _loopIterations,
}: DetailPanelProps) {
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

      {/* Prompt */}
      {prompt && (
        <CollapsibleBlock title="Prompt" content={prompt} />
      )}

      {/* Response */}
      {response ? (
        <CollapsibleBlock title="Response" content={response} />
      ) : detailLoading ? (
        <div style={{ color: "var(--text-tertiary)", fontSize: "0.8rem", padding: "var(--space-sm)" }}>
          Loading…
        </div>
      ) : prompt !== undefined && prompt !== null ? (
        <div style={{ color: "var(--text-tertiary)", fontSize: "0.8rem", padding: "var(--space-sm)" }}>
          Response not available in this data source mode
        </div>
      ) : null}

      {/* Edge Routing */}
      {edgeDecisions && edgeDecisions.length > 0 && (
        <div style={{ marginTop: "var(--space-md)" }}>
          <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "var(--space-xs)" }}>
            Edge Routing
          </h3>
          {edgeDecisions.map((d, i) => (
            <div key={i} style={{
              fontSize: "0.8rem",
              fontFamily: "var(--font-mono)",
              background: "var(--bg-tertiary)",
              padding: "var(--space-xs) var(--space-sm)",
              borderRadius: "var(--radius-sm)",
              marginBottom: "var(--space-xs)",
            }}>
              <div style={{ color: "var(--text-primary)" }}>
                → {d.selected_edge.label || d.selected_edge.to_node || "default"}
              </div>
              {d.reason && d.reason !== "default" && (
                <div style={{ color: "var(--text-tertiary)", fontSize: "0.75rem" }}>
                  {d.reason}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

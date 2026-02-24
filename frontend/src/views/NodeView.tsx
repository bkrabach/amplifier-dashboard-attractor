/**
 * Node Detail View -- Level 3: full node forensics.
 *
 * URL: /pipelines/:contextId/nodes/:nodeId
 *
 * Layout: two-column
 *   Left:  Node identity, prompt text, response text
 *   Right: Execution runs (attempts), edge routing decisions
 *
 * Fetches data from GET /api/pipelines/:contextId/nodes/:nodeId
 */

import { useParams, Link } from "react-router-dom";
import { useState, useEffect } from "react";
import { getNode } from "../lib/api";
import type { NodeDetail, NodeRun, EdgeDecision } from "../lib/types";

const STATUS_COLORS: Record<string, string> = {
  running: "var(--state-running)",
  success: "var(--state-success)",
  fail: "var(--state-failed)",
  failed: "var(--state-failed)",
  timeout: "var(--state-retrying)",
  partial_success: "var(--state-retrying)",
};

function formatDuration(ms: number): string {
  if (ms === 0) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTokens(n: number): string {
  if (n === 0) return "0";
  if (n < 1000) return String(n);
  return `${(n / 1000).toFixed(1)}k`;
}

/** Total duration across all runs for a node. */
function totalDuration(runs: NodeRun[]): number {
  return runs.reduce((sum, r) => sum + r.duration_ms, 0);
}

/** Total tokens in/out across all runs. */
function totalTokens(runs: NodeRun[]): { tokensIn: number; tokensOut: number } {
  return runs.reduce(
    (acc, r) => ({
      tokensIn: acc.tokensIn + r.tokens_in,
      tokensOut: acc.tokensOut + r.tokens_out,
    }),
    { tokensIn: 0, tokensOut: 0 }
  );
}

/** Effective status: last run's status. */
function effectiveStatus(runs: NodeRun[]): string {
  if (runs.length === 0) return "pending";
  return runs[runs.length - 1].status;
}

export default function NodeView() {
  const { contextId, nodeId } = useParams<{
    contextId: string;
    nodeId: string;
  }>();
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [prompt, setPrompt] = useState<string | null>(null);
  const [response, setResponse] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!contextId || !nodeId) return;

    async function load() {
      try {
        const data = await getNode(contextId!, nodeId!);
        setDetail(data);
        // The API may return prompt/response as extra fields (pipeline_logs_reader)
        const raw = data as unknown as Record<string, unknown>;
        setPrompt((raw.prompt as string) ?? null);
        setResponse((raw.response as string) ?? null);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load node");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [contextId, nodeId]);

  if (loading) {
    return (
      <div style={{ padding: "var(--space-lg)", color: "var(--text-secondary)" }}>
        Loading node...
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div style={{ padding: "var(--space-lg)", color: "var(--state-failed)" }}>
        {error ?? "Node not found"}
      </div>
    );
  }

  const { info, runs, edge_decisions } = detail;
  const status = effectiveStatus(runs);
  const tokens = totalTokens(runs);

  return (
    <div style={{ padding: "var(--space-lg)", maxWidth: 1200, margin: "0 auto" }}>
      {/* Breadcrumbs */}
      <div
        style={{
          fontSize: "0.8rem",
          color: "var(--text-tertiary)",
          marginBottom: "var(--space-lg)",
        }}
      >
        <Link
          to="/pipelines"
          style={{ color: "var(--text-secondary)", textDecoration: "none" }}
        >
          Fleet
        </Link>
        {" / "}
        <Link
          to={`/pipelines/${contextId}`}
          style={{ color: "var(--text-secondary)", textDecoration: "none" }}
        >
          Pipeline
        </Link>
        {" / "}
        <span style={{ fontFamily: "var(--font-mono)" }}>{nodeId}</span>
      </div>

      {/* Two-column layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 340px",
          gap: "var(--space-xl)",
          alignItems: "start",
        }}
      >
        {/* ── Left column: Identity + Prompt + Response ── */}
        <div>
          {/* Node identity card */}
          <div
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border-default)",
              borderRadius: 8,
              padding: "var(--space-lg)",
              marginBottom: "var(--space-lg)",
            }}
          >
            <h1
              style={{
                fontSize: "1.25rem",
                fontWeight: 600,
                marginBottom: "var(--space-sm)",
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
              }}
            >
              <span>Node: {info.label || nodeId}</span>
              <span
                style={{
                  fontSize: "0.75rem",
                  fontFamily: "var(--font-mono)",
                  padding: "2px 8px",
                  borderRadius: 4,
                  background: "var(--surface-overlay)",
                  color: STATUS_COLORS[status] ?? "var(--text-secondary)",
                  border: `1px solid ${STATUS_COLORS[status] ?? "var(--border-default)"}`,
                }}
              >
                {status}
              </span>
            </h1>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                gap: "var(--space-md)",
                marginTop: "var(--space-md)",
              }}
            >
              <StatBox label="Type" value={info.type || "-"} />
              <StatBox label="Shape" value={info.shape || "-"} />
              <StatBox label="Duration" value={formatDuration(totalDuration(runs))} />
              <StatBox
                label="Tokens"
                value={`${formatTokens(tokens.tokensIn)} in / ${formatTokens(tokens.tokensOut)} out`}
              />
              <StatBox label="Attempts" value={String(runs.length)} />
            </div>
          </div>

          {/* Prompt */}
          <ContentBlock title="Prompt" content={prompt ?? info.prompt} />

          {/* Response */}
          <ContentBlock title="Response" content={response} />
        </div>

        {/* ── Right column: Execution Runs + Edge Routing ── */}
        <div>
          {/* Execution Runs */}
          <div style={{ marginBottom: "var(--space-xl)" }}>
            <h2
              style={{
                fontSize: "0.9rem",
                fontWeight: 600,
                marginBottom: "var(--space-md)",
                color: "var(--text-secondary)",
              }}
            >
              Execution Runs
            </h2>
            {runs.length === 0 && (
              <div style={{ color: "var(--text-tertiary)", fontSize: "0.85rem" }}>
                No runs recorded
              </div>
            )}
            {runs.map((run, i) => (
              <RunCard key={i} run={run} />
            ))}
          </div>

          {/* Edge Routing */}
          {edge_decisions.length > 0 && (
            <div>
              <h2
                style={{
                  fontSize: "0.9rem",
                  fontWeight: 600,
                  marginBottom: "var(--space-md)",
                  color: "var(--text-secondary)",
                }}
              >
                Edge Routing
              </h2>
              {edge_decisions.map((d, i) => (
                <EdgeDecisionCard key={i} decision={d} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        style={{
          fontSize: "0.7rem",
          color: "var(--text-tertiary)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 2,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.85rem",
          color: "var(--text-primary)",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function ContentBlock({ title, content }: { title: string; content: string | null | undefined }) {
  if (!content) return null;

  return (
    <div style={{ marginBottom: "var(--space-lg)" }}>
      <h2
        style={{
          fontSize: "0.9rem",
          fontWeight: 600,
          color: "var(--text-secondary)",
          marginBottom: "var(--space-sm)",
        }}
      >
        {title}
      </h2>
      <pre
        style={{
          background: "var(--surface-overlay)",
          border: "1px solid var(--border-default)",
          borderRadius: 6,
          padding: "var(--space-md)",
          fontFamily: "var(--font-mono)",
          fontSize: "0.8rem",
          lineHeight: 1.6,
          color: "var(--text-secondary)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          maxHeight: 400,
          overflow: "auto",
        }}
      >
        {content}
      </pre>
    </div>
  );
}

function RunCard({ run }: { run: NodeRun }) {
  return (
    <div
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border-default)",
        borderRadius: 6,
        padding: "var(--space-sm) var(--space-md)",
        marginBottom: "var(--space-sm)",
        fontSize: "0.8rem",
      }}
    >
      {/* Header: attempt + status */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "var(--space-xs)",
        }}
      >
        <span style={{ fontWeight: 500 }}>
          Run {run.attempt}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            color: STATUS_COLORS[run.status] ?? "var(--text-secondary)",
          }}
        >
          {run.status}
        </span>
      </div>

      {/* Metrics row */}
      <div
        style={{
          fontFamily: "var(--font-mono)",
          color: "var(--text-secondary)",
          display: "flex",
          gap: "var(--space-md)",
          flexWrap: "wrap",
          fontSize: "0.75rem",
        }}
      >
        <span>Duration: {formatDuration(run.duration_ms)}</span>
        {run.llm_calls > 0 && <span>{run.llm_calls} LLM calls</span>}
        {run.tokens_in > 0 && <span>{formatTokens(run.tokens_in)} in</span>}
        {run.tokens_out > 0 && <span>{formatTokens(run.tokens_out)} out</span>}
      </div>

      {/* Outcome notes */}
      {run.outcome_notes && (
        <div
          style={{
            color: "var(--text-tertiary)",
            marginTop: "var(--space-xs)",
            fontSize: "0.75rem",
          }}
        >
          {run.outcome_notes}
        </div>
      )}

      {/* Timestamps */}
      {run.started_at && (
        <div
          style={{
            color: "var(--text-tertiary)",
            marginTop: "var(--space-xs)",
            fontSize: "0.7rem",
            fontFamily: "var(--font-mono)",
          }}
        >
          {run.started_at}
          {run.completed_at ? ` \u2192 ${run.completed_at}` : " (in progress)"}
        </div>
      )}
    </div>
  );
}

function EdgeDecisionCard({ decision }: { decision: EdgeDecision }) {
  const edge = decision.selected_edge;
  return (
    <div
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border-default)",
        borderRadius: 6,
        padding: "var(--space-sm) var(--space-md)",
        marginBottom: "var(--space-sm)",
        fontSize: "0.8rem",
      }}
    >
      <div style={{ marginBottom: "var(--space-xs)" }}>
        <span style={{ color: "var(--text-secondary)" }}>From: </span>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 500 }}>
          {decision.from_node}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
        <span style={{ color: "var(--state-running)" }}>&rarr;</span>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 500 }}>
          {edge.to_node}
        </span>
        {edge.label && (
          <span
            style={{
              fontSize: "0.7rem",
              padding: "1px 6px",
              borderRadius: 3,
              background: "var(--surface-overlay)",
              color: "var(--text-tertiary)",
            }}
          >
            {edge.label}
          </span>
        )}
        {edge.condition && (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.7rem",
              color: "var(--text-tertiary)",
            }}
          >
            [{edge.condition}]
          </span>
        )}
      </div>
      {decision.reason && decision.reason !== "default" && (
        <div
          style={{
            color: "var(--text-tertiary)",
            marginTop: "var(--space-xs)",
            fontSize: "0.75rem",
          }}
        >
          Reason: {decision.reason}
        </div>
      )}
    </div>
  );
}

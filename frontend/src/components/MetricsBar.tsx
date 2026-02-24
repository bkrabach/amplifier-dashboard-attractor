/**
 * Aggregate metrics bar -- 48px height, sits at top of pipeline detail view.
 * Shows: status, progress, elapsed, tokens, LLM calls, error count.
 */

import type { PipelineRunState } from "../lib/types";

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const secs = ms / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const mins = Math.floor(secs / 60);
  const remainSecs = Math.floor(secs % 60);
  return `${mins}m ${remainSecs}s`;
}

function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  return `${(n / 1000).toFixed(1)}k`;
}

const STATUS_COLORS: Record<string, string> = {
  running: "var(--state-running)",
  complete: "var(--state-success)",
  failed: "var(--state-failed)",
  pending: "var(--state-pending)",
};

interface MetricsBarProps {
  state: PipelineRunState;
}

export default function MetricsBar({ state }: MetricsBarProps) {
  return (
    <div
      style={{
        height: "var(--metrics-bar-height)",
        display: "flex",
        alignItems: "center",
        gap: "var(--space-xl)",
        padding: "0 var(--space-lg)",
        borderBottom: "1px solid var(--border-default)",
        background: "var(--surface-raised)",
        fontSize: "0.85rem",
      }}
    >
      {/* Status badge */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: STATUS_COLORS[state.status] ?? "var(--state-pending)",
            display: "inline-block",
          }}
        />
        <span style={{ fontWeight: 600 }}>{state.status}</span>
      </div>

      {/* Metrics */}
      <Metric label="Progress" value={`${state.nodes_completed}/${state.nodes_total}`} />
      <Metric label="Elapsed" value={formatDuration(state.total_elapsed_ms)} />
      <Metric label="Tokens" value={formatTokens(state.total_tokens_in + state.total_tokens_out)} />
      <Metric label="LLM Calls" value={String(state.total_llm_calls)} />
      {state.errors.length > 0 && (
        <Metric label="Errors" value={String(state.errors.length)} color="var(--state-failed)" />
      )}

      {/* Goal text */}
      <div
        style={{
          marginLeft: "auto",
          color: "var(--text-secondary)",
          maxWidth: 400,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {state.goal}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.9rem",
          fontWeight: 500,
          color: color ?? "var(--text-primary)",
        }}
      >
        {value}
      </span>
      <span style={{ fontSize: "0.7rem", color: "var(--text-tertiary)" }}>
        {label}
      </span>
    </div>
  );
}

/**
 * Fleet View -- Level 1: scannable table of all pipeline instances.
 *
 * Polls GET /api/pipelines every 5 seconds.
 * Click a row to navigate to pipeline detail.
 */

import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getPipelines } from "../lib/api";
import { usePolling } from "../hooks/usePolling";
import type { PipelineFleetItem } from "../lib/types";

/** Format milliseconds to human-readable duration. */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const secs = ms / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const mins = Math.floor(secs / 60);
  const remainSecs = Math.floor(secs % 60);
  return `${mins}m ${remainSecs}s`;
}

/** Format token count to compact form. */
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

export default function FleetView() {
  const fetcher = useCallback(() => getPipelines(), []);
  const { data: pipelines, error, loading } = usePolling<PipelineFleetItem[]>(fetcher);
  const navigate = useNavigate();

  if (loading && !pipelines) {
    return (
      <div style={{ padding: "var(--space-lg)", color: "var(--text-secondary)" }}>
        Loading pipelines...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "var(--space-lg)", color: "var(--state-failed)" }}>
        Error: {error}
      </div>
    );
  }

  return (
    <div style={{ padding: "var(--space-lg)" }}>
      <h1 style={{ marginBottom: "var(--space-lg)", fontWeight: 600 }}>
        Pipeline Fleet
      </h1>

      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontFamily: "var(--font-ui)",
        }}
      >
        <thead>
          <tr
            style={{
              borderBottom: "1px solid var(--border-strong)",
              color: "var(--text-secondary)",
              fontSize: "0.85rem",
              textAlign: "left",
            }}
          >
            <th style={{ padding: "var(--space-sm) var(--space-md)" }}>Status</th>
            <th style={{ padding: "var(--space-sm) var(--space-md)" }}>Pipeline</th>
            <th style={{ padding: "var(--space-sm) var(--space-md)" }}>Progress</th>
            <th style={{ padding: "var(--space-sm) var(--space-md)" }}>Elapsed</th>
            <th style={{ padding: "var(--space-sm) var(--space-md)" }}>Tokens</th>
            <th style={{ padding: "var(--space-sm) var(--space-md)" }}>Goal</th>
          </tr>
        </thead>
        <tbody>
          {pipelines?.map((p) => (
            <tr
              key={p.context_id}
              onClick={() => navigate(`/pipelines/${p.context_id}`)}
              style={{
                cursor: "pointer",
                borderBottom: "1px solid var(--border-default)",
                transition: "background var(--transition-fast)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--surface-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "transparent")
              }
            >
              <td style={{ padding: "var(--space-sm) var(--space-md)" }}>
                <span
                  style={{
                    display: "inline-block",
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: STATUS_COLORS[p.status] ?? "var(--state-pending)",
                    marginRight: "var(--space-sm)",
                  }}
                />
                <span style={{ fontSize: "0.85rem" }}>{p.status}</span>
              </td>
              <td
                style={{
                  padding: "var(--space-sm) var(--space-md)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.85rem",
                }}
              >
                {p.pipeline_id}
              </td>
              <td
                style={{
                  padding: "var(--space-sm) var(--space-md)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.85rem",
                }}
              >
                {p.nodes_completed}/{p.nodes_total}
              </td>
              <td
                style={{
                  padding: "var(--space-sm) var(--space-md)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.85rem",
                }}
              >
                {formatDuration(p.total_elapsed_ms)}
              </td>
              <td
                style={{
                  padding: "var(--space-sm) var(--space-md)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.85rem",
                }}
              >
                {formatTokens(p.total_tokens_in + p.total_tokens_out)}
              </td>
              <td
                style={{
                  padding: "var(--space-sm) var(--space-md)",
                  color: "var(--text-secondary)",
                  fontSize: "0.85rem",
                  maxWidth: 300,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {p.goal}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

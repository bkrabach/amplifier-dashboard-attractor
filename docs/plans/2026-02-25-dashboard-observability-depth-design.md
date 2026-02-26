# Dashboard Observability Depth — Design

> **Date**: 2026-02-25
> **Status**: Approved
> **Approach**: Pragmatic Hybrid — surface existing data in the frontend, plus two surgical engine enrichments

---

## Problem

The dashboard shows pipeline *state* (running/complete/failed, which nodes executed)
but not *insight*. Developers debugging live runs must dig into disk files to see LLM
responses, can't tell why routing decisions were made, and are missing half the
available metrics. Data flows through the system but drops silently at the rendering
layer.

## Priority Stack

| Priority | Need | Summary |
|----------|------|---------|
| A | Prompt/response visibility | See what the LLM said without drill-down |
| B | Routing explainability | Understand why edges were taken |
| C | Richer metrics | Cached tokens, reasoning tokens, timing, errors |
| D | Live event streaming | Deferred to follow-up |

## Primary User

Developer debugging pipeline runs (pipeline_logs mode). Architecture must not
paint into a corner for cxdb/production mode later.

---

## Section 1: Prompt/Response Visibility

### Current State

- `pipeline_logs_reader.get_node_events()` reads `prompt.md` and `response.md`
  from disk and returns them in the API response.
- `NodeView` (Level 3) has `ContentBlock` components to render them.
- The `DetailPanel` (Level 2 sidebar) does not show them — requires two clicks
  to reach Level 3.

### Design

**Expand the Level 2 DetailPanel** with collapsible Prompt and Response sections,
positioned below the run history.

- Content is markdown-rendered with syntax highlighting.
- Collapsed by default if text exceeds 500 characters, with a "Show full" toggle.
- When `prompt`/`response` are `null` (non-pipeline_logs mode), show a subtle
  "Response not available in this data source mode" placeholder.
- `NodeView` (Level 3) stays as-is — it's the full deep-dive view.

### Backend Changes

None. `GET /api/pipelines/{context_id}/nodes/{node_id}` already returns `prompt`
and `response` fields. The frontend simply doesn't render them in the DetailPanel.

### Data Flow

```
Node click → fetch /api/pipelines/{id}/nodes/{nodeId}
           → response includes { prompt, response } (from disk)
           → DetailPanel renders collapsible content blocks
```

---

## Section 2: Routing Explainability

### Current State

- Traversed edges are styled solid/bright; untouched edges are dashed/dim.
- `edge_decisions[]` is populated by the aggregator from `pipeline:edge_selected`
  events and returned in the API.
- `loop_iterations[nodeId]` is tracked by the aggregator from
  `pipeline:stage_retrying` events.
- The `retrying` visual state (dashed orange animation) is defined but never fires
  due to a logic gap in `getNodeState()`.

### Design

**Edge Decisions in the DetailPanel:**

Below prompt/response, show an "Edge Routing" section for each outgoing edge
decision from the selected node. Display:

- Selected edge: label, target node
- Condition: the expression that was evaluated
- Reason: why this edge won (condition matched, default fallback, preferred_label)

**Edge click tooltip:**

Clicking an edge in the ReactFlow graph shows a small popover with the same
routing decision data — label, condition, traversal status.

**Loop iteration badge:**

Nodes in a retry/restart loop show a small iteration badge (e.g., "×3") on the
node in the graph, sourced from `loop_iterations[nodeId]`.

**Fix `getNodeState()` retrying logic:**

Return `"retrying"` when a node has ≥1 failed run AND `loop_iterations[nodeId] > 0`,
rather than only for `partial_success`. This activates the existing dashed-orange
animation CSS.

### What We Skip

`evaluated_edges` (candidate edges that weren't selected) — the engine doesn't
emit this data. Showing the selected edge's decision reason covers the 80% case.
Follow-up engine enrichment if needed.

---

## Section 3: Richer Metrics

### Current State

- MetricsBar shows: status, progress, elapsed, tokens (in+out), LLM calls, errors
  (detail only).
- `total_tokens_cached`, `total_tokens_reasoning` flow from `StateAggregator` but
  are never rendered.
- `tokens_cached` per run is in the data model but not rendered.
- `timing{}` (per-node duration map) is in `PipelineRunState` but not rendered.
- Fleet view has `errors[]` in the API response but doesn't render error counts.

### Design

**MetricsBar additions:**

- **Cached Tokens**: shown with cache icon, muted/secondary styling next to
  existing tokens display. Shows `total_tokens_cached`.
- **Reasoning Tokens**: shown similarly. Shows `total_tokens_reasoning`.
- Both are enrichments to the existing tokens area, not new rows.

**Fleet View:**

- **Error Count column**: red badge with count when `errors.length > 0`.

**DetailPanel per-node runs:**

- Add `tokens_cached` to each run card.

**Per-node timing bar:**

In the DetailPanel, below run history, a simple horizontal bar chart of node
durations from `timing{}`. Instant visual answer to "where did the time go?"

### Backend Changes

None. All data already exists in API responses.

---

## Section 4: Engine Enrichments

Two changes to `amplifier-bundle-attractor/modules/loop-pipeline/`. Both add
fields to existing event emit calls — no new event types, no architectural changes.

### Enrichment 1: `pipeline:node_complete` event

**Current emit** (engine.py ~line 326):

```python
await self._emit(PIPELINE_NODE_COMPLETE, {
    "node_id": current_node.id,
    "status": outcome.status.value,
    "duration_ms": node_duration_ms,
})
```

**Add two fields:**

```python
    "notes": outcome.notes,
    "failure_reason": outcome.failure_reason,
```

**Aggregator update** (`hooks-pipeline-observability`):

`handle_node_complete()` reads `notes` and `failure_reason` from event data and
sets `outcome_notes` on the `NodeRun`. This makes `outcome_notes` work in every
data source mode, not just `pipeline_logs`.

### Enrichment 2: `pipeline:start` event

Add `dot_source` field to the `pipeline:start` event. The DOT source string is
available on the engine's `self.graph` object. This lets the aggregator populate
`PipelineRunState.dot_source` in live/SSE mode, future-proofing graph
visualization for non-disk data sources.

### Testing Impact

Both changes add fields to event data dicts. Existing tests pass (they don't
assert against absence of fields). New tests verify the fields are present.

---

## Explicitly Deferred

| Item | Reason |
|------|--------|
| SSE frontend connection / live event log | Priority D — lowest on the stack |
| Response text in engine events | Large payloads need truncation strategy |
| Model name per LLM call | Aggregator change, not urgent |
| Candidate edges evaluated | Engine design decision, not needed yet |
| Cost/dollar amounts | No pricing data source exists |
| Supervisor cycles / subgraph runs | No engine events defined |
| Human interaction UI | Backend API exists, but no frontend yet — separate effort |

---

## Change Summary

| Repo | Files Changed | Type |
|------|---------------|------|
| `amplifier-dashboard-attractor` | `frontend/src/components/DetailPanel.tsx` | Prompt/response sections, edge routing, timing bar |
| | `frontend/src/components/PipelineNode.tsx` | Loop iteration badge |
| | `frontend/src/components/PipelineEdge.tsx` | Edge click tooltip |
| | `frontend/src/components/MetricsBar.tsx` | Cached + reasoning tokens |
| | `frontend/src/views/FleetView.tsx` | Error count column |
| | `frontend/src/lib/types.ts` | Possible type refinements |
| `amplifier-bundle-attractor` | `modules/loop-pipeline/.../engine.py` | Two emit enrichments |
| | `modules/hooks-pipeline-observability/...` | Aggregator reads new fields |

## Success Criteria

1. Click a node in Level 2 → see prompt and response immediately in the sidebar
2. Click a node → see which edge was taken and why (condition + reason)
3. Nodes in retry loops show iteration badge and retrying animation
4. MetricsBar shows cached and reasoning token counts
5. Fleet view shows error counts on failing pipelines
6. Per-node timing bar visible in DetailPanel
7. `outcome_notes` populated in all data source modes (via enriched engine event)
8. All existing tests pass; new tests cover enrichments
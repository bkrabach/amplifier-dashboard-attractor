# Dashboard Observability Depth — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface existing pipeline data in the dashboard UI and add two engine enrichments, following the approved design in `2026-02-25-dashboard-observability-depth-design.md`.

**Architecture:** Frontend-heavy changes to render data that already flows but isn't shown. Two surgical Python changes in the engine (add fields to existing event emits) and aggregator (read those fields). Frontend work modifies React components in the dashboard; backend work modifies Python modules in the bundle repo.

**Tech Stack:** React + TypeScript (frontend), Python + pytest (backend engine/aggregator), FastAPI (dashboard backend — no changes needed)

**Repos:**
- `amplifier-bundle-attractor` — engine + aggregator (Tasks 1–3)
- `amplifier-dashboard-attractor` — frontend (Tasks 4–12)

**Testing strategy:**
- Engine/aggregator tasks: strict TDD with pytest (`.venv/bin/pytest`)
- Frontend tasks: manual verification via dev server (`cd frontend && npm run dev`)
- No frontend test harness exists — visual verification only

---

## Phase 1: Engine Enrichments (amplifier-bundle-attractor)

### Task 1: Add `notes` and `failure_reason` to `PIPELINE_NODE_COMPLETE` events

**Files:**
- Modify: `modules/loop-pipeline/amplifier_module_loop_pipeline/engine.py` (3 emit sites)
- Test: `modules/loop-pipeline/tests/` (new or augmented test)

**Step 1: Write a test that asserts `notes` and `failure_reason` are in the node_complete event data**

Find an existing engine test that captures emitted events (grep for `PIPELINE_NODE_COMPLETE` in tests/). Add assertions:

```python
# In a test that runs the engine and captures events via a mock hook:
node_complete_events = [e for e in captured if e[0] == "pipeline:node_complete"]
assert len(node_complete_events) > 0
event_data = node_complete_events[0][1]
assert "notes" in event_data
assert "failure_reason" in event_data
```

**Step 2: Run test, verify it fails**

```bash
cd amplifier-bundle-attractor/modules/loop-pipeline && .venv/bin/pytest tests/ -k "test_name" -v
```
Expected: FAIL — `notes` and `failure_reason` not in event data.

**Step 3: Add fields to all three PIPELINE_NODE_COMPLETE emit sites**

Site 1 — Timeout path (engine.py ~line 269):
```python
await self._emit(PIPELINE_NODE_COMPLETE, {
    "node_id": current_node.id,
    "status": "timeout",
    "duration_ms": node_duration_ms,
    "notes": outcome.notes,               # NEW
    "failure_reason": outcome.failure_reason,  # NEW
})
```

Site 2 — Normal completion (engine.py ~line 326):
```python
await self._emit(PIPELINE_NODE_COMPLETE, {
    "node_id": current_node.id,
    "status": outcome.status.value,
    "duration_ms": node_duration_ms,
    "notes": outcome.notes,               # NEW
    "failure_reason": outcome.failure_reason,  # NEW
})
```

Site 3 — Parallel fan-out branch (engine.py ~line 846):
```python
await self._emit(PIPELINE_NODE_COMPLETE, {
    "node_id": target_node_id,
    "status": outcome.status.value,
    "duration_ms": node_duration,
    "notes": outcome.notes,               # NEW
    "failure_reason": outcome.failure_reason,  # NEW
})
```

**Step 4: Run test, verify it passes**

```bash
cd amplifier-bundle-attractor/modules/loop-pipeline && .venv/bin/pytest tests/ -k "test_name" -v
```

**Step 5: Run full engine test suite**

```bash
cd amplifier-bundle-attractor/modules/loop-pipeline && .venv/bin/pytest tests/ -q
```
Expected: 873 passed.

**Step 6: Commit**

```
feat: include notes and failure_reason in pipeline:node_complete events
```

---

### Task 2: Add `dot_source` to Graph dataclass and `PIPELINE_START` event

**Files:**
- Modify: `modules/loop-pipeline/amplifier_module_loop_pipeline/graph.py` (~line 274)
- Modify: `modules/loop-pipeline/amplifier_module_loop_pipeline/engine.py` (~line 110)
- Modify: DOT parser file (find via `grep -r "def parse" modules/loop-pipeline/` — the function that returns a `Graph`)
- Test: `modules/loop-pipeline/tests/`

**Step 1: Write a test that asserts `dot_source` is in the `pipeline:start` event data**

```python
start_events = [e for e in captured if e[0] == "pipeline:start"]
assert len(start_events) == 1
assert "dot_source" in start_events[0][1]
assert len(start_events[0][1]["dot_source"]) > 0  # non-empty
```

**Step 2: Run test, verify it fails**

**Step 3: Add `dot_source` field to Graph dataclass**

In `graph.py` ~line 274, add to the `Graph` dataclass:
```python
dot_source: str = ""
```

**Step 4: Store DOT source during parsing**

Find the parser function (likely `parse_dot()` or similar). It receives the raw DOT string and returns a `Graph`. After constructing the Graph, set `graph.dot_source = raw_dot_string`.

**Step 5: Emit `dot_source` in PIPELINE_START**

In engine.py ~line 110:
```python
await self._emit(PIPELINE_START, {
    "graph_name": self.graph.name,
    "node_count": len(self.graph.nodes),
    "edge_count": len(self.graph.edges),
    "goal": self.graph.goal or goal or "",
    "dot_source": self.graph.dot_source,  # NEW
})
```

**Step 6: Run test, verify it passes. Run full suite (873 tests).**

**Step 7: Commit**

```
feat: store dot_source on Graph and emit in pipeline:start event
```

---

### Task 3: Update StateAggregator to read new event fields

**Files:**
- Modify: `modules/hooks-pipeline-observability/amplifier_module_hooks_pipeline_observability/aggregator.py`
- Test: `modules/hooks-pipeline-observability/tests/`

**Step 1: Write tests for both handler updates**

Test A — `handle_node_complete` reads `notes`:
```python
async def test_node_complete_stores_outcome_notes():
    aggregator = StateAggregator()
    await aggregator.handle_pipeline_start("pipeline:start", {"graph_name": "test", "node_count": 1})
    await aggregator.handle_node_start("pipeline:node_start", {"node_id": "A"})
    await aggregator.handle_node_complete("pipeline:node_complete", {
        "node_id": "A",
        "status": "success",
        "duration_ms": 100,
        "notes": "Completed with high confidence",
        "failure_reason": None,
    })
    runs = aggregator.state.node_runs.get("A", [])
    assert len(runs) == 1
    assert runs[0].outcome_notes == "Completed with high confidence"
```

Test B — `handle_pipeline_start` reads `dot_source`:
```python
async def test_pipeline_start_stores_dot_source():
    aggregator = StateAggregator()
    await aggregator.handle_pipeline_start("pipeline:start", {
        "graph_name": "test",
        "node_count": 3,
        "dot_source": "digraph { A -> B -> C; }",
    })
    assert aggregator.state.dot_source == "digraph { A -> B -> C; }"
```

**Step 2: Run tests, verify they fail**

```bash
cd amplifier-bundle-attractor/modules/hooks-pipeline-observability && .venv/bin/pytest tests/ -v
```

**Step 3: Update `handle_node_complete` (~line 95)**

After setting `current_run.duration_ms`, add:
```python
# Populate outcome_notes from event data (enriched in engine)
notes = data.get("notes")
failure_reason = data.get("failure_reason")
if notes or failure_reason:
    current_run.outcome_notes = notes or failure_reason
```

**Step 4: Update `handle_pipeline_start` (~line 48)**

Change `dot_source=""` to read from event data:
```python
dot_source=data.get("dot_source", ""),
```

**Step 5: Run tests, verify they pass. Run full suite (51 tests).**

**Step 6: Commit**

```
feat: aggregator reads notes, failure_reason, and dot_source from enriched events
```

---

## Phase 2: Frontend Data Layer (amplifier-dashboard-attractor)

### Task 4: Fix `getNodeState()` to return `"retrying"`

**Files:**
- Modify: `frontend/src/lib/types.ts` (~line 107, `getNodeState` function)

**Step 1: Update `getNodeState` to detect retrying state**

Current code (lines 107–120):
```typescript
export function getNodeState(nodeId: string, state: PipelineRunState): NodeState {
  const runs = state.node_runs[nodeId];
  if (!runs || runs.length === 0) return "pending";
  const lastRun = runs[runs.length - 1];
  if (lastRun.status === "running") return "running";
  if (lastRun.status === "success") return "success";
  if (lastRun.status === "fail" || lastRun.status === "timeout") return "failed";
  return "pending";
}
```

Replace with:
```typescript
export function getNodeState(nodeId: string, state: PipelineRunState): NodeState {
  const runs = state.node_runs[nodeId];
  if (!runs || runs.length === 0) return "pending";
  const lastRun = runs[runs.length - 1];
  if (lastRun.status === "running") {
    // If there are prior runs, this is a retry, not first attempt
    return runs.length > 1 ? "retrying" : "running";
  }
  if (lastRun.status === "success") return "success";
  if (lastRun.status === "fail" || lastRun.status === "timeout") {
    // If loop_iterations shows active retries, show retrying state
    const loopCount = state.loop_iterations[nodeId] ?? 0;
    if (loopCount > 0 && state.status === "running") return "retrying";
    return "failed";
  }
  return "pending";
}
```

**Step 2: Verify** — `npm run dev`, trigger a pipeline with `loop_restart`, confirm the node shows dashed orange border during retries.

**Step 3: Commit**

```
fix: getNodeState returns retrying for nodes in active retry loops
```

---

### Task 5: Add lazy node detail fetch on node click in PipelineView

**Files:**
- Modify: `frontend/src/views/PipelineView.tsx` (~line 49, 88, 199)
- Modify: `frontend/src/components/DetailPanel.tsx` (props interface ~line 9)

**Step 1: Add state and fetch logic in PipelineView**

After existing `selectedNodeId` state (~line 49), add:
```typescript
const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
const [detailLoading, setDetailLoading] = useState(false);
```

Add a `useEffect` that fetches node detail when `selectedNodeId` changes:
```typescript
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
```

Import `getNode` from `../lib/api` and `NodeDetail` from `../lib/types`.

**Step 2: Pass new props to DetailPanel**

Update the DetailPanel invocation (~line 199):
```tsx
<DetailPanel
  nodeId={selectedNodeId}
  nodeInfo={selectedNodeInfo}
  runs={selectedNodeRuns}
  contextId={contextId ?? ""}
  prompt={nodeDetail?.prompt ?? null}
  response={nodeDetail?.response ?? null}
  edgeDecisions={nodeDetail?.edge_decisions ?? []}
  detailLoading={detailLoading}
/>
```

**Step 3: Update DetailPanel props interface**

In `DetailPanel.tsx` (~line 9), add to `DetailPanelProps`:
```typescript
prompt?: string | null;
response?: string | null;
edgeDecisions?: EdgeDecision[];
detailLoading?: boolean;
```

Import `EdgeDecision` from `../lib/types`.

**Step 4: Update NodeDetail type if needed**

Check if `NodeDetail` in `types.ts` has `prompt` and `response` fields. If not, add:
```typescript
export interface NodeDetail {
  node_id: string;
  info: NodeInfo;
  runs: NodeRun[];
  edge_decisions: EdgeDecision[];
  prompt?: string | null;    // from pipeline_logs_reader
  response?: string | null;  // from pipeline_logs_reader
}
```

**Step 5: Verify** — click a node, confirm network request fires in DevTools, DetailPanel receives data.

**Step 6: Commit**

```
feat: lazy-fetch node detail on click for prompt/response data
```

---

## Phase 3: DetailPanel Enhancements (amplifier-dashboard-attractor)

### Task 6: Prompt and Response collapsible sections

**Files:**
- Modify: `frontend/src/components/DetailPanel.tsx`

**Step 1: Add collapsible content sections after run history**

After the `runs.map()` block (~line 166), add:

```tsx
{/* Prompt */}
{prompt && (
  <CollapsibleBlock title="Prompt" content={prompt} />
)}

{/* Response */}
{response ? (
  <CollapsibleBlock title="Response" content={response} />
) : detailLoading ? (
  <div style={{ color: "var(--text-tertiary)", fontSize: "0.8rem", padding: "var(--space-sm)" }}>
    Loading...
  </div>
) : prompt !== undefined ? (
  <div style={{ color: "var(--text-tertiary)", fontSize: "0.8rem", padding: "var(--space-sm)" }}>
    Response not available in this data source mode
  </div>
) : null}
```

**Step 2: Create the `CollapsibleBlock` helper component** (inline in same file or extracted):

```tsx
function CollapsibleBlock({ title, content }: { title: string; content: string }) {
  const [expanded, setExpanded] = useState(content.length <= 500);
  const displayContent = expanded ? content : content.slice(0, 500) + "...";
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
          style={{ fontSize: "0.75rem", color: "var(--text-link)", background: "none", border: "none", cursor: "pointer", padding: "var(--space-xs) 0" }}>
          {expanded ? "Show less" : "Show full"}
        </button>
      )}
    </div>
  );
}
```

**Step 3: Verify** — click a node that has a completed LLM call, confirm prompt and response appear in the sidebar.

**Step 4: Commit**

```
feat: show prompt and response in DetailPanel sidebar
```

---

### Task 7: Edge routing section in DetailPanel

**Files:**
- Modify: `frontend/src/components/DetailPanel.tsx`

**Step 1: Add edge decisions section after prompt/response**

```tsx
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
        <div>→ {d.selected_edge?.label || d.selected_edge?.to_node || "default"}</div>
        {d.reason && d.reason !== "default" && (
          <div style={{ color: "var(--text-tertiary)", fontSize: "0.75rem" }}>
            {d.reason}
          </div>
        )}
      </div>
    ))}
  </div>
)}
```

**Step 2: Verify** — click a node with outgoing conditional edges, confirm routing decisions appear.

**Step 3: Commit**

```
feat: show edge routing decisions in DetailPanel
```

---

### Task 8: Per-node timing bar in DetailPanel

**Files:**
- Modify: `frontend/src/components/DetailPanel.tsx`
- Modify: `frontend/src/views/PipelineView.tsx` (pass `timing` prop)

**Step 1: Pass `timing` from PipelineView to DetailPanel**

Add `timing?: Record<string, number>` to `DetailPanelProps`.
Pass `timing={state?.timing}` in the PipelineView invocation.

**Step 2: Render a simple horizontal bar chart**

After edge routing, add:
```tsx
{timing && Object.keys(timing).length > 1 && (
  <div style={{ marginTop: "var(--space-md)" }}>
    <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "var(--space-xs)" }}>
      Time Distribution
    </h3>
    {(() => {
      const maxMs = Math.max(...Object.values(timing));
      return Object.entries(timing).map(([nid, ms]) => (
        <div key={nid} style={{ display: "flex", alignItems: "center", gap: "var(--space-xs)", marginBottom: 2, fontSize: "0.75rem" }}>
          <span style={{ width: 80, fontFamily: "var(--font-mono)", color: nid === nodeId ? "var(--text-primary)" : "var(--text-tertiary)", textAlign: "right" }}>
            {nid}
          </span>
          <div style={{ flex: 1, height: 8, background: "var(--bg-tertiary)", borderRadius: 4 }}>
            <div style={{
              width: `${(ms / maxMs) * 100}%`,
              height: "100%",
              background: nid === nodeId ? "var(--state-running)" : "var(--text-tertiary)",
              borderRadius: 4,
            }} />
          </div>
          <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", width: 50 }}>
            {ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`}
          </span>
        </div>
      ));
    })()}
  </div>
)}
```

**Step 3: Verify** — click a node, confirm timing bars appear with all nodes' durations.

**Step 4: Commit**

```
feat: per-node timing bar chart in DetailPanel
```

---

## Phase 4: Graph Visual Enhancements

### Task 9: PipelineNode loop iteration badge

**Files:**
- Modify: `frontend/src/components/PipelineNode.tsx`
- Modify: `frontend/src/views/PipelineView.tsx` (pass loop_iterations into node data)

**Step 1: Include `loopCount` in node data passed to ReactFlow**

In PipelineView where ReactFlow nodes are built from state, add `loopCount: state.loop_iterations[nodeId] ?? 0` to each node's `data` object. (Find the node mapping code — likely in `dotLayout.ts` or PipelineView itself.)

**Step 2: Render badge in PipelineNode**

In `PipelineNode.tsx`, after the subtitle div (~line 114), add:
```tsx
{nodeData.loopCount > 0 && (
  <div style={{
    position: "absolute", top: -6, right: -6,
    background: "var(--state-retrying, #f59e0b)",
    color: "#000", fontSize: "0.65rem", fontWeight: 700,
    borderRadius: "999px", padding: "0 5px", lineHeight: "16px",
  }}>
    ×{nodeData.loopCount}
  </div>
)}
```

Add `position: "relative"` to the outer div style (~line 73).

**Step 3: Verify** — run a pipeline with `loop_restart`, confirm badge appears on retrying nodes.

**Step 4: Commit**

```
feat: loop iteration badge on pipeline nodes
```

---

### Task 10: PipelineEdge click tooltip

**Files:**
- Modify: `frontend/src/components/PipelineEdge.tsx`
- Modify: `frontend/src/views/PipelineView.tsx` (pass edge decisions into edge data)

**Step 1: Include edge decision data in ReactFlow edge objects**

When building ReactFlow edges from state, find the matching `EdgeDecision` from `state.edge_decisions` and attach it to `edge.data`.

**Step 2: Add click handler and tooltip to PipelineEdge**

Add an invisible wider `<path>` overlay for click target (common ReactFlow pattern), and a tooltip div that shows on click with: label, condition, traversal status.

**Step 3: Verify** — click an edge, confirm tooltip appears with routing info.

**Step 4: Commit**

```
feat: edge click tooltip with routing decision info
```

---

## Phase 5: Metrics Enhancements

### Task 11: MetricsBar — cached and reasoning tokens

**Files:**
- Modify: `frontend/src/components/MetricsBar.tsx`

**Step 1: Add two Metric components after the existing Tokens metric (~line 64)**

```tsx
{state.total_tokens_cached > 0 && (
  <Metric label="Cached" value={formatTokens(state.total_tokens_cached)} />
)}
{state.total_tokens_reasoning > 0 && (
  <Metric label="Reasoning" value={formatTokens(state.total_tokens_reasoning)} />
)}
```

These are conditional — only shown when > 0 so they don't clutter for providers that don't support them.

**Step 2: Verify** — run a pipeline, confirm cached/reasoning tokens appear when non-zero.

**Step 3: Commit**

```
feat: show cached and reasoning tokens in MetricsBar
```

---

### Task 12: FleetView — error count column

**Files:**
- Modify: `frontend/src/views/FleetView.tsx`

**Step 1: Add Errors column header**

After the Tokens `<th>` (~line 84), add:
```tsx
<th>Errors</th>
```

**Step 2: Add Errors column cell**

After the Tokens `<td>` in the row mapping (~line 153 area), add:
```tsx
<td style={{
  fontFamily: "var(--font-mono)",
  color: p.errors.length > 0 ? "var(--state-failed)" : "var(--text-tertiary)",
}}>
  {p.errors.length > 0 ? p.errors.length : "—"}
</td>
```

**Step 3: Verify** — trigger a pipeline failure, confirm error count appears in fleet view.

**Step 4: Commit**

```
feat: show error count column in fleet view
```

---

## Task Dependency Graph

```
Phase 1 (bundle repo):       Phase 2-5 (dashboard repo):
  Task 1 ─┐                    Task 4 (types.ts fix)
  Task 2 ─┤                    Task 5 (lazy fetch) ──→ Task 6 (prompt/response)
  Task 3 ─┘                                       ──→ Task 7 (edge routing)
     ↓                          Task 8 (timing bar) — independent
  Push bundle repo              Task 9 (node badge) — independent
                                Task 10 (edge tooltip) — depends on Task 5 data
                                Task 11 (metrics) — independent
                                Task 12 (fleet errors) — independent
```

Tasks 4, 8, 9, 11, 12 are fully independent and can run in parallel.
Tasks 6, 7, 10 depend on Task 5 (the lazy fetch wiring).
Tasks 1–3 (engine) are independent of all frontend tasks.

## Commit and Push Strategy

1. Complete Tasks 1–3, push `amplifier-bundle-attractor` to `microsoft/amplifier-bundle-attractor`
2. Complete Tasks 4–12, push `amplifier-dashboard-attractor` to `bkrabach/amplifier-dashboard-attractor`
3. Both repos stay on `main` — no feature branches needed for this scope
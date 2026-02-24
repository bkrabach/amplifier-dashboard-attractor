import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import FleetView from "./views/FleetView";
import PipelineView from "./views/PipelineView";
import NodeView from "./views/NodeView";

export default function App() {
  return (
    <BrowserRouter>
      {/* Application shell -- persistent nav */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-md)",
          padding: "var(--space-sm) var(--space-lg)",
          borderBottom: "1px solid var(--border-default)",
          background: "var(--surface-raised)",
        }}
      >
        <Link
          to="/pipelines"
          style={{
            color: "var(--text-primary)",
            textDecoration: "none",
            fontWeight: 600,
            fontSize: "1rem",
          }}
        >
          Attractor Dashboard
        </Link>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/pipelines" replace />} />
          <Route path="/pipelines" element={<FleetView />} />
          <Route path="/pipelines/:contextId" element={<PipelineView />} />
          <Route
            path="/pipelines/:contextId/nodes/:nodeId"
            element={<NodeView />}
          />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

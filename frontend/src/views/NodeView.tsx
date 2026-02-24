/**
 * Node Detail View -- Level 3: node forensics (deferred to v1.1).
 */
import { useParams } from "react-router-dom";

export default function NodeView() {
  const { contextId, nodeId } = useParams<{
    contextId: string;
    nodeId: string;
  }>();
  return (
    <div style={{ padding: "var(--space-lg)" }}>
      <h1>Node Detail</h1>
      <p style={{ color: "var(--text-secondary)" }}>
        Context {contextId}, Node {nodeId} -- deferred to v1.1.
      </p>
    </div>
  );
}
